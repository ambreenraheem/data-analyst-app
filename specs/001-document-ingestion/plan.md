# Implementation Plan: Document Ingestion Pipeline

**Branch**: `001-document-ingestion` | **Date**: 2026-01-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-document-ingestion/spec.md`

**Note**: This template is filled in by the `/sp.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

The Document Ingestion Pipeline enables financial analysts to upload PDF and Excel financial reports for automated extraction of structured financial metrics with full source reference tracking. The system accepts documents up to 50MB, extracts tables and key-value pairs using Azure Document Intelligence, validates data quality with OCR confidence scoring, and persists both raw documents and structured data for 7-year audit trail compliance. Core capabilities include asynchronous processing (< 5 minutes for typical documents), validation rules for completeness and reasonableness, real-time status tracking, and retry mechanisms for transient failures.

**Technical Approach**: Azure-native serverless architecture using Azure Functions for event-driven processing, Azure Blob Storage for raw document persistence, Azure Document Intelligence for PDF/Excel extraction, Cosmos DB for structured data storage with source references, and Azure Service Bus for asynchronous message queueing between processing stages.

## Technical Context

**Language/Version**: Python 3.11 (Azure Functions v4 runtime, asyncio for concurrent processing)

**Primary Dependencies**:
- `azure-functions` 1.18.0 - Serverless compute runtime
- `azure-ai-formrecognizer` 3.3.2 - Azure Document Intelligence SDK (prebuilt-layout model)
- `azure-storage-blob` 12.19.0 - Document persistence in Blob Storage
- `azure-cosmos` 4.5.1 - Structured data storage with source references
- `azure-servicebus` 7.11.4 - Message queueing for async processing
- `azure-identity` 1.15.0 - Managed Identity authentication
- `azure-keyvault-secrets` 4.7.0 - Secrets management
- `pydantic` 2.5.0 - Data validation and schema enforcement
- `openpyxl` 3.1.2 - Excel file parsing (.xlsx)
- `pandas` 2.1.4 - Data manipulation for validation logic

**Storage**:
- Azure Blob Storage (raw documents): Container `financial-documents`, 7-year retention with Cool tier after 90 days
- Azure Cosmos DB (structured data): Containers `extraction-results`, `financial-metrics`, `source-references`, `processing-logs` with Session consistency
- Azure Table Storage (audit logs): Table `AuditLogs` with 7-year retention for compliance

**Testing**:
- `pytest` 7.4.4 - Unit and integration testing framework
- `pytest-asyncio` 0.23.3 - Async test support
- `pytest-mock` 3.12.0 - Mocking Azure services for unit tests
- Contract tests using golden datasets (sample PDFs/Excel with known expected outputs)
- Integration tests with Azure Storage Emulator (Azurite) for local development

**Target Platform**: Azure Cloud (serverless, multi-region deployment support for DR)

**Project Type**: Single backend project (serverless functions + storage)

**Performance Goals**:
- Document upload acceptance: < 2 seconds to acknowledge receipt and return document ID
- PDF extraction (10-50 pages): < 5 minutes end-to-end (upload → extraction → validation → storage)
- Excel extraction (multi-sheet): < 3 minutes end-to-end
- Status query latency: < 500ms (read from Cosmos DB)
- Concurrent uploads: Support 100 simultaneous uploads without degradation

**Constraints**:
- Maximum file size: 50MB (enforced at API gateway level)
- Azure Document Intelligence API: 15 requests/second rate limit (queue bursts via Service Bus)
- OCR processing timeout: 10 minutes maximum per document (fail with retry option after timeout)
- Cosmos DB: < 100ms p95 read latency for status queries
- Blob Storage: Standard tier (not Premium) for cost optimization with lifecycle management

**Scale/Scope**:
- Expected volume: 1,000 documents/day initially, scaling to 10,000 documents/day
- Storage: ~500GB raw documents in first year (assuming avg 10MB per document × 50K documents)
- Cosmos DB: ~10M metrics records/year (assuming avg 200 metrics per document)
- Concurrent processing: 10 documents simultaneously (Azure Functions auto-scaling)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: Data-First Financial Analysis

