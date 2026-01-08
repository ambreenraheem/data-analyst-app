"""
ProcessingLog Pydantic model.

Represents a log entry for document processing events,
supporting Constitution Principle III (Auditability).
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ProcessingLog(BaseModel):
    """
    Log entry for document processing events.

    Provides audit trail for all document processing stages
    per Constitution Principle III (Explainability and Auditability).
    """

    id: str = Field(..., description="Unique identifier for this log entry (UUID)")
    document_id: str = Field(..., description="ID of the document being processed")
    event_type: str = Field(
        ...,
        description="Event type: 'queued', 'ingestion_started', 'extraction_started', "
        "'extraction_completed', 'validation_completed', 'retry_initiated', 'failed'",
    )
    event_timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Event timestamp (UTC)"
    )
    event_data: Optional[Dict[str, Any]] = Field(
        None, description="Additional event-specific data (e.g., error details, metrics)"
    )
    function_name: Optional[str] = Field(
        None, description="Azure Function that generated this log entry"
    )
    execution_id: Optional[str] = Field(
        None, description="Azure Functions execution/invocation ID for correlation"
    )

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "id": "log-l1m2n3o4",
                "document_id": "doc-a1b2c3d4",
                "event_type": "extraction_completed",
                "event_timestamp": "2024-01-15T10:33:45Z",
                "event_data": {
                    "metrics_extracted": 25,
                    "avg_confidence": 0.92,
                    "duration_seconds": 225,
                },
                "function_name": "extraction_worker",
                "execution_id": "inv-x1y2z3",
            }
        }
