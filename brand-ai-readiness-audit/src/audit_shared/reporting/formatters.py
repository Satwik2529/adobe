from typing import List, Optional
import json
import re
from audit_shared.reporting.models import FinalReport
from audit_shared.models.finding import Finding

class MarkdownFormatter:
    @classmethod
    def generate(cls, report: FinalReport) -> str:
        lines = []
        lines.append(f"# AI Readiness Audit Report: {cls._escape(report.site)}")
        lines.append(f"**Score:** {report.summary.score}/100")
        lines.append(f"**Pages evaluated:** {report.crawl.pages_evaluated}")
        lines.append(f"**Crawl status:** {cls._escape(report.crawl.status)}")
        lines.append("")
        
        # Group by Pipeline
        pipelines = {}
        for f in report.findings:
            p_val = f.pipeline.value
            if p_val not in pipelines:
                pipelines[p_val] = []
            pipelines[p_val].append(f)
            
        pipeline_names = {
            "ai_discoverability": "AI Discoverability",
            "freshness": "Freshness",
            "engagement": "On-site Engagement"
        }
        
        for p_val in ["ai_discoverability", "freshness", "engagement"]:
            if p_val in pipelines:
                lines.append(f"## {pipeline_names.get(p_val, p_val.title())}")
                lines.append("")
                
                for finding in pipelines[p_val]:
                    lines.extend(cls._format_finding(finding))
                    
        # Add Validation diagnostics
        lines.append("## Audit Validation Summary")
        lines.append(f"- Findings evaluated: {report.diagnostics.findings_evaluated}")
        lines.append(f"- Evidence-valid findings: {report.diagnostics.evidence_valid_findings}")
        lines.append(f"- Findings excluded during evidence validation: {report.diagnostics.excluded_during_validation}")
        lines.append("")
        
        return "\n".join(lines)
        
    @classmethod
    def _format_finding(cls, f: Finding) -> List[str]:
        lines = []
        lines.append(f"### {cls._escape(f.title)}")
        lines.append(f"**Severity:** {f.severity.value.title()}")
        
        # Affected count
        if f.evidence and f.evidence.affected_pages:
            total_eval = f.evidence.pages_checked or 0
            lines.append(f"**Affected:** {f.evidence.affected_pages.count} of {total_eval} evaluated pages")
        
        lines.append("")
        
        # Problem & Action
        if f.suggested_action:
            lines.append(f"**Problem:** {cls._escape(f.suggested_action.summary)}")
            # For simplicity, if we have a static text for problem we use suggested_action summary as placeholder for action, wait no
            # The prompt says: 
            # Problem: <text>
            # Why it matters: ...
            # Suggested action: <text>
            # Actually, `suggested_action.summary` is exactly the "Suggested action" in our schema. 
            # We don't have a "Problem" or "Why it matters" explicitly outside of `title` or `evidence.details`.
            # We will use title for problem if needed, or omit.
            lines.append(f"**Suggested action:** {cls._escape(f.suggested_action.summary)}")
        lines.append("")
        
        # Evidence block
        if f.evidence:
            lines.append("**Evidence:**")
            if f.evidence.page:
                lines.append(f"- **Page:** `{cls._escape(f.evidence.page)}`")
            if f.evidence.field or f.evidence.source:
                checked = f.evidence.field or f.evidence.source
                lines.append(f"- **Checked:** {cls._escape(checked)}")
                
            if f.evidence.observed_value is not None:
                lines.append(f"- **Observed value:** {cls._escape(str(f.evidence.observed_value))}")
            if f.evidence.expected_value is not None:
                lines.append(f"- **Expected value:** {cls._escape(str(f.evidence.expected_value))}")
            if f.evidence.excerpt:
                lines.append(f"- **Excerpt:**\n  > {cls._escape(f.evidence.excerpt)}")
            if f.evidence.context:
                lines.append(f"- **Context:** {cls._escape(f.evidence.context)}")
                
        # Semantic evidence block
        if f.nlp and f.nlp.semantic_evidence:
            lines.append("**Semantic Observation:**")
            se = f.nlp.semantic_evidence
            if "apparent_topic" in se:
                lines.append(f"- **Apparent topic:** {cls._escape(se['apparent_topic'])}")
            if "content_topic" in se:
                lines.append(f"- **Content topic:** {cls._escape(se['content_topic'])}")
            if "alignment" in se:
                lines.append(f"- **Alignment:** {cls._escape(se['alignment'])}")
        
        lines.append("")
        
        # Affected pages sample
        if f.evidence and f.evidence.affected_pages:
            ap = f.evidence.affected_pages
            trunc_text = "Sample shown:" if ap.truncated else "List:"
            lines.append("**Affected pages:**")
            lines.append(f"{ap.count} pages affected. {trunc_text}")
            for s in ap.sample:
                lines.append(f"- `{cls._escape(s)}`")
                
        lines.append("")
        return lines

    @staticmethod
    def _escape(text: str) -> str:
        if text is None:
            return ""
        # Basic markdown escaping to prevent injection breaking structure
        text = str(text)
        text = text.replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace("`", "'") # Prevent backtick injection breaking code blocks
        return text

class TerminalFormatter:
    @classmethod
    def generate(cls, report: FinalReport) -> str:
        lines = []
        lines.append("Audit Complete")
        lines.append("")
        lines.append(f"Site: {report.site}")
        lines.append(f"Score: {report.summary.score}/100")
        lines.append(f"Pages evaluated: {report.crawl.pages_evaluated}")
        lines.append(f"Crawl status: {report.crawl.status}")
        lines.append("")
        lines.append(f"Findings: {report.summary.total_findings}")
        lines.append(f"High: {report.summary.high}")
        lines.append(f"Medium: {report.summary.medium}")
        lines.append(f"Low: {report.summary.low}")
        lines.append(f"Info: {report.summary.info}")
        lines.append("")
        lines.append("Reports saved to: report.json, report.md")
        return "\n".join(lines)
