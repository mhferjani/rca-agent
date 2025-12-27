# Custom Collectors

RCA Agent uses a pluggable collector architecture. You can create custom collectors to gather context from any source.

## Collector Interface

All collectors inherit from `BaseCollector`:

```python
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

T = TypeVar("T")

class BaseCollector(ABC, Generic[T]):
    name: str = "base"

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    @abstractmethod
    async def collect(self, **kwargs: Any) -> T | None:
        """Collect data from the source."""
        ...

    async def safe_collect(self, **kwargs: Any) -> T | None:
        """Safely collect data with error handling."""
        if not self.enabled:
            return None
        try:
            return await self.collect(**kwargs)
        except Exception as e:
            self.logger.exception("Collection failed", error=str(e))
            return None
```

## Creating a Custom Collector

### Example: Prometheus Metrics Collector

```python
from datetime import datetime
from typing import Any

import httpx

from rca_agent.collectors.base import BaseCollector
from rca_agent.models.context import MetricsSnapshot


class PrometheusCollector(BaseCollector[MetricsSnapshot]):
    """Collector for Prometheus metrics."""

    name = "prometheus"

    def __init__(
        self,
        base_url: str,
        timeout: int = 10,
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def _query(self, query: str) -> float | None:
        """Execute a PromQL query."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/query",
                params={"query": query},
            )
            response.raise_for_status()
            data = response.json()

            if data["status"] == "success" and data["data"]["result"]:
                return float(data["data"]["result"][0]["value"][1])
            return None

    async def collect(
        self,
        job_name: str | None = None,
        **kwargs: Any,
    ) -> MetricsSnapshot:
        """Collect metrics at the time of failure."""

        # Query various metrics
        cpu = await self._query(
            f'100 - (avg(irate(node_cpu_seconds_total{{mode="idle"}}[5m])) * 100)'
        )
        memory = await self._query(
            '100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))'
        )
        disk = await self._query(
            '100 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} * 100)'
        )

        return MetricsSnapshot(
            timestamp=datetime.utcnow(),
            cpu_percent=cpu,
            memory_percent=memory,
            disk_percent=disk,
        )
```

### Example: Datadog Collector

```python
from datetime import datetime, timedelta
from typing import Any

import httpx

from rca_agent.collectors.base import BaseCollector


class DatadogCollector(BaseCollector[dict]):
    """Collector for Datadog metrics and events."""

    name = "datadog"

    def __init__(
        self,
        api_key: str,
        app_key: str,
        site: str = "datadoghq.com",
        enabled: bool = True,
    ) -> None:
        super().__init__(enabled=enabled)
        self.api_key = api_key
        self.app_key = app_key
        self.base_url = f"https://api.{site}"

    async def collect(
        self,
        dag_id: str,
        task_id: str,
        failure_time: datetime,
        **kwargs: Any,
    ) -> dict:
        """Collect metrics and events around failure time."""

        start = failure_time - timedelta(minutes=30)
        end = failure_time + timedelta(minutes=5)

        async with httpx.AsyncClient() as client:
            # Get events
            events_response = await client.get(
                f"{self.base_url}/api/v1/events",
                headers={
                    "DD-API-KEY": self.api_key,
                    "DD-APPLICATION-KEY": self.app_key,
                },
                params={
                    "start": int(start.timestamp()),
                    "end": int(end.timestamp()),
                    "tags": f"dag:{dag_id},task:{task_id}",
                },
            )
            events = events_response.json().get("events", [])

            return {
                "events": events,
                "time_range": {"start": start.isoformat(), "end": end.isoformat()},
            }
```

## Registering Custom Collectors

To use a custom collector, pass it when creating the agent:

```python
from rca_agent import RCAAgent
from rca_agent.agent import AgentConfig

# Create custom config
config = AgentConfig(
    enable_metrics_collector=True,
    # ... other config
)

# Create agent with custom collectors
agent = RCAAgent(config=config)

# Or modify the workflow directly
from rca_agent.agent.graph import RCAWorkflow

workflow = RCAWorkflow(config)
# Add custom nodes to workflow.graph
```

## Best Practices

1. **Error Handling**: Always use `safe_collect()` or handle exceptions
2. **Timeouts**: Set reasonable timeouts for external calls
3. **Logging**: Use structured logging via `self.logger`
4. **Optional Data**: Return `None` if data isn't available
5. **Async**: Use `async`/`await` for I/O operations
6. **Type Hints**: Define clear return types with generics
