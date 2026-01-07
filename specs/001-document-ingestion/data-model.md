# Data Model: Document Ingestion Pipeline

**Feature**: Document Ingestion Pipeline
**Date**: 2026-01-08
**Version**: 1.0.0

## Overview

This document defines the data model for the Document Ingestion Pipeline, including Cosmos DB container schemas, Pydantic models for validation, and entity relationships. All entities support the 7-year audit trail requirement (Constitution Principle III) and source reference tracking (Principle I).

---

## Storage Architecture

### Cosmos DB Containers

| Container Name | Partition Key | Purpose | Estimated Size/Year |
|----------------|---------------|---------|---------------------|
| `extraction-results` | `document_id` | Store overall extraction metadata and OCR quality metrics | ~500K docs × 2KB = 1GB |
| `financial-metrics` | `document_id` | Store individual extracted metrics with source references | ~100M metrics × 1KB = 100GB |
| `processing-logs` | `document_id` | Track processing events for debugging and audit | ~5M events × 500B = 2.5GB |

### Azure Blob Storage

| Container | Path Pattern | Lifecycle Policy |
|-----------|--------------|------------------|
| `financial-documents` | `{year}/{month}/{document_id}.{ext}` | Hot (0-90 days) → Cool (91 days-3 years) → Archive (3-7 years) |

### Azure Table Storage

| Table | Partition Key | Row Key | Purpose |
|-------|---------------|---------|---------|
| `AuditLogs` | `{year}-{month}` | `{timestamp}-{event_id}` | Compliance audit trail |

---

## Entity Definitions

### 1. FinancialDocument

Represents an uploaded financial document (PDF or Excel).

**Cosmos DB Container**: Not stored in Cosmos DB (metadata only in Blob Storage properties)

**Blob Storage Metadata**:
```json
{
  "document_id": "doc-abc123",
  "original_filename": "Q4_2025_Financial_Report.pdf",
  "file_size_bytes": 10485760,
  "file_hash_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "upload_timestamp": "2026-01-08T10:30:00Z",
  "uploader_user_id": "user@company.com",
  "content_type": "application/pdf",
  "status": "queued"  // queued|processing|completed|failed
}
```

**Pydantic Model**:
```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal

class FinancialDocument(BaseModel):
    document_id: str = Field(..., description="Unique document identifier (UUID)")
    original_filename: str = Field(..., max_length=255)
    file_size_bytes: int = Field(..., gt=0, le=52428800)  # Max 50MB
    file_hash_sha256: str = Field(..., regex=r'^[a-f0-9]{64}$')
    upload_timestamp: datetime
    uploader_user_id: str
    content_type: Literal["application/pdf", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]
    status: Literal["queued", "processing", "completed", "failed"]
```

---

### 2. ExtractionResult

Represents the outcome of document processing.

**Cosmos DB Container**: `extraction-results`

**Schema**:
```json
{
  "id": "result-abc123",
  "document_id": "doc-abc123",  // Partition key
  "extraction_timestamp": "2026-01-08T10:35:00Z",
  "document_type": "pdf",  // pdf|excel
  "page_count": 15,
  "tables_extracted": 8,
  "metrics_extracted": 42,
  "overall_ocr_confidence": 0.92,
  "validation_status": "passed",  // passed|flagged|failed
  "validation_errors": [],
  "validation_warnings": [
    "Low OCR confidence on page 12: 0.68"
  ],
  "processing_duration_ms": 285000,
  "model_version": "prebuilt-layout-2024-02-29"
}
```

**Pydantic Model**:
```python
from typing import List, Optional

class ExtractionResult(BaseModel):
    id: str
    document_id: str  // Partition key for Cosmos DB
    extraction_timestamp: datetime
    document_type: Literal["pdf", "excel"]
    page_count: int = Field(..., ge=1)
    tables_extracted: int = Field(..., ge=0)
    metrics_extracted: int = Field(..., ge=0)
    overall_ocr_confidence: float = Field(..., ge=0.0, le=1.0)
    validation_status: Literal["passed", "flagged", "failed"]
    validation_errors: List[str] = []
    validation_warnings: List[str] = []
    processing_duration_ms: int
    model_version: str
```

