"""
Application Insights telemetry integration.

This module provides custom metric tracking and logging for monitoring
document ingestion performance and quality, supporting Constitution
Principle III (Auditability) and operational excellence.
"""

import logging
from typing import Any, Dict, Optional

from azure.monitor.opentelemetry import configure_azure_monitor

from src.shared.config import config


class TelemetryClient:
    """Client for tracking custom metrics and events in Application Insights."""

    def __init__(self) -> None:
        """Initialize telemetry client with Application Insights configuration."""
        self.logger = logging.getLogger("financial_insights")
        self.logger.setLevel(logging.INFO)

        # Configure Azure Monitor if connection string is available
        if config.appinsights_connection_string:
            try:
                configure_azure_monitor(connection_string=config.appinsights_connection_string)
                self.logger.info("Application Insights telemetry initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize Application Insights: {e}")

    def track_metric(
        self, name: str, value: float, properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track a custom metric in Application Insights.

        Args:
            name: Metric name (e.g., "extraction_duration_seconds")
            value: Metric value
            properties: Optional additional properties for context
        """
        properties = properties or {}
        self.logger.info(f"Metric: {name}={value}", extra={"custom_dimensions": properties})

    def track_event(
        self, name: str, properties: Optional[Dict[str, Any]] = None, measurements: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Track a custom event in Application Insights.

        Args:
            name: Event name (e.g., "document_uploaded", "extraction_completed")
            properties: Optional event properties
            measurements: Optional numeric measurements
        """
        properties = properties or {}
        measurements = measurements or {}

        log_data = {**properties, **measurements}
        self.logger.info(f"Event: {name}", extra={"custom_dimensions": log_data})

    def track_exception(
        self, exception: Exception, properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track an exception in Application Insights.

        Args:
            exception: Exception instance to log
            properties: Optional context properties
        """
        properties = properties or {}
        self.logger.exception(
            f"Exception: {type(exception).__name__}", exc_info=exception, extra={"custom_dimensions": properties}
        )

    def track_document_upload(self, document_id: str, file_type: str, file_size_mb: float) -> None:
        """
        Track a document upload event.

        Args:
            document_id: Unique document identifier
            file_type: File type (PDF or XLSX)
            file_size_mb: File size in megabytes
        """
        self.track_event(
            "document_uploaded",
            properties={"document_id": document_id, "file_type": file_type},
            measurements={"file_size_mb": file_size_mb},
        )

    def track_extraction_completed(
        self,
        document_id: str,
        duration_seconds: float,
        metrics_extracted: int,
        avg_confidence: float,
    ) -> None:
        """
        Track a document extraction completion event.

        Args:
            document_id: Unique document identifier
            duration_seconds: Extraction duration in seconds
            metrics_extracted: Number of financial metrics extracted
            avg_confidence: Average OCR confidence score (0.0-1.0)
        """
        self.track_event(
            "extraction_completed",
            properties={"document_id": document_id},
            measurements={
                "duration_seconds": duration_seconds,
                "metrics_extracted": metrics_extracted,
                "avg_confidence": avg_confidence,
            },
        )

    def track_validation_completed(
        self, document_id: str, validation_status: str, error_count: int, warning_count: int
    ) -> None:
        """
        Track a data validation completion event.

        Args:
            document_id: Unique document identifier
            validation_status: Validation outcome (passed, flagged, failed)
            error_count: Number of validation errors
            warning_count: Number of validation warnings
        """
        self.track_event(
            "validation_completed",
            properties={"document_id": document_id, "validation_status": validation_status},
            measurements={"error_count": error_count, "warning_count": warning_count},
        )


# Global telemetry client instance
telemetry = TelemetryClient()
