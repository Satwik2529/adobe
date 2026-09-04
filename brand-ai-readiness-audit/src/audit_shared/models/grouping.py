from dataclasses import dataclass, field
from typing import List, Optional
from audit_shared.models.finding import Finding

@dataclass
class EvaluationScope:
    html_pages_crawled: int
    successful_pages: int
    total_pages_evaluated: int
    is_truncated: bool

@dataclass
class GroupingResult:
    group_id: str
    canonical_finding: Finding
    source_finding_ids: List[str] = field(default_factory=list)
    source_findings: List[Finding] = field(default_factory=list)

