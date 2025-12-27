"""Source health checker for external dependencies."""

import asyncio
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from rca_agent.collectors.base import BaseCollector
from rca_agent.models.context import SourceHealth


class SourceHealthCollector(BaseCollector[list[SourceHealth]]):
    """Collector for checking health of data sources."""

    name = "source_health"

    def __init__(
        self,
        sources: list[dict[str, Any]] | None = None,
        timeout: int = 10,
        enabled: bool = True,
    ) -> None:
        """Initialize source health collector.

        Args:
            sources: List of source configurations. Each source should have:
                - name: Source identifier
                - type: "api", "database", "file"
                - url: URL to check (for API sources)
                - Or other type-specific config
            timeout: Request timeout in seconds
            enabled: Whether the collector is enabled
        """
        super().__init__(enabled=enabled)
        self.sources = sources or []
        self.timeout = timeout

    async def check_api_health(
        self,
        name: str,
        url: str,
        method: str = "GET",
        headers: dict | None = None,
        expected_status: int = 200,
    ) -> SourceHealth:
        """Check health of an API endpoint.

        Args:
            name: Source name
            url: URL to check
            method: HTTP method
            headers: Optional headers
            expected_status: Expected HTTP status code

        Returns:
            SourceHealth result
        """
        start_time = datetime.utcnow()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                start = asyncio.get_event_loop().time()
                response = await client.request(method, url, headers=headers)
                latency = (asyncio.get_event_loop().time() - start) * 1000

                reachable = response.status_code == expected_status
                error_message = None if reachable else f"HTTP {response.status_code}"

                return SourceHealth(
                    source_name=name,
                    source_type="api",
                    reachable=reachable,
                    latency_ms=latency,
                    error_message=error_message,
                    last_checked=start_time,
                )

        except httpx.TimeoutException:
            return SourceHealth(
                source_name=name,
                source_type="api",
                reachable=False,
                error_message="Timeout",
                last_checked=start_time,
            )
        except httpx.ConnectError as e:
            return SourceHealth(
                source_name=name,
                source_type="api",
                reachable=False,
                error_message=f"Connection failed: {e}",
                last_checked=start_time,
            )
        except Exception as e:
            return SourceHealth(
                source_name=name,
                source_type="api",
                reachable=False,
                error_message=str(e),
                last_checked=start_time,
            )

    async def check_database_health(
        self,
        name: str,
        connection_string: str,
    ) -> SourceHealth:
        """Check health of a database connection.

        Note: This is a simplified check. In production, you'd use
        the appropriate database driver.

        Args:
            name: Source name
            connection_string: Database connection string

        Returns:
            SourceHealth result
        """
        # Parse connection string to extract host/port
        # This is a placeholder - real implementation would use actual DB drivers
        start_time = datetime.utcnow()

        try:
            # Extract host from connection string
            # Format: postgresql://user:pass@host:port/db
            parsed = urlparse(connection_string)
            host = parsed.hostname or "localhost"
            port = parsed.port or 5432

            # Simple TCP check
            start = asyncio.get_event_loop().time()
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=self.timeout,
            )
            latency = (asyncio.get_event_loop().time() - start) * 1000
            writer.close()
            await writer.wait_closed()

            return SourceHealth(
                source_name=name,
                source_type="database",
                reachable=True,
                latency_ms=latency,
                last_checked=start_time,
            )

        except TimeoutError:
            return SourceHealth(
                source_name=name,
                source_type="database",
                reachable=False,
                error_message="Connection timeout",
                last_checked=start_time,
            )
        except Exception as e:
            return SourceHealth(
                source_name=name,
                source_type="database",
                reachable=False,
                error_message=str(e),
                last_checked=start_time,
            )

    async def check_source(self, source_config: dict[str, Any]) -> SourceHealth:
        """Check health of a single source based on its configuration.

        Args:
            source_config: Source configuration dict

        Returns:
            SourceHealth result
        """
        source_type = source_config.get("type", "api")
        name = source_config.get("name", "unknown")

        if source_type == "api":
            return await self.check_api_health(
                name=name,
                url=source_config["url"],
                method=source_config.get("method", "GET"),
                headers=source_config.get("headers"),
                expected_status=source_config.get("expected_status", 200),
            )
        elif source_type == "database":
            return await self.check_database_health(
                name=name,
                connection_string=source_config["connection_string"],
            )
        else:
            return SourceHealth(
                source_name=name,
                source_type=source_type,
                reachable=False,
                error_message=f"Unknown source type: {source_type}",
            )

    async def collect(
        self,
        sources: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> list[SourceHealth]:
        """Check health of all configured sources.

        Args:
            sources: Optional override of source configurations

        Returns:
            List of SourceHealth results
        """
        sources_to_check = sources or self.sources

        if not sources_to_check:
            self.logger.info("No sources configured for health check")
            return []

        self.logger.info("Checking source health", count=len(sources_to_check))

        # Check all sources in parallel
        tasks = [self.check_source(src) for src in sources_to_check]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        health_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(
                    "Source check failed",
                    source=sources_to_check[i].get("name"),
                    error=str(result),
                )
                health_results.append(
                    SourceHealth(
                        source_name=sources_to_check[i].get("name", "unknown"),
                        source_type=sources_to_check[i].get("type", "unknown"),
                        reachable=False,
                        error_message=str(result),
                    )
                )
            else:
                health_results.append(result)

        return health_results
