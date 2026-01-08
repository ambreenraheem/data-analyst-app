"""
Validation Worker Azure Function.

Service Bus trigger for validation-queue.
Validates extracted financial data for completeness, reasonableness,
and confidence thresholds.

Supports Constitution Principles II (Confidence Thresholds) and
VI (Human-in-the-Loop for High-Stakes Decisions).
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict

import azure.functions as func

from src.shared.config import config
from src.shared.exceptions import DocumentNotFoundError, StorageError
from src.shared.telemetry import telemetry
from src.ingestion.services.cosmos_manager import CosmosManager
from src.ingestion.services.validator import validator
from src.ingestion.models.processing_log import ProcessingLog


# Initialize services
cosmos_manager = CosmosManager()
logger = logging.getLogger("validation_worker")
logger.setLevel(logging.INFO)


def main(msg: func.ServiceBusMessage) -> None:
    """
    Process validation queue messages.

    Message format:
    {
        "document_id": "doc-abc123",
        "extraction_result_id": "extraction-xyz789",
        "queued_at": "2024-01-15T10:35:00Z"
    }

    Args:
        msg: Service Bus message from validation-queue
    """
    try:
        # Parse message
        message_body = msg.get_body().decode("utf-8")
        message_data = json.loads(message_body)

        document_id = message_data["document_id"]
        extraction_result_id = message_data["extraction_result_id"]

        logger.info(f"Starting validation for document: {document_id}")

        # Log validation started
        _create_processing_log(
            document_id=document_id,
            event_type="validation_started",
            event_data={
                "extraction_result_id": extraction_result_id,
            },
        )

        # Retrieve extraction result and metrics from Cosmos DB (T070)
        extraction_result = cosmos_manager.get_extraction_result(
            result_id=extraction_result_id,
            document_id=document_id
        )

        metrics = cosmos_manager.query_metrics_by_document(document_id=document_id)

        logger.info(
            f"Retrieved extraction result and {len(metrics)} metrics for validation"
        )

        # Run completeness validation (T071)
        # Run range validation (T072)
        # Run confidence validation (T073)
        # Run all validations together
        validation_result = validator.validate_all(
            metrics=metrics,
            extraction_result=extraction_result
        )

        logger.info(
            f"Validation completed: status={validation_result.validation_status}, "
            f"errors={len(validation_result.errors)}, "
            f"warnings={len(validation_result.warnings)}"
        )

        # Update extraction result with validation status (T074)
        updates = {
            "validation_status": validation_result.validation_status,
            "validation_errors": validation_result.errors,
            "validation_warnings": validation_result.warnings,
            "requires_manual_review": validation_result.requires_manual_review(),
        }

        cosmos_manager.update_extraction_result(
            result_id=extraction_result_id,
            document_id=document_id,
            updates=updates
        )

        logger.info(f"Updated extraction result with validation status")

        # Update metrics that require manual review (T076)
        if validation_result.requires_manual_review():
            _flag_low_confidence_metrics(metrics, document_id)

        # Log validation completed (T075)
        _create_processing_log(
            document_id=document_id,
            event_type="validation_completed",
            event_data={
                "extraction_result_id": extraction_result_id,
                "validation_status": validation_result.validation_status,
                "error_count": len(validation_result.errors),
                "warning_count": len(validation_result.warnings),
                "requires_manual_review": validation_result.requires_manual_review(),
            },
        )

        # Track telemetry
        telemetry.track_validation_completed(
            document_id=document_id,
            validation_status=validation_result.validation_status,
            error_count=len(validation_result.errors),
            warning_count=len(validation_result.warnings),
        )

        logger.info(f"Validation completed successfully for document: {document_id}")

    except DocumentNotFoundError as e:
        logger.error(f"Document not found during validation: {e}")
        telemetry.track_exception(e, properties={"error_type": "document_not_found"})
        _create_processing_log(
            document_id=message_data.get("document_id", "unknown"),
            event_type="failed",
            event_data={
                "error": str(e),
                "error_type": "document_not_found",
                "stage": "validation"
            },
        )
        raise  # Let Service Bus handle retry/dead-letter

    except StorageError as e:
        logger.error(f"Storage error during validation: {e}")
        telemetry.track_exception(e, properties={"error_type": "storage"})
        _create_processing_log(
            document_id=message_data.get("document_id", "unknown"),
            event_type="failed",
            event_data={
                "error": str(e),
                "error_type": "storage_error",
                "stage": "validation"
            },
        )
        raise  # Let Service Bus handle retry/dead-letter

    except Exception as e:
        logger.exception(f"Unexpected error during validation: {e}")
        telemetry.track_exception(e, properties={"error_type": "unexpected"})
        _create_processing_log(
            document_id=message_data.get("document_id", "unknown"),
            event_type="failed",
            event_data={
                "error": str(e),
                "error_type": "unexpected_error",
                "stage": "validation"
            },
        )
        raise  # Let Service Bus handle retry/dead-letter


def _flag_low_confidence_metrics(metrics: list, document_id: str) -> None:
    """
    Flag metrics that have low confidence for manual review.

    Updates the flagged_for_review field in Cosmos DB.

    Args:
        metrics: List of metric dictionaries
        document_id: Document identifier
    """
    metric_threshold = config.ocr_confidence_threshold_metric
    flagged_count = 0

    for metric in metrics:
        metric_id = metric.get("id")
        confidence = metric.get("confidence_score", 1.0)

        # Check if should be flagged
        if confidence < metric_threshold and not metric.get("flagged_for_review", False):
            try:
                # Update metric in Cosmos DB
                cosmos_manager.financial_metrics_container.patch_item(
                    item=metric_id,
                    partition_key=document_id,
                    patch_operations=[
                        {"op": "replace", "path": "/flagged_for_review", "value": True}
                    ]
                )
                flagged_count += 1
            except Exception as e:
                logger.warning(f"Failed to flag metric {metric_id} for review: {e}")

    if flagged_count > 0:
        logger.info(f"Flagged {flagged_count} metrics for manual review")


def _create_processing_log(
    document_id: str, event_type: str, event_data: Dict[str, Any]
) -> None:
    """
    Create a processing log entry in Cosmos DB.

    Args:
        document_id: Document identifier
        event_type: Event type (validation_started, validation_completed, failed)
        event_data: Additional event data
    """
    try:
        log_entry = ProcessingLog(
            id=f"log-{uuid.uuid4()}",
            document_id=document_id,
            event_type=event_type,
            event_timestamp=datetime.utcnow(),
            event_data=event_data,
            function_name="validation_worker",
            execution_id=None,
        )

        cosmos_manager.create_processing_log(log_entry.model_dump(mode="json"))
        logger.info(f"Created processing log: {event_type} for document {document_id}")

    except Exception as e:
        # Log error but don't fail the function
        logger.error(f"Failed to create processing log: {e}")
