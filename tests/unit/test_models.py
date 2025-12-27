"""Tests for Pydantic models."""

from datetime import datetime

import pytest

from rca_agent.models import (
    ErrorCategory,
    FailureEvent,
    RCAContext,
    RCAReport,
    Recommendation,
    Severity,
    TaskLogs,
    TaskMetadata,
    TaskState,
    WebhookPayload,
)


class TestFailureEvent:
    """Tests for FailureEvent model."""

    def test_create_minimal(self) -> None:
        """Test creating event with minimal fields."""
        event = FailureEvent(
            dag_id="test_dag",
            task_id="test_task",
            run_id="run_001",
        )
        assert event.dag_id == "test_dag"
        assert event.state == TaskState.FAILED
        assert event.try_number == 1

    def test_create_full(self) -> None:
        """Test creating event with all fields."""
        event = FailureEvent(
            dag_id="test_dag",
            task_id="test_task",
            run_id="run_001",
            execution_date=datetime(2024, 1, 15),
            state=TaskState.UPSTREAM_FAILED,
            error_message="Test error",
            try_number=2,
        )
        assert event.state == TaskState.UPSTREAM_FAILED
        assert event.error_message == "Test error"
        assert event.try_number == 2

    def test_immutable(self) -> None:
        """Test that FailureEvent is immutable."""
        event = FailureEvent(
            dag_id="test_dag",
            task_id="test_task",
            run_id="run_001",
        )
        with pytest.raises(Exception):
            event.dag_id = "modified"  # type: ignore


class TestWebhookPayload:
    """Tests for WebhookPayload model."""

    def test_to_failure_event(self) -> None:
        """Test converting webhook payload to FailureEvent."""
        payload = WebhookPayload(
            dag_id="test_dag",
            task_id="test_task",
            run_id="run_001",
            execution_date="2024-01-15T10:00:00+00:00",
            state="failed",
            try_number=1,
            exception="Test error",
        )

        event = payload.to_failure_event()

        assert event.dag_id == "test_dag"
        assert event.error_message == "Test error"
        assert event.execution_date is not None


class TestRCAContext:
    """Tests for RCAContext model."""

    def test_to_prompt_context(
        self,
        sample_rca_context: RCAContext,
    ) -> None:
        """Test generating prompt context string."""
        prompt = sample_rca_context.to_prompt_context()

        assert "etl_sales_daily" in prompt
        assert "load_to_warehouse" in prompt
        assert "OutOfMemoryError" in prompt
        assert "## Failed Task" in prompt
        assert "## Error Logs" in prompt

    def test_minimal_context(self) -> None:
        """Test context with minimal data."""
        context = RCAContext(
            task=TaskMetadata(
                dag_id="test",
                task_id="task",
                run_id="run",
                state="failed",
            ),
            logs=TaskLogs(stdout="Test log"),
        )
        prompt = context.to_prompt_context()

        assert "test" in prompt


class TestRCAReport:
    """Tests for RCAReport model."""

    @pytest.fixture
    def sample_report(self) -> RCAReport:
        """Create a sample RCA report."""
        return RCAReport(
            report_id="test-001",
            dag_id="etl_sales",
            task_id="load_warehouse",
            run_id="run_001",
            failure_time=datetime(2024, 1, 15, 10, 0, 0),
            error_category=ErrorCategory.RESOURCE_EXHAUSTION,
            severity=Severity.HIGH,
            root_cause="Memory exhaustion during join operation",
            root_cause_summary="OOM during join",
            confidence=0.85,
            evidence=["Java heap space error", "Memory usage spike"],
            recommendations=[
                Recommendation(
                    action="Increase executor memory",
                    priority=1,
                    estimated_effort="5 minutes",
                )
            ],
        )

    def test_to_slack_message(self, sample_report: RCAReport) -> None:
        """Test generating Slack message."""
        message = sample_report.to_slack_message()

        assert "blocks" in message
        assert len(message["blocks"]) > 0

    def test_to_summary(self, sample_report: RCAReport) -> None:
        """Test generating text summary."""
        summary = sample_report.to_summary()

        assert "HIGH" in summary
        assert "etl_sales" in summary
        assert "85%" in summary

    def test_severity_values(self) -> None:
        """Test all severity values."""
        for severity in Severity:
            assert severity.value in ["critical", "high", "medium", "low"]

    def test_error_category_values(self) -> None:
        """Test all error category values."""
        categories = [
            ErrorCategory.RESOURCE_EXHAUSTION,
            ErrorCategory.SCHEMA_MISMATCH,
            ErrorCategory.SOURCE_UNAVAILABLE,
            ErrorCategory.DATA_QUALITY,
            ErrorCategory.PERMISSION_ERROR,
            ErrorCategory.CODE_REGRESSION,
            ErrorCategory.VOLUME_ANOMALY,
            ErrorCategory.NETWORK_ERROR,
            ErrorCategory.CONFIGURATION_ERROR,
            ErrorCategory.UNKNOWN,
        ]
        assert len(categories) == 10
