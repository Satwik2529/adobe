import logging
from typing import List
from urllib.parse import urldefrag
from audit_shared.models.data_flow import CrawlDataset
from audit_shared.rules.base import AuditRule
from audit_shared.models.finding import (
    Finding, Pipeline, Severity, Trigger, TriggerType, SuggestedAction, ActionPriority, Evidence, generate_finding_id
)
from audit_shared.rules.registry import RuleRegistry

logger = logging.getLogger(__name__)

class EngagementRuleBase(AuditRule):
    @property
    def pipeline(self) -> Pipeline:
        return Pipeline.ENGAGEMENT


class DeadEndContentRule(EngagementRuleBase):
    @property
    def rule_id(self) -> str:
        return "ENG-NAV-001"

    @property
    def description(self) -> str:
        return "Dead-End Content Page"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        findings = []
        for page in dataset.pages:
            if page.status_code != 200:
                continue
                
            if page.extracted.page_type not in ["article", "product"]:
                continue
                
            internal_links = page.extracted.internal_links
            valid_outbound_links = set()
            
            # Extract normalized base URL of the current page
            page_base_url, _ = urldefrag(page.final_url or page.url)
            
            for link in internal_links:
                # Remove fragments
                clean_link, _ = urldefrag(link)
                
                # Exclude self-links
                if clean_link == page_base_url:
                    continue
                    
                # Exclude external links (internal_links list already filters these conceptually, 
                # but we rely on the clean deduped set)
                valid_outbound_links.add(clean_link)
                
            if len(valid_outbound_links) == 0:
                finding_id = generate_finding_id(self.rule_id, [page.url])
                findings.append(Finding(
                    id=finding_id,
                    pipeline=self.pipeline,
                    title=self.description,
                    severity=Severity.MEDIUM,
                    trigger=Trigger(
                        type=TriggerType.DETERMINISTIC,
                        rule_id=self.rule_id
                    ),
                    evidence=Evidence(
                        page=page.url,
                        details={
                            "page_type": page.extracted.page_type,
                            "outbound_internal_link_count": 0
                        }
                    ),
                    suggested_action=SuggestedAction(
                        priority=ActionPriority.MEDIUM,
                        summary="Article/product page has no outbound internal navigation links."
                    )
                ))
                
        return findings

class MissingImageAltRule(EngagementRuleBase):
    @property
    def rule_id(self) -> str:
        return "ENG-MEDIA-001"

    @property
    def description(self) -> str:
        return "Missing Image Alt Text"

    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        findings = []
        for page in dataset.pages:
            if page.status_code != 200:
                continue
                
            image_urls = page.extracted.image_urls
            total_images = len(image_urls)
            
            if total_images == 0:
                continue
                
            image_alts = page.extracted.image_alts
            # Count valid alts (excluding whitespace-only)
            valid_alts = [alt for alt in image_alts if alt.strip()]
            images_with_alt = len(valid_alts)
            
            images_missing_alt = total_images - images_with_alt
            
            if images_missing_alt > 0:
                finding_id = generate_finding_id(self.rule_id, [page.url])
                findings.append(Finding(
                    id=finding_id,
                    pipeline=self.pipeline,
                    title=self.description,
                    severity=Severity.MEDIUM,
                    trigger=Trigger(
                        type=TriggerType.DETERMINISTIC,
                        rule_id=self.rule_id
                    ),
                    evidence=Evidence(
                        page=page.url,
                        details={
                            "total_images": total_images,
                            "images_with_alt": images_with_alt,
                            "images_missing_alt": images_missing_alt
                        }
                    ),
                    suggested_action=SuggestedAction(
                        priority=ActionPriority.MEDIUM,
                        summary="Images are missing alternative text."
                    )
                ))
                
        return findings


def register_engagement_rules(registry: RuleRegistry):
    registry.register(DeadEndContentRule())
    registry.register(MissingImageAltRule())