✅ **PASS**: Source reference tracking is core requirement
- **FR-009**: Every extracted value includes document name, page/sheet, table/cell position
- **Key Entities**: `SourceReference` entity captures document ID, page number, cell reference, bounding box coordinates
- **Architecture**: Cosmos DB schema includes source references as nested property in `FinancialMetric` documents
- **Compliance**: Raw documents persisted in Blob Storage before extraction begins (FR-018)

### Principle II: Autonomous Reasoning with Confidence Thresholds

✅ **PASS**: OCR confidence scoring foundation for downstream analysis
- **FR-013**: Azure Document Intelligence assigns confidence scores (0.0-1.0) to extracted text elements
- **FR-016/FR-017**: Threshold-based flagging (< 0.75 avg for document, < 0.70 for individual cells)
- **Data Model**: `ExtractionResult` entity stores overall confidence score; `FinancialMetric` stores per-metric confidence
- **Human-in-the-Loop**: Low confidence triggers manual review flag (aligns with Principle VI)

### Principle III: Explainability and Auditability

✅ **PASS**: 7-year retention and audit logging mandated
- **FR-024**: Raw documents retained for 7 years in Blob Storage (configurable lifecycle policy)
- **FR-025**: All access events logged with user identity and timestamp
- **Storage**: Azure Table Storage `AuditLogs` table with partition key `{year}-{month}` for efficient compliance queries
- **Compliance**: Supports SOX, GDPR audit requirements per constitution

### Principle IV: Anomaly Detection and Risk Flagging

⚠️ **NOT APPLICABLE** (Future Feature): Document ingestion is prerequisite, not anomaly detection
- **Rationale**: This feature provides clean, validated data as input for future anomaly detection features
- **Validation**: FR-014/FR-015 include basic reasonableness checks (revenue > 0, not > $1 trillion) but not statistical anomaly detection
- **Future**: Anomaly detection will consume data from this pipeline via Cosmos DB queries

### Principle V: Secure Data Handling and Access Control

✅ **PASS**: Encryption, RBAC, and secrets management required
- **Encryption at rest**: Azure Blob Storage and Cosmos DB both use Microsoft-managed encryption keys
- **Encryption in transit**: TLS 1.3 enforced for all API calls (Azure Functions HTTPS-only mode)
- **Secrets**: Azure Key Vault for Document Intelligence API key, Cosmos connection string, Storage connection string
- **RBAC**: Azure AD Managed Identity for Functions to access Blob Storage and Cosmos DB (no connection strings in code)
- **Audit**: FR-025 mandates access logging per constitution requirement

### Principle VI: Human-in-the-Loop for High-Stakes Decisions

✅ **PASS**: Manual review flags for low confidence extractions
- **FR-016**: Documents with avg OCR confidence < 0.75 flagged for manual review
- **FR-017**: Individual metrics with confidence < 0.70 flagged for verification
- **User Story 3**: Validation alerts analysts to potential extraction errors before data enters analysis pipeline
- **Rationale**: Ingestion itself has no high-stakes decisions; human review focuses on data quality

### Principle VII: Continuous Learning and Model Versioning

✅ **PASS**: Versioning strategy for extraction logic
- **Semantic Versioning**: Azure Document Intelligence model version tracked in `ExtractionResult` (e.g., "prebuilt-layout-2024-02-29")
- **Validation Rules**: Versioned in code (e.g., `validation_rules_v1.py`) with git history
- **Rollback**: Previous Azure Functions deployment slots retained for 90 days (blue-green deployment)
- **A/B Testing**: Not applicable for extraction (deterministic process), but validation rule changes can be tested in staging

### Overall Gate Status

**✅ ALL GATES PASSED**

No violations requiring justification. The design fully aligns with constitution principles.

## Project Structure

### Documentation (this feature)

```text
specs/001-document-ingestion/
├── plan.md              # This file (/sp.plan command output)
├── research.md          # Phase 0 output (Azure service patterns, best practices)
├── data-model.md        # Phase 1 output (Cosmos DB schema, entity relationships)
├── quickstart.md        # Phase 1 output (local dev setup, sample requests)
├── contracts/           # Phase 1 output (OpenAPI spec for upload/status APIs)
│   └── ingestion-api.openapi.yaml
├── spec.md              # Feature specification (input to planning)
└── checklists/
    └── requirements.md  # Specification quality validation
```

### Source Code (repository root)

