"""Node functions for the RCA agent graph."""

from typing import Any

import structlog

from rca_agent.agent.state import AgentConfig, AgentState
from rca_agent.analyzers import LLMAnalyzer
from rca_agent.collectors import AirflowCollector, GitCollector, SourceHealthCollector
from rca_agent.knowledge import IncidentStore
from rca_agent.models.context import RCAContext

logger = structlog.get_logger()


async def collect_airflow_data(
    state: AgentState,
    config: AgentConfig,
) -> dict[str, Any]:
    """Collect task metadata, logs, and DAG history from Airflow.

    Args:
        state: Current agent state
        config: Agent configuration

    Returns:
        Updated state fields
    """
    log = logger.bind(node="collect_airflow_data")
    event = state["failure_event"]

    collector = AirflowCollector(
        base_url=config.airflow_base_url,
        username=config.airflow_username,
        password=config.airflow_password,
    )

    try:
        result = await collector.safe_collect(
            dag_id=event.dag_id,
            task_id=event.task_id,
            run_id=event.run_id,
            try_number=event.try_number,
        )

        if result:
            metadata, logs, history = result
            log.info("Airflow data collected successfully")
            return {
                "task_metadata": metadata,
                "task_logs": logs,
                "dag_history": history,
                "collectors_completed": state.get("collectors_completed", []) + ["airflow"],
            }
        else:
            log.warning("Airflow collection returned no data")
            return {
                "errors": state.get("errors", []) + ["Airflow collection failed"],
            }

    except Exception as e:
        log.exception("Airflow collection error", error=str(e))
        return {
            "errors": state.get("errors", []) + [f"Airflow error: {e}"],
        }


async def collect_git_data(
    state: AgentState,
    config: AgentConfig,
) -> dict[str, Any]:
    """Collect Git repository context.

    Args:
        state: Current agent state
        config: Agent configuration

    Returns:
        Updated state fields
    """
    log = logger.bind(node="collect_git_data")

    if not config.enable_git_collector or not config.git_repo_path:
        log.info("Git collector disabled or no repo path configured")
        return {}

    event = state["failure_event"]

    collector = GitCollector(
        repo_path=config.git_repo_path,
        lookback_hours=config.git_lookback_hours,
    )

    try:
        result = await collector.safe_collect(dag_id=event.dag_id)

        if result:
            log.info(
                "Git data collected",
                commits=len(result.recent_commits),
            )
            return {
                "git_context": result,
                "collectors_completed": state.get("collectors_completed", []) + ["git"],
            }
        else:
            return {}

    except Exception as e:
        log.exception("Git collection error", error=str(e))
        return {
            "errors": state.get("errors", []) + [f"Git error: {e}"],
        }


async def collect_source_health(
    state: AgentState,
    config: AgentConfig,
) -> dict[str, Any]:
    """Check health of data sources.

    Args:
        state: Current agent state
        config: Agent configuration

    Returns:
        Updated state fields
    """
    log = logger.bind(node="collect_source_health")

    if not config.enable_source_health_collector or not config.sources:
        log.info("Source health collector disabled or no sources configured")
        return {"source_health": []}

    collector = SourceHealthCollector(sources=config.sources)

    try:
        result = await collector.safe_collect()

        if result:
            log.info("Source health collected", sources=len(result))
            return {
                "source_health": result,
                "collectors_completed": state.get("collectors_completed", []) + ["source_health"],
            }
        else:
            return {"source_health": []}

    except Exception as e:
        log.exception("Source health collection error", error=str(e))
        return {
            "source_health": [],
            "errors": state.get("errors", []) + [f"Source health error: {e}"],
        }


