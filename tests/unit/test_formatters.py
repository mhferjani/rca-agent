"""Tests for report formatters."""

from datetime import datetime

import pytest

from rca_agent.actions.formatters import ReportFormatter
from rca_agent.models import ErrorCategory, RCAReport, Recommendation, Severity


@pytest.fixture
def sample_report() -> RCAReport:
    """Create a sample report for testing."""
    return RCAReport(
        report_id="test-001",
        dag_id="etl_sales",
        task_id="load_warehouse",
        run_id="run_001",
        failure_time=datetime(2024, 1, 15, 10, 0, 0),
        error_category=ErrorCategory.RESOURCE_EXHAUSTION,
        severity=Severity.HIGH,
        root_cause="Memory exhaustion during large join operation due to increased data volume",
        root_cause_summary="OOM during join - data volume increased 180%",
        confidence=0.85,
        evidence=[
            "Java heap space error in logs",
            "Input data volume increased 180%",
            "Memory usage peaked at 95%",
        ],
        key_log_lines=[
            "[10:28:00] ERROR: java.lang.OutOfMemoryError: Java heap space",
            "[10:27:59] WARNING: Memory usage at 95%",
        ],
        recommendations=[
            Recommendation(
                action="Increase executor memory to 8GB",
                priority=1,
                estimated_effort="5 minutes",
                automated=False,
            ),
            Recommendation(
                action="Add repartition before join",
                priority=2,
                estimated_effort="30 minutes",
                automated=False,
            ),
        ],
        immediate_action="Increase executor memory to 8GB and retry",
        analysis_duration_ms=1500,
        llm_model="claude-sonnet-4-20250514",
        collectors_used=["airflow", "git", "source_health"],
    )


class TestReportFormatter:
    """Tests for ReportFormatter class."""

    def test_to_markdown(self, sample_report: RCAReport) -> None:
        """Test markdown formatting."""
        markdown = ReportFormatter.to_markdown(sample_report)

        assert "# 🔍 RCA Report" in markdown
        assert "etl_sales" in markdown
        assert "load_warehouse" in markdown
        assert "resource_exhaustion" in markdown
        assert "HIGH" in markdown
        assert "85%" in markdown
        assert "Increase executor memory" in markdown

    def test_to_html(self, sample_report: RCAReport) -> None:
        """Test HTML formatting."""
        html = ReportFormatter.to_html(sample_report)

        assert "<!DOCTYPE html>" in html
        assert "<title>RCA Report" in html
        assert "etl_sales" in html
        assert "Memory exhaustion" in html

    def test_to_json(self, sample_report: RCAReport) -> None:
        """Test JSON formatting."""
        import json

        json_str = ReportFormatter.to_json(sample_report)
        data = json.loads(json_str)

        assert data["report_id"] == "test-001"
        assert data["dag_id"] == "etl_sales"
        assert data["confidence"] == 0.85
        assert len(data["recommendations"]) == 2

    def test_severity_badge(self) -> None:
        """Test severity badge generation."""
        badges = {
            Severity.CRITICAL: "🔴 CRITICAL",
            Severity.HIGH: "🟠 HIGH",
            Severity.MEDIUM: "🟡 MEDIUM",
            Severity.LOW: "🟢 LOW",
        }

        for severity, expected in badges.items():
            badge = ReportFormatter._get_severity_badge(severity)
            assert badge == expected
