"""
SourceReference Pydantic model.

Represents the source location of an extracted financial metric,
supporting Constitution Principle I (Data-First with source traceability).
"""

from typing import Optional

from pydantic import BaseModel, Field


class SourceReference(BaseModel):
    """
    Source reference for an extracted financial metric.

    Captures precise location information to enable traceability from
    insight back to source document (Constitution Principle I).
    """

    document_id: str = Field(..., description="Unique identifier of the source document")
    document_name: str = Field(..., description="Original filename of the source document")
    page_number: Optional[int] = Field(None, description="Page number (for PDFs) starting from 1")
    sheet_name: Optional[str] = Field(None, description="Sheet name (for Excel files)")
    table_id: Optional[str] = Field(
        None, description="Table identifier within the page/sheet (e.g., 'table-1')"
    )
    cell_reference: Optional[str] = Field(
        None, description="Cell reference (e.g., 'B34' for Excel, 'row:2,col:3' for PDF tables)"
    )
    bounding_box: Optional[list[float]] = Field(
        None,
        description="Bounding box coordinates [x1, y1, x2, y2] for PDF text (optional, for UI highlighting)",
    )

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "document_id": "doc-a1b2c3d4",
                "document_name": "Q4_2024_Financial_Report.pdf",
                "page_number": 3,
                "sheet_name": None,
                "table_id": "table-1",
                "cell_reference": "row:5,col:2",
                "bounding_box": [120.5, 450.2, 180.3, 470.8],
            }
        }
