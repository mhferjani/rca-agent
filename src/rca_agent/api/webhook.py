"""Webhook API for receiving Airflow failure callbacks."""

from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


class WebhookRequest(BaseModel):
    """Request body for webhook endpoint."""

    dag_id: str
    task_id: str
    run_id: str
    execution_date: str
    state: str
    try_number: int = 1
    exception: str | None = None
    log_url: str | None = None


class WebhookResponse(BaseModel):
    """Response from webhook endpoint."""

    status: str
    report_id: str | None = None
    root_cause_summary: str | None = None
    error: str | None = None


def create_app(env_file: Path | str | None = None) -> Any:
    """Create FastAPI application for webhook server.

    Args:
        env_file: Path to .env file

    Returns:
        FastAPI application
    """
    try:
        from fastapi import BackgroundTasks, FastAPI, HTTPException
    except ImportError:
        raise ImportError("FastAPI not installed. Run: pip install fastapi uvicorn")

    from rca_agent import RCAAgent

    app = FastAPI(
        title="RCA Agent API",
        description="Webhook endpoint for pipeline failure analysis",
        version="0.1.0",
    )

    # Initialize agent
    agent = RCAAgent(env_file=env_file)

    @app.get("/health")
    async def health() -> dict:
        """Health check endpoint."""
        return {"status": "healthy", "stats": agent.get_statistics()}

    @app.post("/webhook/airflow", response_model=WebhookResponse)
    async def airflow_webhook(
        request: WebhookRequest,
        background_tasks: BackgroundTasks,
    ) -> WebhookResponse:
        """Receive Airflow task failure callback.

        This endpoint is called by Airflow when a task fails.
        Configure in Airflow using on_failure_callback.
        """
        logger.info(
            "Received webhook",
            dag_id=request.dag_id,
            task_id=request.task_id,
        )

        try:
            # Run analysis
            report = await agent.analyze_from_webhook(
                request.model_dump(),
                notify=True,
            )

            if report:
                return WebhookResponse(
                    status="analyzed",
                    report_id=report.report_id,
                    root_cause_summary=report.root_cause_summary,
                )
            else:
                return WebhookResponse(
                    status="failed",
                    error="Analysis did not produce a report",
                )

        except Exception as e:
            logger.exception("Webhook processing failed", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/analyze", response_model=WebhookResponse)
    async def analyze_endpoint(request: WebhookRequest) -> WebhookResponse:
        """Manually trigger analysis for a failure.

        Unlike the webhook, this endpoint waits for analysis to complete.
        """
        try:
            report = await agent.analyze_from_webhook(
                request.model_dump(),
                notify=False,
            )

            if report:
                return WebhookResponse(
                    status="analyzed",
                    report_id=report.report_id,
                    root_cause_summary=report.root_cause_summary,
                )
            else:
                return WebhookResponse(
                    status="failed",
                    error="Analysis did not produce a report",
                )

        except Exception as e:
            logger.exception("Analysis failed", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/reports/{report_id}")
    async def get_report(report_id: str, format: str = "json") -> dict:
        """Get a specific report by ID.

        Args:
            report_id: Report identifier
            format: Output format (json, markdown, html)
        """
        # Note: This would need report storage to work properly
        # For now, returns a placeholder
        raise HTTPException(
            status_code=501,
            detail="Report retrieval not yet implemented",
        )

    @app.patch("/reports/{report_id}/resolution")
    async def update_resolution(
        report_id: str,
        resolution: str,
    ) -> dict:
        """Update the resolution for an incident.

        Args:
            report_id: Report identifier
            resolution: Resolution description
        """
        success = agent.update_resolution(report_id, resolution)

        if success:
            return {"status": "updated", "report_id": report_id}
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Report {report_id} not found",
            )

    return app
