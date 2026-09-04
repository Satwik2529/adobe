import hashlib
from typing import List, Dict
from urllib.parse import urljoin
from audit_shared.models.finding import (
    Finding, Pipeline, Severity, Trigger, TriggerType, SuggestedAction, ActionPriority, Evidence, generate_finding_id, AffectedPages
)
from audit_shared.models.data_flow import CrawlDataset, PageRecord
from audit_shared.rules.base import AuditRule

# Helper for rules that need to look up URLs in the dataset graph
def _build_url_graph(dataset: CrawlDataset) -> Dict[str, PageRecord]:
    return {p.url: p for p in dataset.pages}

class ClientErrorRule(AuditRule):
    @property
    def rule_id(self) -> str: return "AI-CRAWL-001"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Client Error (4xx)"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        findings = []
        for page in dataset.pages:
            if 400 <= page.status_code <= 499 and page.content_type.startswith('text/html'):
                findings.append(Finding(
                    id=generate_finding_id(self.rule_id, [page.url]),
                    pipeline=self.pipeline,
                    title="Client Error (4xx)",
                    severity=Severity.HIGH,
                    trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                    suggested_action=SuggestedAction(summary="Fix broken page or remove links to it.", priority=ActionPriority.HIGH),
                    evidence=Evidence(page=page.url, source="status_code", field="status_code", observed_value=str(page.status_code), pages_checked=1, pages_affected=1, affected_percentage=100.0)
                ))
        return findings

class ServerErrorRule(AuditRule):
    @property
    def rule_id(self) -> str: return "AI-CRAWL-002"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Server Error (5xx)"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        findings = []
        for page in dataset.pages:
            if page.status_code >= 500 and page.content_type.startswith('text/html'):
                findings.append(Finding(
                    id=generate_finding_id(self.rule_id, [page.url]),
                    pipeline=self.pipeline,
                    title="Server Error (5xx)",
                    severity=Severity.HIGH,
                    trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                    suggested_action=SuggestedAction(summary="Fix server error.", priority=ActionPriority.HIGH),
                    evidence=Evidence(page=page.url, source="status_code", field="status_code", observed_value=str(page.status_code), pages_checked=1, pages_affected=1, affected_percentage=100.0)
                ))
        return findings

class RobotsBlockingRule(AuditRule):
    @property
    def rule_id(self) -> str: return "AI-ROBOTS-001"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Robots.txt Blocking"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        blocked_urls = [u["url"] for u in dataset.unfetched_urls if u.get("reason") == "robots_blocked"]
        if not blocked_urls:
            return []
        
        sample = blocked_urls[:3]
        observed = f"{len(blocked_urls)} URLs blocked. Examples: {', '.join(sample)}"
        return [Finding(
            id=generate_finding_id(self.rule_id, [dataset.seed_url]),
            pipeline=self.pipeline,
            title="Robots.txt Blocking",
            severity=Severity.MEDIUM,
            trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
            suggested_action=SuggestedAction(summary="Review robots.txt rules.", priority=ActionPriority.MEDIUM),
            evidence=Evidence(
                page=dataset.seed_url, # Using seed_url as safe provenance for dataset-level finding
                source="unfetched_urls", field="robots_blocked", observed_value=observed,
                pages_checked=1, pages_affected=1, affected_percentage=100.0,
                # Intentionally NOT adding blocked URLs to affected_pages to respect Phase 3
            )
        )]

class NoindexRule(AuditRule):
    @property
    def rule_id(self) -> str: return "AI-ROBOTS-002"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Noindex Directive"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        findings = []
        for page in dataset.pages:
            if any("noindex" in r.lower() for r in page.extracted.meta_robots):
                findings.append(Finding(
                    id=generate_finding_id(self.rule_id, [page.url]),
                    pipeline=self.pipeline,
                    title="Noindex Directive Present",
                    severity=Severity.LOW,
                    trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                    suggested_action=SuggestedAction(summary="Review to ensure directive is intentional. If intended to be discoverable, remove the directive.", priority=ActionPriority.LOW),
                    evidence=Evidence(page=page.url, source="meta_robots", field="meta_robots", observed_value="noindex directive present", pages_checked=1, pages_affected=1, affected_percentage=100.0)
                ))
        return findings

