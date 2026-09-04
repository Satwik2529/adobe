import time
import json
import sys

from audit_shared.config.settings import CrawlSettings
from audit_shared.rules.registry import RuleRegistry
from audit_shared.rules.ai_discoverability import register_ai_discoverability_rules
from audit_shared.rules.freshness import register_freshness_rules
from audit_shared.rules.engagement import register_engagement_rules
from audit_shared.rules.engine import RuleEngine
from audit_shared.grouping.deduplicator import GroupDeduplicator
from audit_shared.models.grouping import EvaluationScope
from audit_shared.cli import hydrate_dataset
from audit_shared.validation.finding_validator import FindingValidator

def main():
    try:
        with open("dataset_dump.json", "r") as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        print("dataset_dump.json not found.")
        sys.exit(1)
        
    dataset = hydrate_dataset(raw_data)
    
    registry = RuleRegistry()
    register_ai_discoverability_rules(registry)
    register_freshness_rules(registry)
    register_engagement_rules(registry)
    
    # 1. Measure Rule Engine Time
    t0 = time.perf_counter()
    result = RuleEngine.run(dataset, registry)
    t1 = time.perf_counter()
    rule_engine_time = t1 - t0
    
    # Analyze raw findings
    raw_findings = result.findings
    
    by_pipeline = {}
    by_severity = {}
    
    for f in raw_findings:
        p = f.pipeline.value
        s = f.severity.value
        by_pipeline[p] = by_pipeline.get(p, 0) + 1
        by_severity[s] = by_severity.get(s, 0) + 1
        
    print("--- 2. RAW FINDINGS BEFORE PHASE 8 ---")
    print(f"Total raw findings: {len(raw_findings)}")
    print(f"By pipeline: {by_pipeline}")
    print(f"By severity: {by_severity}")
    for f in raw_findings:
        print(f"  {f.id} | {f.trigger.rule_id} | {f.evidence.page} | {f.severity.name}")
        
    # 2. Measure Grouping Time and Exact Dedup
    scope = EvaluationScope(
        html_pages_crawled=dataset.crawl_stats.html_pages_crawled,
        successful_pages=dataset.crawl_stats.successful_pages,
        total_pages_evaluated=len(dataset.pages),
        is_truncated=len(dataset.unfetched_urls) > 0
    )
    
    t2 = time.perf_counter()
    deduped = GroupDeduplicator._deduplicate(raw_findings)
    dedup_count = len(raw_findings) - len(deduped)
    grouped_results = GroupDeduplicator.process(raw_findings, scope)
    t3 = time.perf_counter()
    grouping_time = t3 - t2
    
    print("\n--- 3. EXACT DEDUPLICATION ---")
    print(f"Raw findings count: {len(raw_findings)}")
    print(f"Exact duplicates removed: {dedup_count}")
    print(f"Findings remaining after deduplication: {len(deduped)}")
    
    print("\n--- 4. GROUPING RESULTS ---")
    print(f"Number of groups created: {len(grouped_results)}")
    if len(raw_findings) > 0:
        ratio = len(raw_findings) / len(grouped_results)
    else:
        ratio = 1
    print(f"Compression ratio: {ratio:.1f}x")
    
    print("\nGroup details:")
    for grp in grouped_results:
        f = grp.canonical_finding
        print(f"\nGroup ID: {grp.group_id}")
        print(f"Pipeline: {f.pipeline.name} | Rule: {f.trigger.rule_id} | Trigger: {f.trigger.type.name} | Severity: {f.severity.name}")
        print(f"Title: {f.title}")
        print(f"Affected pages: {f.evidence.pages_affected}")
        print(f"Pages checked (EvaluationScope): {f.evidence.pages_checked}")
        if f.evidence.affected_percentage:
            print(f"Affected percentage: {f.evidence.affected_percentage:.1f}%")
        print(f"Crawl partial (truncated): {scope.is_truncated}")
        print(f"Deterministic Sample ({len(f.evidence.affected_pages.sample)} items, truncated={f.evidence.affected_pages.truncated}):")
        for u in f.evidence.affected_pages.sample:
            print(f"  - {u}")
        print(f"Representative Evidence (from {f.evidence.page}): {f.evidence.field} = {f.evidence.observed_value}")
        print(f"Suggested action: {f.suggested_action.summary}")

    print("\n--- 5. VERIFY GROUPING CORRECTNESS & 6. EVIDENCE PRESERVATION ---")
    # Doing verification implicitly in code
    for grp in grouped_results:
        plines = {f.pipeline for f in grp.source_findings}
        rule_ids = {f.trigger.rule_id for f in grp.source_findings}
        severities = {f.severity for f in grp.source_findings}
        types = {f.trigger.type for f in grp.source_findings}
        
        assert len(plines) == 1, "Pipelines merged!"
        assert len(rule_ids) == 1, "Rule IDs merged!"
        assert len(severities) == 1, "Severities merged!"
        assert len(types) == 1, "Trigger types merged!"
        
        assert grp.canonical_finding.evidence.pages_affected == len(set(f.evidence.page for f in grp.source_findings)), "Affected count mismatch"
        # Ensure full source findings aren't duplicated into evidence.details
        assert "source_findings" not in grp.canonical_finding.evidence.details, "Source findings bloated canonical Evidence!"
        assert len(grp.source_finding_ids) == len(grp.source_findings), "IDs mismatch"

    print("All internal verification checks passed.")

    print("\n--- 8. VALIDATOR ---")
    all_passed = True
    for grp in grouped_results:
        errors = FindingValidator.validate(grp.canonical_finding, dataset)
        if errors:
            all_passed = False
            print(f"Validator: FAIL for {grp.group_id}")
            for e in errors:
                print(f"  - {e}")
        else:
            print(f"Validator: PASS for {grp.group_id}")
            
    print("\n--- 10. PERFORMANCE ---")
    print(f"Crawl duration: {dataset.crawl_stats.crawl_duration:.2f}s")
    print(f"Rule Engine time: {rule_engine_time:.4f}s")
    print(f"Phase 8 Grouping/Dedup time: {grouping_time:.4f}s")

if __name__ == "__main__":
    main()
