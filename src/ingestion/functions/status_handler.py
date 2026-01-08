"""
Status Handler Azure Function.

HTTP trigger for GET /api/v1/documents/{document_id}/status endpoint.
Provides real-time processing status tracking for uploaded documents.

Supports Constitution Principle III (Auditability with transparent processing).
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from functools import lru_cache

import azure.functions as func

from src.shared.config import config
from src.shared.exceptions import DocumentNotFoundError, StorageError
from src.shared.telemetry import telemetry
from src.ingestion.services.cosmos_manager import CosmosManager
from src.ingestion.utils.audit_logger import audit_logger


# Initialize services
cosmos_manager = CosmosManager()
logger = logging.getLogger("status_handler")
logger.setLevel(logging.INFO)

# Simple in-memory cache for status queries (10-second TTL)
_status_cache: Dict[str, tuple[Dict[str, Any], datetime]] = {}
CACHE_TTL_SECONDS = 10


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Handle document status query requests.

    Route: GET /api/v1/documents/{document_id}/status

    Response format:
    {
        "document_id": "doc-abc123",
        "status": "completed",  // queued, processing, completed, failed
        "progress": {
            "current_stage": "validation",
            "stages_completed": ["upload", "ingestion", "extraction"],
            "completion_percentage": 75
        },
        "extraction_summary": {
            "tables_extracted": 5,
            "metrics_extracted": 25,
            "ocr_confidence": 0.92
        },
        "validation_status": "passed",  // passed, flagged, failed
        "timestamps": {
            "uploaded_at": "2024-01-15T10:30:00Z",
            "started_processing_at": "2024-01-15T10:30:05Z",
            "completed_at": "2024-01-15T10:33:45Z"
        },
        "estimated_completion_time": null,  // ISO timestamp or null if complete
        "error_message": null  // Error details if status is "failed"
    }

    Args:
        req: HTTP request with document_id in route

    Returns:
        HTTP response with status information
    """
    logger.info("Document status query received")

    try:
        # Extract document_id from route parameter
        document_id = req.route_params.get("document_id")
        if not document_id:
            return func.HttpResponse(
                body=json.dumps({"error": "document_id is required in URL path"}),
                status_code=400,
                mimetype="application/json",
            )

        # Extract user identity for audit logging
        user_id = req.headers.get("X-MS-CLIENT-PRINCIPAL-ID", "unknown-user")

        # Check cache first (T085)
        cached_status = _get_cached_status(document_id)
        if cached_status:
            logger.info(f"Returning cached status for document: {document_id}")
            return func.HttpResponse(
                body=json.dumps(cached_status),
                status_code=200,
                mimetype="application/json",
            )

        # Query processing logs to determine status (T078, T079)
        processing_logs = cosmos_manager.query_processing_logs_by_document(
            document_id=document_id, limit=20
        )

        if not processing_logs:
            raise DocumentNotFoundError(
                document_id=document_id,
                message=f"No processing records found for document: {document_id}"
            )

        # Determine current status from logs (T079)
        status_info = _determine_status_from_logs(processing_logs, document_id)

        # If processing or completed, get extraction summary (T080, T081)
        if status_info["status"] in ["processing", "completed"]:
            extraction_summary = _get_extraction_summary(document_id)
            status_info["extraction_summary"] = extraction_summary

        # If completed, get validation status (T081)
        if status_info["status"] == "completed":
            validation_status = _get_validation_status(document_id)
            status_info["validation_status"] = validation_status

        # If failed, get error details (T082)
        if status_info["status"] == "failed":
            error_details = _get_error_details(processing_logs)
            status_info["error_message"] = error_details

        # Calculate estimated completion time if processing (T083)
        if status_info["status"] == "processing":
            estimated_time = _calculate_estimated_completion(processing_logs)
            status_info["estimated_completion_time"] = estimated_time

        # Cache the status (T085)
        _cache_status(document_id, status_info)

        # Log audit event (T086)
        audit_logger.log_document_view(
            user_id=user_id,
            document_id=document_id,
            view_type="status"
        )

        logger.info(f"Status query completed for document: {document_id}")

        return func.HttpResponse(
            body=json.dumps(status_info, default=str),
            status_code=200,
            mimetype="application/json",
        )

    except DocumentNotFoundError as e:
        logger.warning(f"Document not found: {e}")
        return func.HttpResponse(
            body=json.dumps(
                {"error": str(e), "error_type": "document_not_found"}
            ),
            status_code=404,
            mimetype="application/json",
        )

    except StorageError as e:
        logger.error(f"Storage error during status query: {e}")
        telemetry.track_exception(e, properties={"error_type": "storage"})
        return func.HttpResponse(
            body=json.dumps(
                {"error": "Failed to retrieve document status", "error_type": "storage_error"}
            ),
            status_code=500,
            mimetype="application/json",
        )

    except Exception as e:
        logger.exception(f"Unexpected error during status query: {e}")
        telemetry.track_exception(e, properties={"error_type": "unexpected"})
        return func.HttpResponse(
            body=json.dumps(
                {"error": "Internal server error", "error_type": "server_error"}
            ),
            status_code=500,
            mimetype="application/json",
        )