class NofollowRule(AuditRule):
    @property
    def rule_id(self) -> str: return "AI-ROBOTS-003"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Nofollow Directive"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        findings = []
        for page in dataset.pages:
            if "nofollow" in [r.lower() for r in page.extracted.meta_robots]:
                findings.append(Finding(
                    id=generate_finding_id(self.rule_id, [page.url]),
                    pipeline=self.pipeline,
                    title="Nofollow Directive Present",
                    severity=Severity.LOW,
                    trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                    suggested_action=SuggestedAction(summary="Review to ensure directive is intentional. If intended to be discoverable, remove the directive.", priority=ActionPriority.LOW),
                    evidence=Evidence(page=page.url, source="meta_robots", field="meta_robots", observed_value="nofollow directive present", pages_checked=1, pages_affected=1, affected_percentage=100.0)
                ))
        return findings

class RedirectChainRule(AuditRule):
    @property
    def rule_id(self) -> str: return "AI-REDIRECT-001"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Redirect Chains"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        findings = []
        for page in dataset.pages:
            if len(page.redirect_chain) >= 2:
                observed = " -> ".join(page.redirect_chain)
                findings.append(Finding(
                    id=generate_finding_id(self.rule_id, [page.url]),
                    pipeline=self.pipeline,
                    title="Redirect Chain",
                    severity=Severity.MEDIUM,
                    trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                    suggested_action=SuggestedAction(summary="Update links to point to the final URL directly.", priority=ActionPriority.MEDIUM),
                    evidence=Evidence(page=page.url, source="redirect_chain", field="redirect_chain", observed_value=observed, pages_checked=1, pages_affected=1, affected_percentage=100.0)
                ))
        return findings

class MissingCanonicalRule(AuditRule):
    @property
    def rule_id(self) -> str: return "AI-CANONICAL-001"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Missing Canonical"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        findings = []
        for page in dataset.pages:
            if page.status_code == 200 and page.content_type.startswith('text/html'):
                if not page.extracted.canonical:
                    findings.append(Finding(
                        id=generate_finding_id(self.rule_id, [page.url]),
                        pipeline=self.pipeline,
                        title="Missing Canonical",
                        severity=Severity.MEDIUM,
                        trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                        suggested_action=SuggestedAction(summary="Add a canonical tag.", priority=ActionPriority.MEDIUM),
                        evidence=Evidence(page=page.url, source="extracted", field="canonical", observed_value="No canonical tag found", pages_checked=1, pages_affected=1, affected_percentage=100.0)
                    ))
        return findings

class CanonicalToErrorRule(AuditRule):
    @property
    def rule_id(self) -> str: return "AI-CANONICAL-002"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Canonical to Error (4xx/5xx)"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        graph = _build_url_graph(dataset)
        findings = []
        for page in dataset.pages:
            if page.status_code == 200 and page.content_type.startswith('text/html') and page.extracted.canonical:
                resolved_canonical = urljoin(page.final_url, page.extracted.canonical)
                target = graph.get(resolved_canonical)
                if target and target.status_code >= 400:
                    findings.append(Finding(
                        id=generate_finding_id(self.rule_id, [page.url]),
                        pipeline=self.pipeline,
                        title="Canonical Points to Error",
                        severity=Severity.HIGH,
                        trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                        suggested_action=SuggestedAction(summary="Fix canonical tag to point to a valid 200 OK page.", priority=ActionPriority.HIGH),
                        evidence=Evidence(page=page.url, source="canonical", field="canonical", observed_value=resolved_canonical, pages_checked=1, pages_affected=1, affected_percentage=100.0)
                    ))
        return findings

class CanonicalToRedirectRule(AuditRule):
    @property
    def rule_id(self) -> str: return "AI-CANONICAL-003"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Canonical to Redirect"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        graph = _build_url_graph(dataset)
        findings = []
        for page in dataset.pages:
            if page.status_code == 200 and page.content_type.startswith('text/html') and page.extracted.canonical:
                resolved_canonical = urljoin(page.final_url, page.extracted.canonical)
                target = graph.get(resolved_canonical)
                if target and len(target.redirect_chain) > 0:
                    findings.append(Finding(
                        id=generate_finding_id(self.rule_id, [page.url]),
                        pipeline=self.pipeline,
                        title="Canonical Points to Redirect",
                        severity=Severity.MEDIUM,
                        trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                        suggested_action=SuggestedAction(summary="Fix canonical tag to point directly to the final destination.", priority=ActionPriority.MEDIUM),
                        evidence=Evidence(page=page.url, source="canonical", field="canonical", observed_value=resolved_canonical, pages_checked=1, pages_affected=1, affected_percentage=100.0)
                    ))
        return findings

