import pytest
import asyncio
from typing import Optional, Dict, Any
from audit_shared.models.data_flow import CrawlDataset, PageRecord, ExtractedData
from audit_shared.nlp.schemas import NLPExecutionState, TopicAlignment
from audit_shared.nlp.client import NLPClient
from audit_shared.nlp.rules import SemanticTopicRule
from audit_shared.nlp.gating import CandidateGating
from audit_shared.nlp.interpreter import SemanticInterpreter

# Custom Mock Client to simulate all edge cases
class ExtendedMockNLPClient(NLPClient):
    async def _do_analyze_topic(self, title: str, text: str) -> Optional[Dict[str, Any]]:
        await asyncio.sleep(0.01) # fast for tests
        if "timeout_fail" in text:
            await asyncio.sleep(0.5) # Force timeout
            return None
        if "mock_fail" in text:
            raise ValueError("Simulated network failure")
        if "malformed_json" in text:
            return {"malformed": "json"}
        if "invalid_alignment" in text:
            return _valid_resp(title, text, align="super_low")
        if "missing_evidence" in text:
            resp = _valid_resp(title, text)
            resp["supporting_evidence"]["sources"] = []
            return resp
        if "hallucinated_text" in text:
            resp = _valid_resp(title, text, align="low")
            resp["supporting_evidence"]["sources"][0]["text"] = "I made this up"
            return resp
        if "wrong_field" in text:
            resp = _valid_resp(title, text, align="low")
            resp["supporting_evidence"]["sources"][0]["field"] = "nonexistent"
            return resp
        if "confidence_low" in text:
            resp = _valid_resp(title, text)
            resp["confidence"] = 0.5
            return resp
        if "confidence_invalid_high" in text:
            resp = _valid_resp(title, text)
            resp["confidence"] = 1.5
            return resp
        if "mock_low_alignment" in text:
            resp = _valid_resp(title, text)
            resp["observation"]["alignment"] = "low"
            # Ensure the source text perfectly matches
            resp["supporting_evidence"]["sources"].append({
                "source_type": "visible_text",
                "field": "visible_text",
                "text": "mock_low_alignment"
            })
            return resp
            
        return _valid_resp(title, text)

def _valid_resp(title, text, align="high", conf=0.95):
    return {
        "observation": {
            "apparent_topic": title,
            "content_topic": title,
            "alignment": align
        },
        "confidence": conf,
        "supporting_evidence": {
            "sources": [
                {"source_type": "page_title", "field": "title", "text": title}
            ],
            "interpretation": {
                "what_the_evidence_shows": "Matches",
                "why_it_supports_the_observation": "Yes"
            }
        }
    }

def create_page(url, title, text, status=200, ctype="text/html", lang="en"):
    return PageRecord(
        url=url, final_url=url, status_code=status, content_type=ctype, depth=1, parent_url=None,
        extracted=ExtractedData(language=lang, title=title, visible_text=text)
    )

@pytest.fixture
def base_dataset():
    pages = [
        create_page("http://ex.com/1", "OK", "This is an ok page. " * 30),
        create_page("http://ex.com/2", "Login", "Please login. " * 30, lang="en"),
        create_page("http://ex.com/3", "Mismatch", "mock_low_alignment content. " * 30),
        create_page("http://ex.com/4", "Short", "Too short."),
        create_page("http://ex.com/5", "NoHTML", "text " * 30, ctype="application/json"),
        create_page("http://ex.com/6", "ES", "text text " * 30, lang="es"),
        create_page("http://ex.com/7", "Mixed", "text text " * 30, lang="es-en"),
        create_page("http://ex.com/8", "NoLang", "text text " * 30, lang=None),
        create_page("http://ex.com/9", "Hallucinate", "hallucinated_text content " * 30),
        create_page("http://ex.com/10", "Malformed", "malformed_json content " * 30),
        create_page("http://ex.com/11", "InvAlign", "invalid_alignment content " * 30),
        create_page("http://ex.com/12", "LowConf", "confidence_low content " * 30),
        create_page("http://ex.com/13", "Timeout", "timeout_fail content " * 30),
    ]
    # Set URL 2 as /login to trigger exclusion
    pages[1].final_url = "http://ex.com/login"
    
    return CrawlDataset(seed_url="http://ex.com", crawled_at="now", pages=pages)

