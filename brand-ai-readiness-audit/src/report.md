# Audit Summary
**Score:** 10/100
**Site:** https://arngren.net/
**Audited At:** 2026-09-05T10:25:58.214021Z
**Crawl Status:** Partial (Bounded crawl)
**Pages Evaluated:** 102

## Pipeline Summary
- **AI Discoverability:** 7 findings
- **Freshness:** 0 findings
- **On-site Engagement:** 1 findings

## Crawl Scope
**Configured bounds:** Max depth 3, Max pages 100
**Actual crawl metrics:**
- URLs discovered: 228
- Requests attempted: 104
- HTML pages crawled: 102
- Robots blocked: 0
- Crawl duration: 11.94s
**Termination reason:** closespider_pagecount
**Completeness:** Partial (Bounded crawl)

## Findings

### Broken Internal Link(s)
**Problem:** Broken Internal Link(s)
**Severity:** High
**Affected Pages:** 15 of 102 evaluated pages. Sample:
- `http://www.arngren.net/elbil-barn-volvo.html`
- `http://www.arngren.net/elektrisk-atv-polaris.html`
- `http://www.arngren.net/henes-broon.html`
- `https://arngren.net/`
- `https://arngren.net/elbil-barn-gaucho.html`
- `https://arngren.net/elbil-barn-mercedes.html`
- `https://arngren.net/elbil-barn-volvo.html`
- `https://arngren.net/elbil-liten.html`
- `https://arngren.net/elektrisk-atv-polaris.html`
- `https://arngren.net/elmoped-bil-200.html`
**Why It Matters:** This matters (MOCK) because it affects how search engines and users interact with the page.
**Evidence:**
- **Page:** `http://www.arngren.net/elbil-barn-volvo.html`
- **Checked:** internal_links
- **Observed value:** http://www.arngren.net/elbil-barn-volvo
**Suggested Action:** Remove or update broken links.
**GenAI Explanation:** This is a mock GenAI explanation. The finding indicates an issue with the provided rule trigger.
**GenAI Solution:** Mock solution: Review the affected pages and apply the suggested action.

### Client Error (4xx)
**Problem:** Client Error (4xx)
**Severity:** High
**Affected Pages:** 6 of 102 evaluated pages. Sample:
- `http://www.arngren.net/elbil-barn-rover`
- `http://www.arngren.net/elbil-barn-volvo`
- `http://www.arngren.net/elektrisk-atv`
- `http://www.arngren.net/film`
- `http://www.arngren.net/togbane-dampmaskin`
- `http://www.arngren.net/utv-2`
**Why It Matters:** This matters (MOCK) because it affects how search engines and users interact with the page.
**Evidence:**
- **Page:** `http://www.arngren.net/elbil-barn-rover`
- **Checked:** status_code
- **Observed value:** 404
**Suggested Action:** Fix broken page or remove links to it.
**GenAI Explanation:** This is a mock GenAI explanation. The finding indicates an issue with the provided rule trigger.
**GenAI Solution:** Mock solution: Review the affected pages and apply the suggested action.

### Exact Duplicate Content
**Problem:** Exact Duplicate Content
**Severity:** Medium
**Affected Pages:** 7 of 102 evaluated pages. Sample:
- `http://www.arngren.net/conrad.html`
- `http://www.arngren.net/elbil-barn-flest-1.html`
- `http://www.arngren.net/elbil-barn-volvo.html`
- `http://www.arngren.net/elektrisk-atv-polaris.html`
- `http://www.arngren.net/elscooter.html`
- `http://www.arngren.net/henes-broon.html`
- `https://arngren.net/`
**Why It Matters:** This matters (MOCK) because it affects how search engines and users interact with the page.
**Evidence:**
- **Page:** `http://www.arngren.net/conrad.html`
- **Checked:** visible_text
- **Observed value:** Exact duplicate across 2 pages
**Suggested Action:** Consolidate pages or use canonical tags.
**GenAI Explanation:** This is a mock GenAI explanation. The finding indicates an issue with the provided rule trigger.
**GenAI Solution:** Mock solution: Review the affected pages and apply the suggested action.

### Missing Canonical
**Problem:** Missing Canonical
**Severity:** Medium
**Affected Pages:** 96 of 102 evaluated pages. Sample:
- `http://www.arngren.net/3dprinter.html`
- `http://www.arngren.net/4ch.html`
- `http://www.arngren.net/F1-1.html`
- `http://www.arngren.net/F1-1B.html`
- `http://www.arngren.net/F1-2.html`
- `http://www.arngren.net/F1-3.html`
- `http://www.arngren.net/F1-4.html`
- `http://www.arngren.net/Fjernkontroll-TV.html`
- `http://www.arngren.net/Lykt-stor.html`
- `http://www.arngren.net/akvarium.html`
**Why It Matters:** This matters (MOCK) because it affects how search engines and users interact with the page.
**Evidence:**
- **Page:** `http://www.arngren.net/3dprinter.html`
- **Checked:** canonical
- **Observed value:** No canonical tag found
**Suggested Action:** Add a canonical tag.
**GenAI Explanation:** This is a mock GenAI explanation. The finding indicates an issue with canonical tags, which tell search engines the preferred URL.
**GenAI Solution:** Mock solution: Add or correct the rel="canonical" link.

