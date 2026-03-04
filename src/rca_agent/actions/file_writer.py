"""File-based report writer for RCA Agent."""

from pathlib import Path

import structlog

from rca_agent.actions.formatters import ReportFormatter
from rca_agent.models.reports import RCAReport

logger = structlog.get_logger()


class FileReportWriter:
    """Write RCA reports to text files in a local directory."""

    def __init__(self, output_dir: str = "./reports") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger.bind(component="file_report_writer")

    async def write_report(self, report: RCAReport) -> Path:
        """Write an RCA report to a text file.

        Args:
            report: The RCA report to write

        Returns:
            Path to the written file
        """
        filename = (
            f"{report.failure_time.strftime('%Y%m%d_%H%M%S')}"
            f"_{report.dag_id}_{report.task_id}_{report.report_id[:8]}.txt"
        )
        filepath = self.output_dir / filename

        content = ReportFormatter.to_markdown(report)
        filepath.write_text(content, encoding="utf-8")

        self.logger.info(
            "Report written to file",
            path=str(filepath),
            report_id=report.report_id,
        )

        return filepath
