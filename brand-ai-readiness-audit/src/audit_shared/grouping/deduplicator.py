import hashlib
import json
from typing import List, Dict, Tuple, Set
from audit_shared.models.finding import Finding, AffectedPages, Evidence
from audit_shared.models.grouping import EvaluationScope, GroupingResult
import copy

class GroupDeduplicator:
    @classmethod
    def process(cls, findings: List[Finding], scope: EvaluationScope) -> List[GroupingResult]:
        # 1. Exact Deduplication
        deduped = cls._deduplicate(findings)
        
        # 2. Grouping
        groups = cls._group(deduped)
        
        # 3. Aggregate & Format
        results = []
        for key, group_findings in groups.items():
            results.append(cls._create_grouping_result(key, group_findings, scope))
            
        # Sort results deterministically by group_id
        results.sort(key=lambda r: r.group_id)
        return results

    @classmethod
    def _deduplicate(cls, findings: List[Finding]) -> List[Finding]:
        seen = set()
        deduped = []
        
        # Sort canonically to ensure we pick the first deterministically
        # For deduplication, sorting by ID and then stringified payload is safe
        sorted_findings = sorted(findings, key=lambda f: (f.id, json.dumps(f.to_dict(), sort_keys=True)))
        
        for f in sorted_findings:
            page = f.evidence.page if f.evidence and f.evidence.page else ""
            field = f.evidence.field if f.evidence and f.evidence.field else ""
            obs = str(f.evidence.observed_value) if f.evidence and f.evidence.observed_value is not None else ""
            
            sig_parts = [
                f.id,
                f.pipeline.value,
                f.trigger.rule_id,
                f.trigger.type.value,
                f.severity.value,
                page,
                field,
                obs
            ]
            
            sig = hashlib.sha256(("|".join(sig_parts)).encode('utf-8')).hexdigest()
            if sig not in seen:
                seen.add(sig)
                deduped.append(f)
                
        return deduped

    @classmethod
    def _group(cls, findings: List[Finding]) -> Dict[Tuple[str, str, str, str], List[Finding]]:
        groups = {}
        for f in findings:
            key = (
                f.pipeline.value,
                f.trigger.rule_id,
                f.trigger.type.value,
                f.severity.value
            )
            if key not in groups:
                groups[key] = []
            groups[key].append(f)
        return groups

    @classmethod
    def _create_grouping_result(
        cls, 
        key: Tuple[str, str, str, str], 
        source_findings: List[Finding], 
        scope: EvaluationScope
    ) -> GroupingResult:
        pipeline_val, rule_id, trigger_type_val, severity_val = key
        
        # Sort source findings by page URL, then by ID to get deterministic representative
        def _sort_key(f: Finding) -> Tuple[str, str]:
            return (f.evidence.page or "", f.id)
            
        sorted_sources = sorted(source_findings, key=_sort_key)
        rep = sorted_sources[0]
        
        # Generate stable Group ID
        hasher = hashlib.sha256()
        for k in key:
            hasher.update(k.encode('utf-8'))
        digest = hasher.hexdigest()[:32]
        group_id = f"G-{rule_id}-{digest}".upper()
        
        # Extract unique affected URLs
        unique_urls = set()
        for f in sorted_sources:
            if f.evidence and f.evidence.page:
                unique_urls.add(f.evidence.page)
                
        sorted_unique_urls = sorted(list(unique_urls))
        sample_size = 10
        sample = sorted_unique_urls[:sample_size]
        is_truncated = len(sorted_unique_urls) > sample_size
        
        # Evaluation scope metrics
        pages_checked = scope.total_pages_evaluated
        pages_affected = len(sorted_unique_urls)
        if pages_checked == 0:
            pct = 0.0
        else:
            pct = (pages_affected / pages_checked) * 100
            
        # Create Canonical Finding
        # We start with the representative finding to inherit its structure, title, action, etc.
        canonical = Finding(
            id=group_id,
            pipeline=rep.pipeline,
            title=rep.title,
            severity=rep.severity,
            trigger=copy.deepcopy(rep.trigger),
            suggested_action=copy.deepcopy(rep.suggested_action),
            evidence=Evidence(
                pages_checked=pages_checked,
                pages_affected=pages_affected,
                affected_percentage=pct,
                affected_pages=AffectedPages(
                    count=len(sorted_unique_urls),
                    sample=sample,
                    truncated=is_truncated
                ),
                page=rep.evidence.page if rep.evidence else None,
                source=rep.evidence.source if rep.evidence else None,
                field=rep.evidence.field if rep.evidence else None,
                observed_value=rep.evidence.observed_value if rep.evidence else None,
                expected_value=rep.evidence.expected_value if rep.evidence else None,
                excerpt=rep.evidence.excerpt if rep.evidence else None,
                context=rep.evidence.context if rep.evidence else None,
                details=copy.deepcopy(rep.evidence.details) if rep.evidence else {}
            ),
            nlp=copy.deepcopy(rep.nlp) if rep.nlp else None,
            genai=copy.deepcopy(rep.genai) if rep.genai else None
        )
        
        source_ids = [f.id for f in sorted_sources]
        
        return GroupingResult(
            group_id=group_id,
            canonical_finding=canonical,
            source_finding_ids=source_ids,
            source_findings=sorted_sources
        )
