"""Failure event models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TaskState(str, Enum):
    """Airflow task states."""

    FAILED = "failed"
    UPSTREAM_FAILED = "upstream_failed"
    SKIPPED = "skipped"
    UP_FOR_RETRY = "up_for_retry"
    UP_FOR_RESCHEDULE = "up_for_reschedule"


class FailureEvent(BaseModel):
    """Represents a pipeline failure event that triggers RCA analysis."""

    dag_id: str = Field(..., description="Airflow DAG identifier")
    task_id: str = Field(..., description="Failed task identifier")
    run_id: str = Field(..., description="DAG run identifier")
    execution_date: datetime | None = Field(default=None, description="Scheduled execution date")
    state: TaskState = Field(default=TaskState.FAILED, description="Task state")
    error_message: str | None = Field(default=None, description="Error message if available")
    try_number: int = Field(default=1, description="Current try number")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When the failure was detected"
    )

    model_config = {"frozen": True}


class WebhookPayload(BaseModel):
    """Payload received from Airflow webhook callback."""

    dag_id: str
    task_id: str
    run_id: str
    execution_date: str
    state: str
    try_number: int
    exception: str | None = None
    log_url: str | None = None

    def to_failure_event(self) -> FailureEvent:
        """Convert webhook payload to FailureEvent."""
        return FailureEvent(
            dag_id=self.dag_id,
            task_id=self.task_id,
            run_id=self.run_id,
            execution_date=datetime.fromisoformat(self.execution_date),
            state=TaskState(self.state)
            if self.state in TaskState.__members__.values()
            else TaskState.FAILED,
            error_message=self.exception,
            try_number=self.try_number,
        )
