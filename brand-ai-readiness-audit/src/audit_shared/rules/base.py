from abc import ABC, abstractmethod
from typing import List
from audit_shared.models.finding import Finding, Pipeline
from audit_shared.models.data_flow import CrawlDataset

class AuditRule(ABC):
    @property
    @abstractmethod
    def rule_id(self) -> str:
        pass

    @property
    @abstractmethod
    def pipeline(self) -> Pipeline:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @abstractmethod
    def evaluate(self, dataset: CrawlDataset) -> List[Finding]:
        """
        Evaluates the existing CrawlDataset and returns a list of Findings.
        Must NOT perform network requests or crawl operations.
        """
        pass
