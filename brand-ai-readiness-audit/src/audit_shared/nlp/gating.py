from urllib.parse import urlparse
from typing import Optional
from audit_shared.models.data_flow import PageRecord
from audit_shared.nlp.schemas import NLPExecutionState

class CandidateGating:
    SUPPORTED_LANGUAGES = {"en"}
    EXCLUDED_PATHS = {"/login", "/cart", "/checkout", "/account", "/privacy", "/terms"}

    @classmethod
    def get_eligibility_state(cls, page: PageRecord) -> Optional[NLPExecutionState]:
        """
        Returns an NLPExecutionState if the page should be skipped.
        Returns None if the page is ELIGIBLE for NLP analysis.
        """
        if page.status_code != 200 or not page.content_type or "html" not in page.content_type.lower():
            return NLPExecutionState.NOT_ELIGIBLE
            
        url_to_check = page.final_url or page.url
        try:
            parsed = urlparse(url_to_check)
            path = parsed.path.lower()
            for excluded in cls.EXCLUDED_PATHS:
                if excluded in path:
                    return NLPExecutionState.SKIPPED_BY_GATE
        except Exception:
            # If URL parsing fails, we skip
            return NLPExecutionState.SKIPPED_BY_GATE
            
        lang = page.extracted.language
        if not lang:
            return NLPExecutionState.UNSUPPORTED_LANGUAGE
            
        # Normalize language (e.g. 'en-US' -> 'en')
        base_lang = lang.lower().split('-')[0]
        if base_lang not in cls.SUPPORTED_LANGUAGES:
            return NLPExecutionState.UNSUPPORTED_LANGUAGE
            
        if not page.extracted.visible_text:
            return NLPExecutionState.SKIPPED_BY_GATE
            
        word_count = len(page.extracted.visible_text.split())
        if word_count < 50:
            return NLPExecutionState.SKIPPED_BY_GATE
            
        return None  # Eligible
