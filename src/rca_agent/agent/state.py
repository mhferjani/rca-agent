"""Agent state definition for LangGraph workflow."""

from typing import Annotated

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from rca_agent.models.context import (
    DAGHistory,
    GitContext,
    MetricsSnapshot,
    RCAContext,
    SourceHealth,
    TaskLogs,
    TaskMetadata,
)
from rca_agent.models.events import FailureEvent
from rca_agent.models.reports import RCAReport, SimilarIncident


class AgentState(TypedDict):
    """State passed through the RCA agent graph."""

    # Input
    failure_event: FailureEvent

    # Collected data
    task_metadata: TaskMetadata | None
    task_logs: TaskLogs | None
    dag_history: DAGHistory | None
    git_context: GitContext | None
    source_health: list[SourceHealth]
    metrics: MetricsSnapshot | None

    # Aggregated context
    rca_context: RCAContext | None

    # Knowledge base
    similar_incidents: list[SimilarIncident]

    # Output
    report: RCAReport | None

    # Tracking
    errors: list[str]
    collectors_completed: list[str]

    # Messages (for potential chat interface)
    messages: Annotated[list, add_messages]


class AgentConfig(BaseModel):
    """Configuration for the RCA agent."""

    # Airflow settings
    airflow_base_url: str = Field(default="http://localhost:8080")
    airflow_username: str | None = None
    airflow_password: str | None = None

    # Git settings
    git_repo_path: str | None = None
    git_lookback_hours: int = 24

    # Source health settings
    sources: list[dict] = Field(default_factory=list)

    # LLM settings - General
    llm_provider: str = Field(default="anthropic")
    llm_model: str | None = None
    llm_api_key: str | None = None  # Fallback / generic

    # LLM settings - Provider specific API keys
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    huggingface_api_key: str | None = None
    mistral_api_key: str | None = None
    # Ollama settings
    ollama_base_url: str = "http://localhost:11434"

    # Knowledge base
    chroma_persist_dir: str = "./data/chroma"
    max_similar_incidents: int = 5

    # Feature flags
    enable_git_collector: bool = True
    enable_source_health_collector: bool = True
    enable_metrics_collector: bool = False

    # Notifications
    slack_webhook_url: str | None = None

    model_config = {"extra": "allow"}
