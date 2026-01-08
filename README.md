# Financial Insight & Risk Advisor Agent - Document Ingestion Pipeline

Automated document ingestion pipeline for extracting structured financial data from PDF and Excel reports with full source reference tracking and audit trail compliance.

## Overview

This project implements the document ingestion feature for the Financial Insight & Risk Advisor Agent, supporting:

- **Upload**: PDF and Excel financial document uploads (up to 50MB)
- **Extraction**: Automated OCR and table extraction using Azure Document Intelligence
- **Validation**: Data quality validation with confidence-based flagging
- **Tracking**: Real-time processing status and audit trail
- **Retry**: Retry mechanism for failed ingestions

## Architecture

- **Azure Functions**: Serverless event-driven processing (Python 3.11)
- **Azure Blob Storage**: Raw document persistence with 7-year retention
- **Azure Cosmos DB**: Structured data storage (extraction results, financial metrics, logs)
- **Azure Service Bus**: Asynchronous message queueing
- **Azure Document Intelligence**: PDF/Excel OCR and table extraction
- **Azure Key Vault**: Secrets management
- **Application Insights**: Monitoring and telemetry

## Prerequisites

- Python 3.11+
- Poetry (for dependency management)
- Azure subscription with required resources deployed
- Azure CLI (for authentication)

## Setup

### 1. Install Dependencies

```bash
# Using Poetry (recommended)
poetry install

# Or using pip
pip install -r requirements.txt
```

### 2. Configure Local Settings

```bash
# Copy the example settings file
cp local.settings.json.example local.settings.json

# Edit local.settings.json with your Azure resource details
```

Required configuration:
- Storage Account name and connection
- Cosmos DB endpoint
- Service Bus namespace and connection string
- Document Intelligence endpoint
- Key Vault URL
- Application Insights connection string

### 3. Azure Authentication

```bash
# Login to Azure CLI
az login

# Set your subscription
az subscription set --subscription <your-subscription-id>
```

### 4. Deploy Infrastructure (Optional)

```bash
# Deploy using Bicep
az deployment group create \
  --resource-group <your-rg> \
  --template-file infrastructure/bicep/main.bicep \
  --parameters infrastructure/bicep/parameters/dev.parameters.json
```

## Running Locally

### Start Azure Functions Runtime

```bash
# Using Azure Functions Core Tools
func start

# Or using Poetry
poetry run func start
```

The following endpoints will be available:
- `POST http://localhost:7071/api/v1/documents/upload` - Upload document

### Upload a Document

```bash
# Upload a PDF file
curl -X POST http://localhost:7071/api/v1/documents/upload \
  -F "file=@path/to/financial_report.pdf"

# Upload an Excel file
curl -X POST http://localhost:7071/api/v1/documents/upload \
  -F "file=@path/to/financial_report.xlsx"
```

Expected response:
```json
{
  "document_id": "doc-abc123...",
  "status": "queued",
  "message": "Document uploaded successfully and queued for processing",
  "blob_url": "https://...",
  "estimated_processing_time_minutes": 5
}
```

## Project Structure

```
.
├── src/
│   ├── ingestion/
│   │   ├── functions/           # Azure Functions handlers
│   │   │   ├── upload_handler.py
│   │   │   ├── process_ingestion.py
│   │   │   ├── extraction_worker.py (TODO)
│   │   │   └── validation_worker.py (TODO)
│   │   ├── models/              # Pydantic data models
│   │   ├── services/            # Business logic services
│   │   └── utils/               # Utility functions
│   └── shared/                  # Shared configuration and telemetry
├── tests/                       # Unit and integration tests
├── infrastructure/              # Bicep IaC templates
├── specs/                       # Feature specifications
└── history/                     # Prompt History Records (PHRs)
```

## Development Workflow

### Phase 1: Setup ✅
- Project structure and dependencies
- Configuration files and ignore patterns

### Phase 2: Foundational Infrastructure ✅
- Shared modules (config, exceptions, telemetry)
- Pydantic models for all entities
- Service layer (Storage, Cosmos, Audit)
- Bicep infrastructure templates

### Phase 3: User Story 1 - Upload ✅
- Upload handler HTTP endpoint
- File validation (type, size, integrity)
- Blob Storage persistence
- Service Bus queueing
- Process ingestion worker

### Phase 4: User Story 2 - Extract ✅
- Document Intelligence integration
- PDF table extraction with source references
- Excel parsing with multi-sheet support
- Financial metric extraction (income statement line items)
- OCR confidence scoring and aggregation

### Phase 5: User Story 3 - Validate ✅
- Completeness validation (required and recommended metrics)
- Range validation (reasonable value checks)
- Confidence threshold validation (document and metric levels)
- Relationship validation (mathematical consistency checks)
- Manual review flagging for low confidence or failed validation

### Phase 6: User Story 4 - Status Tracking ✅
- Status query endpoint (GET /documents/{id}/status)
- Real-time progress tracking with stage completion
- Results retrieval endpoint (GET /documents/{id}/results)
- Extraction summary with confidence scores
- Source reference inclusion for full traceability
- In-memory caching (10-second TTL) for performance
- Audit logging for all access events

### Phase 7: User Story 5 - Retry ✅
- Retry endpoint (POST /documents/{id}/retry)
- Eligibility checks (failed status, max retry limit)
- Blob existence verification
- Enhanced OCR option for difficult documents
- Retry count tracking
- Audit logging for all retry attempts

### Phase 8: Polish (TODO)
- Unit tests
- Integration tests
- Documentation
- CI/CD pipelines

## Testing

```bash
# Run unit tests
poetry run pytest tests/unit/

# Run integration tests (requires Azure resources)
poetry run pytest tests/integration/

# Run all tests with coverage
poetry run pytest --cov=src --cov-report=html
```

## Code Quality

```bash
# Format code with Black
poetry run black src/ tests/

# Lint with Ruff
poetry run ruff check src/ tests/

# Type check with MyPy
poetry run mypy src/
```

## Constitution Compliance

This implementation follows the Financial Insight & Risk Advisor Agent Constitution:

- **Principle I**: Data-First - All metrics include source references (document, page, cell)
- **Principle II**: Confidence Thresholds - OCR confidence scores tracked for autonomous reasoning
- **Principle III**: Auditability - 7-year retention, processing logs, access audit trail
- **Principle V**: Secure Data Handling - Managed Identity, Key Vault, TLS encryption
- **Principle VI**: Human-in-the-Loop - Manual review flags for low confidence extractions

## License

Proprietary - Financial Insight & Risk Advisor Agent

## Contact

For questions or support, contact the development team.
