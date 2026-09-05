from dataclasses import dataclass

@dataclass
class GenAIDiagnostics:
    eligible_groups: int = 0
    requests_attempted: int = 0
    successful: int = 0
    rate_limited: int = 0
    timeouts: int = 0
    provider_failures: int = 0
    invalid_responses: int = 0
    skipped_by_budget: int = 0
    total_duration_seconds: float = 0.0

@dataclass
class StageTiming:
    crawling: float = 0.0
    rule_engines: float = 0.0
    grouping: float = 0.0
    evidence_validation: float = 0.0
    nlp: float = 0.0
    genai: float = 0.0
    reporting: float = 0.0
    total: float = 0.0
