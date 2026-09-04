import json
from typing import List
from urllib.parse import urlparse
from ..models.data_flow import CrawlDataset
from ..models.finding import Finding, Evidence

class FindingValidator:
    """
    Validates Finding objects to ensure they meet the structural contract
    and evidence provenance requirements.
    """
    
    @classmethod
    def validate(cls, finding: Finding, dataset: CrawlDataset) -> List[str]:
        errors = []
        
        # 1. Basic structural checks
        if not finding.id:
            errors.append("Finding must have an ID.")
        if not finding.title:
            errors.append("Finding must have a title.")
        if not finding.pipeline:
            errors.append("Finding must have a pipeline.")
        if not finding.severity:
            errors.append("Finding must have a severity.")
        if not finding.trigger or not finding.trigger.rule_id:
            errors.append("Finding must have a valid trigger.")
        if not finding.suggested_action or not finding.suggested_action.summary:
            errors.append("Finding must have a suggested_action.")
        
        if not finding.evidence:
            errors.append("Finding must have evidence.")
        else:
            cls._validate_evidence(finding.evidence, dataset, errors)
            
        # 2. JSON Serialization Proof
        try:
            # We enforce that the finding's to_dict() translates safely to JSON.
            # If a Scrapy Response or other un-serializable object is in evidence, it will fail here.
            json.dumps(finding.to_dict())
        except Exception as e:
            errors.append(f"Finding is not JSON serializable: {str(e)}")
            
        return errors

    @classmethod
    def _validate_evidence(cls, evidence: Evidence, dataset: CrawlDataset, errors: List[str]):
        # Validate Evidence Provenance (URLs)
        if evidence.page:
            if not cls._is_valid_url(evidence.page):
                errors.append(f"Invalid URL format in evidence.page: {evidence.page}")
            elif not cls._page_in_dataset(evidence.page, dataset):
                errors.append(f"Evidence page '{evidence.page}' does not exist in CrawlDataset.")
                
        if evidence.affected_pages and evidence.affected_pages.sample:
            for url in evidence.affected_pages.sample:
                if not cls._is_valid_url(url):
                    errors.append(f"Invalid URL format in affected_pages.sample: {url}")
                elif not cls._page_in_dataset(url, dataset):
                    errors.append(f"Affected page '{url}' does not exist in CrawlDataset.")
                    
        # Validate Mathematical Consistency
        if evidence.pages_affected is not None and evidence.pages_checked is not None:
            if evidence.pages_affected > evidence.pages_checked:
                errors.append("pages_affected cannot exceed pages_checked.")
            
            if evidence.affected_percentage is not None:
                if evidence.pages_checked == 0:
                    expected_pct = 0.0
                else:
                    expected_pct = (evidence.pages_affected / evidence.pages_checked) * 100
                if abs(evidence.affected_percentage - expected_pct) > 0.001:
                    errors.append(f"affected_percentage {evidence.affected_percentage} does not match computed {(expected_pct)}")
                    
        if evidence.affected_pages:
            if evidence.pages_affected is not None and evidence.affected_pages.count != evidence.pages_affected:
                errors.append(f"affected_pages.count ({evidence.affected_pages.count}) does not match pages_affected ({evidence.pages_affected}).")
                
            sample_len = len(evidence.affected_pages.sample)
            if evidence.affected_pages.truncated and sample_len >= evidence.affected_pages.count:
                errors.append("affected_pages.truncated is True but sample length is >= count.")
            elif not evidence.affected_pages.truncated and sample_len < evidence.affected_pages.count:
                errors.append("affected_pages.truncated is False but sample length is < count.")

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    @staticmethod
    def _page_in_dataset(url: str, dataset: CrawlDataset) -> bool:
        # Check fetched pages
        for p in dataset.pages:
            if p.url == url or p.final_url == url:
                return True
        # Note: Phase 3 prompt strictly says unfetched URLs cannot be used for page-level evidence.
        return False
