# Research: Document Ingestion Pipeline

**Feature**: Document Ingestion Pipeline
**Date**: 2026-01-08
**Researchers**: Data Ingestion Engineer, Backend Engineer specialized skills

## Overview

This research document consolidates best practices and architectural decisions for building a document ingestion pipeline on Azure. Research focused on Azure Document Intelligence integration patterns, serverless architecture with Azure Functions, asynchronous processing workflows, and data persistence strategies for financial compliance.

---

## 1. Azure Document Intelligence Integration

### Decision

Use **Azure Document Intelligence (formerly Form Recognizer) prebuilt-layout model** for PDF and table extraction.

### Rationale

- **Purpose-built for financial documents**: Prebuilt-layout model specifically handles complex tables, multi-column layouts, and key-value pairs common in P&L statements and balance sheets
- **OCR confidence scoring**: Native support for confidence scores (0.0-1.0) per text element aligns with Constitution Principle II requirements
- **Bounding box coordinates**: Returns precise coordinates for visual verification and source reference tracking (Principle I)
- **Cell-level precision**: Identifies table structure including headers, row/column indices for exact source referencing
- **No training required**: Prebuilt model works immediately without custom training datasets
- **Cost-effective**: Pay-per-page pricing ($0.001/page for S0 tier) vs maintaining custom OCR infrastructure

### Alternatives Considered

| Alternative | Pros | Cons | Rejection Reason |
|-------------|------|------|------------------|
| Azure Computer Vision OCR | Lower cost ($0.0001/image) | No table structure detection, no confidence scores per cell | Cannot meet FR-009 (source references require table/cell positions) |
| Custom OCR (Tesseract) | Free, self-hosted | Lower accuracy (< 85% on scanned documents), no table parsing | Fails to meet SC-003 (0.90+ avg confidence requirement) |
| AWS Textract | Similar capabilities | Vendor lock-in to AWS, higher cost ($0.0015/page) | Azure-native architecture preferred for ecosystem integration |

### Best Practices

**API Client Pattern**:
```python
# Use singleton pattern with async client for connection pooling
from azure.ai.formrecognizer.aio import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential

class DocumentIntelligenceService:
    _client = None

    @classmethod
    async def get_client(cls):
        if cls._client is None:
            endpoint = os.getenv("DOCUMENT_INTELLIGENCE_ENDPOINT")
            key = await get_secret_from_keyvault("DOCUMENT_INTELLIGENCE_KEY")
            cls._client = DocumentAnalysisClient(endpoint, AzureKeyCredential(key))
        return cls._client
```

**Rate Limiting Strategy**:
- Azure Document Intelligence: 15 requests/second limit on S0 tier
- Solution: Queue bursts in Service Bus (ingestion-queue), process with controlled concurrency (max 10 simultaneous)
- Circuit breaker pattern for transient failures (3 retries with exponential backoff)

**Batching Optimization**:
- Process multi-page PDFs as single API call (not page-by-page) to reduce cost and latency
- For Excel: Process one sheet at a time if > 100 sheets (rare edge case)

---

## 2. Excel File Processing Strategy

### Decision

Use **openpyxl library** for native Excel parsing with fallback to pandas for data manipulation.

### Rationale

- **Cell-level source references**: openpyxl provides cell coordinates (e.g., "B34") directly, meeting FR-009 requirement
- **Preserves formulas**: Can read both formula and calculated value for validation
- **No cloud API needed**: Local processing is faster and more cost-effective than Document Intelligence for Excel (which only supports PDF)
- **Mature library**: openpyxl is industry-standard for Excel manipulation (3M+ downloads/month)

### Alternatives Considered

| Alternative | Pros | Cons | Rejection Reason |
|-------------|------|------|------------------|
| pandas read_excel | Simpler API, good for data analysis | Loses cell-level coordinates, merges cells lose structure | Cannot meet FR-009 (requires exact cell reference) |
| xlrd | Lightweight, fast | Only supports .xls (not .xlsx), deprecated | Modern Excel files use .xlsx format |
| Azure Document Intelligence | Consistent with PDF processing | No native Excel support (requires conversion to PDF first) | Conversion step loses cell references and introduces errors |

### Best Practices

**Handling Large Excel Files**:
- Stream reading for files > 10MB using `openpyxl.load_workbook(filename, read_only=True)`
- Process sheets in parallel using asyncio (limit 5 concurrent sheets to avoid memory issues)
- Memory limit: 200MB per function instance (Azure Functions consumption plan)

**Formula Evaluation**:
```python
# Read both formula and value for validation
cell = worksheet['B34']
raw_value = cell.value  # Calculated value
formula = cell.value if cell.data_type == 'f' else None
```

