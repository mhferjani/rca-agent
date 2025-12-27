"""Airflow API collector for task logs and metadata."""

from datetime import datetime, timedelta
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from rca_agent.collectors.base import BaseCollector
from rca_agent.models.context import DAGHistory, TaskLogs, TaskMetadata


class AirflowCollector(BaseCollector[tuple[TaskMetadata, TaskLogs, DAGHistory]]):
    """Collector for Airflow task logs and metadata via REST API."""

    name = "airflow"

    def __init__(
        self,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
        timeout: int = 30,
        enabled: bool = True,
    ) -> None:
        """Initialize Airflow collector.

        Args:
            base_url: Airflow webserver URL (e.g., http://localhost:8080)
            username: Basic auth username
            password: Basic auth password
            timeout: Request timeout in seconds
            enabled: Whether the collector is enabled
        """
        super().__init__(enabled=enabled)
        self.base_url = base_url.rstrip("/")
        self.auth = (username, password) if username and password else None
        self.timeout = timeout

    def _get_client(self) -> httpx.AsyncClient:
        """Create HTTP client with auth."""
        return httpx.AsyncClient(
            base_url=f"{self.base_url}/api/v1",
            auth=self.auth,
            timeout=self.timeout,
            headers={"Accept": "application/json"},
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _get(self, path: str, **params: Any) -> dict:
        """Make GET request to Airflow API with retry."""
        async with self._get_client() as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()

    async def get_task_logs(
        self,
        dag_id: str,
        run_id: str,
        task_id: str,
        try_number: int = 1,
    ) -> TaskLogs:
        """Fetch logs for a specific task instance.

        Args:
            dag_id: DAG identifier
            run_id: DAG run identifier
            task_id: Task identifier
            try_number: Attempt number

        Returns:
            TaskLogs object with stdout/stderr
        """
        path = f"/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}/logs/{try_number}"

        async with self._get_client() as client:
            # Logs endpoint returns plain text
            client.headers["Accept"] = "text/plain"
            response = await client.get(path)
            response.raise_for_status()
            log_content = response.text

        # Extract error snippet (last 50 lines or error section)
        lines = log_content.strip().split("\n")
        error_snippet = self._extract_error_snippet(lines)

        return TaskLogs(
            stdout=log_content,
            stderr=None,
            log_lines=len(lines),
            truncated=len(log_content) > 100_000,
            error_snippet=error_snippet,
        )

    def _extract_error_snippet(self, lines: list[str], max_lines: int = 50) -> str:
        """Extract relevant error portion from logs."""
        error_keywords = [
            "error",
            "exception",
            "traceback",
            "failed",
            "oom",
            "killed",
            "timeout",
        ]

        # Find lines containing errors
        error_indices = []
        for i, line in enumerate(lines):
            if any(kw in line.lower() for kw in error_keywords):
                error_indices.append(i)

        if error_indices:
            # Get context around first error
            start = max(0, error_indices[0] - 5)
            end = min(len(lines), error_indices[-1] + 10)
            return "\n".join(lines[start:end])

        # Fallback: last N lines
        return "\n".join(lines[-max_lines:])

    async def get_task_instance(
        self,
        dag_id: str,
        run_id: str,
        task_id: str,
    ) -> TaskMetadata:
        """Fetch task instance metadata.

        Args:
            dag_id: DAG identifier
            run_id: DAG run identifier
            task_id: Task identifier

        Returns:
            TaskMetadata object
        """
        path = f"/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}"
        data = await self._get(path)

        start_date = None
        end_date = None
        duration = None

        if data.get("start_date"):
            start_date = datetime.fromisoformat(data["start_date"].replace("Z", "+00:00"))
        if data.get("end_date"):
            end_date = datetime.fromisoformat(data["end_date"].replace("Z", "+00:00"))
        if start_date and end_date:
            duration = (end_date - start_date).total_seconds()

        return TaskMetadata(
            dag_id=dag_id,
            task_id=task_id,
            run_id=run_id,
            state=data.get("state", "unknown"),
            start_date=start_date,
            end_date=end_date,
            duration_seconds=duration,
            try_number=data.get("try_number", 1),
            max_tries=data.get("max_tries", 1),
            operator=data.get("operator"),
            pool=data.get("pool"),
            queue=data.get("queue"),
        )

    async def get_dag_history(
        self,
        dag_id: str,
        limit: int = 20,
    ) -> DAGHistory:
        """Fetch DAG run history.

        Args:
            dag_id: DAG identifier
            limit: Maximum number of runs to fetch

        Returns:
            DAGHistory object with statistics
        """
        path = f"/dags/{dag_id}/dagRuns"
        data = await self._get(path, limit=limit, order_by="-execution_date")

        runs = data.get("dag_runs", [])

        recent_runs = []
        last_success = None
        last_failure = None
        successful_durations = []
        failures_7d = 0
        total_7d = 0
        cutoff_7d = datetime.utcnow() - timedelta(days=7)

        for run in runs:
            state = run.get("state", "unknown")
            execution_date = None
            duration = None

            if run.get("execution_date"):
                execution_date = datetime.fromisoformat(
                    run["execution_date"].replace("Z", "+00:00")
                )

            if run.get("start_date") and run.get("end_date"):
                start = datetime.fromisoformat(run["start_date"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(run["end_date"].replace("Z", "+00:00"))
                duration = (end - start).total_seconds()

            recent_runs.append(
                {
                    "state": state,
                    "execution_date": execution_date.isoformat() if execution_date else None,
                    "duration_seconds": duration,
                }
            )

            # Track success/failure dates
            if state == "success":
                if last_success is None:
                    last_success = execution_date
                if duration:
                    successful_durations.append(duration)
            elif state == "failed":
                if last_failure is None:
                    last_failure = execution_date

            # Count 7-day stats
            if execution_date and execution_date.replace(tzinfo=None) > cutoff_7d:
                total_7d += 1
                if state == "failed":
                    failures_7d += 1

        avg_duration = None
        if successful_durations:
            avg_duration = sum(successful_durations) / len(successful_durations)

        failure_rate = failures_7d / total_7d if total_7d > 0 else 0.0

        return DAGHistory(
            last_success=last_success,
            last_failure=last_failure,
            recent_runs=recent_runs,
            avg_duration_seconds=avg_duration,
            failure_rate_7d=failure_rate,
            total_runs_7d=total_7d,
        )

    async def collect(
        self,
        dag_id: str,
        task_id: str,
        run_id: str,
        try_number: int = 1,
        **kwargs: Any,
    ) -> tuple[TaskMetadata, TaskLogs, DAGHistory]:
        """Collect all Airflow data for a failed task.

        Args:
            dag_id: DAG identifier
            task_id: Task identifier
            run_id: DAG run identifier
            try_number: Attempt number

        Returns:
            Tuple of (TaskMetadata, TaskLogs, DAGHistory)
        """
        self.logger.info(
            "Collecting Airflow data",
            dag_id=dag_id,
            task_id=task_id,
            run_id=run_id,
        )

        # Fetch in parallel would be nice, but for simplicity we do sequential
        metadata = await self.get_task_instance(dag_id, run_id, task_id)
        logs = await self.get_task_logs(dag_id, run_id, task_id, try_number)
        history = await self.get_dag_history(dag_id)

        return metadata, logs, history
