"""Command-line interface for RCA Agent."""

import asyncio
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from rca_agent import RCAAgent
from rca_agent.models import FailureEvent

app = typer.Typer(
    name="rca-agent",
    help="Intelligent Root Cause Analysis for Data Engineering Pipelines",
    add_completion=False,
)
console = Console()


@app.command()
def analyze(
    dag_id: str = typer.Option(..., "--dag-id", "-d", help="Airflow DAG ID"),
    task_id: str = typer.Option(..., "--task-id", "-t", help="Failed task ID"),
    run_id: str = typer.Option(..., "--run-id", "-r", help="DAG run ID"),
    try_number: int = typer.Option(1, "--try", help="Try number"),
    error_message: str | None = typer.Option(None, "--error", "-e", help="Error message"),
    output_format: str = typer.Option(
        "markdown", "--format", "-f", help="Output format: markdown, html, json"
    ),
    output_file: Path | None = typer.Option(None, "--output", "-o", help="Output file path"),
    no_notify: bool = typer.Option(False, "--no-notify", help="Disable Slack notification"),
    env_file: Path | None = typer.Option(None, "--env", help="Path to .env file"),
) -> None:
    """Analyze a pipeline failure and generate RCA report."""
    console.print(
        Panel.fit(
            f"[bold blue]Analyzing failure[/bold blue]\n"
            f"DAG: {dag_id}\n"
            f"Task: {task_id}\n"
            f"Run: {run_id}",
            title="🔍 RCA Agent",
        )
    )

    # Create event
    event = FailureEvent(
        dag_id=dag_id,
        task_id=task_id,
        run_id=run_id,
        try_number=try_number,
        error_message=error_message,
        timestamp=datetime.utcnow(),
    )

    # Run analysis
    async def run_analysis():
        agent = RCAAgent(env_file=env_file)
        return await agent.analyze(event, notify=not no_notify)

    with console.status("[bold green]Analyzing...[/bold green]"):
        report = asyncio.run(run_analysis())

    if report is None:
        console.print("[bold red]Analysis failed![/bold red]")
        raise typer.Exit(1)

    # Format output
    agent = RCAAgent(env_file=env_file)
    formatted = agent.format_report(report, output_format)

    # Output
    if output_file:
        output_file.write_text(formatted)
        console.print(f"[green]Report saved to {output_file}[/green]")
    else:
        console.print(formatted)

    # Summary
    console.print("\n")
    console.print(
        Panel.fit(
            f"[bold]Category:[/bold] {report.error_category.value}\n"
            f"[bold]Severity:[/bold] {report.severity.value}\n"
            f"[bold]Confidence:[/bold] {report.confidence:.0%}\n"
            f"[bold]Root Cause:[/bold] {report.root_cause_summary}",
            title="✅ Analysis Complete",
            border_style="green",
        )
    )


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
    env_file: Path | None = typer.Option(None, "--env", help="Path to .env file"),
) -> None:
    """Start the RCA Agent webhook server."""
    console.print(
        Panel.fit(
            f"[bold blue]Starting webhook server[/bold blue]\n"
            f"Host: {host}:{port}\n"
            f"Reload: {reload}",
            title="🚀 RCA Agent Server",
        )
    )

    try:
        import uvicorn

        from rca_agent.api.webhook import create_app

        app = create_app(env_file)
        uvicorn.run(app, host=host, port=port, reload=reload)
    except ImportError:
        console.print("[red]uvicorn not installed. Run: pip install uvicorn[/red]")
        raise typer.Exit(1)