async def find_similar_incidents(
    state: AgentState,
    config: AgentConfig,
) -> dict[str, Any]:
    """Search for similar past incidents.

    Args:
        state: Current agent state
        config: Agent configuration

    Returns:
        Updated state fields
    """
    log = logger.bind(node="find_similar_incidents")
    event = state["failure_event"]

    try:
        store = IncidentStore(persist_directory=config.chroma_persist_dir)

        # Use error message or log snippet for similarity search
        error_text = event.error_message or ""
        if state.get("task_logs") and state["task_logs"].error_snippet:
            error_text = state["task_logs"].error_snippet

        similar = store.find_similar(
            dag_id=event.dag_id,
            task_id=event.task_id,
            error_text=error_text,
            max_results=config.max_similar_incidents,
        )

        log.info("Found similar incidents", count=len(similar))
        return {"similar_incidents": similar}

    except Exception as e:
        log.exception("Similar incident search error", error=str(e))
        return {
            "similar_incidents": [],
            "errors": state.get("errors", []) + [f"Incident search error: {e}"],
        }


def build_context(
    state: AgentState,
    config: AgentConfig,
) -> dict[str, Any]:
    """Aggregate all collected data into RCAContext.

    Args:
        state: Current agent state
        config: Agent configuration

    Returns:
        Updated state fields
    """
    log = logger.bind(node="build_context")

    # Check required data
    if not state.get("task_metadata") or not state.get("task_logs"):
        log.error("Missing required Airflow data for context")
        return {
            "errors": state.get("errors", []) + ["Cannot build context: missing Airflow data"],
        }

    context = RCAContext(
        failure_time=state["failure_event"].timestamp,
        task=state["task_metadata"],
        logs=state["task_logs"],
        dag_history=state.get("dag_history"),
        git=state.get("git_context"),
        sources=state.get("source_health", []),
        metrics=state.get("metrics"),
    )

    log.info("Context built successfully")
    return {"rca_context": context}


async def analyze_with_llm(
    state: AgentState,
    config: AgentConfig,
) -> dict[str, Any]:
    """Run LLM analysis on the context.

    Args:
        state: Current agent state
        config: Agent configuration

    Returns:
        Updated state fields
    """
    log = logger.bind(node="analyze_with_llm")

    if not state.get("rca_context"):
        log.error("No context available for analysis")
        return {
            "errors": state.get("errors", []) + ["No context for LLM analysis"],
        }

    try:
        # Get the right API key based on provider
        api_key = config.llm_api_key
        if config.llm_provider == "huggingface":
            api_key = config.huggingface_api_key
        elif config.llm_provider == "anthropic":
            api_key = config.anthropic_api_key
        elif config.llm_provider == "openai":
            api_key = config.openai_api_key
        elif config.llm_provider == "mistral":
            api_key = config.mistral_api_key

        # Build extra kwargs for specific providers
        extra_kwargs = {}
        if config.llm_provider == "ollama":
            extra_kwargs["base_url"] = getattr(config, "ollama_base_url", "http://localhost:11434")

        analyzer = LLMAnalyzer(
            provider=config.llm_provider,
            model=config.llm_model,
            api_key=api_key,
            **extra_kwargs,
        )

        report = await analyzer.analyze(
            context=state["rca_context"],
            similar_incidents=state.get("similar_incidents", []),
        )

        log.info(
            "Analysis complete",
            category=report.error_category.value,
            confidence=report.confidence,
        )

        return {"report": report}

    except Exception as e:
        log.exception("LLM analysis error", error=str(e))
        return {
            "errors": state.get("errors", []) + [f"LLM analysis error: {e}"],
        }


async def store_incident(
    state: AgentState,
    config: AgentConfig,
) -> dict[str, Any]:
    """Store the incident in the knowledge base.

    Args:
        state: Current agent state
        config: Agent configuration

    Returns:
        Updated state fields (empty - final node)
    """
    log = logger.bind(node="store_incident")

    if not state.get("report"):
        log.warning("No report to store")
        return {}

    try:
        store = IncidentStore(persist_directory=config.chroma_persist_dir)
        incident_id = store.add_incident(state["report"])
        store.persist()

        log.info("Incident stored", incident_id=incident_id)
        return {}

    except Exception as e:
        log.exception("Failed to store incident", error=str(e))
        return {
            "errors": state.get("errors", []) + [f"Storage error: {e}"],
        }
