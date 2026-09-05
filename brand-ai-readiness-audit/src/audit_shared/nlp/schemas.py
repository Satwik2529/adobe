from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

class NLPExecutionState(Enum):
    NOT_ELIGIBLE = "not_eligible"
    SKIPPED_BY_GATE = "skipped_by_gate"
    UNSUPPORTED_LANGUAGE = "unsupported_language"
    SKIPPED_BY_BUDGET = "skipped_by_budget"
    ANALYSIS_SUCCESS = "analysis_success"
    ANALYSIS_NO_OBSERVATION = "analysis_no_observation"
    ANALYSIS_FAILED = "analysis_failed"
    INVALID_MODEL_OUTPUT = "invalid_model_output"
    EVIDENCE_INVALID = "evidence_invalid"

class TopicAlignment(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class EvidenceSource:
    source_type: str
    field: str
    text: str

@dataclass
class EvidenceInterpretation:
    what_the_evidence_shows: str
    why_it_supports_the_observation: str

@dataclass
class SemanticEvidence:
    sources: List[EvidenceSource] = field(default_factory=list)
    interpretation: Optional[EvidenceInterpretation] = None

@dataclass
class TopicObservation:
    apparent_topic: str
    content_topic: str
    alignment: TopicAlignment
    reason: str = ""

@dataclass
class SemanticObservation:
    page_url: str
    observation: TopicObservation
    confidence: float
    supporting_evidence: SemanticEvidence

@dataclass
class NLPPageResult:
    page_url: str
    state: NLPExecutionState
    observation: Optional[SemanticObservation] = None
    diagnostics: List[str] = field(default_factory=list)
