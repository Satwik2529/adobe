from typing import List, Dict, Optional
from audit_shared.rules.base import AuditRule
from audit_shared.models.finding import Pipeline

class RuleRegistry:
    def __init__(self):
        self._rules: Dict[str, AuditRule] = {}

    def register(self, rule: AuditRule) -> None:
        if not isinstance(rule, AuditRule):
            raise TypeError("Rule must inherit from AuditRule")
            
        if not hasattr(rule, 'rule_id') or not rule.rule_id:
            raise ValueError("Rule must define a valid rule_id")
            
        if rule.rule_id in self._rules:
            raise ValueError(f"Rule with ID {rule.rule_id} is already registered")
            
        if not hasattr(rule, 'pipeline') or not isinstance(rule.pipeline, Pipeline):
            raise ValueError("Rule must define a valid Pipeline enum")
            
        self._rules[rule.rule_id] = rule

    def get(self, rule_id: str) -> Optional[AuditRule]:
        return self._rules.get(rule_id)

    def get_all(self, pipeline: Optional[Pipeline] = None) -> List[AuditRule]:
        """
        Returns all registered rules in deterministic alphabetical order by rule_id.
        Can be optionally filtered by Pipeline.
        """
        rules = list(self._rules.values())
        if pipeline:
            rules = [r for r in rules if r.pipeline == pipeline]
            
        return sorted(rules, key=lambda r: r.rule_id)

    def list(self) -> List[str]:
        return sorted(self._rules.keys())
