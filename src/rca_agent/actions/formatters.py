"""Report formatters for various output formats."""

from jinja2 import Template

from rca_agent.models.reports import RCAReport, Severity

MARKDOWN_TEMPLATE = """# 🔍 RCA Report: {{ report.dag_id }}/{{ report.task_id }}

**Report ID:** `{{ report.report_id }}`
**Generated:** {{ report.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC') }}

---

## Summary

| Field | Value |
|-------|-------|
| **DAG** | {{ report.dag_id }} |
| **Task** | {{ report.task_id }} |
| **Run ID** | {{ report.run_id }} |
| **Failure Time** | {{ report.failure_time.strftime('%Y-%m-%d %H:%M:%S UTC') }} |
| **Category** | {{ report.error_category.value }} |
| **Severity** | {{ severity_badge }} |
| **Confidence** | {{ "%.0f"|format(report.confidence * 100) }}% |

---

## Root Cause

{{ report.root_cause }}

{% if report.evidence %}
### Evidence

{% for e in report.evidence %}
- {{ e }}
{% endfor %}
{% endif %}

{% if report.key_log_lines %}
### Key Log Lines

```
{% for line in report.key_log_lines[:10] %}
{{ line }}
{% endfor %}
```
{% endif %}

{% if report.contributing_factors %}
### Contributing Factors

{% for factor in report.contributing_factors %}
- {{ factor }}
{% endfor %}
{% endif %}

{% if report.recent_changes %}
### Recent Changes

{% for change in report.recent_changes %}
- {{ change }}
{% endfor %}
{% endif %}

---

## Recommendations

{% if report.immediate_action %}
> **Immediate Action:** {{ report.immediate_action }}
{% endif %}

{% for rec in report.recommendations %}
{{ loop.index }}. **{{ rec.action }}**
   - Priority: {{ rec.priority }}/5
   {% if rec.estimated_effort %}- Effort: {{ rec.estimated_effort }}{% endif %}
   {% if rec.automated %}- ✅ Can be automated{% endif %}

{% endfor %}

{% if report.similar_incidents %}
---

## Similar Past Incidents

| Date | DAG/Task | Root Cause | Resolution |
|------|----------|------------|------------|
{% for incident in report.similar_incidents[:5] %}
| {{ incident.date.strftime('%Y-%m-%d') }} | {{ incident.dag_id }}/{{ incident.task_id }} | {{ incident.root_cause[:50] }}... | {{ incident.resolution or 'N/A' }} |
{% endfor %}

{% if report.is_recurring %}
**This appears to be a recurring issue** ({{ report.recurrence_count }} similar incidents)
{% endif %}
{% endif %}

---

## Metadata

- **Analysis Duration:** {{ report.analysis_duration_ms or 'N/A' }}ms
- **LLM Model:** {{ report.llm_model or 'N/A' }}
- **Collectors Used:** {{ report.collectors_used|join(', ') }}
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>RCA Report - {{ report.dag_id }}/{{ report.task_id }}</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; }
        h1 { color: #1a1a1a; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; }
        h2 { color: #333; margin-top: 30px; }
        .summary-table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        .summary-table th, .summary-table td { padding: 10px; text-align: left; border-bottom: 1px solid #e0e0e0; }
        .summary-table th { background: #f5f5f5; width: 150px; }
        .severity-critical { background: #fee2e2; color: #dc2626; padding: 4px 8px; border-radius: 4px; }
        .severity-high { background: #ffedd5; color: #ea580c; padding: 4px 8px; border-radius: 4px; }
        .severity-medium { background: #fef3c7; color: #d97706; padding: 4px 8px; border-radius: 4px; }
        .severity-low { background: #dcfce7; color: #16a34a; padding: 4px 8px; border-radius: 4px; }
        .root-cause { background: #f8fafc; padding: 20px; border-radius: 8px; border-left: 4px solid #3b82f6; }
        .evidence { background: #fefce8; padding: 15px; border-radius: 8px; margin: 10px 0; }
        .log-lines { background: #1e293b; color: #e2e8f0; padding: 15px; border-radius: 8px; font-family: monospace; font-size: 12px; overflow-x: auto; }
        .immediate-action { background: #fef2f2; border: 1px solid #fecaca; padding: 15px; border-radius: 8px; margin: 15px 0; }
        .recommendation { background: #f0f9ff; padding: 15px; border-radius: 8px; margin: 10px 0; }
        ul { padding-left: 20px; }
        li { margin: 5px 0; }
    </style>
</head>
<body>
    <h1>RCA Report</h1>
    <p><strong>{{ report.dag_id }}/{{ report.task_id }}</strong></p>

    <h2>Summary</h2>
    <table class="summary-table">
        <tr><th>Report ID</th><td><code>{{ report.report_id }}</code></td></tr>
        <tr><th>Failure Time</th><td>{{ report.failure_time.strftime('%Y-%m-%d %H:%M:%S UTC') }}</td></tr>
        <tr><th>Category</th><td>{{ report.error_category.value }}</td></tr>
        <tr><th>Severity</th><td><span class="severity-{{ report.severity.value }}">{{ report.severity.value.upper() }}</span></td></tr>
        <tr><th>Confidence</th><td>{{ "%.0f"|format(report.confidence * 100) }}%</td></tr>
    </table>

    <h2>Root Cause</h2>
    <div class="root-cause">
        <p>{{ report.root_cause }}</p>
    </div>

    {% if report.evidence %}
    <h2>Evidence</h2>
    <div class="evidence">
        <ul>
        {% for e in report.evidence %}
            <li>{{ e }}</li>
        {% endfor %}
        </ul>
    </div>
    {% endif %}

    {% if report.key_log_lines %}
    <h2>Key Log Lines</h2>
    <div class="log-lines">
        {% for line in report.key_log_lines[:10] %}
        {{ line }}<br>
        {% endfor %}
    </div>
    {% endif %}

    <h2>Recommendations</h2>

    {% if report.immediate_action %}
    <div class="immediate-action">
        <strong>Immediate Action:</strong> {{ report.immediate_action }}
    </div>
    {% endif %}

    {% for rec in report.recommendations %}
    <div class="recommendation">
        <strong>{{ loop.index }}. {{ rec.action }}</strong>
        <ul>
            <li>Priority: {{ rec.priority }}/5</li>
            {% if rec.estimated_effort %}<li>Estimated Effort: {{ rec.estimated_effort }}</li>{% endif %}
        </ul>
    </div>
    {% endfor %}

    <hr>
    <p style="color: #666; font-size: 12px;">
        Generated at {{ report.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC') }} |
        Model: {{ report.llm_model or 'N/A' }} |
        Duration: {{ report.analysis_duration_ms or 'N/A' }}ms
    </p>
</body>
</html>
"""


class ReportFormatter:
    """Format RCA reports into various output formats."""

    @staticmethod
    def _get_severity_badge(severity: Severity) -> str:
        """Get emoji badge for severity."""
        badges = {
            Severity.CRITICAL: "🔴 CRITICAL",
            Severity.HIGH: "🟠 HIGH",
            Severity.MEDIUM: "🟡 MEDIUM",
            Severity.LOW: "🟢 LOW",
        }
        return badges.get(severity, severity.value)

    @classmethod
    def to_markdown(cls, report: RCAReport) -> str:
        """Format report as Markdown.

        Args:
            report: RCA report

        Returns:
            Markdown string
        """
        template = Template(MARKDOWN_TEMPLATE)
        return template.render(
            report=report,
            severity_badge=cls._get_severity_badge(report.severity),
        )

    @classmethod
    def to_html(cls, report: RCAReport) -> str:
        """Format report as HTML.

        Args:
            report: RCA report

        Returns:
            HTML string
        """
        template = Template(HTML_TEMPLATE)
        return template.render(report=report)

    @classmethod
    def to_json(cls, report: RCAReport) -> str:
        """Format report as JSON.

        Args:
            report: RCA report

        Returns:
            JSON string
        """
        return report.model_dump_json(indent=2)