---

## 3. Serverless Architecture with Azure Functions

### Decision

Use **Azure Functions v4 (Python 3.11)** with **Service Bus triggers** for asynchronous processing pipeline.

### Rationale

- **Event-driven architecture**: Natural fit for upload → extract → validate → store workflow
- **Auto-scaling**: Handles concurrent uploads (target: 100 simultaneous) without manual capacity planning
- **Cost-effective**: Pay-per-execution + consumption plan = $0 when idle, scales automatically under load
- **Managed infrastructure**: No server maintenance, patching handled by Azure
- **Integration**: Native bindings for Blob Storage, Service Bus, Cosmos DB reduce boilerplate code

### Architecture Pattern

**Fan-Out/Fan-In with Service Bus Queues**:

```
[Upload HTTP Trigger]
      ↓ (save to Blob, queue message)
[Service Bus: ingestion-queue]
      ↓
[Process Ingestion Worker] (validate file, enqueue for extraction)
      ↓
[Service Bus: extraction-queue]
      ↓
[Extraction Worker] (PDF: Doc Intelligence, Excel: openpyxl)
      ↓
[Service Bus: validation-queue]
      ↓
[Validation Worker] (confidence check, range validation)
      ↓
[Cosmos DB: extraction-results, financial-metrics]
```

### Best Practices

**Function Composition**:
- Keep functions small (< 200 lines): Single Responsibility Principle
- Extract shared logic to `services/` layer
- Use dependency injection for testability:

```python
# Bad: Hardcoded dependencies
async def extraction_worker(msg: ServiceBusMessage):
    client = DocumentAnalysisClient(...)  # Hard to mock

# Good: Injected dependencies
async def extraction_worker(
    msg: ServiceBusMessage,
    doc_intel_service: DocumentIntelligenceService = Depends()
):
    result = await doc_intel_service.analyze(msg.document_url)
```

**Error Handling**:
- Use Service Bus **dead-letter queue** for messages that fail after 3 retries
- Log full exception stack trace to Application Insights for debugging
- Return clear error messages to user via status API

**Timeout Configuration**:
```json
// host.json
{
  "version": "2.0",
  "functionTimeout": "00:10:00",  // 10 minutes max per function
  "extensions": {
    "serviceBus": {
      "prefetchCount": 0,  // No prefetch to prevent timeout on slow processing
      "maxConcurrentCalls": 10,  // Limit concurrent processing
      "autoCompleteMessages": false  // Manual completion for retry control
    }
  }
}
```

---

## 4. Data Persistence Strategy

### Decision

**Three-tier storage architecture**:
1. **Azure Blob Storage** (Hot tier) → Raw documents
2. **Azure Cosmos DB** (Session consistency) → Structured extraction results
3. **Azure Table Storage** → Audit logs

### Rationale

**Blob Storage for Raw Documents**:
- Immutable storage: Documents never modified after upload (append-only)
- Lifecycle management: Auto-transition to Cool tier after 90 days, Archive after 3 years (meets 7-year retention at lowest cost)
- Supports large files: 50MB limit is well within 5TB block blob limit
- Encryption at rest: Enabled by default (Microsoft-managed keys)

**Cosmos DB for Structured Data**:
- Global distribution: Future multi-region support for disaster recovery
- Low latency: < 10ms p99 read latency for status queries (exceeds SC-011 requirement of < 5 seconds)
- Flexible schema: JSON documents support nested source references without joins
- Automatic indexing: All properties indexed by default for fast queries

**Table Storage for Audit Logs**:
- Cost-effective: $0.05/GB/month vs Cosmos DB $0.25/GB/month (5x cheaper)
- Partition key strategy: `{year}-{month}` enables efficient range queries for compliance reports
- Retention: 7-year lifecycle policy via Blob Storage (Table Storage exports)

### Alternatives Considered

| Alternative | Pros | Cons | Rejection Reason |
|-------------|------|------|------------------|
| Azure SQL Database | Relational integrity, complex queries | Rigid schema, higher cost ($5/month minimum) | Flexible JSON schema preferred for varying financial statement formats |
| MongoDB (self-hosted) | Flexible schema | Requires infrastructure management, no native Azure integration | Managed service preferred (Cosmos DB offers MongoDB API) |
| All-in Cosmos DB (including audit logs) | Single data store | Audit logs are high-volume, low-query → cost inefficient | Table Storage 5x cheaper for append-only logs |

### Best Practices

