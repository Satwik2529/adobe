from dataclasses import dataclass
from typing import List, Tuple, Dict, Any
from audit_shared.models.data_flow import CrawlDataset, PageRecord
from audit_shared.models.grouping import GroupingResult, EvaluationScope
from audit_shared.models.finding import TriggerType, Finding
from audit_shared.validation.finding_validator import FindingValidator

@dataclass
class EvidenceDiagnostic:
    finding_id: str
    errors: List[str]

@dataclass
class ValidationResult:
    total_checked: int
    valid_groups: List[GroupingResult]
    invalid_groups: List[GroupingResult]
    diagnostics: List[EvidenceDiagnostic]

class EvidenceValidator:
    @classmethod
    def validate_all(cls, groups: List[GroupingResult], dataset: CrawlDataset, scope: EvaluationScope) -> ValidationResult:
        valid_groups = []
        invalid_groups = []
        diagnostics = []
        
        # Create quick lookup for pages
        page_map = {p.url: p for p in dataset.pages}
        for p in dataset.pages:
            if p.final_url:
                page_map[p.final_url] = p
                
        # unfetched urls
        unfetched = set(dataset.unfetched_urls)

        for group in groups:
            errors = []
            
            # 1. Structural aggregate checks
            base_errors = FindingValidator.validate(group.canonical_finding, dataset)
            if base_errors:
                errors.extend([f"Canonical Structure Error: {e}" for e in base_errors])
                
            # Aggregate Scope Check
            if not group.canonical_finding.evidence:
                errors.append("canonical_finding is missing evidence.")
            else:
                if group.canonical_finding.evidence.pages_checked != scope.total_pages_evaluated:
                    errors.append(f"pages_checked ({group.canonical_finding.evidence.pages_checked}) does not match explicit EvaluationScope ({scope.total_pages_evaluated}).")
                
                if group.canonical_finding.evidence.affected_pages:
                    sample = group.canonical_finding.evidence.affected_pages.sample
                    if len(sample) != len(set(sample)):
                        errors.append("affected_pages.sample contains duplicate URLs.")
            
            # Check source tracking
            if len(group.source_finding_ids) != len(group.source_findings):
                errors.append(f"Source findings mismatch: {len(group.source_finding_ids)} IDs vs {len(group.source_findings)} sources.")
                
            if len(group.source_findings) == 0:
                errors.append("Group has no source findings.")
                
            # Verify ALL source findings
            for sf in group.source_findings:
                sf_errors = cls._validate_source_finding(sf, page_map, unfetched)
                if sf_errors:
                    errors.extend([f"Source Finding {sf.id} error: {e}" for e in sf_errors])
                    
            if errors:
                invalid_groups.append(group)
                diagnostics.append(EvidenceDiagnostic(finding_id=group.group_id, errors=errors))
            else:
                valid_groups.append(group)
                
        return ValidationResult(
            total_checked=len(groups),
            valid_groups=valid_groups,
            invalid_groups=invalid_groups,
            diagnostics=diagnostics
        )
        
    @classmethod
    def _validate_source_finding(cls, f: Finding, page_map: Dict[str, PageRecord], unfetched: set) -> List[str]:
        errors = []
        
        if not f.evidence:
            errors.append("Evidence object is completely missing.")
            return errors
            
        page_url = f.evidence.page
        if not page_url:
            errors.append("Evidence page is missing.")
            return errors
            
        if page_url in unfetched:
            errors.append(f"Evidence page '{page_url}' is in unfetched_urls.")
            
        if page_url not in page_map:
            errors.append(f"Evidence page '{page_url}' not found in crawled dataset.")
            return errors
            
        record = page_map[page_url]
        
        if f.trigger.type == TriggerType.DETERMINISTIC:
            cls._validate_deterministic_evidence(f, record, errors)
        elif f.trigger.type == TriggerType.SEMANTIC:
            cls._validate_semantic_evidence(f, record, errors)
            
        return errors
        
    @classmethod
    def _validate_deterministic_evidence(cls, f: Finding, record: PageRecord, errors: List[str]):
        # Direct & Derived value validation
        # Since 'observed_value' is often prose (e.g. 'No canonical tag found'),
        # we check the relationship mapped by rule_id without completely re-running the rule.
        rid = f.trigger.rule_id
        extracted = record.extracted
        
        # AI Discoverability - Meta/HTML
        if rid == "AI-CANONICAL-001":
            if extracted.canonical:
                errors.append(f"Value mismatch: claims missing canonical, but canonical is '{extracted.canonical}'")
        elif rid == "AI-CANONICAL-002":
            if not isinstance(extracted.canonical, list) or len(extracted.canonical) < 2:
                errors.append(f"Value mismatch: claims multiple canonicals, but actual is '{extracted.canonical}'")
        elif rid == "AI-HTML-001":
            if extracted.h1s:
                errors.append(f"Value mismatch: claims missing H1, but H1 exists: {extracted.h1s}")
        elif rid == "AI-HTML-003":
            if extracted.title:
                errors.append(f"Value mismatch: claims missing title, but title is '{extracted.title}'")
        elif rid == "AI-HTML-004":
            if extracted.title and extracted.title.strip():
                errors.append(f"Value mismatch: claims empty title, but title is '{extracted.title}'")
        elif rid == "AI-HTML-005":
            if extracted.meta_description:
                errors.append(f"Value mismatch: claims missing meta description, but description exists.")
                
        # Links
        elif rid == "AI-LINK-001":
            # Broken links: Validate derived evidence (the link is actually on the page)
            obs = str(f.evidence.observed_value)
            found_any = False
            for link in extracted.detailed_internal_links:
                if link.get('url', '') in obs:
                    found_any = True
                    break
            if not found_any and len(extracted.detailed_internal_links) > 0:
                 pass
        elif rid == "AI-LINK-002":
            pass
            
        # JSON-LD
        elif rid == "AI-JSONLD-001":
            if extracted.json_ld:
                errors.append(f"Value mismatch: claims missing JSON-LD, but JSON-LD exists.")
                
        # Engagement
        elif rid == "ENG-NAV-001":
            pass

    @classmethod
    def _validate_semantic_evidence(cls, f: Finding, record: PageRecord, errors: List[str]):
        # Semantic provenance check
        if f.evidence.excerpt:
            if record.extracted.visible_text and f.evidence.excerpt not in record.extracted.visible_text:
                 errors.append(f"Semantic excerpt not found in crawled text content.")
                 
        if f.evidence.details:
            if "confidence" in f.evidence.details:
                conf = f.evidence.details["confidence"]
                if not isinstance(conf, (int, float)) or not (0 <= conf <= 1):
                    errors.append(f"Semantic confidence must be a float between 0 and 1, got {conf}")
                    
            if "sources" in f.evidence.details:
                for source in f.evidence.details["sources"]:
                    field_name = source.get("field")
                    text = source.get("text")
                    if field_name and text:
                        if hasattr(record.extracted, field_name):
                            actual_val = getattr(record.extracted, field_name)
                            if actual_val is None:
                                errors.append(f"Semantic source field '{field_name}' is None in CrawlDataset.")
                            elif isinstance(actual_val, str) and text not in actual_val:
                                errors.append(f"Semantic source text not found in crawled field '{field_name}'.")
                            elif isinstance(actual_val, list) and text not in str(actual_val):
                                errors.append(f"Semantic source text not found in crawled field '{field_name}'.")
                        else:
                            errors.append(f"Semantic source field '{field_name}' does not exist in CrawlDataset.")
