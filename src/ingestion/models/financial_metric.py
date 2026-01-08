"""
FinancialMetric Pydantic model.

Represents a single extracted financial metric with full source reference
and confidence tracking per Constitution Principle I and II.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.ingestion.models.source_reference import SourceReference


class FinancialMetric(BaseModel):
    """
    A single extracted financial metric with source reference and confidence score.

    Supports Constitution Principles:
    - Principle I: Source reference traceability
    - Principle II: Confidence score for autonomous reasoning thresholds
    """

    id: str = Field(..., description="Unique identifier for this metric (UUID)")
    document_id: str = Field(..., description="ID of the source document")
    metric_type: str = Field(
        ...,
        description="Type of metric (e.g., 'revenue', 'cogs', 'gross_profit', 'net_income')",
    )
    metric_name: str = Field(
        ..., description="Human-readable name (e.g., 'Total Revenue', 'Cost of Goods Sold')"
    )
    value: float = Field(..., description="Numeric value of the metric")
    currency: Optional[str] = Field("USD", description="Currency code (ISO 4217)")
    period: Optional[str] = Field(
        None, description="Reporting period (e.g., 'Q4 2024', 'FY 2024', '2024-12-31')"
    )
    confidence_score: float = Field(
        ..., description="OCR confidence score for this metric (0.0-1.0)", ge=0.0, le=1.0
    )
    source_reference: SourceReference = Field(
        ..., description="Source location of this metric in the original document"
    )
    extracted_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp when metric was extracted (UTC)"
    )
    flagged_for_review: bool = Field(
        False,
        description="Whether this metric is flagged for manual review (low confidence or validation failure)",
    )

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "id": "metric-x1y2z3",
                "document_id": "doc-a1b2c3d4",
                "metric_type": "revenue",
                "metric_name": "Total Revenue",
                "value": 15750000.0,
                "currency": "USD",
                "period": "Q4 2024",
                "confidence_score": 0.95,
                "source_reference": {
                    "document_id": "doc-a1b2c3d4",
                    "document_name": "Q4_2024_Financial_Report.pdf",
                    "page_number": 3,
                    "table_id": "table-1",
                    "cell_reference": "row:5,col:2",
                },
                "extracted_at": "2024-01-15T10:30:00Z",
                "flagged_for_review": False,
            }
        }
