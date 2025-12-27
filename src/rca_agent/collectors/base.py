"""Base collector interface."""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

import structlog

T = TypeVar("T")

logger = structlog.get_logger()


class BaseCollector(ABC, Generic[T]):
    """Abstract base class for all collectors."""

    name: str = "base"

    def __init__(self, enabled: bool = True) -> None:
        """Initialize collector.

        Args:
            enabled: Whether the collector is enabled.
        """
        self.enabled = enabled
        self.logger = logger.bind(collector=self.name)

    @abstractmethod
    async def collect(self, **kwargs: Any) -> T | None:
        """Collect data from the source.

        Returns:
            Collected data or None if collection failed.
        """
        ...

    async def safe_collect(self, **kwargs: Any) -> T | None:
        """Safely collect data, catching and logging exceptions.

        Returns:
            Collected data or None if collection failed.
        """
        if not self.enabled:
            self.logger.debug("Collector disabled, skipping")
            return None

        try:
            self.logger.info("Starting collection")
            result = await self.collect(**kwargs)
            self.logger.info("Collection completed", success=result is not None)
            return result
        except Exception as e:
            self.logger.exception("Collection failed", error=str(e))
            return None
