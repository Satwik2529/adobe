from typing import List
from audit_shared.models.finding import Finding, Severity

def calculate_score(findings: List[Finding]) -> int:
    """
    Calculates the Audit Health Score (0-100).
    
    The score starts at 100 and deducts penalties for each canonical finding based on its severity.
    Because findings are already grouped (via Phase 8) into canonical root causes, 
    this avoids double-counting and page-volume inflation.
    
    Penalties:
    - High: 20
    - Medium: 10
    - Low: 5
    - Info: 0
    """
    score = 100
    
    penalty_map = {
        Severity.CRITICAL: 30, # Fallback if ever used
        Severity.HIGH: 20,
        Severity.MEDIUM: 10,
        Severity.LOW: 5,
        Severity.INFO: 0
    }
    
    for f in findings:
        score -= penalty_map.get(f.severity, 0)
        
    return max(0, score)
