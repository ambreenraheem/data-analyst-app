"""
FinancialDocument Pydantic model.

Represents metadata for a financial document stored in Azure Blob Storage.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FinancialDocument(BaseModel):
    """
    Metadata for a financial document in Azure Blob Storage.

    Supports Constitution Principle III (7-year retention and audit trail).
    """

    document_id: str = Field(..., description="Unique identifier (UUID with 'doc-' prefix)")
    document_name: str = Field(..., description="Original filename")
    document_type: str = Field(..., description="Document type: 'PDF' or 'XLSX'")
    file_size_bytes: int = Field(..., description="File size in bytes")
    file_hash_sha256: str = Field(..., description="SHA256 hash for duplicate detection and integrity verification")
    blob_url: str = Field(..., description="Azure Blob Storage URL")
    blob_path: str = Field(..., description="Blob path within container (e.g., '2024/01/doc-abc123.pdf')")
    uploaded_at: datetime = Field(
        default_factory=datetime.utcnow, description="Upload timestamp (UTC)"
    )
    uploaded_by_user_id: str = Field(..., description="Azure AD user ID of uploader")
    processing_status: str = Field(
        "queued", description="Processing status: 'queued', 'processing', 'completed', 'failed'"
    )
    retention_expiry_date: Optional[datetime] = Field(
        None, description="Date when document can be deleted (7 years from upload)"
    )

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "document_id": "doc-a1b2c3d4",
                "document_name": "Q4_2024_Financial_Report.pdf",
                "document_type": "PDF",
                "file_size_bytes": 2457600,
                "file_hash_sha256": "a3b5c7d9e1f3...",
                "blob_url": "https://storage.blob.core.windows.net/financial-documents/2024/01/doc-a1b2c3d4.pdf",
                "blob_path": "2024/01/doc-a1b2c3d4.pdf",
                "uploaded_at": "2024-01-15T10:30:00Z",
                "uploaded_by_user_id": "user@company.com",
                "processing_status": "queued",
                "retention_expiry_date": "2031-01-15T10:30:00Z",
            }
        }
