"""Git repository collector for recent changes."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from git import Repo
from git.exc import GitError

from rca_agent.collectors.base import BaseCollector
from rca_agent.models.context import GitCommit, GitContext


class GitCollector(BaseCollector[GitContext]):
    """Collector for Git repository history related to DAG files."""

    name = "git"

    def __init__(
        self,
        repo_path: str | Path,
        lookback_hours: int = 24,
        enabled: bool = True,
    ) -> None:
        """Initialize Git collector.

        Args:
            repo_path: Path to the Git repository
            lookback_hours: How far back to look for commits
            enabled: Whether the collector is enabled
        """
        super().__init__(enabled=enabled)
        self.repo_path = Path(repo_path)
        self.lookback_hours = lookback_hours
        self._repo: Repo | None = None

    @property
    def repo(self) -> Repo:
        """Get or initialize Git repository."""
        if self._repo is None:
            self._repo = Repo(self.repo_path)
        return self._repo

    def _commit_to_model(self, commit: Any) -> GitCommit:
        """Convert git.Commit to GitCommit model."""
        return GitCommit(
            sha=commit.hexsha,
            short_sha=commit.hexsha[:7],
            author=commit.author.name,
            email=commit.author.email,
            message=commit.message.strip().split("\n")[0],  # First line only
            date=datetime.fromtimestamp(commit.committed_date),
            files_changed=list(commit.stats.files.keys()),
        )

    async def get_recent_commits(
        self,
        since: datetime | None = None,
        max_count: int = 20,
    ) -> list[GitCommit]:
        """Get recent commits.

        Args:
            since: Only include commits after this date
            max_count: Maximum number of commits to return

        Returns:
            List of recent commits
        """
        if since is None:
            since = datetime.utcnow() - timedelta(hours=self.lookback_hours)

        commits = []
        for commit in self.repo.iter_commits(max_count=max_count):
            commit_date = datetime.fromtimestamp(commit.committed_date)
            if commit_date < since:
                break
            commits.append(self._commit_to_model(commit))

        return commits

    async def get_commits_for_file(
        self,
        file_path: str,
        max_count: int = 10,
    ) -> list[GitCommit]:
        """Get commits that touched a specific file.

        Args:
            file_path: Path to the file (relative to repo root)
            max_count: Maximum number of commits to return

        Returns:
            List of commits that modified the file
        """
        commits = []
        try:
            for commit in self.repo.iter_commits(paths=file_path, max_count=max_count):
                commits.append(self._commit_to_model(commit))
        except GitError as e:
            self.logger.warning("Failed to get file commits", file=file_path, error=str(e))

        return commits

    async def find_dag_file(self, dag_id: str) -> str | None:
        """Try to find the DAG file by searching for the dag_id.

        Args:
            dag_id: DAG identifier to search for

        Returns:
            Path to the DAG file if found, None otherwise
        """
        # Common patterns for DAG files
        patterns = [
            f"**/dags/**/*{dag_id}*.py",
            f"**/{dag_id}.py",
            f"**/dag_{dag_id}.py",
            f"**/{dag_id}_dag.py",
        ]

        for pattern in patterns:
            matches = list(self.repo_path.glob(pattern))
            if matches:
                return str(matches[0].relative_to(self.repo_path))

        # Fallback: grep for dag_id in Python files
        try:
            import subprocess

            result = subprocess.run(
                ["grep", "-rl", f'dag_id="{dag_id}"', str(self.repo_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                first_match = result.stdout.strip().split("\n")[0]
                return str(Path(first_match).relative_to(self.repo_path))
        except Exception as e:
            self.logger.debug("Grep search failed", error=str(e))

        return None

    async def collect(
        self,
        dag_id: str,
        dag_file_path: str | None = None,
        **kwargs: Any,
    ) -> GitContext:
        """Collect Git context for a DAG.

        Args:
            dag_id: DAG identifier
            dag_file_path: Optional path to the DAG file

        Returns:
            GitContext with recent commits and file-specific changes
        """
        self.logger.info("Collecting Git context", dag_id=dag_id)

        # Find DAG file if not provided
        if dag_file_path is None:
            dag_file_path = await self.find_dag_file(dag_id)
            if dag_file_path:
                self.logger.info("Found DAG file", path=dag_file_path)

        # Get recent commits
        recent_commits = await self.get_recent_commits()

        # Get commits for DAG file
        last_dag_commit = None
        hours_since_change = None

        if dag_file_path:
            file_commits = await self.get_commits_for_file(dag_file_path)
            if file_commits:
                last_dag_commit = file_commits[0]
                delta = datetime.utcnow() - last_dag_commit.date
                hours_since_change = delta.total_seconds() / 3600

        return GitContext(
            recent_commits=recent_commits,
            last_commit_touching_dag=last_dag_commit,
            dag_file_path=dag_file_path,
            hours_since_last_change=hours_since_change,
        )