### Missing H1
**Problem:** Missing H1
**Severity:** Medium
**Affected Pages:** 96 of 102 evaluated pages. Sample:
- `http://www.arngren.net/3dprinter.html`
- `http://www.arngren.net/4ch.html`
- `http://www.arngren.net/F1-1.html`
- `http://www.arngren.net/F1-1B.html`
- `http://www.arngren.net/F1-2.html`
- `http://www.arngren.net/F1-3.html`
- `http://www.arngren.net/F1-4.html`
- `http://www.arngren.net/Fjernkontroll-TV.html`
- `http://www.arngren.net/Lykt-stor.html`
- `http://www.arngren.net/akvarium.html`
**Why It Matters:** This matters (MOCK) because it affects how search engines and users interact with the page.
**Evidence:**
- **Page:** `http://www.arngren.net/3dprinter.html`
- **Checked:** h1s
- **Observed value:** 0 H1 tags found
**Suggested Action:** Add an H1 tag to describe the page's main topic.
**GenAI Explanation:** This is a mock GenAI explanation. The finding indicates an issue with the primary heading (H1), which is crucial for topic discoverability.
**GenAI Solution:** Mock solution: Ensure every page has exactly one descriptive H1.

### Missing Meta Description
**Problem:** Missing Meta Description
**Severity:** Low
**Affected Pages:** 71 of 102 evaluated pages. Sample:
- `http://www.arngren.net/3dprinter.html`
- `http://www.arngren.net/4ch.html`
- `http://www.arngren.net/F1-1.html`
- `http://www.arngren.net/F1-1B.html`
- `http://www.arngren.net/F1-2.html`
- `http://www.arngren.net/F1-3.html`
- `http://www.arngren.net/F1-4.html`
- `http://www.arngren.net/Fjernkontroll-TV.html`
- `http://www.arngren.net/Lykt-stor.html`
- `http://www.arngren.net/apache-fly.html`
**Why It Matters:** This matters (MOCK) because it affects how search engines and users interact with the page.
**Evidence:**
- **Page:** `http://www.arngren.net/3dprinter.html`
- **Checked:** meta_description
- **Observed value:** None or empty
**Suggested Action:** Consider adding a meta description.
**GenAI Explanation:** This is a mock GenAI explanation. The finding indicates an issue with the provided rule trigger.
**GenAI Solution:** Mock solution: Review the affected pages and apply the suggested action.

### Thin Content
**Problem:** Thin Content
**Severity:** Low
**Affected Pages:** 10 of 102 evaluated pages. Sample:
- `http://www.arngren.net/F1-1.html`
- `http://www.arngren.net/F1-1B.html`
- `http://www.arngren.net/F1-2.html`
- `http://www.arngren.net/F1-3.html`
- `http://www.arngren.net/F1-4.html`
- `http://www.arngren.net/apache2.html`
- `http://www.arngren.net/atv-bensin-1.html`
- `http://www.arngren.net/bil2.html`
- `http://www.arngren.net/conrad.html`
- `http://www.arngren.net/globus.html`
**Why It Matters:** This matters (MOCK) because it affects how search engines and users interact with the page.
**Evidence:**
- **Page:** `http://www.arngren.net/F1-1.html`
- **Checked:** visible_text_length
- **Observed value:** 31
**Suggested Action:** Review to ensure page has enough context to be discoverable.
**GenAI Explanation:** This is a mock GenAI explanation. The finding indicates an issue with the provided rule trigger.
**GenAI Solution:** Mock solution: Review the affected pages and apply the suggested action.

### Missing Image Alt Text
**Problem:** Missing Image Alt Text
**Severity:** Medium
**Affected Pages:** 96 of 102 evaluated pages. Sample:
- `http://www.arngren.net/3dprinter.html`
- `http://www.arngren.net/4ch.html`
- `http://www.arngren.net/F1-1.html`
- `http://www.arngren.net/F1-1B.html`
- `http://www.arngren.net/F1-2.html`
- `http://www.arngren.net/F1-3.html`
- `http://www.arngren.net/F1-4.html`
- `http://www.arngren.net/Fjernkontroll-TV.html`
- `http://www.arngren.net/Lykt-stor.html`
- `http://www.arngren.net/akvarium.html`
**Evidence:**
- **Page:** `http://www.arngren.net/3dprinter.html`
**Suggested Action:** Images are missing alternative text.

## Diagnostics
### NLP
NLP diagnostics completed.

### GenAI
Eligible groups: 7
Successful: 7
Total time: 0.03s

### Stage Timing
- Crawling: 12.58s
- Rule engines: 0.03s
- Grouping: 0.01s
- Evidence validation: 0.00s
- NLP: 0.00s
- GenAI: 0.03s
- Reporting: 0.01s
- Total: 12.65s

### Crawl Diagnostics
Findings evaluated: 8
Evidence-valid findings: 8
Findings excluded during validation: 0

## Final Assessment
The site requires urgent technical optimization to be properly discovered and understood by AI platforms.