---

### 3. FinancialMetric

Represents a single extracted financial data point with full source reference.

**Cosmos DB Container**: `financial-metrics`

**Schema**:
```json
{
  "id": "metric-xyz789",
  "document_id": "doc-abc123",  // Partition key
  "extraction_result_id": "result-abc123",
  "metric_name": "revenue",
  "value": 10000000.00,
  "currency": "USD",
  "reporting_period": "Q4 2025",
  "confidence_score": 0.95,
  "source_reference": {
    "document_name": "Q4_2025_Financial_Report.pdf",
    "page_number": 12,
    "table_id": "table-3",
    "row_index": 2,
    "column_index": 1,
    "cell_reference": null,  // For Excel: "B34"
    "bounding_box": {
      "x": 150,
      "y": 320,
      "width": 80,
      "height": 20
    }
  },
  "extracted_timestamp": "2026-01-08T10:35:15Z"
}
```

**Pydantic Model**:
```python
class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float

class SourceReference(BaseModel):
    document_name: str
    page_number: Optional[int] = None  // For PDF
    table_id: Optional[str] = None
    row_index: Optional[int] = None
    column_index: Optional[int] = None
    cell_reference: Optional[str] = None  // For Excel: "B34"
    bounding_box: Optional[BoundingBox] = None

class FinancialMetric(BaseModel):
    id: str
    document_id: str  // Partition key
    extraction_result_id: str
    metric_name: str = Field(..., max_length=100)
    value: float
    currency: str = Field(default="USD", max_length=3)
    reporting_period: str = Field(..., max_length=50)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    source_reference: SourceReference
    extracted_timestamp: datetime
```

---

### 4. ProcessingLog

Represents a log entry for document processing events.

**Cosmos DB Container**: `processing-logs`

**Schema**:
```json
{
  "id": "log-def456",
  "document_id": "doc-abc123",  // Partition key
  "timestamp": "2026-01-08T10:30:05Z",
  "event_type": "processing_started",  // uploaded|queued|processing_started|extraction_completed|validation_completed|failed
  "status_message": "Extraction started for 15-page PDF",
  "error_details": null,
  "retry_count": 0,
  "function_name": "extraction_worker"
}
```

**Pydantic Model**:
```python
class ProcessingLog(BaseModel):
    id: str
    document_id: str  // Partition key
    timestamp: datetime
    event_type: Literal["uploaded", "queued", "processing_started", "extraction_completed", "validation_completed", "failed"]
    status_message: str
    error_details: Optional[str] = None
    retry_count: int = Field(default=0, ge=0, le=3)
    function_name: str
```

---

### 5. AuditLog (Azure Table Storage)

Represents an access event for compliance auditing.

**Table Storage Entity**:
```python
{
  "PartitionKey": "2026-01",  // {year}-{month}
  "RowKey": "2026-01-08T10:30:00Z-abc123",  // {timestamp}-{event_id}
  "EventId": "audit-abc123",
  "Timestamp": "2026-01-08T10:30:00Z",
  "UserId": "user@company.com",
  "UserEmail": "user@company.com",
  "Action": "upload",  // upload|download|view|delete
  "Resource": "doc-abc123",
  "Result": "success",  // success|denied
  "IpAddress": "203.0.113.5",
  "Metadata": "{\"file_size\": 10485760}"
}
```

---

## Entity Relationships

```
FinancialDocument (Blob Storage)
  ↓ 1:1
ExtractionResult (Cosmos DB: extraction-results)
  ↓ 1:N
FinancialMetric (Cosmos DB: financial-metrics)
  ↓ references
SourceReference (nested in FinancialMetric)

FinancialDocument
  ↓ 1:N
ProcessingLog (Cosmos DB: processing-logs)

All entities
  ↓ N:N
AuditLog (Table Storage)
```

