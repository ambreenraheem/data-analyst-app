"""
Process Ingestion Azure Function.

Service Bus trigger for ingestion-queue.
Handles file integrity validation, duplicate detection,
and queueing to extraction-queue.

Supports Constitution Principles I (Data-First) and III (Auditability).
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict

import azure.functions as func
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.identity import DefaultAzureCredential

from src.shared.config import config
from src.shared.exceptions import DocumentNotFoundError, StorageError
from src.shared.telemetry import telemetry
from src.ingestion.services.storage_manager import StorageManager
from src.ingestion.services.cosmos_manager import CosmosManager
from src.ingestion.models.processing_log import ProcessingLog


# Initialize services
storage_manager = StorageManager()
cosmos_manager = CosmosManager()
logger = logging.getLogger("process_ingestion")
logger.setLevel(logging.INFO)


def main(msg: func.ServiceBusMessage) -> None:
    """
    Process ingestion queue messages.

    Message format:
    {
        "document_id": "doc-abc123",
        "blob_url": "https://...",
        "document_name": "report.pdf",
        "document_type": "PDF",
        "file_hash_sha256": "abc123...",
        "uploader_user_id": "user@company.com",
        "upload_timestamp": "2024-01-15T10:30:00Z"
    }

    Args:
        msg: Service Bus message from ingestion-queue
    """
    try:
        # Parse message
        message_body = msg.get_body().decode("utf-8")
        message_data = json.loads(message_body)

        document_id = message_data["document_id"]
        blob_url = message_data["blob_url"]
        document_name = message_data["document_name"]
        document_type = message_data["document_type"]
        file_hash = message_data["file_hash_sha256"]
        uploader_user_id = message_data["uploader_user_id"]

        logger.info(f"Processing ingestion for document: {document_id}")

        # Log ingestion started event (T041)
        _create_processing_log(
            document_id=document_id,
            event_type="ingestion_started",
            event_data={
                "document_name": document_name,
                "document_type": document_type,
                "uploader_user_id": uploader_user_id,
            },
        )

        # Validate file integrity (T038)
        file_extension = ".pdf" if document_type == "PDF" else ".xlsx"
        is_valid = storage_manager.verify_document_integrity(
            document_id=document_id,
            expected_hash=file_hash,
            file_extension=file_extension,
        )

        if not is_valid:
            logger.error(f"File integrity check failed for document: {document_id}")
            _create_processing_log(
                document_id=document_id,
                event_type="failed",
                event_data={
                    "error": "File integrity validation failed",
                    "error_type": "integrity_check_failed",
                },
            )
            raise Exception("File integrity validation failed")

        logger.info(f"File integrity verified for document: {document_id}")

        # Check for duplicates (T039)
        duplicate_docs = cosmos_manager.query_by_file_hash(
            file_hash=file_hash,
            container_name=config.cosmos_container_extraction_results,
        )

        if duplicate_docs:
            logger.warning(
                f"Duplicate document detected: {document_id} "
                f"(matches {len(duplicate_docs)} existing document(s))"
            )
            _create_processing_log(
                document_id=document_id,
                event_type="duplicate_detected",
                event_data={
                    "duplicate_count": len(duplicate_docs),
                    "existing_document_ids": [doc.get("document_id") for doc in duplicate_docs],
                    "action": "proceeding_with_extraction",
                },
            )
            # Note: Proceeding with extraction even if duplicate exists
            # Business logic can be adjusted to skip duplicates if needed

        # Queue to extraction queue (T040)
        _enqueue_to_extraction_queue(
            document_id=document_id,
            blob_url=blob_url,
            document_name=document_name,
            document_type=document_type,
        )

        # Log queued event (T041)
        _create_processing_log(
            document_id=document_id,
            event_type="queued",
            event_data={
                "queue": "extraction-queue",
                "document_name": document_name,
                "document_type": document_type,
            },
        )

        logger.info(f"Document queued for extraction: {document_id}")

    except DocumentNotFoundError as e:
        logger.error(f"Document not found: {e}")
        telemetry.track_exception(e, properties={"error_type": "document_not_found"})
        _create_processing_log(
            document_id=message_data.get("document_id", "unknown"),
            event_type="failed",
            event_data={"error": str(e), "error_type": "document_not_found"},
        )
        raise  # Let Service Bus handle retry/dead-letter

    except StorageError as e:
        logger.error(f"Storage error during ingestion: {e}")
        telemetry.track_exception(e, properties={"error_type": "storage"})
        _create_processing_log(
            document_id=message_data.get("document_id", "unknown"),
            event_type="failed",
            event_data={"error": str(e), "error_type": "storage_error"},
        )
        raise  # Let Service Bus handle retry/dead-letter

    except Exception as e:
        logger.exception(f"Unexpected error during ingestion: {e}")
        telemetry.track_exception(e, properties={"error_type": "unexpected"})
        _create_processing_log(
            document_id=message_data.get("document_id", "unknown"),
            event_type="failed",
            event_data={"error": str(e), "error_type": "unexpected_error"},
        )
        raise  # Let Service Bus handle retry/dead-letter (T042)


def _create_processing_log(
    document_id: str, event_type: str, event_data: Dict[str, Any]
) -> None:
    """
    Create a processing log entry in Cosmos DB.

    Args:
        document_id: Document identifier
        event_type: Event type (ingestion_started, queued, failed, etc.)
        event_data: Additional event data
    """
    try:
        log_entry = ProcessingLog(
            id=f"log-{uuid.uuid4()}",
            document_id=document_id,
            event_type=event_type,
            event_timestamp=datetime.utcnow(),
            event_data=event_data,
            function_name="process_ingestion",
            execution_id=None,  # Azure Functions context not available in this simplified version
        )

        cosmos_manager.create_processing_log(log_entry.model_dump(mode="json"))
        logger.info(f"Created processing log: {event_type} for document {document_id}")

    except Exception as e:
        # Log error but don't fail the function
        logger.error(f"Failed to create processing log: {e}")


def _enqueue_to_extraction_queue(
    document_id: str, blob_url: str, document_name: str, document_type: str
) -> None:
    """
    Enqueue document to Service Bus extraction queue.

    Args:
        document_id: Unique document identifier
        blob_url: Blob Storage URL
        document_name: Original filename
        document_type: Document type (PDF or XLSX)

    Raises:
        Exception: If queueing fails
    """
    try:
        credential = DefaultAzureCredential()
        fully_qualified_namespace = config.service_bus_namespace

        with ServiceBusClient(
            fully_qualified_namespace=fully_qualified_namespace, credential=credential
        ) as client:
            with client.get_queue_sender(
                queue_name=config.service_bus_extraction_queue
            ) as sender:
                message_body = {
                    "document_id": document_id,
                    "blob_url": blob_url,
                    "document_name": document_name,
                    "document_type": document_type,
                    "queued_at": datetime.utcnow().isoformat(),
                }

                message = ServiceBusMessage(
                    body=json.dumps(message_body),
                    content_type="application/json",
                    message_id=document_id,  # For duplicate detection
                )

                sender.send_messages(message)
                logger.info(f"Enqueued document to extraction queue: {document_id}")

    except Exception as e:
        logger.error(f"Failed to enqueue message to extraction queue: {e}")
        raise
