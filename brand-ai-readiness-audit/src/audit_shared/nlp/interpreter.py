from typing import List
from audit_shared.models.finding import (
    Finding, Pipeline, Severity, Trigger, TriggerType, SuggestedAction, ActionPriority,
    Evidence, NLPContext, generate_finding_id
)
from audit_shared.nlp.schemas import NLPExecutionState, NLPPageResult

class SemanticInterpreter:
    @classmethod
    def interpret(cls, results: List[NLPPageResult]) -> List[Finding]:
        findings = []
        for res in results:
            if res.state == NLPExecutionState.ANALYSIS_SUCCESS and res.observation:
                finding = cls._create_topic_finding(res)
                findings.append(finding)
        return findings

    @classmethod
    def _create_topic_finding(cls, result: NLPPageResult) -> Finding:
        rule_id = "SEMANTIC_TOPIC_RELEVANCE"
        pipeline = Pipeline.AI_DISCOVERABILITY
        severity = Severity.MEDIUM
        trigger = Trigger(rule_id=rule_id, type=TriggerType.SEMANTIC)
        
        obs = result.observation
        
        semantic_ev_dict = {
            "apparent_topic": obs.observation.apparent_topic,
            "content_topic": obs.observation.content_topic,
            "alignment": obs.observation.alignment.value,
            "reason": obs.observation.reason
        }
        
        nlp_context = NLPContext(
            used=True,
            confidence=obs.confidence,
            semantic_evidence=semantic_ev_dict
        )
        
        excerpt = None
        for s in obs.supporting_evidence.sources:
            if s.field == "visible_text":
                excerpt = s.text
                break
                
        evidence = Evidence(
            page=result.page_url,
            source="semantic_analysis",
            field="visible_text",
            observed_value=f"Apparent topic: {obs.observation.apparent_topic} vs Content topic: {obs.observation.content_topic}",
            expected_value="High alignment between title and content topics",
            excerpt=excerpt,
            details=semantic_ev_dict
        )
        
        suggested_action = SuggestedAction(
            summary="Align the page content with the topic indicated by the title.",
            priority=ActionPriority.MEDIUM
        )
        
        finding_id = generate_finding_id(rule_id, [result.page_url])
        
        return Finding(
            id=finding_id,
            pipeline=pipeline,
            title="Pages do not clearly address their apparent topics",
            severity=severity,
            trigger=trigger,
            evidence=evidence,
            suggested_action=suggested_action,
            nlp=nlp_context
        )
