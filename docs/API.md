# Document Ingestion API Documentation

REST API for the Financial Insight & Risk Advisor Agent - Document Ingestion Pipeline

**Base URL**: `http://localhost:7071/api/v1` (local) or `https://your-app.azurewebsites.net/api/v1` (production)

**API Version**: 1.0

## Authentication

All endpoints require function-level authentication. Include the function key in requests:

```bash
curl -H "x-functions-key: YOUR_FUNCTION_KEY" ...
```

## Endpoints

### 1. Upload Document

Upload a PDF or Excel financial document for processing.

**Endpoint**: `POST /documents/upload`

**Content-Type**: `multipart/form-data`

**Request Body**:
- `file` (required): PDF or XLSX file (max 50MB)

**Request Example**:
```bash
curl -X POST http://localhost:7071/api/v1/documents/upload \
  -F "file=@Q4_2024_Financial_Report.pdf"
```

**Success Response** (202 Accepted):
```json
{
  "document_id": "doc-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "queued",
  "message": "Document uploaded successfully and queued for processing",
  "blob_url": "https://storage.blob.core.windows.net/financial-documents/2024/01/doc-a1b2c3d4.pdf",
  "estimated_processing_time_minutes": 5
}
```

**Error Responses**:

400 Bad Request - Invalid file type:
```json
{
  "error": "Unsupported file type. Only PDF and XLSX files are accepted.",
  "error_type": "validation_error"
}
```

413 Payload Too Large:
```json
{
  "error": "File size exceeds maximum allowed size. Size: 55.2MB, Max: 50MB",
  "error_type": "validation_error"
}
```

500 Internal Server Error:
```json
{
  "error": "Failed to store document",
  "error_type": "storage_error"
}
```

---

### 2. Check Processing Status

Query the current processing status of a document.

**Endpoint**: `GET /documents/{document_id}/status`

**Path Parameters**:
- `document_id` (required): Document identifier returned from upload

**Request Example**:
```bash
curl -X GET http://localhost:7071/api/v1/documents/doc-abc123/status
```

**Success Response** (200 OK):

**Processing**:
```json
{
  "document_id": "doc-abc123",
  "status": "processing",
  "progress": {
    "current_stage": "extraction",
    "stages_completed": ["upload", "ingestion", "extraction"],
    "completion_percentage": 75
  },
  "extraction_summary": {
    "tables_extracted": 5,
    "metrics_extracted": 25,
    "ocr_confidence": 0.92
  },
  "timestamps": {
    "uploaded_at": "2024-01-15T10:30:00Z",
    "started_processing_at": "2024-01-15T10:30:05Z",
    "completed_at": null
  },
  "estimated_completion_time": "2024-01-15T10:40:00Z"
}
```

**Completed**:
```json
{
  "document_id": "doc-abc123",
  "status": "completed",
  "progress": {
    "current_stage": "validation",
    "stages_completed": ["upload", "ingestion", "extraction", "validation"],
    "completion_percentage": 100
  },
  "extraction_summary": {
    "tables_extracted": 5,
    "metrics_extracted": 25,
    "ocr_confidence": 0.92
  },
  "validation_status": "passed",
  "timestamps": {
    "uploaded_at": "2024-01-15T10:30:00Z",
    "started_processing_at": "2024-01-15T10:30:05Z",
    "completed_at": "2024-01-15T10:33:45Z"
  },
  "estimated_completion_time": null,
  "error_message": null
}
```

**Failed**:
```json
{
  "document_id": "doc-abc123",
  "status": "failed",
  "progress": {
    "current_stage": "extraction",
    "stages_completed": ["upload", "ingestion"],
    "completion_percentage": 50
  },
  "timestamps": {
    "uploaded_at": "2024-01-15T10:30:00Z",
    "started_processing_at": "2024-01-15T10:30:05Z",
    "completed_at": null
  },
  "error_message": "Document Intelligence extraction failed: Timeout after 10 minutes"
}
```

**Error Responses**:

404 Not Found:
```json
{
  "error": "No processing records found for document: doc-abc123",
  "error_type": "document_not_found"
}
```

---

### 3. Get Extraction Results

Retrieve extracted financial metrics with full source references.

**Endpoint**: `GET /documents/{document_id}/results`

**Path Parameters**:
- `document_id` (required): Document identifier

**Query Parameters**:
- `include_low_confidence` (optional): Include flagged metrics (default: true)
- `format` (optional): Response format - "detailed" or "summary" (default: detailed)

**Request Example**:
```bash
# Detailed format (default)
curl -X GET http://localhost:7071/api/v1/documents/doc-abc123/results

# Summary format
curl -X GET "http://localhost:7071/api/v1/documents/doc-abc123/results?format=summary"

# Exclude low confidence metrics
curl -X GET "http://localhost:7071/api/v1/documents/doc-abc123/results?include_low_confidence=false"
```

**Success Response** (200 OK):

**Detailed Format**:
```json
{
  "document_id": "doc-abc123",
  "document_name": "Q4_2024_Financial_Report.pdf",
  "document_type": "PDF",
  "extraction_status": "completed",
  "validation_status": "passed",
  "requires_manual_review": false,
  "validation_errors": [],
  "validation_warnings": [],
  "metrics": [
    {
      "id": "metric-xyz789",
      "metric_type": "revenue",
      "metric_name": "Total Revenue",
      "value": 15750000.0,
      "currency": "USD",
      "period": "Q4 2024",
      "confidence_score": 0.95,
      "flagged_for_review": false,
      "source_reference": {
        "document_id": "doc-abc123",
        "document_name": "Q4_2024_Financial_Report.pdf",
        "page_number": 3,
        "sheet_name": null,
        "table_id": "table-1",
        "cell_reference": "row:5,col:2",
        "bounding_box": [120.5, 450.2, 180.3, 470.8]
      },
      "extracted_at": "2024-01-15T10:33:45Z"
    }
  ],
  "summary": {
    "total_metrics": 25,
    "flagged_metrics": 2,
    "avg_confidence": 0.92,
    "tables_extracted": 5
  },
  "timestamps": {
    "extracted_at": "2024-01-15T10:33:45Z"
  }
}
```