class BrokenInternalLinkRule(AuditRule):
    @property
    def rule_id(self) -> str: return "AI-LINK-001"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Broken Internal Link"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        graph = _build_url_graph(dataset)
        findings = []
        for page in dataset.pages:
            if page.status_code == 200 and page.content_type.startswith('text/html'):
                broken_targets = []
                for link in page.extracted.internal_links:
                    target = graph.get(link)
                    if target and target.status_code >= 400:
                        broken_targets.append(link)
                
                if broken_targets:
                    observed = ", ".join(broken_targets[:5])
                    findings.append(Finding(
                        id=generate_finding_id(self.rule_id, [page.url]),
                        pipeline=self.pipeline,
                        title="Broken Internal Link(s)",
                        severity=Severity.HIGH,
                        trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                        suggested_action=SuggestedAction(summary="Remove or update broken links.", priority=ActionPriority.HIGH),
                        evidence=Evidence(page=page.url, source="internal_links", field="internal_links", observed_value=observed, pages_checked=1, pages_affected=1, affected_percentage=100.0)
                    ))
        return findings

class InternalLinkToRedirectRule(AuditRule):
    @property
    def rule_id(self) -> str: return "AI-LINK-002"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Internal Link to Redirect"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        graph = _build_url_graph(dataset)
        findings = []
        for page in dataset.pages:
            if page.status_code == 200 and page.content_type.startswith('text/html'):
                redir_targets = []
                for link in page.extracted.internal_links:
                    target = graph.get(link)
                    if target and len(target.redirect_chain) > 0:
                        redir_targets.append(link)
                
                if redir_targets:
                    observed = ", ".join(redir_targets[:5])
                    findings.append(Finding(
                        id=generate_finding_id(self.rule_id, [page.url]),
                        pipeline=self.pipeline,
                        title="Internal Link(s) to Redirect",
                        severity=Severity.LOW,
                        trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                        suggested_action=SuggestedAction(summary="Update internal links to point directly to their final destinations.", priority=ActionPriority.LOW),
                        evidence=Evidence(page=page.url, source="internal_links", field="internal_links", observed_value=observed, pages_checked=1, pages_affected=1, affected_percentage=100.0)
                    ))
        return findings

class OrphanPageRule(AuditRule):
    @property
    def rule_id(self) -> str: return "AI-LINK-003"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Orphan Page"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        # Suppress if crawl was incomplete
        if dataset.crawl_diagnostics.crawl_termination_reason != "finished" or dataset.crawl_diagnostics.pages_discovered_not_fetched > 0:
            return []
            
        all_linked = set()
        for page in dataset.pages:
            all_linked.update(page.extracted.internal_links)
            
        findings = []
        for page in dataset.pages:
            if page.depth > 0 and page.url not in all_linked and page.status_code == 200 and page.content_type.startswith('text/html'):
                findings.append(Finding(
                    id=generate_finding_id(self.rule_id, [page.url]),
                    pipeline=self.pipeline,
                    title="Orphan Page",
                    severity=Severity.HIGH,
                    trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                    suggested_action=SuggestedAction(summary="Add internal links pointing to this page to make it discoverable.", priority=ActionPriority.HIGH),
                    evidence=Evidence(page=page.url, source="graph", field="incoming_links", observed_value="0 incoming internal links found", pages_checked=1, pages_affected=1, affected_percentage=100.0)
                ))
        return findings

