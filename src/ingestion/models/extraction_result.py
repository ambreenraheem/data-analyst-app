"""
ExtractionResult Pydantic model.

Represents the overall result of document extraction including
OCR quality metrics and validation status.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ExtractionResult(BaseModel):
    """
    Overall extraction result for a financial document.

    Tracks extraction progress, OCR quality, and validation status
    supporting Constitution Principles II (Confidence Thresholds) and
    III (Auditability).
    """

    id: str = Field(..., description="Unique identifier for this extraction result (UUID)")
    document_id: str = Field(..., description="ID of the extracted document")
    document_name: str = Field(..., description="Original filename")
    document_type: str = Field(..., description="Document type: 'PDF' or 'XLSX'")
    extraction_status: str = Field(
        ...,
        description="Extraction status: 'queued', 'processing', 'completed', 'failed'",
    )
    ocr_confidence_avg: Optional[float] = Field(
        None, description="Average OCR confidence across all extracted elements (0.0-1.0)"
    )
    tables_extracted: int = Field(0, description="Number of tables extracted from document")
    metrics_extracted: int = Field(0, description="Number of financial metrics extracted")
    extraction_started_at: Optional[datetime] = Field(
        None, description="Timestamp when extraction started (UTC)"
    )
    extraction_completed_at: Optional[datetime] = Field(
        None, description="Timestamp when extraction completed (UTC)"
    )
    document_intelligence_model_version: Optional[str] = Field(
        None, description="Azure Document Intelligence model version used (e.g., 'prebuilt-layout-2024-02-29')"
    )
    validation_status: Optional[str] = Field(
        None, description="Validation status: 'passed', 'flagged', 'failed'"
    )
    validation_errors: list[str] = Field(default_factory=list, description="List of validation error messages")
    validation_warnings: list[str] = Field(default_factory=list, description="List of validation warning messages")
    requires_manual_review: bool = Field(
        False,
        description="Whether document requires manual review (low confidence or validation issues)",
    )
    error_message: Optional[str] = Field(None, description="Error message if extraction failed")

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "id": "extraction-e1f2g3h4",
                "document_id": "doc-a1b2c3d4",
                "document_name": "Q4_2024_Financial_Report.pdf",
                "document_type": "PDF",
                "extraction_status": "completed",
                "ocr_confidence_avg": 0.92,
                "tables_extracted": 5,
                "metrics_extracted": 25,
                "extraction_started_at": "2024-01-15T10:30:00Z",
                "extraction_completed_at": "2024-01-15T10:33:45Z",
                "document_intelligence_model_version": "prebuilt-layout-2024-02-29",
                "validation_status": "passed",
                "validation_errors": [],
                "validation_warnings": [],
                "requires_manual_review": False,
                "error_message": None,
            }
        }
