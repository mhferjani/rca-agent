"""Main RCA Agent class - high-level API with multi-model support."""

import os
from pathlib import Path

import structlog
from dotenv import load_dotenv

from rca_agent.actions import ReportFormatter, SlackNotifier
from rca_agent.agent import AgentConfig, RCAWorkflow
from rca_agent.knowledge import IncidentStore
from rca_agent.models import FailureEvent, RCAReport

logger = structlog.get_logger()


# Supported LLM providers
SUPPORTED_PROVIDERS = [
    "anthropic",
    "openai",
    "mistral",
    "huggingface",
    "huggingface_local",
    "ollama",
]


class RCAAgent:
    """High-level interface for the RCA Agent.

    Supports multiple LLM providers:
    - anthropic: Claude API (default)
    - openai: GPT-4 API
    - huggingface: HuggingFace Inference API
    - huggingface_local: Local HuggingFace models
    - ollama: Local Ollama models

    Example:
        ```python
        # Default (Anthropic)
        agent = RCAAgent()

        # OpenAI
        agent = RCAAgent(llm_provider="openai")

        # HuggingFace
        agent = RCAAgent(
            llm_provider="huggingface",
            llm_model="mistralai/Mixtral-8x7B-Instruct-v0.1"
        )

        # Ollama (local)
        agent = RCAAgent(llm_provider="ollama", llm_model="mistral")

        # Analyze
        report = await agent.analyze(event)
        ```
    """

    def __init__(
        self,
        config: AgentConfig | None = None,
        env_file: str | Path | None = None,
        llm_provider: str | None = None,
        llm_model: str | None = None,
        llm_api_key: str | None = None,
    ) -> None:
        """Initialize RCA Agent.

        Args:
            config: Agent configuration. If not provided, will be loaded
                from environment variables.
            env_file: Path to .env file to load
            llm_provider: Override LLM provider (anthropic, openai, huggingface, ollama)
            llm_model: Override LLM model name
            llm_api_key: Override LLM API key
        """
        # Load environment
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        # Build config from environment if not provided
        if config is None:
            config = self._config_from_env()

        # Override with explicit parameters
        if llm_provider:
            config.llm_provider = llm_provider
        if llm_model:
            config.llm_model = llm_model
        if llm_api_key:
            config.llm_api_key = llm_api_key

        # Validate provider
        if config.llm_provider not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unknown LLM provider: {config.llm_provider}. "
                f"Supported: {', '.join(SUPPORTED_PROVIDERS)}"
            )

        self.config = config
        self.workflow = RCAWorkflow(config)
        self.logger = logger.bind(
            component="rca_agent",
            llm_provider=config.llm_provider,
            llm_model=config.llm_model,
        )

        # Initialize optional components
        self._slack: SlackNotifier | None = None
        if config.slack_webhook_url:
            self._slack = SlackNotifier(config.slack_webhook_url)

        self._store = IncidentStore(persist_directory=config.chroma_persist_dir)

        self.logger.info(
            "RCA Agent initialized",
            provider=config.llm_provider,
            model=config.llm_model,
        )

    def _config_from_env(self) -> AgentConfig:
        """Build configuration from environment variables."""
        provider = os.getenv("LLM_PROVIDER", "anthropic")

        # Get API key based on provider
        api_key = None
        model = None

        if provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        elif provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            model = os.getenv("OPENAI_MODEL", "gpt-4o")
        elif provider in ("huggingface", "huggingface_local"):
            api_key = os.getenv("HUGGINGFACE_API_KEY")
            model = os.getenv("HUGGINGFACE_MODEL", "mistralai/Mixtral-8x7B-Instruct-v0.1")
        elif provider == "ollama":
            model = os.getenv("OLLAMA_MODEL", "mistral")
            # Ollama doesn't need API key
        elif provider == "mistral":
            api_key = os.getenv("MISTRAL_API_KEY")
            model = os.getenv("MISTRAL_MODEL", "open-mistral-7b")
        return AgentConfig(
            airflow_base_url=os.getenv("AIRFLOW_BASE_URL", "http://localhost:8080"),
            airflow_username=os.getenv("AIRFLOW_USERNAME"),
            airflow_password=os.getenv("AIRFLOW_PASSWORD"),
            git_repo_path=os.getenv("GIT_REPO_PATH"),
            git_lookback_hours=int(os.getenv("GIT_LOOKBACK_HOURS", "24")),
            llm_provider=provider,
            llm_model=model,
            llm_api_key=api_key,
            # Provider-specific API keys
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            huggingface_api_key=os.getenv("HUGGINGFACE_API_KEY"),
            mistral_api_key=os.getenv("MISTRAL_API_KEY"),
            # Ollama
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            # Other settings
            chroma_persist_dir=os.getenv("CHROMA_PERSIST_DIR", "./data/chroma"),
            max_similar_incidents=int(os.getenv("MAX_SIMILAR_INCIDENTS", "5")),
            enable_git_collector=os.getenv("ENABLE_GIT_COLLECTOR", "true").lower() == "true",
            enable_source_health_collector=os.getenv(
                "ENABLE_SOURCE_HEALTH_COLLECTOR", "true"
            ).lower()
            == "true",
            enable_metrics_collector=os.getenv("ENABLE_METRICS_COLLECTOR", "false").lower()
            == "true",
            slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
        )

    async def analyze(
        self,
        event: FailureEvent,
        notify: bool = True,
        store: bool = True,
    ) -> RCAReport | None:
        """Analyze a pipeline failure.

        Args:
            event: The failure event to analyze
            notify: Whether to send Slack notification (if configured)
            store: Whether to store the incident in knowledge base

        Returns:
            RCA report if successful, None otherwise
        """
        self.logger.info(
            "Analyzing failure",
            dag_id=event.dag_id,
            task_id=event.task_id,
        )

        # Run analysis
        report = await self.workflow.analyze(event)

        if report is None:
            self.logger.error("Analysis failed")
            return None

        # Send notification
        if notify and self._slack:
            await self._slack.send_report(report)

        # Store incident
        if store:
            self._store.persist()

        return report

    async def analyze_from_webhook(
        self,
        payload: dict,
        notify: bool = True,
    ) -> RCAReport | None:
        """Analyze a failure from Airflow webhook payload.

        Args:
            payload: Webhook payload dict
            notify: Whether to send notification

        Returns:
            RCA report if successful
        """
        from rca_agent.models.events import WebhookPayload

        webhook = WebhookPayload(**payload)
        event = webhook.to_failure_event()
        return await self.analyze(event, notify=notify)

    def update_resolution(
        self,
        report_id: str,
        resolution: str,
    ) -> bool:
        """Update the resolution for a stored incident.

        Args:
            report_id: Report/incident ID
            resolution: Resolution description

        Returns:
            True if updated successfully
        """
        return self._store.update_resolution(report_id, resolution)

    def get_similar_incidents(
        self,
        dag_id: str,
        task_id: str,
        error_text: str,
        max_results: int = 5,
    ) -> list:
        """Find similar past incidents.

        Args:
            dag_id: DAG identifier
            task_id: Task identifier
            error_text: Error message or log excerpt
            max_results: Maximum results

        Returns:
            List of similar incidents
        """
        return self._store.find_similar(
            dag_id=dag_id,
            task_id=task_id,
            error_text=error_text,
            max_results=max_results,
        )

    def format_report(
        self,
        report: RCAReport,
        format: str = "markdown",
    ) -> str:
        """Format a report for output.

        Args:
            report: RCA report
            format: Output format ("markdown", "html", "json")

        Returns:
            Formatted report string
        """
        if format == "markdown":
            return ReportFormatter.to_markdown(report)
        elif format == "html":
            return ReportFormatter.to_html(report)
        elif format == "json":
            return ReportFormatter.to_json(report)
        else:
            raise ValueError(f"Unknown format: {format}")

    def get_statistics(self) -> dict:
        """Get incident store statistics.

        Returns:
            Statistics dict
        """
        return self._store.get_statistics()

    @staticmethod
    def list_providers() -> list[str]:
        """List supported LLM providers.

        Returns:
            List of provider names
        """
        return SUPPORTED_PROVIDERS
