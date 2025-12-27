"""RCA Report models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ErrorCategory(str, Enum):
    """Categories of pipeline errors."""

    RESOURCE_EXHAUSTION = "resource_exhaustion"
    SCHEMA_MISMATCH = "schema_mismatch"
    SOURCE_UNAVAILABLE = "source_unavailable"
    DATA_QUALITY = "data_quality"
    PERMISSION_ERROR = "permission_error"
    CODE_REGRESSION = "code_regression"
    VOLUME_ANOMALY = "volume_anomaly"
    NETWORK_ERROR = "network_error"
    CONFIGURATION_ERROR = "configuration_error"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    """Severity levels for incidents."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SimilarIncident(BaseModel):
    """Reference to a similar past incident."""

    incident_id: str
    date: datetime
    dag_id: str
    task_id: str
    error_category: ErrorCategory
    root_cause: str
    resolution: str | None = None
    similarity_score: float = Field(ge=0.0, le=1.0)


class Recommendation(BaseModel):
    """Actionable recommendation."""

    action: str = Field(..., description="What to do")
    priority: int = Field(ge=1, le=5, description="Priority 1 (highest) to 5")
    estimated_effort: str | None = Field(default=None, description="e.g., '5 minutes', '1 hour'")
    automated: bool = Field(default=False, description="Can this be automated?")


class RCAReport(BaseModel):
    """Complete Root Cause Analysis report."""

    # Identifiers
    report_id: str = Field(..., description="Unique report identifier")
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    # Task reference
    dag_id: str
    task_id: str
    run_id: str
    failure_time: datetime

    # Analysis results
    error_category: ErrorCategory
    severity: Severity
    root_cause: str = Field(..., description="Human-readable root cause explanation")
    root_cause_summary: str = Field(..., description="One-line summary for notifications")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score of the analysis")

    # Evidence
    evidence: list[str] = Field(
        default_factory=list,
        description="List of evidence supporting the diagnosis",
    )
    key_log_lines: list[str] = Field(
        default_factory=list,
        description="Key log lines that led to diagnosis",
    )

    # Context
    contributing_factors: list[str] = Field(
        default_factory=list,
        description="Additional factors that may have contributed",
    )
    recent_changes: list[str] = Field(
        default_factory=list,
        description="Recent changes that might be relevant",
    )

    # Recommendations
    recommendations: list[Recommendation] = Field(default_factory=list)
    immediate_action: str | None = Field(default=None, description="Most urgent action to take")

    # Historical context
    similar_incidents: list[SimilarIncident] = Field(default_factory=list)
    is_recurring: bool = Field(default=False, description="Whether this is a recurring issue")
    recurrence_count: int = Field(
        default=0, description="Number of similar incidents in past 30 days"
    )

    # Metadata
    analysis_duration_ms: int | None = Field(default=None, description="Time taken for analysis")
    llm_model: str | None = Field(default=None, description="LLM model used")
    collectors_used: list[str] = Field(
        default_factory=list, description="List of collectors that provided data"
    )

    def to_slack_message(self) -> dict:
        """Format report as Slack message blocks."""
        severity_emoji = {
            Severity.CRITICAL: "🔴",
            Severity.HIGH: "🟠",
            Severity.MEDIUM: "🟡",
            Severity.LOW: "🟢",
        }

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{severity_emoji[self.severity]} Pipeline Failure: {self.dag_id}/{self.task_id}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Category:*\n{self.error_category.value}"},
                    {"type": "mrkdwn", "text": f"*Confidence:*\n{self.confidence:.0%}"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Root Cause:*\n{self.root_cause}",
                },
            },
        ]

        if self.immediate_action:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*🚨 Immediate Action:*\n{self.immediate_action}",
                    },
                }
            )

        if self.evidence:
            evidence_text = "\n".join(f"• {e}" for e in self.evidence[:3])
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Evidence:*\n{evidence_text}",
                    },
                }
            )

        if self.similar_incidents:
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"📚 {len(self.similar_incidents)} similar incidents found. "
                            f"Last occurrence: {self.similar_incidents[0].date.strftime('%Y-%m-%d')}",
                        }
                    ],
                }
            )

        return {"blocks": blocks}

    def to_summary(self) -> str:
        """Generate a brief text summary."""
        return (
            f"[{self.severity.value.upper()}] {self.dag_id}/{self.task_id}: "
            f"{self.root_cause_summary} (Confidence: {self.confidence:.0%})"
        )
