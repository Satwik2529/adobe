import hashlib
from enum import Enum
from dataclasses import dataclass, field as dc_field, asdict
from typing import List, Dict, Any, Optional

class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class Pipeline(Enum):
    AI_DISCOVERABILITY = "ai_discoverability"
    FRESHNESS = "freshness"
    ENGAGEMENT = "engagement"

class TriggerType(Enum):
    DETERMINISTIC = "deterministic"
    SEMANTIC = "semantic"

class ActionPriority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class Trigger:
    rule_id: str
    type: TriggerType

@dataclass
class SuggestedAction:
    summary: str
    priority: ActionPriority

@dataclass
class NLPContext:
    used: bool
    confidence: Optional[float] = None
    semantic_evidence: Dict[str, Any] = dc_field(default_factory=dict)

@dataclass
class GenAIContext:
    used: bool
    explanation: Optional[str] = None
    why_it_matters: Optional[str] = None
    possible_solution: Optional[str] = None

@dataclass
class AffectedPages:
    count: int
    sample: List[str]
    truncated: bool

@dataclass
class Evidence:
    # Scope metrics
    pages_checked: Optional[int] = None
    pages_affected: Optional[int] = None
    affected_percentage: Optional[float] = None
    affected_pages: Optional[AffectedPages] = None
    
    # Specifics
    page: Optional[str] = None
    source: Optional[str] = None
    field: Optional[str] = None
    observed_value: Any = None
    expected_value: Any = None
    excerpt: Optional[str] = None
    context: Optional[str] = None
    
    # Catch-all for rule-specific extractions
    details: Dict[str, Any] = dc_field(default_factory=dict)

@dataclass
class Finding:
    id: str
    pipeline: Pipeline
    title: str
    severity: Severity
    trigger: Trigger
    evidence: Evidence
    suggested_action: SuggestedAction
    nlp: Optional[NLPContext] = None
    genai: Optional[GenAIContext] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Custom serialization path that correctly maps enums to their string values
        and returns a clean, JSON-serializable dictionary.
        """
        def convert(obj: Any) -> Any:
            if isinstance(obj, Enum):
                return obj.value
            elif isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items() if v is not None}
            elif isinstance(obj, list):
                return [convert(i) for i in obj]
            elif isinstance(obj, tuple):
                return [convert(i) for i in obj]
            elif hasattr(obj, "__dataclass_fields__"):
                return {k: convert(getattr(obj, k)) for k in obj.__dataclass_fields__ if getattr(obj, k) is not None}
            else:
                return obj
        
        return convert(self)

def generate_finding_id(rule_id: str, identity_components: List[str]) -> str:
    """
    Deterministically generates a Finding ID based on the rule ID and identity components
    (like URL, or grouped signature).
    
    Example: 
    generate_finding_id("AI-SCHEMA-010", ["https://example.com/products/a"])
    """
    hasher = hashlib.sha256()
    hasher.update(rule_id.encode('utf-8'))
    for comp in identity_components:
        hasher.update(comp.encode('utf-8'))
    
    # Take first 32 chars of hash to append to a prefix to drastically reduce collision probability
    digest = hasher.hexdigest()[:32]
    return f"F-{rule_id}-{digest}".upper()
