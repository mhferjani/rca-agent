"""LangGraph workflow definition for RCA Agent."""

import warnings
from functools import partial

import structlog
from langgraph.graph import END, StateGraph

from rca_agent.agent.nodes import (
    analyze_with_llm,
    build_context,
    collect_airflow_data,
    collect_git_data,
    collect_source_health,
    find_similar_incidents,
    store_incident,
)
from rca_agent.agent.state import AgentConfig, AgentState
from rca_agent.models.events import FailureEvent
from rca_agent.models.reports import RCAReport

logger = structlog.get_logger()

# Suppress LangGraph config type warnings (we use our own AgentConfig)
warnings.filterwarnings(
    "ignore", message=".*config.*parameter should be typed as.*RunnableConfig.*"
)


def create_rca_graph(config: AgentConfig) -> StateGraph:
    """Create the RCA analysis workflow graph.

    The graph follows this flow:
    1. Collect data from multiple sources in parallel
    2. Build unified context
    3. Search for similar incidents
    4. Analyze with LLM
    5. Store incident for future reference

    Args:
        config: Agent configuration

    Returns:
        Compiled StateGraph
    """
    # Create graph
    graph = StateGraph(AgentState)

    # Bind config to node functions
    airflow_node = partial(collect_airflow_data, config=config)
    git_node = partial(collect_git_data, config=config)
    source_health_node = partial(collect_source_health, config=config)
    similar_node = partial(find_similar_incidents, config=config)
    context_node = partial(build_context, config=config)
    analyze_node = partial(analyze_with_llm, config=config)
    store_node = partial(store_incident, config=config)

    # Add nodes
    graph.add_node("collect_airflow", airflow_node)
    graph.add_node("collect_git", git_node)
    graph.add_node("collect_source_health", source_health_node)
    graph.add_node("find_similar", similar_node)
    graph.add_node("build_context", context_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("store_incident", store_node)

    # Define edges
    # Start with parallel collection
    graph.set_entry_point("collect_airflow")

    # After Airflow, run other collectors and context building
    graph.add_edge("collect_airflow", "collect_git")
    graph.add_edge("collect_airflow", "collect_source_health")
    graph.add_edge("collect_airflow", "find_similar")

    # All collectors feed into context building
    graph.add_edge("collect_git", "build_context")
    graph.add_edge("collect_source_health", "build_context")
    graph.add_edge("find_similar", "build_context")

    # Context -> Analysis -> Store -> End
    graph.add_edge("build_context", "analyze")
    graph.add_edge("analyze", "store_incident")
    graph.add_edge("store_incident", END)

    return graph


class RCAWorkflow:
    """High-level interface for the RCA workflow."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        """Initialize RCA workflow.

        Args:
            config: Agent configuration (uses defaults if not provided)
        """
        self.config = config or AgentConfig()
        self.graph = create_rca_graph(self.config)
        self.compiled = self.graph.compile()
        self.logger = logger.bind(component="rca_workflow")

    async def analyze(self, event: FailureEvent) -> RCAReport | None:
        """Run RCA analysis for a failure event.

        Args:
            event: The failure event to analyze

        Returns:
            RCA report if successful, None otherwise
        """
        self.logger.info(
            "Starting RCA analysis",
            dag_id=event.dag_id,
            task_id=event.task_id,
            run_id=event.run_id,
        )

        # Initialize state
        initial_state: AgentState = {
            "failure_event": event,
            "task_metadata": None,
            "task_logs": None,
            "dag_history": None,
            "git_context": None,
            "source_health": [],
            "metrics": None,
            "rca_context": None,
            "similar_incidents": [],
            "report": None,
            "errors": [],
            "collectors_completed": [],
            "messages": [],
        }

        # Run the graph
        try:
            final_state = await self.compiled.ainvoke(initial_state)

            if final_state.get("errors"):
                self.logger.warning(
                    "Analysis completed with errors",
                    errors=final_state["errors"],
                )

            report = final_state.get("report")
            if report:
                self.logger.info(
                    "Analysis successful",
                    report_id=report.report_id,
                    category=report.error_category.value,
                )
            else:
                self.logger.error("Analysis failed to produce report")

            return report

        except Exception as e:
            self.logger.exception("Workflow execution failed", error=str(e))
            return None

    def get_graph_visualization(self) -> str:
        """Get a Mermaid diagram of the workflow graph.

        Returns:
            Mermaid diagram string
        """
        return self.compiled.get_graph().draw_mermaid()