class ExcessiveDepthRule(AuditRule):
    @property
    def rule_id(self) -> str: return "AI-LINK-004"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Excessive Depth"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        findings = []
        for page in dataset.pages:
            if page.depth >= 4 and page.status_code == 200 and page.content_type.startswith('text/html'):
                findings.append(Finding(
                    id=generate_finding_id(self.rule_id, [page.url]),
                    pipeline=self.pipeline,
                    title="Excessive Crawl Depth",
                    severity=Severity.LOW,
                    trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                    suggested_action=SuggestedAction(summary="Improve site architecture so this page is reachable in fewer clicks.", priority=ActionPriority.LOW),
                    evidence=Evidence(page=page.url, source="crawler", field="depth", observed_value=str(page.depth), pages_checked=1, pages_affected=1, affected_percentage=100.0)
                ))
        return findings

class MissingH1Rule(AuditRule):
    @property
    def rule_id(self) -> str: return "AI-HTML-001"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Missing H1"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        findings = []
        for page in dataset.pages:
            if page.status_code == 200 and page.content_type.startswith('text/html'):
                if not page.extracted.h1s:
                    findings.append(Finding(
                        id=generate_finding_id(self.rule_id, [page.url]),
                        pipeline=self.pipeline,
                        title="Missing H1",
                        severity=Severity.MEDIUM,
                        trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                        suggested_action=SuggestedAction(summary="Add an H1 tag to describe the page's main topic.", priority=ActionPriority.MEDIUM),
                        evidence=Evidence(page=page.url, source="extracted", field="h1s", observed_value="0 H1 tags found", pages_checked=1, pages_affected=1, affected_percentage=100.0)
                    ))
        return findings

class MissingTitleRule(AuditRule):
    @property
    def rule_id(self) -> str: return "AI-META-001"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Missing Title"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        findings = []
        for page in dataset.pages:
            if page.status_code == 200 and page.content_type.startswith('text/html'):
                if page.extracted.title is None:
                    findings.append(Finding(
                        id=generate_finding_id(self.rule_id, [page.url]),
                        pipeline=self.pipeline,
                        title="Missing Title",
                        severity=Severity.HIGH,
                        trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                        suggested_action=SuggestedAction(summary="Add a descriptive <title> tag.", priority=ActionPriority.HIGH),
                        evidence=Evidence(page=page.url, source="extracted", field="title", observed_value="None", pages_checked=1, pages_affected=1, affected_percentage=100.0)
                    ))
        return findings

class EmptyTitleRule(AuditRule):
    @property
    def rule_id(self) -> str: return "AI-META-002"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Empty Title"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        findings = []
        for page in dataset.pages:
            if page.status_code == 200 and page.content_type.startswith('text/html'):
                if page.extracted.title is not None and page.extracted.title.strip() == "":
                    findings.append(Finding(
                        id=generate_finding_id(self.rule_id, [page.url]),
                        pipeline=self.pipeline,
                        title="Empty Title",
                        severity=Severity.HIGH,
                        trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                        suggested_action=SuggestedAction(summary="Provide a non-empty <title> tag.", priority=ActionPriority.HIGH),
                        evidence=Evidence(page=page.url, source="extracted", field="title", observed_value='""', pages_checked=1, pages_affected=1, affected_percentage=100.0)
                    ))
        return findings

class MissingMetaDescriptionRule(AuditRule):
    @property
    def rule_id(self) -> str: return "AI-META-003"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Missing Meta Description"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        findings = []
        for page in dataset.pages:
            if page.status_code == 200 and page.content_type.startswith('text/html'):
                if not page.extracted.meta_description or page.extracted.meta_description.strip() == "":
                    findings.append(Finding(
                        id=generate_finding_id(self.rule_id, [page.url]),
                        pipeline=self.pipeline,
                        title="Missing Meta Description",
                        severity=Severity.LOW,
                        trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                        suggested_action=SuggestedAction(summary="Consider adding a meta description.", priority=ActionPriority.LOW),
                        evidence=Evidence(page=page.url, source="extracted", field="meta_description", observed_value="None or empty", pages_checked=1, pages_affected=1, affected_percentage=100.0)
                    ))
        return findings