**Query Patterns**:
- Get extraction result: `SELECT * FROM extraction_results r WHERE r.document_id = '{doc_id}'` (single-partition)
- Get all metrics for document: `SELECT * FROM financial_metrics m WHERE m.document_id = '{doc_id}'` (single-partition)
- Get processing history: `SELECT * FROM processing_logs p WHERE p.document_id = '{doc_id}' ORDER BY p.timestamp DESC` (single-partition)
- Audit query (compliance): `PartitionKey eq '2026-01' and UserId eq 'user@company.com'` (Table Storage filter)

---

## Validation Rules

Implemented in `services/validator.py`:

### Completeness Validation
```python
REQUIRED_METRICS = ["revenue", "expenses", "net_income"]

def validate_completeness(metrics: List[FinancialMetric]) -> List[str]:
    """Validate that critical financial metrics are present"""
    errors = []
    extracted_names = [m.metric_name.lower() for m in metrics]

    for required in REQUIRED_METRICS:
        if required not in extracted_names:
            errors.append(f"Missing critical metric: {required}")

    return errors
```

### Range Validation
```python
VALIDATION_RULES = {
    "revenue": {"min": 0, "max": 1_000_000_000_000},  # $1 trillion max
    "expenses": {"min": 0, "max": 1_000_000_000_000},
    "net_income": {"min": -1_000_000_000_000, "max": 1_000_000_000_000}  // Can be negative
}

def validate_ranges(metric: FinancialMetric) -> Optional[str]:
    """Validate that metric value is within reasonable range"""
    if metric.metric_name not in VALIDATION_RULES:
        return None  // No validation rule for this metric

    rules = VALIDATION_RULES[metric.metric_name]
    if metric.value < rules["min"] or metric.value > rules["max"]:
        return f"Invalid {metric.metric_name}: {metric.value} (expected {rules['min']}-{rules['max']})"

    return None
```

### Confidence Validation
```python
LOW_CONFIDENCE_THRESHOLD = 0.70
DOCUMENT_CONFIDENCE_THRESHOLD = 0.75

def validate_confidence(result: ExtractionResult, metrics: List[FinancialMetric]) -> List[str]:
    """Flag low-confidence extractions for manual review"""
    warnings = []

    # Check overall document confidence
    if result.overall_ocr_confidence < DOCUMENT_CONFIDENCE_THRESHOLD:
        warnings.append(f"Low document confidence: {result.overall_ocr_confidence:.2f} (threshold: {DOCUMENT_CONFIDENCE_THRESHOLD})")

    # Check individual metric confidence
    low_conf_metrics = [m for m in metrics if m.confidence_score < LOW_CONFIDENCE_THRESHOLD]
    if low_conf_metrics:
        warnings.append(f"{len(low_conf_metrics)} metrics with low confidence (< {LOW_CONFIDENCE_THRESHOLD}): {[m.metric_name for m in low_conf_metrics]}")

    return warnings
```

---

## Indexing Strategy

**Cosmos DB Indexing Policy** (automatic by default):
```json
{
  "indexingMode": "consistent",
  "automatic": true,
  "includedPaths": [
    { "path": "/*" }
  ],
  "excludedPaths": [
    { "path": "/source_reference/bounding_box/*" }  // Exclude coordinates (never queried)
  ]
}
```

**Benefits**:
- All properties indexed except excluded paths
- Single-partition queries (by `document_id`) are fast (< 10ms)
- Cross-partition queries avoided (no need to query across documents)

---

## TTL (Time-to-Live) Strategy

**Not Applicable**: 7-year retention required per Constitution Principle III. No TTL configured on Cosmos DB containers.

**Lifecycle Management**: Blob Storage handles cost optimization via tier transitions (Hot → Cool → Archive).

---

## Summary

The data model supports:
- ✅ Source reference tracking (Constitution Principle I)
- ✅ Confidence scoring for downstream analysis (Principle II)
- ✅ 7-year audit trail (Principle III)
- ✅ Secure storage with RBAC (Principle V)

**Next Steps**: Generate API contracts (OpenAPI spec) for upload and status endpoints.
