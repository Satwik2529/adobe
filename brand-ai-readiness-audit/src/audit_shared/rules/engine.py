import time
import logging
import traceback
from typing import Optional, List
from audit_shared.models.data_flow import CrawlDataset
from audit_shared.models.finding import Pipeline
from audit_shared.validation.finding_validator import FindingValidator
from audit_shared.rules.registry import RuleRegistry
from audit_shared.rules.models import (
    RuleExecutionDiagnostic, RuleExecutionResult, RuleExecutionStatus
)

logger = logging.getLogger(__name__)

class RuleEngine:
    @staticmethod
    def run(dataset: CrawlDataset, registry: RuleRegistry, pipeline: Optional[Pipeline] = None) -> RuleExecutionResult:
        rules = registry.get_all(pipeline)
        
        logger.info(f"Rule engine started. {len(rules)} rules to execute.")
        
        engine_start_time = time.time()
        
        all_findings = []
        diagnostics = []
        successful_rules = 0
        failed_rules = 0
        
        for rule in rules:
            logger.info(f"Executing rule {rule.rule_id}...")
            rule_start = time.time()
            diag = RuleExecutionDiagnostic(
                rule_id=rule.rule_id,
                status=RuleExecutionStatus.SUCCESS,
                duration_seconds=0.0,
                findings_generated=0,
                valid_findings=0,
                invalid_findings=0
            )
            
            try:
                raw_findings = rule.evaluate(dataset)
                diag.findings_generated = len(raw_findings)
                
                valid_findings = []
                for f in raw_findings:
                    errors = FindingValidator.validate(f, dataset)
                    if errors:
                        diag.validation_errors.extend(errors)
                        diag.invalid_findings += 1
                    else:
                        valid_findings.append(f)
                        diag.valid_findings += 1
                
                if diag.invalid_findings > 0:
                    diag.status = RuleExecutionStatus.INVALID_FINDINGS
                elif diag.findings_generated == 0:
                    diag.status = RuleExecutionStatus.NO_FINDINGS
                else:
                    diag.status = RuleExecutionStatus.SUCCESS
                
                all_findings.extend(valid_findings)
                
                if diag.status == RuleExecutionStatus.SUCCESS or diag.status == RuleExecutionStatus.NO_FINDINGS:
                    successful_rules += 1
                else:
                    failed_rules += 1
                    
            except Exception as e:
                diag.status = RuleExecutionStatus.FAILED
                diag.error_type = type(e).__name__
                diag.error_message = str(e)
                diag.traceback = traceback.format_exc()
                failed_rules += 1
                logger.error(f"Rule {rule.rule_id} failed with exception: {diag.error_type}: {diag.error_message}")
                
            diag.duration_seconds = time.time() - rule_start
            diagnostics.append(diag)
            logger.info(f"Rule {rule.rule_id} completed with status {diag.status.value} in {diag.duration_seconds:.3f}s. Generated {diag.findings_generated} findings (Valid: {diag.valid_findings}, Invalid: {diag.invalid_findings})")
            
        engine_duration = time.time() - engine_start_time
        logger.info(f"Rule engine completed in {engine_duration:.3f}s. Total valid findings: {len(all_findings)}.")
        
        return RuleExecutionResult(
            findings=all_findings,
            diagnostics=diagnostics,
            total_rules_run=len(rules),
            successful_rules=successful_rules,
            failed_rules=failed_rules,
            total_duration_seconds=engine_duration
        )