def test_gating_states(base_dataset):
    ds = base_dataset.pages
    assert CandidateGating.get_eligibility_state(ds[0]) is None # OK
    assert CandidateGating.get_eligibility_state(ds[1]) == NLPExecutionState.SKIPPED_BY_GATE # /login
    assert CandidateGating.get_eligibility_state(ds[3]) == NLPExecutionState.SKIPPED_BY_GATE # Short
    assert CandidateGating.get_eligibility_state(ds[4]) == NLPExecutionState.NOT_ELIGIBLE # non-html
    assert CandidateGating.get_eligibility_state(ds[5]) == NLPExecutionState.UNSUPPORTED_LANGUAGE # es
    assert CandidateGating.get_eligibility_state(ds[6]) == NLPExecutionState.UNSUPPORTED_LANGUAGE # mixed es-en
    assert CandidateGating.get_eligibility_state(ds[7]) == NLPExecutionState.UNSUPPORTED_LANGUAGE # no lang

def test_execution_states(base_dataset):
    client = ExtendedMockNLPClient(use_mock=True, timeout=0.2)
    rule = SemanticTopicRule(client=client, time_budget=10)
    results = asyncio.run(rule.evaluate(base_dataset))
    
    states = {r.page_url: r.state for r in results}
    
    assert states["http://ex.com/1"] == NLPExecutionState.ANALYSIS_NO_OBSERVATION
    assert states["http://ex.com/3"] == NLPExecutionState.ANALYSIS_SUCCESS
    assert states["http://ex.com/9"] == NLPExecutionState.EVIDENCE_INVALID # hallucinated
    assert states["http://ex.com/10"] == NLPExecutionState.INVALID_MODEL_OUTPUT # malformed
    assert states["http://ex.com/11"] == NLPExecutionState.INVALID_MODEL_OUTPUT # invalid enum
    assert states["http://ex.com/12"] == NLPExecutionState.ANALYSIS_NO_OBSERVATION # low conf dropped
    assert states["http://ex.com/13"] == NLPExecutionState.ANALYSIS_FAILED # timeout

def test_budget_150_pages():
    pages = [create_page(f"http://ex.com/page{i:03d}", f"T{i}", "Content words here. " * 30) for i in range(150)]
    # Make them explicitly out of order
    import random
    random.seed(42)
    random.shuffle(pages)
    
    ds = CrawlDataset(seed_url="http://ex.com", crawled_at="now", pages=pages)
    client = ExtendedMockNLPClient(use_mock=True)
    rule = SemanticTopicRule(client=client)
    
    results = asyncio.run(rule.evaluate(ds))
    
    analyzed = [r for r in results if r.state == NLPExecutionState.ANALYSIS_NO_OBSERVATION]
    skipped = [r for r in results if r.state == NLPExecutionState.SKIPPED_BY_BUDGET]
    
    assert len(analyzed) == 100
    assert len(skipped) == 50
    
    # Verify deterministic stable sorting (000 to 099 analyzed)
    analyzed_urls = sorted([r.page_url for r in analyzed])
    assert analyzed_urls[0] == "http://ex.com/page000"
    assert analyzed_urls[-1] == "http://ex.com/page099"

def test_global_timeout():
    pages = [create_page(f"http://ex.com/t{i}", f"T{i}", "timeout_fail content " * 30) for i in range(5)]
    ds = CrawlDataset(seed_url="http://ex.com", crawled_at="now", pages=pages)
    # Each takes 0.5s. Global budget = 0.2s. 
    # Global timeout will fire before any complete.
    client = ExtendedMockNLPClient(use_mock=True, timeout=1.0)
    rule = SemanticTopicRule(client=client, time_budget=0.2)
    
    import time
    start = time.time()
    results = asyncio.run(rule.evaluate(ds))
    duration = time.time() - start
    
    # Verify timeout didn't deadlock and completed fast
    assert duration < 0.4
    for r in results:
        assert r.state == NLPExecutionState.ANALYSIS_FAILED

