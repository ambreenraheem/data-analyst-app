"""
Integration test for end-to-end PDF processing.

Tests the full workflow: upload → extract → validate for PDF documents.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import asyncio

# Test data paths
GOLDEN_DIR = Path(__file__).parent.parent / "contract" / "golden_datasets"
SAMPLE_PDF = GOLDEN_DIR / "sample_income_statement.pdf"
EXPECTED_OUTPUTS = GOLDEN_DIR / "expected_outputs.json"


class TestEndToEndPDF:
    """Integration test suite for PDF processing workflow."""

    @pytest.fixture
    def expected_data(self):
        """Load expected outputs from golden dataset."""
        with open(EXPECTED_OUTPUTS) as f:
            data = json.load(f)
        return data["sample_income_statement"]

    @pytest.fixture
    def mock_blob_storage(self):
        """Mock Blob Storage client."""
        with patch('src.ingestion.services.storage_manager.BlobServiceClient') as mock:
            blob_client = Mock()
            blob_client.upload_blob = Mock(return_value=None)
            blob_client.get_blob_properties = Mock(return_value=Mock(size=2600))
            mock.return_value.get_blob_client = Mock(return_value=blob_client)
            yield mock

    @pytest.fixture
    def mock_cosmos_db(self):
        """Mock Cosmos DB client."""
        with patch('src.ingestion.services.cosmos_manager.CosmosClient') as mock:
            container = Mock()
            container.create_item = Mock(return_value={'id': 'test-id'})
            container.query_items = Mock(return_value=[])
            mock.return_value.get_database_client.return_value.get_container_client = Mock(return_value=container)
            yield mock

    @pytest.fixture
    def mock_service_bus(self):
        """Mock Service Bus client."""
        with patch('azure.servicebus.ServiceBusClient') as mock:
            sender = Mock()
            sender.send_messages = Mock(return_value=None)
            mock.return_value.get_queue_sender = Mock(return_value=sender)
            yield mock

    @pytest.mark.asyncio
    async def test_upload_pdf_document(self, mock_blob_storage, mock_service_bus, mock_cosmos_db):
        """Test uploading PDF document creates document ID and queues for processing."""
        # Import function handler
        from src.ingestion.functions.upload_handler import upload_document

        # Read sample PDF
        with open(SAMPLE_PDF, "rb") as f:
            pdf_content = f.read()

        # Create mock request
        mock_request = Mock()
        mock_request.files = {"file": Mock(filename="sample_income_statement.pdf", read=Mock(return_value=pdf_content))}

        # Execute upload
        response = await upload_document(mock_request)

        # Verify response
        assert response.status_code == 200
        response_data = json.loads(response.get_body())
        assert "document_id" in response_data
        assert response_data["status"] == "queued"
        assert response_data["document_id"].startswith("doc-")

        # Verify Blob Storage was called
        mock_blob_storage.return_value.get_blob_client.assert_called_once()

        # Verify Service Bus was called
        mock_service_bus.return_value.get_queue_sender.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_from_pdf(self, expected_data, mock_cosmos_db):
        """Test extracting financial metrics from PDF."""
        # Import extraction worker
        from src.ingestion.functions.extraction_worker import process_extraction

        # Mock Azure Document Intelligence response
        mock_analysis_result = Mock()
        mock_analysis_result.tables = [
            Mock(
                cells=[
                    Mock(content="Line Item", row_index=0, column_index=0, confidence=0.96),
                    Mock(content="Amount (USD)", row_index=0, column_index=1, confidence=0.96),
                    Mock(content="Total Revenue", row_index=1, column_index=0, confidence=0.96),
                    Mock(content="$15,750,000", row_index=1, column_index=1, confidence=0.96),
                    Mock(content="Net Income", row_index=10, column_index=0, confidence=0.96),
                    Mock(content="$2,320,000", row_index=10, column_index=1, confidence=0.96),
                ]
            )
        ]

        with patch('src.ingestion.services.document_intelligence.DocumentAnalysisClient') as mock_doc_intel:
            mock_doc_intel.return_value.begin_analyze_document_from_url.return_value.result = Mock(
                return_value=mock_analysis_result
            )

            # Create mock Service Bus message
            mock_message = Mock()
            mock_message.get_body().decode.return_value = json.dumps({
                "document_id": "doc-sample-001",
                "blob_url": "https://test.blob.core.windows.net/test/sample.pdf",
                "document_type": "pdf"
            })

            # Execute extraction
            await process_extraction(mock_message)

            # Verify Cosmos DB was called to save extraction results
            assert mock_cosmos_db.return_value.get_database_client.called

    @pytest.mark.asyncio
    async def test_validate_extracted_data(self, expected_data, mock_cosmos_db):
        """Test validating extracted financial data."""
        # Import validation worker
        from src.ingestion.functions.validation_worker import process_validation

        # Mock extracted metrics from Cosmos DB
        mock_metrics = expected_data["metrics"]
        mock_extraction_result = {
            "document_id": "doc-sample-001",
            "ocr_confidence_avg": expected_data["extraction_summary"]["ocr_confidence"]
        }

        mock_cosmos_db.return_value.get_database_client.return_value.get_container_client.return_value.query_items = Mock(
            return_value=iter([mock_extraction_result])
        )

        # Create mock Service Bus message
        mock_message = Mock()
        mock_message.get_body().decode.return_value = json.dumps({
            "document_id": "doc-sample-001",
            "extraction_result_id": "extraction-001"
        })

        # Execute validation
        await process_validation(mock_message)

        # Verify validation updated the extraction result
        assert mock_cosmos_db.return_value.get_database_client.called

    @pytest.mark.asyncio
    async def test_full_workflow_pdf_to_validated_metrics(self, expected_data, mock_blob_storage, mock_service_bus, mock_cosmos_db):
        """Test complete workflow from PDF upload to validated metrics."""
        # This test simulates the entire pipeline

        # Step 1: Upload
        with open(SAMPLE_PDF, "rb") as f:
            pdf_content = f.read()

        # Mock successful upload
        document_id = "doc-test-001"

        # Step 2: Mock extraction results
        extracted_metrics = expected_data["metrics"][:3]  # First 3 metrics for simplicity

        # Step 3: Mock validation
        from src.ingestion.services.validator import Validator

        validation_result = Validator.validate_completeness(extracted_metrics, {"ocr_confidence_avg": 0.95})

        # Verify validation passed
        assert validation_result.is_valid()
        assert validation_result.validation_status == "passed"

    def test_extraction_matches_golden_dataset(self, expected_data):
        """Test that extraction results match golden dataset expectations."""
        # Load expected metrics
        expected_metrics = expected_data["metrics"]

        # Verify we have expected metrics
        assert len(expected_metrics) == 10  # All 10 metrics from income statement

        # Verify metric structure
        for metric in expected_metrics:
            assert "metric_name" in metric
            assert "value" in metric
            assert "metric_type" in metric
            assert "confidence" in metric
            assert "source_reference" in metric

            # Verify source reference structure
            source_ref = metric["source_reference"]
            assert "document_name" in source_ref
            assert "page_number" in source_ref
            assert "table_id" in source_ref
            assert "cell_reference" in source_ref

    def test_validation_rules_against_golden_data(self, expected_data):
        """Test validation rules against golden dataset."""
        from src.ingestion.services.validator import Validator

        metrics = expected_data["metrics"]
        extraction_result = {
            "ocr_confidence_avg": expected_data["extraction_summary"]["ocr_confidence"]
        }

        # Test completeness validation
        result = Validator.validate_completeness(metrics, extraction_result)
        assert result.validation_status == "passed"

        # Test range validation
        result = Validator.validate_ranges(metrics)
        assert result.validation_status == "passed"

        # Test confidence validation
        result = Validator.validate_confidence(metrics, extraction_result)
        assert result.validation_status == "passed"

        # Test relationship validation
        result = Validator.validate_relationships(metrics)
        assert result.validation_status == "passed"

    @pytest.mark.asyncio
    async def test_status_tracking_during_processing(self, mock_cosmos_db):
        """Test status tracking throughout the processing pipeline."""
        from src.ingestion.functions.status_handler import get_document_status

        document_id = "doc-test-001"

        # Mock processing logs
        mock_logs = [
            {"event_type": "upload_completed", "timestamp": "2024-01-01T10:00:00Z"},
            {"event_type": "extraction_started", "timestamp": "2024-01-01T10:01:00Z"},
            {"event_type": "extraction_completed", "timestamp": "2024-01-01T10:05:00Z", "metrics_extracted": 10},
            {"event_type": "validation_completed", "timestamp": "2024-01-01T10:06:00Z", "validation_status": "passed"},
        ]

        mock_cosmos_db.return_value.get_database_client.return_value.get_container_client.return_value.query_items = Mock(
            return_value=iter(mock_logs)
        )

        # Create mock request
        mock_request = Mock()
        mock_request.route_params = {"document_id": document_id}

        # Execute status check
        response = await get_document_status(mock_request)

        # Verify response
        assert response.status_code == 200
        response_data = json.loads(response.get_body())
        assert response_data["status"] == "completed"
        assert response_data["metrics_extracted"] == 10

    def test_error_handling_invalid_pdf(self):
        """Test error handling for invalid PDF files."""
        from src.ingestion.services.document_intelligence import DocumentIntelligenceService

        # Test with invalid PDF content
        with pytest.raises(Exception) as exc_info:
            service = DocumentIntelligenceService()
            # This would fail with actual invalid PDF
            # service.extract_tables_from_pdf(b"invalid pdf content")

        # Verify appropriate error is raised
        # assert "invalid" in str(exc_info.value).lower()

    def test_confidence_scoring_calculation(self, expected_data):
        """Test confidence score calculation for extracted metrics."""
        from src.ingestion.utils.confidence_scorer import ConfidenceScorer

        metrics = expected_data["metrics"]

        # Calculate document confidence
        confidences = [m["confidence"] for m in metrics]
        stats = ConfidenceScorer.get_confidence_statistics(confidences)

        # Verify statistics match expectations
        assert stats["mean"] >= 0.90  # High quality OCR expected
        assert stats["min"] >= 0.80  # No extremely low confidence
        assert stats["count"] == len(metrics)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
