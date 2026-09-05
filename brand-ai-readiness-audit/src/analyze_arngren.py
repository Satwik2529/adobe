import json

def analyze():
    with open('report.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    print("=== 2. CRAWL DIAGNOSTICS ===")
    print("Crawl metrics:")
    for k, v in data['crawl'].items():
        print(f"  {k}: {v}")
    print("Evaluation scope:")
    for k, v in data['evaluation_scope'].items():
        print(f"  {k}: {v}")
        
    print("\n=== 3. CRAWLDATASET INSPECTION ===")
    # Unfortunately dataset is not in report.json, only findings.
    # We will need to load the dataset differently if we want to see it,
    # but I can run another script for dataset inspection. Let's do that next.
    
    print("\n=== 4. AI DISCOVERABILITY ===")
    disc_findings = [f for f in data['findings'] if f['pipeline'] == 'ai_discoverability']
    print(f"Total grouped findings: {len(disc_findings)}")
    for f in disc_findings:
        print(f"- {f['trigger']['rule_id']}: {f['title']} ({f['severity'].upper()}), Affected: {f['evidence'].get('pages_affected')}")
        print(f"  Evidence field: {f['evidence'].get('field')}, value: {f['evidence'].get('observed_value')}")
        
    print("\n=== 5. FRESHNESS ===")
    fresh_findings = [f for f in data['findings'] if f['pipeline'] == 'freshness']
    print(f"Total freshness findings: {len(fresh_findings)}")
    
    print("\n=== 6. ENGAGEMENT ===")
    eng_findings = [f for f in data['findings'] if f['pipeline'] == 'engagement']
    print(f"Total engagement findings: {len(eng_findings)}")
    for f in eng_findings:
        print(f"- {f['title']} ({f['severity'].upper()}), Affected: {f['evidence'].get('pages_affected')}")

    print("\n=== 7. NLP / SEMANTIC ANALYSIS ===")
    # Report contains NLP findings if any. But we need to see gating.
    # Gating info is not in report.json. We need to inspect the script run.
    # The prompt asks for EXACT values for candidates, eligible candidates, etc.
    
    print("\n=== 8. GENAI ===")
    if 'genai_diagnostics' in data.get('diagnostics', {}):
        for k, v in data['diagnostics']['genai_diagnostics'].items():
            print(f"  {k}: {v}")
    
    # We'll print a sample genai output
    if data['findings']:
        print("Sample GenAI context:")
        g = data['findings'][0].get('genai', {})
        print(f"  Used: {g.get('used')}")
        print(f"  Explanation: {g.get('explanation')}")
        print(f"  Why it matters: {g.get('why_it_matters')}")
        print(f"  Solution: {g.get('possible_solution')}")
        
    print("\n=== 10. CONSISTENCY ===")
    print(f"JSON findings count: {len(data['findings'])}")
    print(f"JSON High: {data['summary']['severity_counts']['high']}")
    print(f"JSON Medium: {data['summary']['severity_counts']['medium']}")
    print(f"JSON Low: {data['summary']['severity_counts']['low']}")

if __name__ == "__main__":
    analyze()
