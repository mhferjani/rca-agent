"""Incident store using ChromaDB for RAG-based similar incident retrieval."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import chromadb
import structlog

from rca_agent.models.reports import ErrorCategory, RCAReport, SimilarIncident

logger = structlog.get_logger()


class IncidentStore:
    """ChromaDB-backed store for past incidents."""

    def __init__(
        self,
        persist_directory: str | Path = "./data/chroma",
        collection_name: str = "rca_incidents",
    ) -> None:
        """Initialize incident store.

        Args:
            persist_directory: Directory for ChromaDB persistence
            collection_name: Name of the collection
        """
        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name
        self.logger = logger.bind(component="incident_store")

        # Ensure directory exists
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(path=str(self.persist_directory))

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "RCA incident history"},
        )

        self.logger.info(
            "Initialized incident store",
            persist_dir=str(self.persist_directory),
            collection=collection_name,
        )

    def _create_embedding_text(self, report: RCAReport) -> str:
        """Create text representation for embedding.

        Args:
            report: RCA report

        Returns:
            Text to embed
        """
        parts = [
            f"DAG: {report.dag_id}",
            f"Task: {report.task_id}",
            f"Category: {report.error_category.value}",
            f"Root cause: {report.root_cause}",
        ]

        if report.evidence:
            parts.append(f"Evidence: {'; '.join(report.evidence[:3])}")

        if report.key_log_lines:
            parts.append(f"Key logs: {' '.join(report.key_log_lines[:5])}")

        return "\n".join(parts)

    def add_incident(
        self,
        report: RCAReport,
        resolution: str | None = None,
    ) -> str:
        """Add a new incident to the store.

        Args:
            report: RCA report from analysis
            resolution: Optional resolution description

        Returns:
            Incident ID
        """
        incident_id = report.report_id

        # Create metadata
        metadata: dict[str, Any] = {
            "dag_id": report.dag_id,
            "task_id": report.task_id,
            "run_id": report.run_id,
            "error_category": report.error_category.value,
            "severity": report.severity.value,
            "confidence": report.confidence,
            "date": report.failure_time.isoformat(),
            "root_cause_summary": report.root_cause_summary,
        }

        if resolution:
            metadata["resolution"] = resolution

        # Create embedding text
        embedding_text = self._create_embedding_text(report)

        # Store full report as document
        document = json.dumps(
            {
                "root_cause": report.root_cause,
                "evidence": report.evidence,
                "recommendations": [r.model_dump() for r in report.recommendations],
                "resolution": resolution,
            }
        )

        self.collection.add(
            ids=[incident_id],
            documents=[document],
            metadatas=[metadata],
        )

        self.logger.info(
            "Added incident to store",
            incident_id=incident_id,
            dag_id=report.dag_id,
        )

        return incident_id

    def find_similar(
        self,
        dag_id: str,
        task_id: str,
        error_text: str,
        error_category: ErrorCategory | None = None,
        max_results: int = 5,
    ) -> list[SimilarIncident]:
        """Find similar past incidents.

        Args:
            dag_id: Current DAG ID
            task_id: Current task ID
            error_text: Error message or log excerpt
            error_category: Optional category filter
            max_results: Maximum results to return

        Returns:
            List of similar incidents
        """
        # Build query text
        query_text = f"DAG: {dag_id}\nTask: {task_id}\nError: {error_text}"

        # Build where filter
        where_filter: dict[str, Any] | None = None
        if error_category:
            where_filter = {"error_category": error_category.value}

        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=max_results,
                where=where_filter,
            )
        except Exception as e:
            self.logger.error("Failed to query incident store", error=str(e))
            return []

        if not results["ids"] or not results["ids"][0]:
            return []

        similar_incidents = []
        for i, incident_id in enumerate(results["ids"][0]):
            metadata = results["metadatas"][0][i]
            document = json.loads(results["documents"][0][i])

            # Calculate similarity score (ChromaDB returns distances)
            distance = results["distances"][0][i] if results.get("distances") else 0.5
            similarity_score = max(0.0, min(1.0, 1.0 - distance))

            similar_incidents.append(
                SimilarIncident(
                    incident_id=incident_id,
                    date=datetime.fromisoformat(metadata["date"]),
                    dag_id=metadata["dag_id"],
                    task_id=metadata["task_id"],
                    error_category=ErrorCategory(metadata["error_category"]),
                    root_cause=document.get("root_cause", metadata["root_cause_summary"]),
                    resolution=document.get("resolution") or metadata.get("resolution"),
                    similarity_score=similarity_score,
                )
            )

        # Sort by similarity score
        similar_incidents.sort(key=lambda x: x.similarity_score, reverse=True)

        self.logger.info(
            "Found similar incidents",
            count=len(similar_incidents),
            dag_id=dag_id,
        )

        return similar_incidents

    def update_resolution(
        self,
        incident_id: str,
        resolution: str,
    ) -> bool:
        """Update the resolution for an incident.

        Args:
            incident_id: Incident ID
            resolution: Resolution description

        Returns:
            True if updated successfully
        """
        try:
            # Get current data
            result = self.collection.get(ids=[incident_id])
            if not result["ids"]:
                return False

            # Update metadata
            metadata = result["metadatas"][0]
            metadata["resolution"] = resolution

            # Update document
            document = json.loads(result["documents"][0])
            document["resolution"] = resolution

            self.collection.update(
                ids=[incident_id],
                documents=[json.dumps(document)],
                metadatas=[metadata],
            )

            self.logger.info("Updated incident resolution", incident_id=incident_id)
            return True

        except Exception as e:
            self.logger.error(
                "Failed to update resolution",
                incident_id=incident_id,
                error=str(e),
            )
            return False

    def get_statistics(self) -> dict[str, Any]:
        """Get statistics about stored incidents.

        Returns:
            Dictionary of statistics
        """
        count = self.collection.count()

        # Get category distribution (simplified)
        stats = {
            "total_incidents": count,
            "collection_name": self.collection_name,
        }

        return stats

    def persist(self) -> None:
        """Persist the database to disk."""
        pass
