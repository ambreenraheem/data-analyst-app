# Tasks: Document Ingestion Pipeline

**Input**: Design documents from `/specs/001-document-ingestion/`
**Prerequisites**: plan.md (required), spec.md (required), data-model.md, contracts/, research.md

**Tests**: No test tasks included (not explicitly requested in feature specification)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4, US5)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root (confirmed in plan.md)
- Paths shown below use absolute paths where needed

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create project directory structure per plan.md (src/ingestion/, tests/, infrastructure/)
- [ ] T002 Initialize Python project with Poetry in pyproject.toml
- [ ] T003 [P] Add Azure SDK dependencies to pyproject.toml (azure-functions, azure-storage-blob, azure-cosmos, azure-servicebus, azure-ai-formrecognizer, azure-identity, azure-keyvault-secrets)
- [ ] T004 [P] Add data processing dependencies to pyproject.toml (pydantic, openpyxl, pandas)
- [ ] T005 [P] Add testing dependencies to pyproject.toml dev group (pytest, pytest-asyncio, pytest-mock)
- [ ] T006 [P] Configure linting and formatting tools in pyproject.toml (black, ruff, mypy)
- [ ] T007 Create Azure Functions host.json with timeout and Service Bus configuration
- [ ] T008 Create local.settings.json.example template with Key Vault and storage references
- [ ] T009 Create .env.example template for local development environment variables
- [ ] T010 [P] Create .gitignore for Python, Azure Functions, and IDE files

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T011 Create src/shared/config.py with Key Vault secret retrieval using DefaultAzureCredential
- [ ] T012 [P] Create src/shared/exceptions.py with custom exception classes (DocumentNotFoundError, ExtractionFailedError, ValidationError)
- [ ] T013 [P] Create src/shared/telemetry.py with Application Insights client initialization and custom metric tracking
- [ ] T014 Create src/ingestion/models/financial_document.py with Pydantic model matching Blob metadata schema
- [ ] T015 [P] Create src/ingestion/models/extraction_result.py with Pydantic model for ExtractionResult entity
- [ ] T016 [P] Create src/ingestion/models/financial_metric.py with Pydantic model for FinancialMetric entity
- [ ] T017 [P] Create src/ingestion/models/source_reference.py with Pydantic model for SourceReference (nested in FinancialMetric)
- [ ] T018 [P] Create src/ingestion/models/processing_log.py with Pydantic model for ProcessingLog entity
- [ ] T019 Create src/ingestion/services/storage_manager.py with BlobServiceClient wrapper for document upload/download operations
- [ ] T020 [P] Create src/ingestion/services/cosmos_manager.py with CosmosClient wrapper for CRUD operations on extraction-results, financial-metrics, processing-logs containers
- [ ] T021 [P] Create src/ingestion/utils/audit_logger.py with TableServiceClient wrapper for writing access events to AuditLogs table
- [ ] T022 Create infrastructure/bicep/main.bicep with module references for all Azure resources
- [ ] T023 [P] Create infrastructure/bicep/modules/storage.bicep for Blob Storage and Table Storage with lifecycle policy
- [ ] T024 [P] Create infrastructure/bicep/modules/cosmos.bicep for Cosmos DB account with extraction-results, financial-metrics, processing-logs containers
- [ ] T025 [P] Create infrastructure/bicep/modules/function_app.bicep for Azure Functions with Python 3.11 runtime
- [ ] T026 [P] Create infrastructure/bicep/modules/service_bus.bicep for Service Bus namespace with ingestion-queue, extraction-queue, validation-queue
- [ ] T027 [P] Create infrastructure/bicep/modules/key_vault.bicep for Key Vault with access policies for Function App Managed Identity
- [ ] T028 Create infrastructure/bicep/parameters/dev.parameters.json with development environment configuration

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Upload Financial Document (Priority: P1) 🎯 MVP

**Goal**: Enable analysts to upload PDF and Excel files with validation and queueing

