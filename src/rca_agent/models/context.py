"""Context models for RCA analysis."""

from datetime import datetime

from pydantic import BaseModel, Field


class TaskLogs(BaseModel):
    """Logs extracted from a failed task."""

    stdout: str = Field(default="", description="Standard output logs")
    stderr: str | None = Field(default=None, description="Standard error logs")
    log_lines: int = Field(default=0, description="Total number of log lines")
    truncated: bool = Field(default=False, description="Whether logs were truncated")
    error_snippet: str | None = Field(default=None, description="Extracted error message snippet")


class TaskMetadata(BaseModel):
    """Metadata about the failed task."""

    dag_id: str
    task_id: str
    run_id: str
    state: str
    start_date: datetime | None = None
    end_date: datetime | None = None
    duration_seconds: float | None = None
    try_number: int = 1
    max_tries: int = 1
    operator: str | None = Field(default=None, description="Airflow operator type")
    pool: str | None = Field(default=None, description="Airflow pool name")
    queue: str | None = Field(default=None, description="Celery queue name")


class DAGHistory(BaseModel):
    """Historical information about the DAG."""

    last_success: datetime | None = Field(default=None, description="Last successful run")
    last_failure: datetime | None = Field(
        default=None, description="Last failed run before this one"
    )
    recent_runs: list[dict] = Field(
        default_factory=list,
        description="Recent runs with state and duration",
    )
    avg_duration_seconds: float | None = Field(
        default=None, description="Average successful run duration"
    )
    failure_rate_7d: float = Field(default=0.0, description="Failure rate in last 7 days")
    total_runs_7d: int = Field(default=0, description="Total runs in last 7 days")


class GitCommit(BaseModel):
    """Git commit information."""

    sha: str
    short_sha: str
    author: str
    email: str
    message: str
    date: datetime
    files_changed: list[str] = Field(default_factory=list)


class GitContext(BaseModel):
    """Git repository context."""

    recent_commits: list[GitCommit] = Field(default_factory=list, description="Recent commits")
    last_commit_touching_dag: GitCommit | None = Field(
        default=None, description="Most recent commit touching the DAG file"
    )
    dag_file_path: str | None = Field(default=None, description="Path to the DAG file")
    hours_since_last_change: float | None = Field(
        default=None, description="Hours since last change to DAG"
    )


class SourceHealth(BaseModel):
    """Health check result for a data source."""

    source_name: str
    source_type: str = Field(
        default="unknown",
        description="Type: api, database, file, etc.",
    )
    reachable: bool = True
    latency_ms: float | None = None
    error_message: str | None = None
    row_count: int | None = Field(default=None, description="Current row count if applicable")
    row_count_previous: int | None = Field(
        default=None, description="Previous row count for comparison"
    )
    row_count_delta_pct: float | None = Field(
        default=None, description="Percentage change in row count"
    )
    schema_changed: bool = False
    last_checked: datetime = Field(default_factory=datetime.utcnow)


class MetricsSnapshot(BaseModel):
    """Infrastructure metrics at failure time."""

    timestamp: datetime
    cpu_percent: float | None = None
    memory_percent: float | None = None
    memory_used_gb: float | None = None
    disk_percent: float | None = None
    active_connections: int | None = None
    worker_slots_available: int | None = None


class RCAContext(BaseModel):
    """Complete context aggregated for RCA analysis."""

    failure_time: datetime = Field(default_factory=datetime.utcnow)
    task: TaskMetadata
    logs: TaskLogs
    dag_history: DAGHistory = Field(default_factory=DAGHistory)
    git: GitContext | None = None
    sources: list[SourceHealth] = Field(default_factory=list)
    metrics: MetricsSnapshot | None = None

    def to_prompt_context(self) -> str:
        """Format context as structured text for LLM prompt."""
        sections = []

        # Task info
        sections.append(f"""## Failed Task
- DAG: {self.task.dag_id}
- Task: {self.task.task_id}
- State: {self.task.state}
- Try: {self.task.try_number}/{self.task.max_tries}
- Duration: {self.task.duration_seconds or "N/A"}s
- Operator: {self.task.operator or "unknown"}""")

        # Logs
        log_content = self.logs.error_snippet or self.logs.stdout[-2000:]
        sections.append(f"""## Error Logs
```
{log_content}
```""")

        # DAG History
        if self.dag_history.recent_runs:
            runs_summary = ", ".join(
                f"{r.get('state', 'unknown')}" for r in self.dag_history.recent_runs[:5]
            )
            sections.append(f"""## DAG History
- Last success: {self.dag_history.last_success or "Never"}
- Recent runs: [{runs_summary}]
- Failure rate (7d): {self.dag_history.failure_rate_7d:.1%}
- Avg duration: {self.dag_history.avg_duration_seconds or "N/A"}s""")

        # Git context
        if self.git and self.git.recent_commits:
            commits_text = "\n".join(
                f"  - {c.short_sha}: {c.message[:50]} ({c.author})"
                for c in self.git.recent_commits[:3]
            )
            sections.append(f"""## Recent Git Changes
{commits_text}
- Hours since last DAG change: {self.git.hours_since_last_change or "N/A"}""")

        # Source health
        if self.sources:
            sources_text = "\n".join(
                f"  - {s.source_name}: {'✓' if s.reachable else '✗'} "
                f"({s.latency_ms or 'N/A'}ms)"
                + (" [SCHEMA CHANGED]" if s.schema_changed else "")
                + (f" [Volume: {s.row_count_delta_pct:+.1f}%]" if s.row_count_delta_pct else "")
                for s in self.sources
            )
            sections.append(f"""## Source Health
{sources_text}""")

        # Metrics
        if self.metrics:
            sections.append(f"""## Infrastructure Metrics
- CPU: {self.metrics.cpu_percent or "N/A"}%
- Memory: {self.metrics.memory_percent or "N/A"}%
- Disk: {self.metrics.disk_percent or "N/A"}%""")

        return "\n\n".join(sections)