class MalformedJsonLdRule(AuditRule):
    @property
    def rule_id(self) -> str: return "AI-SCHEMA-001"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Malformed JSON-LD"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        findings = []
        for page in dataset.pages:
            if page.status_code == 200 and page.content_type.startswith('text/html'):
                if page.diagnostics.malformed_jsonld_count > 0:
                    findings.append(Finding(
                        id=generate_finding_id(self.rule_id, [page.url]),
                        pipeline=self.pipeline,
                        title="Malformed JSON-LD",
                        severity=Severity.HIGH,
                        trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                        suggested_action=SuggestedAction(summary="Fix JSON syntax errors in schema markup.", priority=ActionPriority.HIGH),
                        evidence=Evidence(page=page.url, source="diagnostics", field="malformed_jsonld_count", observed_value=str(page.diagnostics.malformed_jsonld_count), pages_checked=1, pages_affected=1, affected_percentage=100.0)
                    ))
        return findings

class ExactDuplicateContentRule(AuditRule):
    @property
    def rule_id(self) -> str: return "AI-CONTENT-001"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Exact Duplicate Content"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        # Hash visible text (ignoring whitespace)
        hash_map = {}
        for page in dataset.pages:
            # Exclude error pages, empty text
            if page.status_code == 200 and page.content_type.startswith('text/html') and page.extracted.visible_text:
                norm_text = "".join(page.extracted.visible_text.split())
                if len(norm_text) > 0:
                    h = hashlib.sha256(norm_text.encode('utf-8')).hexdigest()
                    if h not in hash_map:
                        hash_map[h] = []
                    hash_map[h].append(page.url)
        
        findings = []
        for h, urls in hash_map.items():
            if len(urls) > 1:
                findings.append(Finding(
                    id=generate_finding_id(self.rule_id, sorted(urls)),
                    pipeline=self.pipeline,
                    title="Exact Duplicate Content",
                    severity=Severity.MEDIUM,
                    trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                    suggested_action=SuggestedAction(summary="Consolidate pages or use canonical tags.", priority=ActionPriority.MEDIUM),
                    evidence=Evidence(
                        page=urls[0], source="extracted", field="visible_text", observed_value=f"Exact duplicate across {len(urls)} pages",
                        pages_checked=len(dataset.pages), pages_affected=len(urls), affected_percentage=round((len(urls)/len(dataset.pages))*100, 2),
                        affected_pages=AffectedPages(count=len(urls), sample=urls[:5], truncated=len(urls)>5)
                    )
                ))
        return findings

class ThinContentRule(AuditRule):
    @property
    def rule_id(self) -> str: return "AI-CONTENT-002"
    @property
    def pipeline(self) -> Pipeline: return Pipeline.AI_DISCOVERABILITY
    @property
    def description(self) -> str: return "Thin Content"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        findings = []
        for page in dataset.pages:
            if page.status_code == 200 and page.content_type.startswith('text/html'):
                if page.diagnostics.visible_text_length > 0 and page.diagnostics.visible_text_length < 50:
                    findings.append(Finding(
                        id=generate_finding_id(self.rule_id, [page.url]),
                        pipeline=self.pipeline,
                        title="Thin Content",
                        severity=Severity.LOW,
                        trigger=Trigger(rule_id=self.rule_id, type=TriggerType.DETERMINISTIC),
                        suggested_action=SuggestedAction(summary="Review to ensure page has enough context to be discoverable.", priority=ActionPriority.LOW),
                        evidence=Evidence(page=page.url, source="diagnostics", field="visible_text_length", observed_value=str(page.diagnostics.visible_text_length), pages_checked=1, pages_affected=1, affected_percentage=100.0)
                    ))
        return findings

# A function to quickly register all these rules
def register_ai_discoverability_rules(registry):
    registry.register(ClientErrorRule())
    registry.register(ServerErrorRule())
    registry.register(RobotsBlockingRule())
    registry.register(NoindexRule())
    registry.register(NofollowRule())
    registry.register(RedirectChainRule())
    registry.register(MissingCanonicalRule())
    registry.register(CanonicalToErrorRule())
    registry.register(CanonicalToRedirectRule())
    registry.register(BrokenInternalLinkRule())
    registry.register(InternalLinkToRedirectRule())
    registry.register(OrphanPageRule())
    registry.register(ExcessiveDepthRule())
    registry.register(MissingH1Rule())
    registry.register(MissingTitleRule())
    registry.register(EmptyTitleRule())
    registry.register(MissingMetaDescriptionRule())
    registry.register(MalformedJsonLdRule())
    registry.register(ExactDuplicateContentRule())
    registry.register(ThinContentRule())
