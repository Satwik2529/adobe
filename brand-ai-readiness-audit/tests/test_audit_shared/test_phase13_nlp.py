import pytest
import asyncio
from typing import List

from audit_shared.models.data_flow import CrawlDataset, PageRecord, ExtractedData, ExtractionDiagnostics
from audit_shared.nlp.rules import SemanticTopicRule
from audit_shared.nlp.client import NLPClient
from audit_shared.nlp.schemas import NLPExecutionState

def mock_dataset(pages: List[PageRecord]) -> CrawlDataset:
    return CrawlDataset(
        seed_url="https://example.com",
        crawled_at="2024-01-01T12:00:00Z",
        pages=pages
    )

def mock_page_nlp(url: str, title: str, text: str, page_type: str = "article") -> PageRecord:
    # Ensure text is at least 50 words to pass CandidateGating
    if len(text.split()) < 50:
        text += " word" * (50 - len(text.split()))
        
    ext = ExtractedData(
        title=title,
        meta_description="Test",
        h1s=["H1"],
        canonical=url,
        meta_robots=[],
        visible_text=text,
        internal_links=[],
        page_type=page_type,
        language="en"
    )
    return PageRecord(
        url=url,
        final_url=url,
        status_code=200,
        content_type="text/html",
        depth=1,
        redirect_chain=[],
        parent_url=None,
        crawl_status="success",
        raw_html="<html></html>",
        extracted=ext,
        diagnostics=ExtractionDiagnostics(malformed_jsonld_count=0, visible_text_length=10)
    )

def test_topic_alignment_high():
    # Regular mock behavior returns High alignment
    page = mock_page_nlp("https://example.com/ok", title="Good Topic", text="good content")
    ds = mock_dataset([page])
    client = NLPClient(use_mock=True)
    rule = SemanticTopicRule(client=client)
    
    results = asyncio.run(rule.evaluate(ds))
    assert len(results) == 1
    assert results[0].state == NLPExecutionState.ANALYSIS_NO_OBSERVATION
    assert results[0].observation is None

def test_topic_mismatch_low():
    # Use "mock_low_alignment" string in text to trigger mismatch in mock
    page = mock_page_nlp("https://example.com/bad", title="Bad Topic", text="mock_low_alignment content")
    ds = mock_dataset([page])
    client = NLPClient(use_mock=True)
    rule = SemanticTopicRule(client=client)
    
    results = asyncio.run(rule.evaluate(ds))
    assert len(results) == 1
    assert results[0].state == NLPExecutionState.ANALYSIS_SUCCESS
    assert results[0].observation is not None
    assert results[0].observation.observation.alignment.value == "low"
    assert results[0].observation.observation.content_topic == "Unrelated Topic"

def test_missing_title_bypassed():
    # Missing title bypasses NLP rule
    page = mock_page_nlp("https://example.com/notitle", title="", text="content")
    ds = mock_dataset([page])
    client = NLPClient(use_mock=True)
    rule = SemanticTopicRule(client=client)
    
    results = asyncio.run(rule.evaluate(ds))
    assert len(results) == 1
    assert results[0].state == NLPExecutionState.SKIPPED_BY_GATE
    assert "Missing title" in results[0].diagnostics[0]