```text
src/
├── ingestion/
│   ├── functions/
│   │   ├── upload_handler.py          # HTTP trigger: POST /api/v1/documents/upload
│   │   ├── process_ingestion.py       # Service Bus trigger: ingestion-queue
│   │   ├── extraction_worker.py       # Service Bus trigger: extraction-queue
│   │   ├── validation_worker.py       # Service Bus trigger: validation-queue
│   │   └── status_handler.py          # HTTP trigger: GET /api/v1/documents/{id}/status
│   ├── models/
│   │   ├── financial_document.py      # Pydantic model for FinancialDocument entity
│   │   ├── extraction_result.py       # Pydantic model for ExtractionResult
│   │   ├── financial_metric.py        # Pydantic model for FinancialMetric
│   │   ├── source_reference.py        # Pydantic model for SourceReference
│   │   └── processing_log.py          # Pydantic model for ProcessingLog
│   ├── services/
│   │   ├── document_intelligence.py   # Azure Document Intelligence client wrapper
│   │   ├── excel_parser.py            # Excel extraction logic (openpyxl)
│   │   ├── financial_parser.py        # Income statement/balance sheet parser
│   │   ├── validator.py               # Data validation rules (completeness, ranges)
│   │   ├── storage_manager.py         # Blob Storage operations
│   │   └── cosmos_manager.py          # Cosmos DB CRUD operations
│   └── utils/
│       ├── confidence_scorer.py       # OCR confidence analysis
│       ├── number_parser.py           # Financial number parsing ($, commas, K/M/B)
│       └── audit_logger.py            # Audit log writer (Table Storage)
│
├── shared/
│   ├── config.py                      # Configuration (Key Vault references)
│   ├── exceptions.py                  # Custom exception classes
│   └── telemetry.py                   # Application Insights integration
│
tests/
├── contract/
│   ├── test_upload_api.py             # Contract tests for upload endpoint
│   ├── test_status_api.py             # Contract tests for status endpoint
│   └── golden_datasets/               # Sample PDFs/Excel with expected outputs
│       ├── sample_income_statement.pdf
│       ├── sample_excel_report.xlsx
│       └── expected_outputs.json
├── integration/
│   ├── test_end_to_end_pdf.py         # Upload → extract → validate flow (PDF)
│   ├── test_end_to_end_excel.py       # Upload → extract → validate flow (Excel)
│   └── test_retry_logic.py            # Retry failed ingestion scenarios
└── unit/
    ├── test_financial_parser.py       # Unit tests for income statement parsing
    ├── test_validator.py               # Unit tests for validation rules
    ├── test_number_parser.py           # Unit tests for $10M parsing logic
    └── test_confidence_scorer.py       # Unit tests for OCR quality assessment

infrastructure/
├── bicep/
│   ├── main.bicep                     # Main infrastructure template
│   ├── modules/
│   │   ├── storage.bicep              # Blob Storage and Table Storage
│   │   ├── cosmos.bicep               # Cosmos DB account and containers
│   │   ├── function_app.bicep         # Azure Functions app service plan
│   │   ├── service_bus.bicep          # Service Bus namespace and queues
│   │   └── key_vault.bicep            # Key Vault for secrets
│   └── parameters/
│       ├── dev.parameters.json
│       ├── staging.parameters.json
│       └── production.parameters.json

.github/
└── workflows/
    ├── ci.yml                         # Build, test, security scan
    └── deploy.yml                     # Deploy to Azure (staging/production)

pyproject.toml                          # Poetry dependencies
requirements.txt                        # Locked dependencies (pip-tools output)
.env.example                            # Environment variables template
host.json                               # Azure Functions host configuration
local.settings.json.example             # Local development settings template
```

**Structure Decision**: Single backend project selected because the feature is purely server-side document processing with no frontend UI components. Azure Functions provides natural separation of concerns through individual function handlers (upload, extraction, validation, status) while sharing common models and services. This structure supports:
- **Independent deployment**: Each function can be deployed separately
- **Testability**: Clear boundaries between HTTP triggers, Service Bus triggers, and business logic
- **Scalability**: Azure Functions auto-scaling handles concurrent processing
- **Maintainability**: Shared models and services in `src/ingestion/` prevent duplication

## Complexity Tracking

> **Not Applicable**: No constitution violations to justify.

All constitution principles pass without requiring complexity trade-offs.