**Independent Test**: Upload sample PDF, verify document ID returned, status="queued", document persisted in Blob Storage

### Implementation for User Story 1

- [ ] T029 [P] [US1] Create src/ingestion/functions/upload_handler.py with HTTP trigger for POST /api/v1/documents/upload
- [ ] T030 [US1] Implement file upload validation in upload_handler.py (check file type PDF/XLSX, size < 50MB, integrity check)
- [ ] T031 [US1] Implement document ID generation in upload_handler.py (UUID with "doc-" prefix)
- [ ] T032 [US1] Implement Blob Storage upload in upload_handler.py using storage_manager.py (save to financial-documents container with {year}/{month}/{document_id} path)
- [ ] T033 [US1] Implement Service Bus message queueing in upload_handler.py (enqueue to ingestion-queue with document_id, blob_url, uploader_user_id)
- [ ] T034 [US1] Implement audit logging in upload_handler.py using audit_logger.py (log upload event with user identity and timestamp)
- [ ] T035 [US1] Implement error handling in upload_handler.py (400 for invalid format, 413 for oversized, 500 for server errors)
- [ ] T036 [US1] Add OpenAPI route registration for /documents/upload endpoint in function.json
- [ ] T037 [P] [US1] Create src/ingestion/functions/process_ingestion.py with Service Bus trigger for ingestion-queue
- [ ] T038 [US1] Implement file integrity validation in process_ingestion.py (verify Blob exists, not corrupted)
- [ ] T039 [US1] Implement duplicate detection in process_ingestion.py using file hash (query Cosmos DB for existing document_id by SHA256 hash)
- [ ] T040 [US1] Implement Service Bus queueing to extraction-queue in process_ingestion.py (enqueue with document_id and document_type)
- [ ] T041 [US1] Implement processing log creation in process_ingestion.py using cosmos_manager.py (log "queued" event to processing-logs container)
- [ ] T042 [US1] Add error handling and dead-letter queue logic in process_ingestion.py (retry up to 3 times, move to DLQ on failure)

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently (upload → validate → queue → persist)

---

## Phase 4: User Story 2 - Extract Structured Financial Data (Priority: P1)

**Goal**: Automatically extract financial metrics from PDF and Excel with source references

**Independent Test**: Upload known financial report, verify extracted metrics match expected values with complete source references (document name, page, cell)

### Implementation for User Story 2

- [ ] T043 [P] [US2] Create src/ingestion/services/document_intelligence.py with DocumentAnalysisClient wrapper for Azure Document Intelligence prebuilt-layout model
- [ ] T044 [US2] Implement PDF table extraction in document_intelligence.py (call begin_analyze_document_from_url, parse tables with row/column indices)
- [ ] T045 [US2] Implement source reference extraction in document_intelligence.py (capture page number, table ID, bounding box coordinates for each cell)
- [ ] T046 [P] [US2] Create src/ingestion/services/excel_parser.py with openpyxl-based Excel extraction
- [ ] T047 [US2] Implement multi-sheet Excel parsing in excel_parser.py (iterate all sheets, extract data with cell references like "Sheet1!B34")
- [ ] T048 [P] [US2] Create src/ingestion/services/financial_parser.py for identifying financial statement types
- [ ] T049 [US2] Implement income statement detection in financial_parser.py (search for keywords: "revenue", "COGS", "operating expenses", "net income")
- [ ] T050 [US2] Implement income statement line item parsing in financial_parser.py (extract revenue, COGS, gross profit, operating expenses, EBITDA, net income with row/column positions)
- [ ] T051 [P] [US2] Create src/ingestion/utils/number_parser.py for financial number format handling
- [ ] T052 [US2] Implement currency parsing in number_parser.py (handle $, €, commas, parentheses for negatives, K/M/B abbreviations)
- [ ] T053 [P] [US2] Create src/ingestion/utils/confidence_scorer.py for OCR quality assessment
- [ ] T054 [US2] Implement confidence score aggregation in confidence_scorer.py (calculate average confidence per document, per table, per cell)
- [ ] T055 [P] [US2] Create src/ingestion/functions/extraction_worker.py with Service Bus trigger for extraction-queue
- [ ] T056 [US2] Implement PDF extraction workflow in extraction_worker.py (call document_intelligence.py, parse tables, extract financial metrics)
- [ ] T057 [US2] Implement Excel extraction workflow in extraction_worker.py (call excel_parser.py, extract metrics from all sheets)
- [ ] T058 [US2] Implement source reference creation in extraction_worker.py (build SourceReference objects with document name, page/sheet, table/cell positions)
- [ ] T059 [US2] Implement ExtractionResult persistence in extraction_worker.py using cosmos_manager.py (save to extraction-results container with overall OCR confidence)
- [ ] T060 [US2] Implement FinancialMetric persistence in extraction_worker.py using cosmos_manager.py (save to financial-metrics container with nested source_reference)
- [ ] T061 [US2] Implement Service Bus queueing to validation-queue in extraction_worker.py (enqueue with document_id and extraction_result_id)
- [ ] T062 [US2] Implement processing log update in extraction_worker.py (log "extraction_completed" event with metrics_extracted count)
- [ ] T063 [US2] Add error handling for OCR timeout in extraction_worker.py (fail gracefully after 10 minutes, log error, mark for retry)