def _get_cached_status(document_id: str) -> Optional[Dict[str, Any]]:
    """
    Get cached status if available and not expired.

    Args:
        document_id: Document identifier

    Returns:
        Cached status dict or None if not cached or expired
    """
    if document_id in _status_cache:
        cached_data, cached_time = _status_cache[document_id]
        age_seconds = (datetime.utcnow() - cached_time).total_seconds()

        if age_seconds < CACHE_TTL_SECONDS:
            return cached_data
        else:
            # Expired - remove from cache
            del _status_cache[document_id]

    return None


def _cache_status(document_id: str, status_info: Dict[str, Any]) -> None:
    """
    Cache status information with timestamp.

    Args:
        document_id: Document identifier
        status_info: Status information to cache
    """
    _status_cache[document_id] = (status_info, datetime.utcnow())


def _determine_status_from_logs(
    processing_logs: list, document_id: str
) -> Dict[str, Any]:
    """
    Determine current processing status from logs.

    Processing stages:
    1. queued (ingestion_started or queued)
    2. processing (extraction_started or validation_started)
    3. completed (validation_completed)
    4. failed (failed event)

    Args:
        processing_logs: List of processing log entries (newest first)
        document_id: Document identifier

    Returns:
        Status information dictionary
    """
    # Get the latest event
    latest_log = processing_logs[0] if processing_logs else None
    latest_event = latest_log.get("event_type") if latest_log else None

    # Collect all event types for progress calculation
    all_events = {log.get("event_type") for log in processing_logs}

    # Determine status
    if "failed" in all_events:
        status = "failed"
    elif "validation_completed" in all_events:
        status = "completed"
    elif "validation_started" in all_events or "extraction_started" in all_events:
        status = "processing"
    elif "queued" in all_events or "ingestion_started" in all_events:
        status = "queued"
    else:
        status = "unknown"

    # Calculate progress
    progress = _calculate_progress(all_events)

    # Extract timestamps
    timestamps = _extract_timestamps(processing_logs)

    return {
        "document_id": document_id,
        "status": status,
        "progress": progress,
        "timestamps": timestamps,
    }


def _calculate_progress(events: set) -> Dict[str, Any]:
    """
    Calculate processing progress from events.

    Args:
        events: Set of event types

    Returns:
        Progress information
    """
    # Define stages in order
    stages = [
        ("upload", ["queued"]),
        ("ingestion", ["ingestion_started"]),
        ("extraction", ["extraction_started", "extraction_completed"]),
        ("validation", ["validation_started", "validation_completed"]),
    ]

    completed_stages = []
    current_stage = None

    for stage_name, stage_events in stages:
        if any(event in events for event in stage_events):
            completed_stages.append(stage_name)
            current_stage = stage_name

    # Calculate percentage
    total_stages = len(stages)
    completion_percentage = int((len(completed_stages) / total_stages) * 100)

    return {
        "current_stage": current_stage or "queued",
        "stages_completed": completed_stages,
        "completion_percentage": completion_percentage,
    }


