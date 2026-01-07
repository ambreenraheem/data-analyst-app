# Quick Start: Document Ingestion Pipeline

**Feature**: Document Ingestion Pipeline
**For**: Developers setting up local environment and testing the ingestion flow
**Last Updated**: 2026-01-08

## Prerequisites

- Python 3.11+
- Azure subscription with Document Intelligence resource
- Azure Storage Account (or Azurite emulator for local dev)
- Azure Cosmos DB account (or emulator)
- Azure Functions Core Tools v4
- Poetry or pip for dependency management

## Local Development Setup

### 1. Clone and Install Dependencies

```bash
cd H:\data-analyst-app

# Install Python dependencies
poetry install
# OR
pip install -r requirements.txt

# Install Azure Functions Core Tools (if not already installed)
npm install -g azure-functions-core-tools@4 --unsafe-perm true
```

### 2. Setup Azure Services (Local Emulators)

**Azurite** (Azure Storage Emulator):
```bash
# Install Azurite
npm install -g azurite

# Start Azurite (Blob + Table Storage)
azurite --silent --location ./azurite --debug ./azurite/debug.log
```

**Cosmos DB Emulator**:
- Download from: https://aka.ms/cosmosdb-emulator
- Run installer and start emulator
- Default endpoint: `https://localhost:8081`
- Emulator key: `C2y6yDjf5...` (copy from emulator UI)

### 3. Configure Local Settings

Create `local.settings.json` (from template):

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",

    "DOCUMENT_INTELLIGENCE_ENDPOINT": "https://YOUR_RESOURCE.cognitiveservices.azure.com/",
    "DOCUMENT_INTELLIGENCE_KEY": "your-key-here",

    "COSMOS_ENDPOINT": "https://localhost:8081",
    "COSMOS_KEY": "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==",
    "COSMOS_DATABASE": "financial-advisor",

    "SERVICE_BUS_CONNECTION_STRING": "Endpoint=sb://YOUR_NAMESPACE.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=YOUR_KEY",

    "TABLE_STORAGE_CONNECTION_STRING": "UseDevelopmentStorage=true",

    "APPLICATIONINSIGHTS_CONNECTION_STRING": "InstrumentationKey=00000000-0000-0000-0000-000000000000"
  }
}
```

**Note**: For local development, you can skip Service Bus and Application Insights (functions will run without async queueing).

### 4. Initialize Cosmos DB Containers

```bash
# Run setup script to create containers
python scripts/setup_cosmos.py

# OR manually create via Cosmos DB Data Explorer:
# Database: financial-advisor
# Containers:
#   - extraction-results (partition key: /document_id)
#   - financial-metrics (partition key: /document_id)
#   - processing-logs (partition key: /document_id)
```

### 5. Start Azure Functions Locally

```bash
# From repository root
func start

# Functions will be available at:
# http://localhost:7071/api/v1/documents/upload
# http://localhost:7071/api/v1/documents/{id}/status
```

---

## Quick Test: Upload a Sample Document

### Prepare Test Document

Use sample from `tests/contract/golden_datasets/`:
- `sample_income_statement.pdf` (3-page P&L statement, 300 DPI)
- `sample_excel_report.xlsx` (multi-sheet financial report)

### Upload via cURL

```bash
# Upload PDF
curl -X POST http://localhost:7071/api/v1/documents/upload \
  -F "file=@tests/contract/golden_datasets/sample_income_statement.pdf" \
  -H "Content-Type: multipart/form-data"

# Response:
# {
#   "document_id": "doc-abc123",
#   "status": "queued",
#   "upload_timestamp": "2026-01-08T10:30:00Z",
#   "estimated_processing_time_minutes": 5
# }
```

### Check Status

```bash
# Get processing status
curl http://localhost:7071/api/v1/documents/doc-abc123/status

# Response (while processing):
# {
#   "document_id": "doc-abc123",
#   "status": "processing",
#   "progress": {
#     "current_step": "Extracting tables",
#     "tables_extracted": 3,
#     "total_tables_estimated": 5,
#     "percent_complete": 60
#   }
# }
```

### Retrieve Results

```bash
# Get extraction results (after status = "completed")
curl http://localhost:7071/api/v1/documents/doc-abc123/results

