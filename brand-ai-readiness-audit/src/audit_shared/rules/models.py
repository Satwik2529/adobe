from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum
from audit_shared.models.finding import Finding

class RuleExecutionStatus(str, Enum):
    SUCCESS = "success"
    NO_FINDINGS = "no_findings"
    FAILED = "failed"
    INVALID_FINDINGS = "invalid_findings"

@dataclass
class RuleExecutionDiagnostic:
    rule_id: str
    status: RuleExecutionStatus
    duration_seconds: float
    findings_generated: int
    valid_findings: int
    invalid_findings: int
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    traceback: Optional[str] = None
    validation_errors: List[str] = field(default_factory=list)

@dataclass
class RuleExecutionResult:
    findings: List[Finding]
    diagnostics: List[RuleExecutionDiagnostic]
    total_rules_run: int
    successful_rules: int
    failed_rules: int
    total_duration_seconds: float