**Checkpoint**: At this point, User Story 2 should work independently (extract PDF/Excel → parse financial metrics → store with source references)

---

## Phase 5: User Story 3 - Validate Extracted Data Quality (Priority: P2)

**Goal**: Validate extracted data for completeness and reasonableness with confidence-based flagging

**Independent Test**: Upload document with missing/invalid data, verify validation detects errors and flags low confidence extractions

### Implementation for User Story 3

- [ ] T064 [P] [US3] Create src/ingestion/services/validator.py with validation rule engine
- [ ] T065 [US3] Implement completeness validation in validator.py (check for required metrics: revenue, expenses, net_income)
- [ ] T066 [US3] Implement range validation in validator.py (revenue > 0, not > $1 trillion, net_income can be negative)
- [ ] T067 [US3] Implement confidence threshold validation in validator.py (flag document if avg OCR confidence < 0.75, flag individual metrics if confidence < 0.70)
- [ ] T068 [US3] Implement validation error and warning generation in validator.py (return structured error/warning messages)
- [ ] T069 [P] [US3] Create src/ingestion/functions/validation_worker.py with Service Bus trigger for validation-queue
- [ ] T070 [US3] Implement extraction result retrieval in validation_worker.py using cosmos_manager.py (query extraction-results and financial-metrics by document_id)
- [ ] T071 [US3] Implement completeness validation execution in validation_worker.py (call validator.py check for missing metrics)
- [ ] T072 [US3] Implement range validation execution in validation_worker.py (call validator.py check for out-of-range values)
- [ ] T073 [US3] Implement confidence validation execution in validation_worker.py (call validator.py check OCR confidence thresholds)
- [ ] T074 [US3] Implement ExtractionResult update in validation_worker.py (update validation_status to "passed"/"flagged"/"failed", add validation_errors and validation_warnings)
- [ ] T075 [US3] Implement processing log update in validation_worker.py (log "validation_completed" event with validation_status)
- [ ] T076 [US3] Add manual review flagging logic in validation_worker.py (if validation_status="flagged", set requires_manual_review flag in ExtractionResult)

**Checkpoint**: User Story 3 complete - validation runs automatically after extraction and flags quality issues

---

## Phase 6: User Story 4 - Track Document Processing Status (Priority: P2)

**Goal**: Provide real-time status tracking for document processing

**Independent Test**: Upload document, poll status endpoint, verify status transitions (queued → processing → completed/failed) with accurate progress details

### Implementation for User Story 4

