"""
Upload Handler Azure Function.

HTTP trigger for POST /api/v1/documents/upload endpoint.
Handles financial document uploads (PDF/Excel) with validation,
Blob Storage persistence, and Service Bus queueing.

Supports Constitution Principles I (Data-First), III (Auditability),
and V (Secure Data Handling).
"""

import io
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Tuple

import azure.functions as func
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.identity import DefaultAzureCredential

from src.shared.config import config
from src.shared.exceptions import FileUploadError, StorageError
from src.shared.telemetry import telemetry
from src.ingestion.services.storage_manager import StorageManager
from src.ingestion.utils.audit_logger import audit_logger


# Initialize services
storage_manager = StorageManager()
logger = logging.getLogger("upload_handler")
logger.setLevel(logging.INFO)


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Handle document upload requests.

    Request format: multipart/form-data with 'file' field

    Response format:
    {
        "document_id": "doc-abc123",
        "status": "queued",
        "message": "Document uploaded successfully",
        "blob_url": "https://..."
    }

    Args:
        req: HTTP request with uploaded file

    Returns:
        HTTP response with document ID and status
    """
    logger.info("Document upload request received")

    try:
        # Extract user identity from Azure AD token (simplified for demo)
        user_id = req.headers.get("X-MS-CLIENT-PRINCIPAL-ID", "unknown-user")

        # Validate and extract file from request
        file_data, filename, content_type = _extract_file_from_request(req)

        # Validate file type and size (T030)
        file_extension = _validate_file_type_and_size(filename, file_data)

        # Generate document ID (T031)
        document_id = _generate_document_id()

        # Calculate file hash for integrity verification and duplicate detection
        file_hash = StorageManager.calculate_file_hash(file_data)

        # Upload to Blob Storage (T032)
        file_data.seek(0)
        blob_url = storage_manager.upload_document(
            document_id=document_id,
            file_stream=file_data,
            file_extension=file_extension,
            metadata={
                "original_filename": filename,
                "uploader_user_id": user_id,
                "upload_timestamp": datetime.utcnow().isoformat(),
                "file_hash_sha256": file_hash,
            },
        )

        # Send message to Service Bus ingestion queue (T033)
        _enqueue_to_ingestion_queue(
            document_id=document_id,
            blob_url=blob_url,
            document_name=filename,
            document_type=file_extension.upper().replace(".", ""),
            file_hash=file_hash,
            uploader_user_id=user_id,
        )

        # Log audit event (T034)
        file_size_mb = len(file_data.getvalue()) / (1024 * 1024)
        audit_logger.log_document_upload(
            user_id=user_id,
            document_id=document_id,
            document_name=filename,
            file_size_mb=round(file_size_mb, 2),
        )

        # Track telemetry
        telemetry.track_document_upload(
            document_id=document_id,
            file_type=file_extension.upper().replace(".", ""),
            file_size_mb=file_size_mb,
        )

        logger.info(f"Document uploaded successfully: {document_id}")

        # Return success response
        return func.HttpResponse(
            body=json.dumps(
                {
                    "document_id": document_id,
                    "status": "queued",
                    "message": "Document uploaded successfully and queued for processing",
                    "blob_url": blob_url,
                    "estimated_processing_time_minutes": 5,
                }
            ),
            status_code=202,  # Accepted
            mimetype="application/json",
        )

    except FileUploadError as e:
        # Handle validation errors (T035)
        logger.warning(f"File upload validation failed: {e}")
        telemetry.track_exception(e, properties={"error_type": "validation"})

        if "size exceeds" in str(e).lower():
            status_code = 413  # Payload Too Large
        else:
            status_code = 400  # Bad Request

        return func.HttpResponse(
            body=json.dumps({"error": str(e), "error_type": "validation_error"}),
            status_code=status_code,
            mimetype="application/json",
        )

    except StorageError as e:
        # Handle storage errors (T035)
        logger.error(f"Storage error during upload: {e}")
        telemetry.track_exception(e, properties={"error_type": "storage"})

        return func.HttpResponse(
            body=json.dumps(
                {"error": "Failed to store document", "error_type": "storage_error"}
            ),
            status_code=500,
            mimetype="application/json",
        )

    except Exception as e:
        # Handle unexpected errors (T035)
        logger.exception(f"Unexpected error during upload: {e}")
        telemetry.track_exception(e, properties={"error_type": "unexpected"})

        return func.HttpResponse(
            body=json.dumps(
                {"error": "Internal server error", "error_type": "server_error"}
            ),
            status_code=500,
            mimetype="application/json",
        )


def _extract_file_from_request(req: func.HttpRequest) -> Tuple[io.BytesIO, str, str]:
    """
    Extract file data from multipart/form-data request.

    Args:
        req: HTTP request

    Returns:
        Tuple of (file_data, filename, content_type)

    Raises:
        FileUploadError: If file extraction fails
    """
    try:
        # Parse multipart form data
        files = req.files.get("file")
        if not files:
            raise FileUploadError("", "No file uploaded. Expected 'file' field in form data.")

        filename = files.filename
        content_type = files.content_type
        file_content = files.read()

        if not file_content:
            raise FileUploadError(filename, "File is empty")

        file_data = io.BytesIO(file_content)
        return file_data, filename, content_type

    except FileUploadError:
        raise
    except Exception as e:
        raise FileUploadError("", f"Failed to extract file from request: {str(e)}")


def _validate_file_type_and_size(filename: str, file_data: io.BytesIO) -> str:
    """
    Validate file type (PDF or XLSX) and size (< 50MB).

    Args:
        filename: Original filename
        file_data: File content as BytesIO

    Returns:
        File extension (.pdf or .xlsx)

    Raises:
        FileUploadError: If validation fails
    """
    # Check file extension
    if not filename:
        raise FileUploadError(filename, "Filename is missing")

    filename_lower = filename.lower()
    if filename_lower.endswith(".pdf"):
        file_extension = ".pdf"
    elif filename_lower.endswith(".xlsx"):
        file_extension = ".xlsx"
    else:
        raise FileUploadError(
            filename,
            f"Unsupported file type. Only PDF and XLSX files are accepted. Got: {filename}",
        )

    # Check file size
    file_data.seek(0, 2)  # Seek to end
    file_size_bytes = file_data.tell()
    file_data.seek(0)  # Reset to beginning

    max_size_bytes = config.max_file_size_mb * 1024 * 1024
    if file_size_bytes > max_size_bytes:
        file_size_mb = file_size_bytes / (1024 * 1024)
        raise FileUploadError(
            filename,
            f"File size exceeds maximum allowed size. "
            f"Size: {file_size_mb:.2f}MB, Max: {config.max_file_size_mb}MB",
        )

    if file_size_bytes == 0:
        raise FileUploadError(filename, "File is empty")

    return file_extension


def _generate_document_id() -> str:
    """
    Generate unique document ID with 'doc-' prefix.

    Returns:
        Document ID (e.g., 'doc-a1b2c3d4-e5f6-7890-abcd-ef1234567890')
    """
    return f"doc-{uuid.uuid4()}"


def _enqueue_to_ingestion_queue(
    document_id: str,
    blob_url: str,
    document_name: str,
    document_type: str,
    file_hash: str,
    uploader_user_id: str,
) -> None:
    """
    Enqueue document to Service Bus ingestion queue.

    Args:
        document_id: Unique document identifier
        blob_url: Blob Storage URL
        document_name: Original filename
        document_type: Document type (PDF or XLSX)
        file_hash: SHA256 hash of file
        uploader_user_id: User who uploaded the document

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
                queue_name=config.service_bus_ingestion_queue
            ) as sender:
                message_body = {
                    "document_id": document_id,
                    "blob_url": blob_url,
                    "document_name": document_name,
                    "document_type": document_type,
                    "file_hash_sha256": file_hash,
                    "uploader_user_id": uploader_user_id,
                    "upload_timestamp": datetime.utcnow().isoformat(),
                }

                message = ServiceBusMessage(
                    body=json.dumps(message_body),
                    content_type="application/json",
                    message_id=document_id,  # For duplicate detection
                )

                sender.send_messages(message)
                logger.info(f"Enqueued document to ingestion queue: {document_id}")

    except Exception as e:
        logger.error(f"Failed to enqueue message to Service Bus: {e}")
        raise
