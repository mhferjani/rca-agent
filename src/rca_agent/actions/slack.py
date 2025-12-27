"""Slack notification integration."""

import httpx
import structlog

from rca_agent.models.reports import RCAReport

logger = structlog.get_logger()


class SlackNotifier:
    """Send RCA reports to Slack."""

    def __init__(
        self,
        webhook_url: str,
        channel: str | None = None,
        timeout: int = 10,
    ) -> None:
        """Initialize Slack notifier.

        Args:
            webhook_url: Slack webhook URL
            channel: Optional channel override
            timeout: Request timeout in seconds
        """
        self.webhook_url = webhook_url
        self.channel = channel
        self.timeout = timeout
        self.logger = logger.bind(component="slack_notifier")

    async def send_report(self, report: RCAReport) -> bool:
        """Send RCA report to Slack.

        Args:
            report: RCA report to send

        Returns:
            True if sent successfully
        """
        payload = report.to_slack_message()

        if self.channel:
            payload["channel"] = self.channel

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                )
                response.raise_for_status()

            self.logger.info(
                "Slack notification sent",
                report_id=report.report_id,
                dag_id=report.dag_id,
            )
            return True

        except httpx.HTTPStatusError as e:
            self.logger.error(
                "Slack API error",
                status=e.response.status_code,
                body=e.response.text,
            )
            return False
        except Exception as e:
            self.logger.exception("Failed to send Slack notification", error=str(e))
            return False

    async def send_simple_message(self, text: str) -> bool:
        """Send a simple text message to Slack.

        Args:
            text: Message text

        Returns:
            True if sent successfully
        """
        payload = {"text": text}

        if self.channel:
            payload["channel"] = self.channel

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                )
                response.raise_for_status()
            return True

        except Exception as e:
            self.logger.exception("Failed to send Slack message", error=str(e))
            return False
