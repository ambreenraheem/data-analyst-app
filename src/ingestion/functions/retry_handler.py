"""
Retry Handler Azure Function.

HTTP trigger for POST /api/v1/documents/{document_id}/retry endpoint.
Enables retry of failed document ingestions without re-uploading.

Supports Constitution Principle III (Auditability) and operational resilience.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import azure.functions as func
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.identity import DefaultAzureCredential

from src.shared.config import config
from src.shared.exceptions import DocumentNotFoundError, StorageError
from src.shared.telemetry import telemetry
from src.ingestion.services.cosmos_manager import CosmosManager
from src.ingestion.services.storage_manager import StorageManager
from src.ingestion.models.processing_log import ProcessingLog
from src.ingestion.utils.audit_logger import audit_logger


# Initialize services
cosmos_manager = CosmosManager()
storage_manager = StorageManager()
logger = logging.getLogger("retry_handler")
logger.setLevel(logging.INFO)


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Handle document retry requests.

    Route: POST /api/v1/documents/{document_id}/retry

    Request body (JSON):
    {
        "enhanced_ocr": false  // Optional: Use enhanced OCR settings
    }

    Response format:
    {
        "document_id": "doc-abc123",
        "status": "retry_queued",
        "message": "Document queued for retry processing",
        "retry_count": 2,
        "enhanced_ocr": false
    }

    Args:
        req: HTTP request with document_id in route

    Returns:
        HTTP response with retry status
    """
    logger.info("Document retry request received")

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

        # Parse request body
        try:
            request_body = req.get_json()
        except ValueError:
            request_body = {}

        enhanced_ocr = request_body.get("enhanced_ocr", False)

        logger.info(
            f"Retry requested for document: {document_id}, enhanced_ocr={enhanced_ocr}"
        )

        # Check retry eligibility (T094)
        retry_eligibility = _check_retry_eligibility(document_id)

        if not retry_eligibility["eligible"]:
            return func.HttpResponse(
                body=json.dumps({
                    "error": retry_eligibility["reason"],
                    "error_type": "retry_not_eligible",
                    "current_status": retry_eligibility.get("current_status"),
                    "message": "Document cannot be retried. " + retry_eligibility["reason"]
                }),
                status_code=400,
                mimetype="application/json",
            )

        # Verify blob existence (T095)
        document_info = retry_eligibility["document_info"]
        blob_exists = _verify_blob_existence(document_id, document_info)

        if not blob_exists:
            return func.HttpResponse(
                body=json.dumps({
                    "error": "Original document no longer exists in Blob Storage",
                    "error_type": "blob_not_found",
                    "message": "Document has been deleted or expired. Please re-upload the document."
                }),
                status_code=404,
                mimetype="application/json",
            )

        # Get current retry count
        retry_count = _get_retry_count(document_id)
        new_retry_count = retry_count + 1

        logger.info(f"Document retry count: {retry_count} → {new_retry_count}")

        # Re-queue to extraction queue (T097)
        _enqueue_for_retry(
            document_id=document_id,
            document_info=document_info,
            enhanced_ocr=enhanced_ocr,
            retry_count=new_retry_count
        )

        # Create processing log for retry (T098)
        _create_processing_log(
            document_id=document_id,
            retry_count=new_retry_count,
            enhanced_ocr=enhanced_ocr,
            user_id=user_id
        )

        # Log audit event (T100)
        audit_logger.log_document_retry(
            user_id=user_id,
            document_id=document_id,
            retry_count=new_retry_count
        )

        # Track telemetry
        telemetry.track_event(
            "document_retry",
            properties={
                "document_id": document_id,
                "retry_count": new_retry_count,
                "enhanced_ocr": enhanced_ocr
            }
        )

        logger.info(f"Retry queued successfully for document: {document_id}")

        return func.HttpResponse(
            body=json.dumps({
                "document_id": document_id,
                "status": "retry_queued",
                "message": "Document queued for retry processing",
                "retry_count": new_retry_count,
                "enhanced_ocr": enhanced_ocr,
                "estimated_processing_time_minutes": config.processing_timeout_minutes
            }),
            status_code=202,  # Accepted
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
        logger.error(f"Storage error during retry: {e}")
        telemetry.track_exception(e, properties={"error_type": "storage"})
        return func.HttpResponse(
            body=json.dumps(
                {"error": "Failed to queue document for retry", "error_type": "storage_error"}
            ),
            status_code=500,
            mimetype="application/json",
        )

    except Exception as e:
        logger.exception(f"Unexpected error during retry: {e}")
        telemetry.track_exception(e, properties={"error_type": "unexpected"})
        return func.HttpResponse(
            body=json.dumps(
                {"error": "Internal server error", "error_type": "server_error"}
            ),
            status_code=500,
            mimetype="application/json",
        )


def _check_retry_eligibility(document_id: str) -> Dict[str, Any]:
    """
    Check if document is eligible for retry.

    A document is eligible for retry if:
    - It exists in the system
    - Its status is "failed"
    - It has not exceeded maximum retry attempts (e.g., 3 retries)

    Args:
        document_id: Document identifier

    Returns:
        Dictionary with eligibility status and reason
    """
    try:
        # Get processing logs to determine current status
        processing_logs = cosmos_manager.query_processing_logs_by_document(
            document_id=document_id, limit=20
        )

        if not processing_logs:
            return {
                "eligible": False,
                "reason": "Document not found in processing logs",
                "current_status": "unknown"
            }

        # Check if document has failed
        latest_log = processing_logs[0]
        event_types = {log.get("event_type") for log in processing_logs}

        # Determine current status
        if "failed" not in event_types:
            # Check if already completed
            if "validation_completed" in event_types:
                return {
                    "eligible": False,
                    "reason": "Document processing already completed successfully",
                    "current_status": "completed"
                }
            else:
                return {
                    "eligible": False,
                    "reason": "Document is still processing or not in failed state",
                    "current_status": "processing"
                }

        # Get document information from logs
        document_info = {}
        for log in reversed(processing_logs):  # Oldest first
            event_data = log.get("event_data", {})
            if "document_name" in event_data:
                document_info["document_name"] = event_data["document_name"]
            if "document_type" in event_data:
                document_info["document_type"] = event_data["document_type"]
            if document_info.get("document_name") and document_info.get("document_type"):
                break

        if not document_info:
            return {
                "eligible": False,
                "reason": "Document metadata not found in processing logs",
                "current_status": "failed"
            }

        # Check retry count (limit to 5 retries)
        retry_count = sum(1 for log in processing_logs if log.get("event_type") == "retry_initiated")
        if retry_count >= 5:
            return {
                "eligible": False,
                "reason": f"Maximum retry attempts exceeded (5 retries already attempted)",
                "current_status": "failed",
                "retry_count": retry_count
            }

        # Document is eligible for retry
        return {
            "eligible": True,
            "reason": "Document failed and is eligible for retry",
            "current_status": "failed",
            "document_info": document_info
        }

    except Exception as e:
        logger.error(f"Failed to check retry eligibility: {e}")
        return {
            "eligible": False,
            "reason": f"Failed to check eligibility: {str(e)}",
            "current_status": "unknown"
        }


def _verify_blob_existence(document_id: str, document_info: Dict[str, Any]) -> bool:
    """
    Verify that the original document still exists in Blob Storage.

    Args:
        document_id: Document identifier
        document_info: Document metadata (document_type, etc.)

    Returns:
        True if blob exists, False otherwise
    """
    try:
        document_type = document_info.get("document_type", "PDF")
        file_extension = ".pdf" if document_type == "PDF" else ".xlsx"

        # Try to download (just check existence)
        _ = storage_manager.download_document(document_id, file_extension)
        return True

    except DocumentNotFoundError:
        logger.warning(f"Blob not found for document: {document_id}")
        return False
    except Exception as e:
        logger.error(f"Failed to verify blob existence: {e}")
        return False


def _get_retry_count(document_id: str) -> int:
    """
    Get the current retry count for a document.

    Args:
        document_id: Document identifier

    Returns:
        Number of retry attempts already made
    """
    try:
        processing_logs = cosmos_manager.query_processing_logs_by_document(
            document_id=document_id
        )

        retry_count = sum(
            1 for log in processing_logs
            if log.get("event_type") == "retry_initiated"
        )

        return retry_count

    except Exception as e:
        logger.warning(f"Failed to get retry count: {e}")
        return 0


def _enqueue_for_retry(
    document_id: str,
    document_info: Dict[str, Any],
    enhanced_ocr: bool,
    retry_count: int
) -> None:
    """
    Enqueue document to extraction queue for retry.

    Args:
        document_id: Document identifier
        document_info: Document metadata
        enhanced_ocr: Whether to use enhanced OCR settings
        retry_count: Current retry attempt number

    Raises:
        Exception: If queueing fails
    """
    try:
        credential = DefaultAzureCredential()
        fully_qualified_namespace = config.service_bus_namespace

        # Reconstruct blob URL
        document_type = document_info.get("document_type", "PDF")
        file_extension = ".pdf" if document_type == "PDF" else ".xlsx"
        blob_path = storage_manager.generate_blob_path(document_id, file_extension)
        blob_url = storage_manager.get_blob_url(blob_path)

        with ServiceBusClient(
            fully_qualified_namespace=fully_qualified_namespace, credential=credential
        ) as client:
            with client.get_queue_sender(
                queue_name=config.service_bus_extraction_queue
            ) as sender:
                message_body = {
                    "document_id": document_id,
                    "blob_url": blob_url,
                    "document_name": document_info.get("document_name", "unknown"),
                    "document_type": document_type,
                    "queued_at": datetime.utcnow().isoformat(),
                    "retry_count": retry_count,
                    "enhanced_ocr": enhanced_ocr,  # T096
                }

                message = ServiceBusMessage(
                    body=json.dumps(message_body),
                    content_type="application/json",
                    message_id=f"{document_id}-retry-{retry_count}",
                )

                sender.send_messages(message)
                logger.info(f"Enqueued document for retry: {document_id}")

    except Exception as e:
        logger.error(f"Failed to enqueue document for retry: {e}")
        raise


def _create_processing_log(
    document_id: str,
    retry_count: int,
    enhanced_ocr: bool,
    user_id: str
) -> None:
    """
    Create a processing log entry for the retry event.

    Args:
        document_id: Document identifier
        retry_count: Current retry attempt number
        enhanced_ocr: Whether enhanced OCR is enabled
        user_id: User who initiated the retry
    """
    try:
        log_entry = ProcessingLog(
            id=f"log-{uuid.uuid4()}",
            document_id=document_id,
            event_type="retry_initiated",
            event_timestamp=datetime.utcnow(),
            event_data={
                "retry_count": retry_count,
                "enhanced_ocr": enhanced_ocr,
                "initiated_by": user_id
            },
            function_name="retry_handler",
            execution_id=None,
        )

        cosmos_manager.create_processing_log(log_entry.model_dump(mode="json"))
        logger.info(f"Created processing log for retry: {document_id}")

    except Exception as e:
        # Log error but don't fail the function
        logger.error(f"Failed to create processing log: {e}")
