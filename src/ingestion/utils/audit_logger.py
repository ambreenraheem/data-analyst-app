"""
Audit logger for Azure Table Storage.

Provides audit trail for all data access events supporting
Constitution Principle III (Explainability and Auditability)
and Principle V (Secure Data Handling with access logging).
"""

from datetime import datetime
from typing import Any, Dict, Optional

from azure.data.tables import TableServiceClient
from azure.identity import DefaultAzureCredential

from src.shared.config import config
from src.shared.exceptions import StorageError


class AuditLogger:
    """Logger for audit events to Azure Table Storage."""

    def __init__(self) -> None:
        """Initialize Table Storage client with Managed Identity authentication."""
        account_url = f"https://{config.storage_account_name}.table.core.windows.net"
        credential = DefaultAzureCredential()
        self.table_service_client = TableServiceClient(
            endpoint=account_url, credential=credential
        )
        self.table_name = "AuditLogs"
        self._ensure_table_exists()

    def _ensure_table_exists(self) -> None:
        """Create the AuditLogs table if it doesn't exist."""
        try:
            self.table_service_client.create_table_if_not_exists(self.table_name)
        except Exception as e:
            # Log warning but don't fail initialization
            print(f"Warning: Could not ensure AuditLogs table exists: {e}")

    def log_access_event(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log an access event to the audit trail.

        Args:
            user_id: Azure AD user ID performing the action
            action: Action performed (e.g., "upload", "view", "view_results", "retry")
            resource_type: Type of resource accessed (e.g., "document", "extraction_result")
            resource_id: ID of the resource accessed
            additional_data: Optional additional context data

        Raises:
            StorageError: If audit log write fails
        """
        try:
            now = datetime.utcnow()

            # Partition key: YYYY-MM for efficient time-based queries
            partition_key = now.strftime("%Y-%m")

            # Row key: Timestamp + resource_id for uniqueness and ordering
            row_key = f"{now.isoformat()}_{resource_id}"

            entity = {
                "PartitionKey": partition_key,
                "RowKey": row_key,
                "Timestamp": now,
                "UserId": user_id,
                "Action": action,
                "ResourceType": resource_type,
                "ResourceId": resource_id,
            }

            # Add additional data as separate columns
            if additional_data:
                for key, value in additional_data.items():
                    # Table Storage requires simple types
                    if isinstance(value, (str, int, float, bool, datetime)):
                        entity[key] = value
                    else:
                        entity[key] = str(value)

            table_client = self.table_service_client.get_table_client(self.table_name)
            table_client.create_entity(entity=entity)

        except Exception as e:
            raise StorageError(
                operation="log_audit_event",
                resource=f"AuditLogs/{partition_key}/{row_key}",
                reason=str(e),
            )

    def log_document_upload(
        self, user_id: str, document_id: str, document_name: str, file_size_mb: float
    ) -> None:
        """
        Log a document upload event.

        Args:
            user_id: User who uploaded the document
            document_id: Unique document identifier
            document_name: Original filename
            file_size_mb: File size in megabytes
        """
        self.log_access_event(
            user_id=user_id,
            action="upload",
            resource_type="document",
            resource_id=document_id,
            additional_data={"DocumentName": document_name, "FileSizeMB": file_size_mb},
        )

    def log_document_view(self, user_id: str, document_id: str, view_type: str = "status") -> None:
        """
        Log a document view event.

        Args:
            user_id: User who viewed the document
            document_id: Document identifier
            view_type: Type of view ("status", "results", "metadata")
        """
        self.log_access_event(
            user_id=user_id,
            action="view",
            resource_type="document",
            resource_id=document_id,
            additional_data={"ViewType": view_type},
        )

    def log_document_retry(self, user_id: str, document_id: str, retry_count: int) -> None:
        """
        Log a document retry event.

        Args:
            user_id: User who initiated the retry
            document_id: Document identifier
            retry_count: Number of retries for this document
        """
        self.log_access_event(
            user_id=user_id,
            action="retry",
            resource_type="document",
            resource_id=document_id,
            additional_data={"RetryCount": retry_count},
        )


# Global audit logger instance
audit_logger = AuditLogger()