def _extract_timestamps(processing_logs: list) -> Dict[str, Optional[str]]:
    """
    Extract key timestamps from processing logs.

    Args:
        processing_logs: List of processing log entries

    Returns:
        Dictionary of timestamps
    """
    timestamps = {
        "uploaded_at": None,
        "started_processing_at": None,
        "completed_at": None,
    }

    # Find specific events
    for log in reversed(processing_logs):  # Oldest first
        event_type = log.get("event_type")
        event_time = log.get("event_timestamp")

        if event_type in ["queued", "ingestion_started"] and not timestamps["uploaded_at"]:
            timestamps["uploaded_at"] = event_time

        if event_type == "extraction_started" and not timestamps["started_processing_at"]:
            timestamps["started_processing_at"] = event_time

        if event_type == "validation_completed":
            timestamps["completed_at"] = event_time

    return timestamps


def _get_extraction_summary(document_id: str) -> Optional[Dict[str, Any]]:
    """
    Get extraction summary from Cosmos DB.

    Args:
        document_id: Document identifier

    Returns:
        Extraction summary or None if not available
    """
    try:
        # Query for extraction results
        query = "SELECT * FROM c WHERE c.document_id = @document_id AND c.extraction_status = 'completed'"
        parameters = [{"name": "@document_id", "value": document_id}]

        results = list(
            cosmos_manager.extraction_results_container.query_items(
                query=query,
                parameters=parameters,
                partition_key=document_id,
                enable_cross_partition_query=False,
            )
        )

        if results:
            extraction_result = results[0]
            return {
                "tables_extracted": extraction_result.get("tables_extracted", 0),
                "metrics_extracted": extraction_result.get("metrics_extracted", 0),
                "ocr_confidence": extraction_result.get("ocr_confidence_avg", 0.0),
            }

    except Exception as e:
        logger.warning(f"Failed to get extraction summary: {e}")

    return None


def _get_validation_status(document_id: str) -> Optional[str]:
    """
    Get validation status from Cosmos DB.

    Args:
        document_id: Document identifier

    Returns:
        Validation status (passed, flagged, failed) or None
    """
    try:
        query = "SELECT c.validation_status FROM c WHERE c.document_id = @document_id"
        parameters = [{"name": "@document_id", "value": document_id}]

        results = list(
            cosmos_manager.extraction_results_container.query_items(
                query=query,
                parameters=parameters,
                partition_key=document_id,
                enable_cross_partition_query=False,
            )
        )

        if results and results[0].get("validation_status"):
            return results[0].get("validation_status")

    except Exception as e:
        logger.warning(f"Failed to get validation status: {e}")

    return None


def _get_error_details(processing_logs: list) -> Optional[str]:
    """
    Extract error details from failed processing logs.

    Args:
        processing_logs: List of processing log entries

    Returns:
        Error message or None
    """
    for log in processing_logs:
        if log.get("event_type") == "failed":
            event_data = log.get("event_data", {})
            return event_data.get("error", "Unknown error occurred")

    return None


def _calculate_estimated_completion(processing_logs: list) -> Optional[str]:
    """
    Calculate estimated completion time based on processing history.

    Uses average processing time for similar documents (simplified version).

    Args:
        processing_logs: List of processing log entries

    Returns:
        Estimated completion time (ISO format) or None
    """
    try:
        # Find when processing started
        start_time = None
        for log in reversed(processing_logs):
            if log.get("event_type") == "extraction_started":
                start_time = log.get("event_timestamp")
                break

        if start_time and isinstance(start_time, str):
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))

            # Use configured processing timeout as estimate
            estimated_minutes = config.processing_timeout_minutes
            estimated_completion = start_dt.replace(tzinfo=None) + timedelta(minutes=estimated_minutes)

            # Only return if in the future
            if estimated_completion > datetime.utcnow():
                return estimated_completion.isoformat() + "Z"

    except Exception as e:
        logger.warning(f"Failed to calculate estimated completion: {e}")

    return None


# Import timedelta for estimated completion calculation
from datetime import timedelta