# Response includes all extracted metrics with source references
```

---

## Running Tests

### Unit Tests

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run specific test file
pytest tests/unit/test_financial_parser.py -v

# With coverage
pytest tests/unit/ --cov=src/ingestion --cov-report=html
```

### Contract Tests (Golden Datasets)

```bash
# Run contract tests against sample PDFs/Excel
pytest tests/contract/ -v

# These tests verify:
# - Upload API accepts valid files
# - Extraction matches expected outputs in golden_datasets/expected_outputs.json
# - Source references are complete (document name, page, cell)
```

### Integration Tests (End-to-End)

```bash
# Requires Azurite and Cosmos DB Emulator running
pytest tests/integration/ -v

# Tests full workflow:
# 1. Upload document → Blob Storage
# 2. Extract via Document Intelligence → Cosmos DB
# 3. Validate data quality → Flag warnings
# 4. Query results via API
```

---

## Common Development Tasks

### Add New Validation Rule

1. Edit `src/ingestion/services/validator.py`
2. Add rule to `VALIDATION_RULES` dictionary
3. Add unit test in `tests/unit/test_validator.py`
4. Run tests: `pytest tests/unit/test_validator.py`

Example:
```python
# Add rule for "gross_profit"
VALIDATION_RULES = {
    ...
    "gross_profit": {"min": -1_000_000_000, "max": 1_000_000_000_000}
}
```

### Debug Extraction Logic

```bash
# Enable verbose logging
export AZURE_LOG_LEVEL=DEBUG

# Run function with debugger
python -m pdb src/ingestion/functions/extraction_worker.py

# Or use VS Code debugger (launch.json configured for Azure Functions)
```

### Test with Real Azure Document Intelligence

If you have an Azure Document Intelligence resource:

1. Update `local.settings.json` with real endpoint and key
2. Upload test document: `curl -X POST ... -F "file=@your_document.pdf"`
3. Monitor extraction in Application Insights (if configured)

---

## Troubleshooting

### Issue: "Document Intelligence API rate limit exceeded"

**Solution**: Reduce concurrent processing in `host.json`:
```json
{
  "extensions": {
    "serviceBus": {
      "maxConcurrentCalls": 5  // Reduced from 10
    }
  }
}
```

### Issue: "Cosmos DB connection timeout"

**Symptoms**: Functions fail with `CosmosException: Request timeout`

**Solution**:
1. Verify Cosmos DB Emulator is running (`https://localhost:8081`)
2. Check firewall allows localhost connections
3. Increase timeout in Cosmos client: `request_timeout=30` (default 10s)

### Issue: "Azurite blob not found"

**Symptoms**: Upload succeeds but extraction fails with "BlobNotFound"

**Solution**:
```bash
# Stop Azurite
# Clear Azurite data
rm -rf ./azurite

# Restart Azurite
azurite --silent --location ./azurite
```

### Issue: "Excel extraction returns empty metrics"

**Symptoms**: Excel upload succeeds but 0 metrics extracted

**Debug**:
1. Check Excel file has data in first sheet (openpyxl reads Sheet1 by default)
2. Verify financial keywords in headers ("Revenue", "Expenses", etc.)
3. Add debug logging in `src/ingestion/services/excel_parser.py`:

```python
logger.debug(f"Sheet names: {workbook.sheetnames}")
logger.debug(f"First row: {list(sheet.iter_rows(min_row=1, max_row=1, values_only=True))}")
```

---

## Next Steps

1. **Run full test suite**: `pytest tests/ -v`
2. **Deploy to Azure**: See deployment guide in `/infrastructure/README.md`
3. **Create first feature task list**: Run `/sp.tasks` to generate implementation tasks
4. **Explore specialized skills**: Review `.claude/skills/` for Data Ingestion Engineer and Backend Engineer expertise

---

## Resources

- **API Documentation**: `contracts/ingestion-api.openapi.yaml` (view in Swagger Editor)
- **Data Model**: `data-model.md` (Cosmos DB schemas, validation rules)
- **Research**: `research.md` (Azure service patterns, best practices)
- **Specification**: `spec.md` (user stories, functional requirements)

**Constitution Reference**: All design decisions align with `.specify/memory/constitution.md` principles.