- [ ] T077 [P] [US4] Create src/ingestion/functions/status_handler.py with HTTP trigger for GET /api/v1/documents/{document_id}/status
- [ ] T078 [US4] Implement document existence check in status_handler.py (query Cosmos DB processing-logs for document_id)
- [ ] T079 [US4] Implement status determination logic in status_handler.py (check latest processing-logs event_type to determine queued/processing/completed/failed)
- [ ] T080 [US4] Implement progress calculation in status_handler.py (if processing, return tables_extracted/total_tables_estimated from ExtractionResult)
- [ ] T081 [US4] Implement completion summary in status_handler.py (if completed, return extraction_summary with ocr_confidence, metrics_extracted, validation_status)
- [ ] T082 [US4] Implement failure details in status_handler.py (if failed, return error_message and recommendations from processing-logs)
- [ ] T083 [US4] Implement estimated completion time in status_handler.py (calculate based on average processing time for similar documents)
- [ ] T084 [US4] Add OpenAPI route registration for /documents/{id}/status endpoint in function.json
- [ ] T085 [US4] Implement caching for status queries in status_handler.py (use in-memory cache with 10-second TTL to reduce Cosmos DB queries)
- [ ] T086 [US4] Add audit logging in status_handler.py using audit_logger.py (log "view" action for status queries)
- [ ] T087 [P] [US4] Create src/ingestion/functions/results_handler.py with HTTP trigger for GET /api/v1/documents/{document_id}/results
- [ ] T088 [US4] Implement extraction results retrieval in results_handler.py using cosmos_manager.py (query financial-metrics container by document_id)
- [ ] T089 [US4] Implement completion check in results_handler.py (return 409 Conflict if status not "completed")
- [ ] T090 [US4] Implement source reference inclusion in results_handler.py (return full SourceReference nested objects for each metric)
- [ ] T091 [US4] Add OpenAPI route registration for /documents/{id}/results endpoint in function.json
- [ ] T092 [US4] Add audit logging in results_handler.py using audit_logger.py (log "view_results" action)

**Checkpoint**: User Story 4 complete - analysts can track processing status and retrieve results independently

---

## Phase 7: User Story 5 - Retry Failed Ingestions (Priority: P3)

**Goal**: Enable retry of failed ingestions without re-uploading documents

**Independent Test**: Trigger failed ingestion (timeout), retry via API, verify re-processing succeeds without re-upload

### Implementation for User Story 5

- [ ] T093 [P] [US5] Create src/ingestion/functions/retry_handler.py with HTTP trigger for POST /api/v1/documents/{document_id}/retry
- [ ] T094 [US5] Implement retry eligibility check in retry_handler.py (verify document status is "failed")
- [ ] T095 [US5] Implement Blob existence verification in retry_handler.py using storage_manager.py (confirm document still in Blob Storage)
- [ ] T096 [US5] Implement enhanced OCR parameter handling in retry_handler.py (accept enhanced_ocr flag in request body)
- [ ] T097 [US5] Implement Service Bus re-queueing in retry_handler.py (enqueue to extraction-queue with retry metadata)
- [ ] T098 [US5] Implement processing log creation in retry_handler.py (log "retry_initiated" event with retry_count)
- [ ] T099 [US5] Add OpenAPI route registration for /documents/{id}/retry endpoint in function.json
- [ ] T100 [US5] Add audit logging in retry_handler.py using audit_logger.py (log "retry" action)
- [ ] T101 [US5] Update extraction_worker.py to handle enhanced_ocr flag (if set, use higher quality OCR settings in Document Intelligence API)

