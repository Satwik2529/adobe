from typing import List, Dict
from audit_shared.models.finding import Finding, Severity



class ScoringConfig:
    def __init__(self, weights: Dict[Severity, int] = None):
        self.weights = weights or {
            Severity.CRITICAL: 50,
            Severity.HIGH: 20,
            Severity.MEDIUM: 10,
            Severity.LOW: 5,
            Severity.INFO: 0
        }

class ScoringEngine:
    def __init__(self, config: ScoringConfig = None):
        self.config = config or ScoringConfig()
        
    def calculate_score(self, findings: List[Finding]) -> int:
        """
        Calculates the Audit Health Score (0-100).
        
        The score starts at 100 and deducts penalties for each canonical finding based on its severity weight.
        """
        score = 100
        
        for f in findings:
            score -= self.config.weights.get(f.severity, 0)
            
        return max(0, score)

def calculate_score(findings: List[Finding]) -> int:
    # Backwards compatibility function
    return ScoringEngine().calculate_score(findings)
