"""Pytest configuration and fixtures."""

from datetime import datetime

import pytest

from rca_agent.models import (
    DAGHistory,
    FailureEvent,
    GitCommit,
    GitContext,
    RCAContext,
    SourceHealth,
    TaskLogs,
    TaskMetadata,
    TaskState,
)


@pytest.fixture
def sample_failure_event() -> FailureEvent:
    """Create a sample failure event for testing."""
    return FailureEvent(
        dag_id="etl_sales_daily",
        task_id="load_to_warehouse",
        run_id="scheduled__2024-01-15T00:00:00+00:00",
        state=TaskState.FAILED,
        error_message="java.lang.OutOfMemoryError: Java heap space",
        try_number=1,
        timestamp=datetime(2024, 1, 15, 10, 30, 0),
    )


@pytest.fixture
def sample_task_metadata() -> TaskMetadata:
    """Create sample task metadata."""
    return TaskMetadata(
        dag_id="etl_sales_daily",
        task_id="load_to_warehouse",
        run_id="scheduled__2024-01-15T00:00:00+00:00",
        state="failed",
        start_date=datetime(2024, 1, 15, 10, 0, 0),
        end_date=datetime(2024, 1, 15, 10, 30, 0),
        duration_seconds=1800.0,
        try_number=1,
        max_tries=3,
        operator="SparkSubmitOperator",
        pool="default_pool",
    )


@pytest.fixture
def sample_task_logs() -> TaskLogs:
    """Create sample task logs with OOM error."""
    return TaskLogs(
        stdout="""
[2024-01-15 10:00:00] Starting Spark job
[2024-01-15 10:15:00] Processing batch 1/10
[2024-01-15 10:20:00] Processing batch 5/10
[2024-01-15 10:25:00] WARNING: Memory usage high
[2024-01-15 10:28:00] ERROR: java.lang.OutOfMemoryError: Java heap space
    at java.util.Arrays.copyOf(Arrays.java:3236)
    at java.util.ArrayList.grow(ArrayList.java:265)
    at org.apache.spark.sql.execution.SparkPlan.executeQuery(SparkPlan.scala:152)
[2024-01-15 10:30:00] Task failed with exit code 137
        """,
        stderr=None,
        log_lines=10,
        truncated=False,
        error_snippet="ERROR: java.lang.OutOfMemoryError: Java heap space",
    )


@pytest.fixture
def sample_dag_history() -> DAGHistory:
    """Create sample DAG history."""
    return DAGHistory(
        last_success=datetime(2024, 1, 14, 10, 0, 0),
        last_failure=datetime(2024, 1, 10, 10, 0, 0),
        recent_runs=[
            {"state": "failed", "duration_seconds": 1800.0},
            {"state": "success", "duration_seconds": 900.0},
            {"state": "success", "duration_seconds": 850.0},
            {"state": "success", "duration_seconds": 920.0},
        ],
        avg_duration_seconds=890.0,
        failure_rate_7d=0.1,
        total_runs_7d=10,
    )


@pytest.fixture
def sample_git_context() -> GitContext:
    """Create sample Git context."""
    return GitContext(
        recent_commits=[
            GitCommit(
                sha="abc123def456",
                short_sha="abc123d",
                author="developer",
                email="dev@example.com",
                message="Increase batch size for performance",
                date=datetime(2024, 1, 15, 8, 0, 0),
                files_changed=["dags/etl_sales_daily.py"],
            ),
            GitCommit(
                sha="def456abc789",
                short_sha="def456a",
                author="developer",
                email="dev@example.com",
                message="Add new data source",
                date=datetime(2024, 1, 14, 15, 0, 0),
                files_changed=["dags/etl_sales_daily.py", "plugins/sources.py"],
            ),
        ],
        last_commit_touching_dag=GitCommit(
            sha="abc123def456",
            short_sha="abc123d",
            author="developer",
            email="dev@example.com",
            message="Increase batch size for performance",
            date=datetime(2024, 1, 15, 8, 0, 0),
            files_changed=["dags/etl_sales_daily.py"],
        ),
        dag_file_path="dags/etl_sales_daily.py",
        hours_since_last_change=2.5,
    )


@pytest.fixture
def sample_source_health() -> list[SourceHealth]:
    """Create sample source health checks."""
    return [
        SourceHealth(
            source_name="sales_api",
            source_type="api",
            reachable=True,
            latency_ms=150.0,
            row_count=50000,
            row_count_previous=25000,
            row_count_delta_pct=100.0,
            schema_changed=False,
        ),
        SourceHealth(
            source_name="postgres_warehouse",
            source_type="database",
            reachable=True,
            latency_ms=25.0,
        ),
    ]


@pytest.fixture
def sample_rca_context(
    sample_task_metadata: TaskMetadata,
    sample_task_logs: TaskLogs,
    sample_dag_history: DAGHistory,
    sample_git_context: GitContext,
    sample_source_health: list[SourceHealth],
) -> RCAContext:
    """Create a complete sample RCA context."""
    return RCAContext(
        failure_time=datetime(2024, 1, 15, 10, 30, 0),
        task=sample_task_metadata,
        logs=sample_task_logs,
        dag_history=sample_dag_history,
        git=sample_git_context,
        sources=sample_source_health,
    )