**Checkpoint**: User Story 5 complete - all user stories independently functional

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T102 [P] Create tests/contract/golden_datasets/sample_income_statement.pdf (3-page P&L at 300 DPI)
- [ ] T103 [P] Create tests/contract/golden_datasets/sample_excel_report.xlsx (multi-sheet financial report)
- [ ] T104 [P] Create tests/contract/golden_datasets/expected_outputs.json (known-good extraction results for regression testing)
- [ ] T105 [P] Create tests/unit/test_financial_parser.py with unit tests for income statement line item extraction
- [ ] T106 [P] Create tests/unit/test_validator.py with unit tests for completeness, range, and confidence validation rules
- [ ] T107 [P] Create tests/unit/test_number_parser.py with unit tests for $10M, (5,000), 1.2B parsing logic
- [ ] T108 [P] Create tests/unit/test_confidence_scorer.py with unit tests for OCR quality assessment
- [ ] T109 [P] Create tests/integration/test_end_to_end_pdf.py with full workflow test (upload → extract → validate for PDF)
- [ ] T110 [P] Create tests/integration/test_end_to_end_excel.py with full workflow test (upload → extract → validate for Excel)
- [ ] T111 [P] Create tests/integration/test_retry_logic.py with retry workflow test (fail → retry → succeed)
- [ ] T112 [P] Create .github/workflows/ci.yml with pytest, coverage, and security scanning (Bandit, Safety)
- [ ] T113 [P] Create .github/workflows/deploy.yml with Azure Functions deployment to staging and production
- [ ] T114 Create docs/API.md with OpenAPI spec documentation and usage examples
- [ ] T115 [P] Create docs/RUNBOOK.md with operational procedures (re-ingest failed documents, adjust confidence thresholds)
- [ ] T116 Run quickstart.md validation (verify local dev setup works end-to-end)
- [ ] T117 [P] Configure Application Insights alerts (extraction failure rate > 10%, queue depth > 100, avg confidence < 0.75)
- [ ] T118 [P] Create Power BI dashboard template for monitoring extraction metrics (confidence distribution, processing latency, validation failure rate)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - User Story 1 (P1): Can start after Foundational - No dependencies on other stories
  - User Story 2 (P1): Can start after Foundational - No dependencies on other stories (can run parallel with US1 if staffed)
  - User Story 3 (P2): Depends on User Story 2 (needs extracted data to validate)
  - User Story 4 (P2): Depends on User Stories 1, 2, 3 (needs all statuses to track)
  - User Story 5 (P3): Depends on User Story 1, 2 (needs upload and extraction to retry)
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (Upload)**: Independent - can be implemented and tested standalone
- **User Story 2 (Extract)**: Independent - can be implemented in parallel with US1
- **User Story 3 (Validate)**: Depends on US2 completion (requires extracted data)
- **User Story 4 (Status Tracking)**: Depends on US1, US2, US3 (tracks all processing stages)
- **User Story 5 (Retry)**: Depends on US1, US2 (retries upload and extraction)

### Within Each User Story

- Upload (US1): Upload handler → Process ingestion → Queue to extraction
- Extract (US2): Extraction worker → Parse tables → Store metrics with source references
- Validate (US3): Validation worker → Run rules → Update extraction result
- Status (US4): Status handler → Query logs → Results handler → Return metrics
- Retry (US5): Retry handler → Re-queue → Enhanced OCR (if requested)

### Parallel Opportunities

- **Phase 1 (Setup)**: All tasks marked [P] can run in parallel (T003, T004, T005, T006, T010)
- **Phase 2 (Foundational)**: Models (T014-T018), Bicep modules (T023-T027) can run in parallel
- **User Story 2**: document_intelligence.py (T043), excel_parser.py (T046), financial_parser.py (T048), number_parser.py (T051), confidence_scorer.py (T053) can all be developed in parallel
- **User Story 4**: status_handler.py (T077) and results_handler.py (T087) can be developed in parallel
- **Phase 8 (Polish)**: All test creation tasks (T102-T111), documentation tasks (T114-T115), monitoring (T117-T118) can run in parallel

---

## Parallel Example: User Story 2 (Extract)

```bash
# Launch all utilities and parsers in parallel:
Task: "Create document_intelligence.py with DocumentAnalysisClient wrapper" (T043)
Task: "Create excel_parser.py with openpyxl-based extraction" (T046)
Task: "Create financial_parser.py for statement type detection" (T048)
Task: "Create number_parser.py for currency format handling" (T051)
Task: "Create confidence_scorer.py for OCR quality assessment" (T053)

# Then sequentially integrate in extraction_worker.py:
Task: "Create extraction_worker.py with Service Bus trigger" (T055)
Task: "Implement PDF extraction workflow" (T056)
Task: "Implement Excel extraction workflow" (T057)
...
```