**Cosmos DB Partition Strategy**:
```python
# Partition key: document_id (high cardinality, evenly distributed)
# Queries by document_id are single-partition (low RU cost)

# Container: extraction-results
{
    "id": "result-abc123",
    "document_id": "doc-abc123",  // Partition key
    "extraction_timestamp": "2026-01-08T10:30:00Z",
    "ocr_confidence": 0.92,
    ...
}

# Container: financial-metrics
{
    "id": "metric-xyz789",
    "document_id": "doc-abc123",  // Partition key (enables grouped queries)
    "metric_name": "revenue",
    "value": 10000000,
    "source_reference": { ... },
    ...
}
```

**Blob Storage Naming Convention**:
```
Container: financial-documents
Path: {year}/{month}/{document_id}.pdf

Example: 2026/01/doc-abc123.pdf

Benefits:
- Chronological organization for lifecycle policies
- Partition-friendly (Azure Blob partitions by prefix)
- Easy to locate documents by upload date for audits
```

---

## 5. Asynchronous Message Queueing

### Decision

Use **Azure Service Bus Standard tier** with **topic/subscription pattern** for future extensibility.

### Rationale

- **Decoupling**: Upload function doesn't wait for extraction to complete (async processing)
- **Reliability**: Messages persist until processed (at-least-once delivery guarantee)
- **Dead-letter queue**: Failed messages after 3 retries move to DLQ for manual investigation
- **Future-proof**: Topic/subscription pattern enables multiple consumers (e.g., future real-time dashboard subscriber)

### Queue Design

**Queue Hierarchy**:
1. `ingestion-queue` (max delivery count: 3)
   - Message: `{ "document_id": "doc-abc123", "blob_url": "...", "uploader_user_id": "user-123" }`
   - Consumer: `process_ingestion.py` (validate file, enqueue for extraction)

2. `extraction-queue` (max delivery count: 3)
   - Message: `{ "document_id": "doc-abc123", "document_type": "pdf|excel" }`
   - Consumer: `extraction_worker.py` (call Document Intelligence or openpyxl)

3. `validation-queue` (max delivery count: 1)
   - Message: `{ "document_id": "doc-abc123", "extraction_result_id": "result-abc123" }`
   - Consumer: `validation_worker.py` (check completeness, range validation)

**Dead-Letter Queue Monitoring**:
- Azure Monitor alert if DLQ depth > 10 messages
- Runbook: Investigate error patterns, fix validation logic, replay messages

### Best Practices

**Idempotency**:
```python
# Ensure processing same message twice doesn't cause duplicates
async def extraction_worker(msg: ServiceBusMessage):
    document_id = msg.body["document_id"]

    # Check if already processed (Cosmos DB query)
    existing = await cosmos.query_item(
        container="extraction-results",
        query=f"SELECT * FROM c WHERE c.document_id = '{document_id}'"
    )

    if existing:
        logger.info(f"Document {document_id} already processed, skipping")
        await msg.complete()  # Acknowledge without re-processing
        return

    # Proceed with extraction...
```

**Exponential Backoff**:
```python
# Service Bus built-in retry with exponential backoff
# host.json configuration
{
  "extensions": {
    "serviceBus": {
      "retryOptions": {
        "mode": "exponential",
        "tryTimeout": "00:01:00",
        "delay": "00:00:05",
        "maxDelay": "00:01:00",
        "maxRetries": 3
      }
    }
  }
}
```

---

## 6. Security Best Practices

### Decision

**Azure AD Managed Identity + Key Vault** for secrets management, **RBAC** for resource access.

### Rationale (per Constitution Principle V)

- **No hardcoded secrets**: Connection strings and API keys stored in Key Vault
- **Managed Identity**: Azure Functions use system-assigned MI to access Key Vault, Blob Storage, Cosmos DB (no credentials in code)
- **Least privilege**: Each function has minimum required permissions (e.g., upload function: Blob write-only, no read)
- **Audit trail**: Azure AD logs all access attempts for compliance

### Implementation

**Key Vault Integration**:
```python
# Retrieve secret at runtime (cached for performance)
from azure.identity.aio import DefaultAzureCredential
from azure.keyvault.secrets.aio import SecretClient

async def get_secret_from_keyvault(secret_name: str) -> str:
    credential = DefaultAzureCredential()  # Uses Managed Identity in Azure
    vault_url = os.getenv("KEY_VAULT_URL")
    client = SecretClient(vault_url=vault_url, credential=credential)

    secret = await client.get_secret(secret_name)
    return secret.value
```

**RBAC Assignments** (via Bicep):
```bicep
// Grant Function App Managed Identity access to Blob Storage
resource blobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(functionApp.id, storageAccount.id, 'StorageBlobDataContributor')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')  // Storage Blob Data Contributor
    principalId: functionApp.identity.principalId
  }
}
```

