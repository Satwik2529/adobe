import asyncio
import time
import logging
from typing import List
from audit_shared.models.grouping import GroupingResult
from audit_shared.models.finding import GenAIContext
from audit_shared.genai.client import GenAIClient, RateLimitError, ProviderError
from audit_shared.genai.diagnostics import GenAIDiagnostics

logger = logging.getLogger(__name__)

class GenAIEngine:
    def __init__(self, client: GenAIClient, global_budget_seconds: float = 10.0, max_concurrency: int = 5):
        self.client = client
        self.global_budget_seconds = global_budget_seconds
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.diagnostics = GenAIDiagnostics()
        
    async def enrich_groups(self, valid_groups: List[GroupingResult]) -> GenAIDiagnostics:
        """
        Enriches a list of valid grouped findings with GenAI contextual explanations.
        Enforces a global time budget and tracks diagnostics.
        """
        start_time = time.time()
        
        # Determine eligibility (must have evidence)
        eligible_groups = []
        for group in valid_groups:
            if group.canonical_finding.evidence and group.canonical_finding.evidence.observed_value is not None:
                eligible_groups.append(group)
                
        self.diagnostics.eligible_groups = len(eligible_groups)
        
        # Create tasks
        tasks = []
        for group in eligible_groups:
            tasks.append(self._process_single_group(group, start_time))
            
        await asyncio.gather(*tasks)
        
        self.diagnostics.total_duration_seconds = time.time() - start_time
        return self.diagnostics

    async def _process_single_group(self, group: GroupingResult, start_time: float):
        """
        Processes a single group with strict concurrency and budget checks.
        """
        # Budget check
        if (time.time() - start_time) >= self.global_budget_seconds:
            self.diagnostics.skipped_by_budget += 1
            return
            
        async with self.semaphore:
            # Second budget check after acquiring lock (in case queueing took too long)
            if (time.time() - start_time) >= self.global_budget_seconds:
                self.diagnostics.skipped_by_budget += 1
                return
                
            self.diagnostics.requests_attempted += 1
            
            finding = group.canonical_finding
            
            # Construct prompt from validated deterministic evidence
            # Include mock text if present in observed_value for testing
            prompt = (
                f"Explain the impact of '{finding.title}' "
                f"(Severity: {finding.severity.value}). "
                f"Observed: {finding.evidence.observed_value}."
            )
            
            try:
                result_dict = await self.client.generate_explanation(prompt)
                
                # Validation
                if not isinstance(result_dict, dict):
                    self.diagnostics.invalid_responses += 1
                    finding.genai = GenAIContext(used=False)
                    return
                    
                explanation = result_dict.get("explanation", "")
                why_it_matters = result_dict.get("why_it_matters", "")
                possible_solution = result_dict.get("possible_solution", "")
                
                if not isinstance(explanation, str) or not isinstance(why_it_matters, str) or not isinstance(possible_solution, str):
                    self.diagnostics.invalid_responses += 1
                    finding.genai = GenAIContext(used=False)
                    return
                
                explanation = explanation.strip()
                why_it_matters = why_it_matters.strip()
                possible_solution = possible_solution.strip()
                
                if not explanation or not why_it_matters or not possible_solution:
                    self.diagnostics.invalid_responses += 1
                    finding.genai = GenAIContext(used=False)
                    return
                    
                if len(explanation) > 1000 or len(why_it_matters) > 1000 or len(possible_solution) > 1000:
                    self.diagnostics.invalid_responses += 1
                    finding.genai = GenAIContext(used=False)
                    return
                    
                # Success
                self.diagnostics.successful += 1
                finding.genai = GenAIContext(
                    used=True, 
                    explanation=explanation,
                    why_it_matters=why_it_matters,
                    possible_solution=possible_solution
                )
                
            except asyncio.TimeoutError:
                self.diagnostics.timeouts += 1
                finding.genai = GenAIContext(used=False)
            except RateLimitError:
                self.diagnostics.rate_limited += 1
                finding.genai = GenAIContext(used=False)
            except ProviderError:
                self.diagnostics.provider_failures += 1
                finding.genai = GenAIContext(used=False)
            except Exception as e:
                logger.error(f"Unexpected error in GenAIEngine: {e}")
                self.diagnostics.provider_failures += 1
                finding.genai = GenAIContext(used=False)