---

## Implementation Strategy

### MVP First (User Story 1 + User Story 2 Only)

1. Complete Phase 1: Setup (T001-T010)
2. Complete Phase 2: Foundational (T011-T028) - CRITICAL blocker
3. Complete Phase 3: User Story 1 - Upload (T029-T042)
4. Complete Phase 4: User Story 2 - Extract (T043-T063)
5. **STOP and VALIDATE**: Test upload → extract workflow end-to-end with sample PDFs
6. Deploy/demo if ready

**MVP Delivers**:
- Upload PDF/Excel financial reports
- Extract structured financial metrics
- Store with full source references (Constitution Principle I)
- Basic validation (completeness)

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready (28 tasks)
2. Add User Story 1 → Test independently → Deploy/Demo (14 tasks) ✅ **Checkpoint 1**
3. Add User Story 2 → Test independently → Deploy/Demo (21 tasks) ✅ **Checkpoint 2 (MVP)**
4. Add User Story 3 → Test independently → Deploy/Demo (13 tasks) ✅ **Checkpoint 3**
5. Add User Story 4 → Test independently → Deploy/Demo (16 tasks) ✅ **Checkpoint 4**
6. Add User Story 5 → Test independently → Deploy/Demo (9 tasks) ✅ **Checkpoint 5**
7. Add Polish → Production-ready (17 tasks) ✅ **Checkpoint 6 (Production Release)**

Each checkpoint delivers working functionality without breaking previous stories.

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (28 tasks)
2. Once Foundational is done:
   - **Developer A**: User Story 1 (Upload) - 14 tasks
   - **Developer B**: User Story 2 (Extract) - 21 tasks in parallel
   - **Developer C**: Infrastructure/Bicep refinement
3. After US1 + US2 complete:
   - **Developer A**: User Story 3 (Validate) - 13 tasks
   - **Developer B**: User Story 4 (Status) - 16 tasks in parallel
   - **Developer C**: User Story 5 (Retry) - 9 tasks in parallel
4. Team integrates and tests all stories together
5. Team completes Polish tasks in parallel (17 tasks)

**Timeline Estimate** (parallel team):
- Setup + Foundational: 1-2 weeks
- US1 + US2 (parallel): 2-3 weeks → **MVP Release**
- US3 + US4 + US5 (parallel): 1-2 weeks → **Feature Complete**
- Polish + Production Prep: 1 week → **Production Release**

**Total**: 5-8 weeks for full feature (4-5 weeks for MVP)

---

## Notes

- **[P] tasks** = different files, no dependencies (can run in parallel)
- **[Story] label** maps task to specific user story for traceability (US1, US2, US3, US4, US5)
- Each user story should be independently completable and testable
- Commit after each task or logical group (e.g., after completing a service module)
- Stop at any checkpoint to validate story independently before proceeding
- **No test tasks included** - feature specification does not explicitly request TDD approach. Add test tasks if adopting test-first methodology.
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence

---

## Task Count Summary

- **Phase 1 (Setup)**: 10 tasks
- **Phase 2 (Foundational)**: 18 tasks (BLOCKING)
- **Phase 3 (User Story 1)**: 14 tasks
- **Phase 4 (User Story 2)**: 21 tasks
- **Phase 5 (User Story 3)**: 13 tasks
- **Phase 6 (User Story 4)**: 16 tasks
- **Phase 7 (User Story 5)**: 9 tasks
- **Phase 8 (Polish)**: 17 tasks

**Total**: 118 tasks

**Parallel Opportunities**: 42 tasks marked [P] can run in parallel with others in same phase

**MVP Scope** (Recommended): Phase 1 + Phase 2 + Phase 3 + Phase 4 = **63 tasks** (Upload + Extract capabilities)