---

## 7. Monitoring and Telemetry

### Decision

**Application Insights** for distributed tracing, custom metrics, and log aggregation.

### Rationale

- **Correlation IDs**: Track single document through entire pipeline (upload → extract → validate)
- **Custom metrics**: Track OCR confidence distribution, processing latency percentiles, validation failure rate
- **Alerts**: Proactive notification for extraction failures, queue depth, slow processing
- **Query language (KQL)**: Powerful log analysis for debugging and compliance reporting

### Best Practices

**Custom Telemetry**:
```python
from opencensus.ext.azure.log_exporter import AzureLogHandler
from azure.monitor.opentelemetry import configure_azure_monitor

# Track custom metrics
telemetry_client.track_metric("document_extraction_duration_ms", duration_ms)
telemetry_client.track_metric("ocr_confidence_score", confidence_score)
telemetry_client.track_metric("validation_failure_rate", failure_rate)

# Track custom events
telemetry_client.track_event(
    "LowConfidenceExtraction",
    properties={
        "document_id": document_id,
        "confidence_score": 0.68,
        "flagged_for_review": True
    }
)
```

**Alerts Configuration**:
- Extraction failure rate > 10% in 15 minutes → Page on-call engineer
- Service Bus queue depth > 100 messages for 30 minutes → Investigate processing bottleneck
- Average OCR confidence < 0.75 for 1 hour → Review document quality with business users

---

## 8. Testing Strategy

### Decision

**Three-tier testing**: Unit tests (pytest), contract tests (golden datasets), integration tests (Azurite emulator).

### Rationale

- **Unit tests**: Fast feedback, cover business logic in services/validators
- **Contract tests**: Verify API responses match OpenAPI spec, use real sample PDFs/Excel
- **Integration tests**: Validate Azure service interactions without deploying to cloud (cost savings)

### Golden Datasets

Create representative samples covering edge cases:
- `sample_income_statement.pdf`: Standard P&L with 3 pages, 300 DPI scan
- `low_quality_scan.pdf`: 150 DPI scan to test confidence flagging
- `complex_multi_sheet.xlsx`: 5 sheets with various table structures
- `expected_outputs.json`: Known-good extraction results for regression testing

**Test Coverage Targets**:
- Unit tests: 80% code coverage minimum
- Contract tests: 100% of API endpoints
- Integration tests: All critical paths (upload → extract → validate)

---

## Implementation Priorities

Based on user story priorities (P1, P2, P3) from spec:

1. **Phase 1 (P1 - MVP)**:
   - Upload handler (HTTP trigger)
   - Blob Storage integration
   - Azure Document Intelligence integration (PDF)
   - Excel parser (openpyxl)
   - Cosmos DB persistence
   - Basic validation (completeness check)

2. **Phase 2 (P2 - Enhanced)**:
   - Confidence scoring and flagging
   - Advanced validation (range checks)
   - Status tracking API
   - Audit logging to Table Storage

3. **Phase 3 (P3 - Polish)**:
   - Retry logic for failed ingestions
   - Performance optimizations
   - Monitoring dashboards
   - Alerting rules

---

## Risk Analysis

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Azure Document Intelligence API rate limits hit | Medium | High (processing delays) | Service Bus queueing with controlled concurrency (max 10 simultaneous) |
| OCR quality < 0.75 for majority of documents | Low | High (manual review overhead) | User education on document quality (300+ DPI), pre-upload validation |
| Large Excel files (> 100 sheets) timeout | Low | Medium | Stream processing with read-only mode, process sheets in parallel |
| Cosmos DB cost overruns | Medium | Medium | Monitor RU consumption, optimize queries with partition keys, use TTL for non-critical data |
| Blob Storage reaching 500GB faster than expected | Low | Low | Lifecycle policy to Archive tier after 3 years, monitor growth rate monthly |

---

## Conclusion

Research validates the Azure-native serverless architecture as optimal for the Document Ingestion Pipeline. Key decisions:
- Azure Document Intelligence for PDF extraction (purpose-built, confidence scoring)
- openpyxl for Excel parsing (cell-level references)
- Azure Functions + Service Bus for scalable async processing
- Three-tier storage (Blob, Cosmos DB, Table Storage) for cost-optimized persistence
- Managed Identity + Key Vault for secure secrets management

All decisions align with constitution principles, particularly Principle I (source reference tracking), Principle III (7-year audit trail), and Principle V (secure data handling).

**Next Steps**: Proceed to Phase 1 (data-model.md, contracts/, quickstart.md) for detailed schema design and API specifications.