**Summary Format**:
```json
{
  "document_id": "doc-abc123",
  "document_name": "Q4_2024_Financial_Report.pdf",
  "validation_status": "passed",
  "metrics_summary": [
    {
      "metric_type": "revenue",
      "metric_name": "Total Revenue",
      "value": 15750000.0,
      "currency": "USD",
      "period": "Q4 2024",
      "confidence_score": 0.95
    }
  ],
  "total_metrics": 25
}
```

**Error Responses**:

404 Not Found:
```json
{
  "error": "No extraction result found for document: doc-abc123",
  "error_type": "document_not_found"
}
```

409 Conflict (processing incomplete):
```json
{
  "error": "Document processing is not complete",
  "error_type": "processing_incomplete",
  "current_status": "processing",
  "message": "Please check /status endpoint for processing status"
}
```

---

### 4. Retry Failed Processing

Retry processing for a failed document without re-uploading.

**Endpoint**: `POST /documents/{document_id}/retry`

**Path Parameters**:
- `document_id` (required): Document identifier

**Request Body** (JSON, optional):
```json
{
  "enhanced_ocr": false
}
```

**Request Example**:
```bash
# Standard retry
curl -X POST http://localhost:7071/api/v1/documents/doc-abc123/retry \
  -H "Content-Type: application/json" \
  -d '{}'

# Retry with enhanced OCR
curl -X POST http://localhost:7071/api/v1/documents/doc-abc123/retry \
  -H "Content-Type: application/json" \
  -d '{"enhanced_ocr": true}'
```

**Success Response** (202 Accepted):
```json
{
  "document_id": "doc-abc123",
  "status": "retry_queued",
  "message": "Document queued for retry processing",
  "retry_count": 1,
  "enhanced_ocr": false,
  "estimated_processing_time_minutes": 10
}
```

**Error Responses**:

400 Bad Request (not eligible):
```json
{
  "error": "Document processing already completed successfully",
  "error_type": "retry_not_eligible",
  "current_status": "completed",
  "message": "Document cannot be retried. Document processing already completed successfully"
}
```

400 Bad Request (max retries):
```json
{
  "error": "Maximum retry attempts exceeded (5 retries already attempted)",
  "error_type": "retry_not_eligible",
  "current_status": "failed",
  "message": "Document cannot be retried. Maximum retry attempts exceeded (5 retries already attempted)"
}
```

404 Not Found (blob deleted):
```json
{
  "error": "Original document no longer exists in Blob Storage",
  "error_type": "blob_not_found",
  "message": "Document has been deleted or expired. Please re-upload the document."
}
```

---

## Processing Status Values

| Status | Description |
|--------|-------------|
| `queued` | Document uploaded, waiting for processing |
| `processing` | Extraction or validation in progress |
| `completed` | All processing complete, results available |
| `failed` | Processing failed, retry available |

## Validation Status Values

| Status | Description |
|--------|-------------|
| `passed` | All validations successful |
| `flagged` | Warnings present, manual review recommended |
| `failed` | Critical errors found, requires correction |

## Rate Limits

- Upload: 100 concurrent uploads
- Status queries: Cached for 10 seconds per document
- API requests: Standard Azure Functions throttling applies

## Error Codes

| Code | Type | Description |
|------|------|-------------|
| 400 | validation_error | Invalid request or file |
| 404 | document_not_found | Document doesn't exist |
| 409 | processing_incomplete | Results not ready yet |
| 413 | validation_error | File too large |
| 500 | storage_error | Storage operation failed |
| 500 | server_error | Internal server error |

## Best Practices

1. **Upload**: Validate file size and type client-side before uploading
2. **Status**: Poll status endpoint with exponential backoff (e.g., 1s, 2s, 4s, 8s...)
3. **Results**: Only retrieve results after status is "completed"
4. **Retry**: Use enhanced OCR for low-quality scans or poor initial results
5. **Errors**: Implement proper error handling for all endpoints

## Examples

### Complete Workflow

```bash
# 1. Upload document
RESPONSE=$(curl -X POST http://localhost:7071/api/v1/documents/upload \
  -F "file=@report.pdf")
DOC_ID=$(echo $RESPONSE | jq -r '.document_id')

# 2. Poll for status
while true; do
  STATUS=$(curl -X GET http://localhost:7071/api/v1/documents/$DOC_ID/status | jq -r '.status')
  echo "Status: $STATUS"
  if [ "$STATUS" == "completed" ] || [ "$STATUS" == "failed" ]; then
    break
  fi
  sleep 2
done

# 3. Get results (if completed)
if [ "$STATUS" == "completed" ]; then
  curl -X GET http://localhost:7071/api/v1/documents/$DOC_ID/results | jq .
fi

# 4. Retry if failed
if [ "$STATUS" == "failed" ]; then
  curl -X POST http://localhost:7071/api/v1/documents/$DOC_ID/retry \
    -H "Content-Type: application/json" \
    -d '{"enhanced_ocr": true}'
fi
```

## Support

For issues or questions, please refer to the project documentation or contact the development team.
