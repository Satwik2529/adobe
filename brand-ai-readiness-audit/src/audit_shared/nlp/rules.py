import asyncio
from typing import List, Optional
from audit_shared.models.data_flow import CrawlDataset, PageRecord
from audit_shared.nlp.client import NLPClient
from audit_shared.nlp.gating import CandidateGating
from audit_shared.nlp.schemas import (
    NLPExecutionState, NLPPageResult, SemanticObservation, 
    TopicObservation, TopicAlignment, SemanticEvidence, 
    EvidenceSource, EvidenceInterpretation
)

class SemanticTopicRule:
    RULE_ID = "SEMANTIC-TOPIC-001"
    MAX_CANDIDATES = 100
    MAX_WORDS = 1500
    CONFIDENCE_THRESHOLD = 0.85
    
    def __init__(self, client: NLPClient, time_budget: int = 180):
        self.client = client
        self.time_budget = time_budget
        
    async def evaluate(self, dataset: CrawlDataset) -> List[NLPPageResult]:
        results = []
        eligible_pages = []
        
        # 1. Gating
        for page in dataset.pages:
            skip_state = CandidateGating.get_eligibility_state(page)
            if skip_state:
                results.append(NLPPageResult(page_url=page.final_url or page.url, state=skip_state))
            else:
                if not page.extracted.title or not page.extracted.title.strip():
                    results.append(NLPPageResult(
                        page_url=page.final_url or page.url, 
                        state=NLPExecutionState.SKIPPED_BY_GATE, 
                        diagnostics=["Missing title"]
                    ))
                else:
                    eligible_pages.append(page)
                    
        # 2. Deterministic candidate selection
        eligible_pages.sort(key=lambda p: p.final_url or p.url)
        
        candidates = eligible_pages[:self.MAX_CANDIDATES]
        skipped_by_budget = eligible_pages[self.MAX_CANDIDATES:]
        
        for page in skipped_by_budget:
            results.append(NLPPageResult(
                page_url=page.final_url or page.url, 
                state=NLPExecutionState.SKIPPED_BY_BUDGET
            ))
            
        # 3. Analyze Candidates concurrently with a global time budget
        if not candidates:
            return results

        async def _bounded_analyze():
            tasks = [self._analyze_page(p) for p in candidates]
            return await asyncio.gather(*tasks, return_exceptions=True)

        try:
            candidate_results = await asyncio.wait_for(_bounded_analyze(), timeout=self.time_budget)
            
            for i, res in enumerate(candidate_results):
                if isinstance(res, Exception):
                    url = candidates[i].final_url or candidates[i].url
                    results.append(NLPPageResult(
                        page_url=url, 
                        state=NLPExecutionState.ANALYSIS_FAILED, 
                        diagnostics=["Global budget exhaustion or internal error"]
                    ))
                else:
                    results.append(res)
        except asyncio.TimeoutError:
            # If the global budget is exhausted, any incomplete tasks are failed
            # We don't know exactly which completed, so we'll just fail them all
            # (A more robust implementation would track completion individually)
            for page in candidates:
                results.append(NLPPageResult(
                    page_url=page.final_url or page.url, 
                    state=NLPExecutionState.ANALYSIS_FAILED, 
                    diagnostics=["Global NLP time budget exhausted"]
                ))
        
        return results

    async def _analyze_page(self, page: PageRecord) -> NLPPageResult:
        url = page.final_url or page.url
        title = page.extracted.title
        text = page.extracted.visible_text
        
        # Deterministic truncation
        words = text.split()
        if len(words) > self.MAX_WORDS:
            text = " ".join(words[:self.MAX_WORDS])
            
        try:
            raw_result = await self.client.analyze_topic(title, text)
            if not raw_result:
                return NLPPageResult(page_url=url, state=NLPExecutionState.ANALYSIS_FAILED)
                
            if "malformed" in raw_result:
                return NLPPageResult(page_url=url, state=NLPExecutionState.INVALID_MODEL_OUTPUT)
                
            obs_data = raw_result.get("observation", {})
            try:
                alignment = TopicAlignment(obs_data.get("alignment", "").lower())
            except ValueError:
                return NLPPageResult(page_url=url, state=NLPExecutionState.INVALID_MODEL_OUTPUT, diagnostics=["Invalid alignment value"])
                
            confidence = raw_result.get("confidence", 0.0)
            
            ev_data = raw_result.get("supporting_evidence", {})
            sources = []
            for s in ev_data.get("sources", []):
                sources.append(EvidenceSource(
                    source_type=s.get("source_type", ""),
                    field=s.get("field", ""),
                    text=s.get("text", "")
                ))
                
            interp_data = ev_data.get("interpretation", {})
            interpretation = EvidenceInterpretation(
                what_the_evidence_shows=interp_data.get("what_the_evidence_shows", ""),
                why_it_supports_the_observation=interp_data.get("why_it_supports_the_observation", "")
            )
            
            evidence = SemanticEvidence(sources=sources, interpretation=interpretation)
            
            observation = SemanticObservation(
                page_url=url,
                observation=TopicObservation(
                    apparent_topic=obs_data.get("apparent_topic", ""),
                    content_topic=obs_data.get("content_topic", ""),
                    alignment=alignment
                ),
                confidence=confidence,
                supporting_evidence=evidence
            )
            
            if confidence < self.CONFIDENCE_THRESHOLD:
                return NLPPageResult(page_url=url, state=NLPExecutionState.ANALYSIS_NO_OBSERVATION, diagnostics=["Low confidence"])
                
            if alignment != TopicAlignment.LOW:
                return NLPPageResult(page_url=url, state=NLPExecutionState.ANALYSIS_NO_OBSERVATION)
                
            # Basic provenance checks (EVIDENCE_INVALID)
            for s in sources:
                if s.field == "title":
                    if s.text not in title:
                        return NLPPageResult(page_url=url, state=NLPExecutionState.EVIDENCE_INVALID, diagnostics=["Hallucinated title text"])
                elif s.field == "visible_text":
                    if s.text not in page.extracted.visible_text:
                        return NLPPageResult(page_url=url, state=NLPExecutionState.EVIDENCE_INVALID, diagnostics=["Hallucinated visible_text"])
                else:
                    return NLPPageResult(page_url=url, state=NLPExecutionState.EVIDENCE_INVALID, diagnostics=[f"Unknown field: {s.field}"])
                    
            return NLPPageResult(page_url=url, state=NLPExecutionState.ANALYSIS_SUCCESS, observation=observation)
            
        except Exception as e:
            return NLPPageResult(page_url=url, state=NLPExecutionState.ANALYSIS_FAILED, diagnostics=[str(e)])