@app.command()
def stats(
    env_file: Path | None = typer.Option(None, "--env", help="Path to .env file"),
) -> None:
    """Show incident store statistics."""
    agent = RCAAgent(env_file=env_file)
    stats = agent.get_statistics()

    table = Table(title="📊 Incident Store Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    for key, value in stats.items():
        table.add_row(key.replace("_", " ").title(), str(value))

    console.print(table)


@app.command()
def demo(
    scenario: str = typer.Option(
        "oom",
        "--scenario",
        "-s",
        help="Demo scenario: oom, schema-break, source-timeout, code-regression",
    ),
    output_format: str = typer.Option(
        "markdown", "--format", "-f", help="Output format: markdown, html, json"
    ),
    output_file: Path | None = typer.Option(None, "--output", "-o", help="Output file path"),
    env_file: Path | None = typer.Option(None, "--env", help="Path to .env file"),
) -> None:
    """Run a demo scenario to see RCA Agent in action (with real LLM analysis)."""
    from rca_agent.actions import ReportFormatter
    from rca_agent.analyzers import LLMAnalyzer
    from rca_agent.models.context import DAGHistory, RCAContext, TaskLogs, TaskMetadata

    console.print(
        Panel.fit(
            f"[bold blue]Running demo scenario[/bold blue]\n" f"Scenario: {scenario}",
            title="🎮 RCA Agent Demo",
        )
    )

    # Demo scenarios with mock data
    scenarios = {
        "oom": {
            "dag_id": "etl_sales_daily",
            "task_id": "transform_large_dataset",
            "run_id": "demo_oom_001",
            "error": "java.lang.OutOfMemoryError: Java heap space",
            "logs": """
[2025-12-26 01:00:00] INFO - Starting transform_large_dataset
[2025-12-26 01:00:01] INFO - Loading data from source table: sales_raw (50M rows)
[2025-12-26 01:00:15] INFO - Applying transformations...
[2025-12-26 01:00:30] WARN - Memory usage at 85%
[2025-12-26 01:00:45] WARN - Memory usage at 95%
[2025-12-26 01:00:50] ERROR - java.lang.OutOfMemoryError: Java heap space
    at java.util.Arrays.copyOf(Arrays.java:3210)
    at java.util.ArrayList.grow(ArrayList.java:265)
    at org.apache.spark.sql.execution.SparkPlan.executeCollect(SparkPlan.scala:390)
[2025-12-26 01:00:50] ERROR - Task failed with exit code 137 (OOM Killed)
""",
        },
        "schema-break": {
            "dag_id": "ingest_api_data",
            "task_id": "parse_response",
            "run_id": "demo_schema_001",
            "error": "KeyError: 'customer_id' - column not found in response",
            "logs": """
[2025-12-26 01:00:00] INFO - Starting parse_response
[2025-12-26 01:00:01] INFO - Fetching data from API: https://api.example.com/v2/customers
[2025-12-26 01:00:02] INFO - Received 1000 records
[2025-12-26 01:00:03] INFO - Parsing response schema...
[2025-12-26 01:00:03] ERROR - KeyError: 'customer_id'
    File "dags/ingest_api.py", line 45, in parse_response
        customer_id = record['customer_id']
[2025-12-26 01:00:03] ERROR - Expected field 'customer_id' not found in API response
[2025-12-26 01:00:03] INFO - Available fields: ['id', 'name', 'email', 'created_at']
[2025-12-26 01:00:03] ERROR - Possible schema change in upstream API v2
""",
        },
        "source-timeout": {
            "dag_id": "sync_external_api",
            "task_id": "fetch_data",
            "run_id": "demo_timeout_001",
            "error": "TimeoutError: Connection to api.external.com timed out after 30s",
            "logs": """
[2025-12-26 01:00:00] INFO - Starting fetch_data
[2025-12-26 01:00:01] INFO - Connecting to https://api.external.com/data
[2025-12-26 01:00:01] INFO - Timeout configured: 30s
[2025-12-26 01:00:10] WARN - Connection slow, 10s elapsed...
[2025-12-26 01:00:20] WARN - Connection slow, 20s elapsed...
[2025-12-26 01:00:31] ERROR - TimeoutError: Connection to api.external.com timed out after 30s
    File "dags/sync_api.py", line 28, in fetch_data
        response = requests.get(url, timeout=30)
[2025-12-26 01:00:31] ERROR - External API not responding
[2025-12-26 01:00:31] INFO - Last successful connection: 2025-12-25 23:00:00
""",
        },
        "code-regression": {
            "dag_id": "data_quality_checks",
            "task_id": "validate_schema",
            "run_id": "demo_regression_001",
            "error": "TypeError: unsupported operand type(s) for +: 'int' and 'str'",
            "logs": """
[2025-12-26 01:00:00] INFO - Starting validate_schema
[2025-12-26 01:00:01] INFO - Loading schema from config...
[2025-12-26 01:00:02] INFO - Validating 15 columns...
[2025-12-26 01:00:02] ERROR - TypeError: unsupported operand type(s) for +: 'int' and 'str'
    File "dags/quality_checks.py", line 67, in validate_schema
        total = count + suffix
    File "dags/quality_checks.py", line 45, in run_validation
        result = validate_schema(df)
[2025-12-26 01:00:02] ERROR - Type mismatch in validation logic
[2025-12-26 01:00:02] INFO - Recent commit: abc123 - "refactored validation logic" by dev@example.com
""",
        },
    }

    if scenario not in scenarios:
        console.print(f"[red]Unknown scenario: {scenario}[/red]")
        console.print(f"Available: {', '.join(scenarios.keys())}")
        raise typer.Exit(1)

    demo_data = scenarios[scenario]

    console.print(f"\n[dim]Simulated error: {demo_data['error']}[/dim]\n")

    # Create mock context
    task_metadata = TaskMetadata(
        dag_id=demo_data["dag_id"],
        task_id=demo_data["task_id"],
        run_id=demo_data["run_id"],
        try_number=1,
        state="failed",
        operator="PythonOperator",
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow(),
        duration=50.0,
        pool="default_pool",
        queue="default",
    )

    task_logs = TaskLogs(
        stdout=demo_data["logs"],
        stderr="",
        error_snippet=demo_data["error"],
    )

    dag_history = DAGHistory(
        recent_runs=[
            {
                "run_id": "previous_run_001",
                "state": "success",
            }
        ],
        failure_rate_7d=0.1,
        avg_duration_seconds=45.0,
    )

    context = RCAContext(
        failure_time=datetime.utcnow(),
        task=task_metadata,
        logs=task_logs,
        dag_history=dag_history,
    )

    # Run real LLM analysis
    async def run_demo_analysis():
        import os

        from dotenv import load_dotenv

        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        provider = os.getenv("LLM_PROVIDER", "anthropic")

        # Get the right API key
        api_key = None
        model = None
        if provider == "mistral":
            api_key = os.getenv("MISTRAL_API_KEY")
            model = os.getenv("MISTRAL_MODEL", "open-mistral-7b")
        elif provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        elif provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            model = os.getenv("OPENAI_MODEL", "gpt-4o")
        elif provider == "ollama":
            model = os.getenv("OLLAMA_MODEL", "mistral")

        analyzer = LLMAnalyzer(
            provider=provider,
            model=model,
            api_key=api_key,
        )

        return await analyzer.analyze(context, similar_incidents=[])

    with console.status("[bold green]Analyzing with LLM...[/bold green]"):
        report = asyncio.run(run_demo_analysis())

    # Format output
    if output_format == "markdown":
        formatted = ReportFormatter.to_markdown(report)
    elif output_format == "html":
        formatted = ReportFormatter.to_html(report)
    elif output_format == "json":
        formatted = ReportFormatter.to_json(report)
    else:
        formatted = ReportFormatter.to_markdown(report)

    # Output
    if output_file:
        output_file.write_text(formatted)
        console.print(f"[green]Report saved to {output_file}[/green]")
    else:
        console.print("\n")
        console.print(formatted)

    # Summary
    console.print("\n")
    console.print(
        Panel.fit(
            f"[bold]Category:[/bold] {report.error_category.value}\n"
            f"[bold]Severity:[/bold] {report.severity.value}\n"
            f"[bold]Confidence:[/bold] {report.confidence:.0%}\n"
            f"[bold]Root Cause:[/bold] {report.root_cause_summary}",
            title="✅ Analysis Complete",
            border_style="green",
        )
    )


@app.command()
def version() -> None:
    """Show version information."""
    from rca_agent import __version__

    console.print(f"[bold]RCA Agent[/bold] version {__version__}")


def main() -> None:
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
