"""
Custom exception classes for the document ingestion pipeline.

These exceptions provide clear error handling and traceability throughout
the ingestion workflow, supporting Constitution Principle III (Auditability).
"""


class IngestionError(Exception):
    """Base exception for all ingestion pipeline errors."""

    pass


class DocumentNotFoundError(IngestionError):
    """Raised when a requested document cannot be found in Blob Storage or Cosmos DB."""

    def __init__(self, document_id: str, message: str = "") -> None:
        """
        Initialize DocumentNotFoundError.

        Args:
            document_id: ID of the missing document
            message: Optional custom error message
        """
        self.document_id = document_id
        if not message:
            message = f"Document not found: {document_id}"
        super().__init__(message)


class ExtractionFailedError(IngestionError):
    """Raised when document extraction fails (OCR timeout, unsupported format, etc.)."""

    def __init__(
        self, document_id: str, reason: str, retry_eligible: bool = True, message: str = ""
    ) -> None:
        """
        Initialize ExtractionFailedError.

        Args:
            document_id: ID of the document that failed extraction
            reason: Detailed reason for extraction failure
            retry_eligible: Whether the extraction can be retried
            message: Optional custom error message
        """
        self.document_id = document_id
        self.reason = reason
        self.retry_eligible = retry_eligible
        if not message:
            message = f"Extraction failed for document {document_id}: {reason}"
        super().__init__(message)


class ValidationError(IngestionError):
    """Raised when extracted data fails validation (missing required fields, out-of-range values)."""

    def __init__(
        self, document_id: str, validation_errors: list[str], message: str = ""
    ) -> None:
        """
        Initialize ValidationError.

        Args:
            document_id: ID of the document that failed validation
            validation_errors: List of specific validation error messages
            message: Optional custom error message
        """
        self.document_id = document_id
        self.validation_errors = validation_errors
        if not message:
            message = (
                f"Validation failed for document {document_id}: "
                f"{len(validation_errors)} error(s)"
            )
        super().__init__(message)


class FileUploadError(IngestionError):
    """Raised when file upload validation fails (invalid type, oversized, corrupted)."""

    def __init__(self, filename: str, reason: str, message: str = "") -> None:
        """
        Initialize FileUploadError.

        Args:
            filename: Name of the file that failed upload
            reason: Detailed reason for upload failure
            message: Optional custom error message
        """
        self.filename = filename
        self.reason = reason
        if not message:
            message = f"File upload failed for {filename}: {reason}"
        super().__init__(message)


class StorageError(IngestionError):
    """Raised when Blob Storage or Cosmos DB operations fail."""

    def __init__(self, operation: str, resource: str, reason: str, message: str = "") -> None:
        """
        Initialize StorageError.

        Args:
            operation: Storage operation that failed (e.g., "upload", "download", "query")
            resource: Storage resource involved (e.g., blob path, container name)
            reason: Detailed reason for storage failure
            message: Optional custom error message
        """
        self.operation = operation
        self.resource = resource
        self.reason = reason
        if not message:
            message = f"Storage operation '{operation}' failed for {resource}: {reason}"
        super().__init__(message)


class QueueError(IngestionError):
    """Raised when Service Bus queue operations fail."""

    def __init__(self, queue_name: str, operation: str, reason: str, message: str = "") -> None:
        """
        Initialize QueueError.

        Args:
            queue_name: Name of the Service Bus queue
            operation: Queue operation that failed (e.g., "send", "receive", "complete")
            reason: Detailed reason for queue failure
            message: Optional custom error message
        """
        self.queue_name = queue_name
        self.operation = operation
        self.reason = reason
        if not message:
            message = f"Queue operation '{operation}' failed for {queue_name}: {reason}"
        super().__init__(message)
