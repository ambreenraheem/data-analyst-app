"""
Azure Blob Storage manager for document persistence.

Provides document upload, download, and integrity verification operations
supporting Constitution Principle I (Data-First) and III (7-year retention).
"""

import hashlib
from datetime import datetime, timedelta
from typing import BinaryIO, Optional

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContainerClient

from src.shared.config import config
from src.shared.exceptions import DocumentNotFoundError, StorageError


class StorageManager:
    """Manager for Azure Blob Storage operations on financial documents."""

    def __init__(self) -> None:
        """Initialize Blob Storage client with Managed Identity authentication."""
        account_url = f"https://{config.storage_account_name}.blob.core.windows.net"
        credential = DefaultAzureCredential()
        self.blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)
        self.container_name = config.blob_container_financial_docs

    def _get_container_client(self) -> ContainerClient:
        """Get container client for financial documents container."""
        return self.blob_service_client.get_container_client(self.container_name)

    def generate_blob_path(self, document_id: str, file_extension: str) -> str:
        """
        Generate blob path with year/month partitioning.

        Args:
            document_id: Unique document identifier
            file_extension: File extension (e.g., '.pdf', '.xlsx')

        Returns:
            Blob path string (e.g., '2024/01/doc-abc123.pdf')
        """
        now = datetime.utcnow()
        year = now.strftime("%Y")
        month = now.strftime("%m")
        return f"{year}/{month}/{document_id}{file_extension}"

    def upload_document(
        self, document_id: str, file_stream: BinaryIO, file_extension: str, metadata: Optional[dict] = None
    ) -> str:
        """
        Upload a financial document to Blob Storage.

        Args:
            document_id: Unique document identifier
            file_stream: File stream to upload
            file_extension: File extension (e.g., '.pdf', '.xlsx')
            metadata: Optional metadata dictionary for blob

        Returns:
            Blob URL of uploaded document

        Raises:
            StorageError: If upload fails
        """
        try:
            container_client = self._get_container_client()
            blob_path = self.generate_blob_path(document_id, file_extension)
            blob_client = container_client.get_blob_client(blob_path)

            # Upload file with metadata
            blob_client.upload_blob(file_stream, overwrite=False, metadata=metadata or {})

            return blob_client.url
        except Exception as e:
            raise StorageError(
                operation="upload",
                resource=f"{self.container_name}/{blob_path}",
                reason=str(e),
            )

    def download_document(self, document_id: str, file_extension: str) -> bytes:
        """
        Download a financial document from Blob Storage.

        Args:
            document_id: Unique document identifier
            file_extension: File extension (e.g., '.pdf', '.xlsx')

        Returns:
            Document content as bytes

        Raises:
            DocumentNotFoundError: If document doesn't exist
            StorageError: If download fails
        """
        try:
            container_client = self._get_container_client()

            # Try to find the blob across all year/month partitions
            # In production, document metadata should store exact blob path
            # This is a simplified approach for demo purposes
            now = datetime.utcnow()
            for year_offset in range(8):  # Check last 7 years + current
                check_date = now - timedelta(days=365 * year_offset)
                year = check_date.strftime("%Y")
                month = check_date.strftime("%m")
                blob_path = f"{year}/{month}/{document_id}{file_extension}"
                blob_client = container_client.get_blob_client(blob_path)

                if blob_client.exists():
                    return blob_client.download_blob().readall()

            raise DocumentNotFoundError(document_id)
        except DocumentNotFoundError:
            raise
        except Exception as e:
            raise StorageError(
                operation="download",
                resource=f"{self.container_name}/{document_id}",
                reason=str(e),
            )

    def verify_document_integrity(self, document_id: str, expected_hash: str, file_extension: str) -> bool:
        """
        Verify document integrity using SHA256 hash.

        Args:
            document_id: Unique document identifier
            expected_hash: Expected SHA256 hash
            file_extension: File extension (e.g., '.pdf', '.xlsx')

        Returns:
            True if hash matches, False otherwise

        Raises:
            DocumentNotFoundError: If document doesn't exist
            StorageError: If verification fails
        """
        try:
            document_bytes = self.download_document(document_id, file_extension)
            actual_hash = hashlib.sha256(document_bytes).hexdigest()
            return actual_hash == expected_hash
        except DocumentNotFoundError:
            raise
        except Exception as e:
            raise StorageError(
                operation="verify_integrity",
                resource=f"{self.container_name}/{document_id}",
                reason=str(e),
            )

    def get_blob_url(self, blob_path: str) -> str:
        """
        Get the full URL for a blob path.

        Args:
            blob_path: Blob path within container

        Returns:
            Full blob URL
        """
        container_client = self._get_container_client()
        blob_client = container_client.get_blob_client(blob_path)
        return blob_client.url

    @staticmethod
    def calculate_file_hash(file_stream: BinaryIO) -> str:
        """
        Calculate SHA256 hash of a file stream.

        Args:
            file_stream: File stream to hash

        Returns:
            SHA256 hash as hexadecimal string
        """
        sha256_hash = hashlib.sha256()
        file_stream.seek(0)
        for byte_block in iter(lambda: file_stream.read(4096), b""):
            sha256_hash.update(byte_block)
        file_stream.seek(0)
        return sha256_hash.hexdigest()
