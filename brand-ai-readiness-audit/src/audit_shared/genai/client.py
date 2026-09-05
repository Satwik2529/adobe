import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class RateLimitError(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after {retry_after}s.")

class ProviderError(Exception):
    pass

class GenAIClient:
    def __init__(self, use_mock: bool = True, timeout: float = 2.0, max_retries: int = 3):
        self.use_mock = use_mock
        self.timeout = timeout
        self.max_retries = max_retries
        
    async def generate_explanation(self, prompt: str) -> Optional[dict]:
        """
        Attempts to generate an explanation with bounded retries and 429 handling.
        """
        base_backoff = 1.0
        
        for attempt in range(self.max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    self._do_request(prompt),
                    timeout=self.timeout
                )
                return result
            except asyncio.TimeoutError:
                logger.warning(f"GenAI timeout on attempt {attempt + 1}")
                if attempt == self.max_retries:
                    raise  # bubble up to engine to log as timeout
            except RateLimitError as e:
                logger.warning(f"GenAI 429 Rate Limit on attempt {attempt + 1}. Retry-After: {e.retry_after}")
                if attempt == self.max_retries:
                    raise  # bubble up to engine to log as 429 exhaustion
                
                # Bounded backoff
                sleep_time = max(e.retry_after, base_backoff * (2 ** attempt))
                await asyncio.sleep(sleep_time)
            except ProviderError as e:
                logger.error(f"GenAI provider failure on attempt {attempt + 1}: {e}")
                if attempt == self.max_retries:
                    raise  # bubble up
                
                await asyncio.sleep(base_backoff * (2 ** attempt))
                
        return None

    async def _do_request(self, prompt: str) -> dict:
        if self.use_mock:
            # Simulate basic latency
            await asyncio.sleep(0.01)
            
            # Deterministic test cases based on prompt injection
            if "mock_429_recover" in prompt:
                if not hasattr(self, '_mock_429_count'):
                    self._mock_429_count = 0
                self._mock_429_count += 1
                if self._mock_429_count == 1:
                    raise RateLimitError(retry_after=0)
                return {
                    "explanation": "Recovered from 429!",
                    "why_it_matters": "It matters because 429 recovery works.",
                    "possible_solution": "Retry with backoff."
                }
                
            if "mock_429_exhaust" in prompt:
                raise RateLimitError(retry_after=0)
                
            if "mock_timeout" in prompt:
                await asyncio.sleep(self.timeout + 1.0)
                return {} # Should not reach here
                
            if "mock_500" in prompt:
                raise ProviderError("Internal Server Error")
                
            if "mock_invalid_type" in prompt:
                return "This is a string, not a dict"  # Intentionally wrong type to test engine validation
                
            if "mock_missing_field" in prompt:
                return {
                    "explanation": "Missing other fields"
                }

            if "mock_empty_string" in prompt:
                return {
                    "explanation": "",
                    "why_it_matters": "test",
                    "possible_solution": "test"
                }
                
            if "mock_oversize" in prompt:
                return {
                    "explanation": "A" * 5000,
                    "why_it_matters": "test",
                    "possible_solution": "test"
                }
                
            # Valid response
            return {
                "explanation": "This is a generalized explanation of the group issue. It helps search engines parse the site.",
                "why_it_matters": "It matters because search engines need clear guidance.",
                "possible_solution": "Implement the suggested best practices."
            }
        else:
            raise NotImplementedError("Real GenAI provider not configured.")
