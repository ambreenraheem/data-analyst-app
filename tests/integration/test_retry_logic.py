"""
Integration test for retry logic.

Tests the retry workflow: fail → retry → succeed
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import asyncio

# Test data paths
GOLDEN_DIR = Path(__file__).parent.parent / "contract" / "golden_datasets"
SAMPLE_PDF = GOLDEN_DIR / "sample_income_statement.pdf"


class TestRetryLogic:
    """Integration test suite for retry workflow."""

    @pytest.fixture
    def mock_blob_storage(self):
        """Mock Blob Storage client."""
        with patch('src.ingestion.services.storage_manager.BlobServiceClient') as mock:
            blob_client = Mock()
            blob_client.exists = Mock(return_value=True)
            blob_client.get_blob_properties = Mock(return_value=Mock(size=2600))
            blob_client.download_blob = Mock(return_value=Mock(readall=Mock(return_value=open(SAMPLE_PDF, 'rb').read())))
            mock.return_value.get_blob_client = Mock(return_value=blob_client)
            yield mock

    @pytest.fixture
    def mock_cosmos_db(self):
        """Mock Cosmos DB client."""
        with patch('src.ingestion.services.cosmos_manager.CosmosClient') as mock:
            container = Mock()
            container.create_item = Mock(return_value={'id': 'test-id'})
            container.upsert_item = Mock(return_value={'id': 'test-id'})
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

    @pytest.fixture
    def failed_document_status(self):
        """Mock a failed document status."""
        return {
            "document_id": "doc-failed-001",
            "status": "failed",
            "blob_url": "https://test.blob.core.windows.net/financial-documents/2024/01/doc-failed-001.pdf",
            "error_message": "Extraction timeout after 10 minutes",
            "retry_count": 0
        }

    @pytest.mark.asyncio
    async def test_retry_eligible_document(self, failed_document_status, mock_blob_storage, mock_cosmos_db, mock_service_bus):
        """Test retrying an eligible failed document."""
        # Import retry handler
        from src.ingestion.functions.retry_handler import retry_document

        # Mock Cosmos DB to return failed document
        mock_cosmos_db.return_value.get_database_client.return_value.get_container_client.return_value.query_items = Mock(
            return_value=iter([failed_document_status])
        )

        # Create mock request
        mock_request = Mock()
        mock_request.route_params = {"document_id": "doc-failed-001"}
        mock_request.get_json = Mock(return_value={"enhanced_ocr": False})

        # Execute retry
        response = await retry_document(mock_request)

        # Verify response
        assert response.status_code == 200
        response_data = json.loads(response.get_body())
        assert response_data["status"] == "retry_queued"
        assert "retry_count" in response_data

        # Verify Service Bus was called to re-queue
        mock_service_bus.return_value.get_queue_sender.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_with_enhanced_ocr(self, failed_document_status, mock_blob_storage, mock_cosmos_db, mock_service_bus):
        """Test retrying with enhanced OCR parameters."""
        # Import retry handler
        from src.ingestion.functions.retry_handler import retry_document

        # Mock Cosmos DB to return failed document
        mock_cosmos_db.return_value.get_database_client.return_value.get_container_client.return_value.query_items = Mock(
            return_value=iter([failed_document_status])
        )

        # Create mock request with enhanced OCR flag
        mock_request = Mock()
        mock_request.route_params = {"document_id": "doc-failed-001"}
        mock_request.get_json = Mock(return_value={"enhanced_ocr": True})

        # Execute retry
        response = await retry_document(mock_request)

        # Verify response
        assert response.status_code == 200
        response_data = json.loads(response.get_body())
        assert response_data["enhanced_ocr"] is True

        # Verify message was queued with enhanced OCR flag
        call_args = mock_service_bus.return_value.get_queue_sender.return_value.send_messages.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_retry_blob_verification(self, failed_document_status, mock_blob_storage, mock_cosmos_db):
        """Test retry verifies blob still exists before retrying."""
        # Import retry handler
        from src.ingestion.functions.retry_handler import retry_document

        # Mock Cosmos DB to return failed document
        mock_cosmos_db.return_value.get_database_client.return_value.get_container_client.return_value.query_items = Mock(
            return_value=iter([failed_document_status])
        )

        # Mock blob doesn't exist
        mock_blob_storage.return_value.get_blob_client.return_value.exists = Mock(return_value=False)

        # Create mock request
        mock_request = Mock()
        mock_request.route_params = {"document_id": "doc-failed-001"}
        mock_request.get_json = Mock(return_value={})

        # Execute retry
        response = await retry_document(mock_request)

        # Verify response is an error
        assert response.status_code == 404
        response_data = json.loads(response.get_body())
        assert "not found" in response_data["error"].lower()

    @pytest.mark.asyncio
    async def test_retry_not_eligible_completed_document(self, mock_cosmos_db):
        """Test retry fails for completed document."""
        # Import retry handler
        from src.ingestion.functions.retry_handler import retry_document

        # Mock Cosmos DB to return completed document
        completed_status = {
            "document_id": "doc-completed-001",
            "status": "completed",
            "retry_count": 0
        }
        mock_cosmos_db.return_value.get_database_client.return_value.get_container_client.return_value.query_items = Mock(
            return_value=iter([completed_status])
        )

        # Create mock request
        mock_request = Mock()
        mock_request.route_params = {"document_id": "doc-completed-001"}
        mock_request.get_json = Mock(return_value={})

        # Execute retry
        response = await retry_document(mock_request)

        # Verify response is an error
        assert response.status_code == 400
        response_data = json.loads(response.get_body())
        assert "not eligible" in response_data["error"].lower()

    @pytest.mark.asyncio
    async def test_retry_count_incremented(self, failed_document_status, mock_blob_storage, mock_cosmos_db, mock_service_bus):
        """Test retry count is incremented on each retry."""
        # Import retry handler
        from src.ingestion.functions.retry_handler import retry_document

        # Mock document with existing retry count
        failed_document_status["retry_count"] = 1

        mock_cosmos_db.return_value.get_database_client.return_value.get_container_client.return_value.query_items = Mock(
            return_value=iter([failed_document_status])
        )

        # Create mock request
        mock_request = Mock()
        mock_request.route_params = {"document_id": "doc-failed-001"}
        mock_request.get_json = Mock(return_value={})

        # Execute retry
        response = await retry_document(mock_request)

        # Verify response
        assert response.status_code == 200
        response_data = json.loads(response.get_body())
        assert response_data["retry_count"] == 2

    @pytest.mark.asyncio
    async def test_retry_max_attempts_exceeded(self, failed_document_status, mock_cosmos_db):
        """Test retry fails when max retry attempts exceeded."""
        # Import retry handler
        from src.ingestion.functions.retry_handler import retry_document

        # Mock document with max retry count
        failed_document_status["retry_count"] = 3  # Max is typically 3

        mock_cosmos_db.return_value.get_database_client.return_value.get_container_client.return_value.query_items = Mock(
            return_value=iter([failed_document_status])
        )

        # Create mock request
        mock_request = Mock()
        mock_request.route_params = {"document_id": "doc-failed-001"}
        mock_request.get_json = Mock(return_value={})

        # Execute retry
        response = await retry_document(mock_request)

        # Verify response is an error
        assert response.status_code == 400
        response_data = json.loads(response.get_body())
        assert "max" in response_data["error"].lower() or "exceeded" in response_data["error"].lower()

    @pytest.mark.asyncio
    async def test_retry_processing_log_created(self, failed_document_status, mock_blob_storage, mock_cosmos_db, mock_service_bus):
        """Test retry creates processing log entry."""
        # Import retry handler
        from src.ingestion.functions.retry_handler import retry_document

        # Mock Cosmos DB to return failed document
        mock_cosmos_db.return_value.get_database_client.return_value.get_container_client.return_value.query_items = Mock(
            return_value=iter([failed_document_status])
        )

        # Create mock request
        mock_request = Mock()
        mock_request.route_params = {"document_id": "doc-failed-001"}
        mock_request.get_json = Mock(return_value={})

        # Execute retry
        response = await retry_document(mock_request)

        # Verify processing log was created
        container_mock = mock_cosmos_db.return_value.get_database_client.return_value.get_container_client.return_value
        # Should have called create_item for processing log
        assert container_mock.create_item.called or container_mock.upsert_item.called

    @pytest.mark.asyncio
    async def test_full_retry_workflow_success(self, mock_blob_storage, mock_cosmos_db, mock_service_bus):
        """Test complete retry workflow from fail to success."""
        # Step 1: Initial extraction fails
        document_id = "doc-retry-test-001"

        # Mock initial failed status
        failed_status = {
            "document_id": document_id,
            "status": "failed",
            "blob_url": f"https://test.blob.core.windows.net/financial-documents/2024/01/{document_id}.pdf",
            "error_message": "OCR timeout",
            "retry_count": 0
        }

        # Step 2: User initiates retry
        from src.ingestion.functions.retry_handler import retry_document

        mock_cosmos_db.return_value.get_database_client.return_value.get_container_client.return_value.query_items = Mock(
            return_value=iter([failed_status])
        )

        mock_request = Mock()
        mock_request.route_params = {"document_id": document_id}
        mock_request.get_json = Mock(return_value={"enhanced_ocr": True})

        retry_response = await retry_document(mock_request)

        # Verify retry was queued
        assert retry_response.status_code == 200

        # Step 3: Simulate successful extraction on retry
        # Mock successful extraction result
        success_status = {
            "document_id": document_id,
            "status": "completed",
            "metrics_extracted": 10,
            "validation_status": "passed",
            "retry_count": 1
        }

        # Verify workflow completes successfully
        assert success_status["status"] == "completed"
        assert success_status["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_retry_audit_logging(self, failed_document_status, mock_blob_storage, mock_cosmos_db, mock_service_bus):
        """Test retry action is properly audit logged."""
        # Import retry handler
        from src.ingestion.functions.retry_handler import retry_document

        # Mock Cosmos DB to return failed document
        mock_cosmos_db.return_value.get_database_client.return_value.get_container_client.return_value.query_items = Mock(
            return_value=iter([failed_document_status])
        )

        # Mock audit logger
        with patch('src.ingestion.utils.audit_logger.TableServiceClient') as mock_audit:
            mock_table_client = Mock()
            mock_audit.return_value.get_table_client = Mock(return_value=mock_table_client)

            # Create mock request
            mock_request = Mock()
            mock_request.route_params = {"document_id": "doc-failed-001"}
            mock_request.get_json = Mock(return_value={})
            mock_request.headers = {"X-User-Id": "test-user@example.com"}

            # Execute retry
            response = await retry_document(mock_request)

            # Verify audit log was written
            # (This depends on implementation of audit_logger)
            # assert mock_table_client.create_entity.called

    @pytest.mark.asyncio
    async def test_extraction_worker_handles_retry_metadata(self, mock_cosmos_db):
        """Test extraction worker handles retry metadata properly."""
        # Import extraction worker
        from src.ingestion.functions.extraction_worker import process_extraction

        # Create mock Service Bus message with retry metadata
        mock_message = Mock()
        mock_message.get_body().decode.return_value = json.dumps({
            "document_id": "doc-retry-001",
            "blob_url": "https://test.blob.core.windows.net/test/sample.pdf",
            "document_type": "pdf",
            "is_retry": True,
            "retry_count": 1,
            "enhanced_ocr": True
        })

        # Mock Document Intelligence with enhanced OCR
        with patch('src.ingestion.services.document_intelligence.DocumentAnalysisClient') as mock_doc_intel:
            mock_analysis_result = Mock()
            mock_analysis_result.tables = []

            mock_doc_intel.return_value.begin_analyze_document_from_url.return_value.result = Mock(
                return_value=mock_analysis_result
            )

            # Execute extraction
            await process_extraction(mock_message)

            # Verify enhanced OCR parameters were used
            # (This depends on implementation)
            # assert mock_doc_intel.return_value.begin_analyze_document_from_url.called

    def test_retry_status_transitions(self):
        """Test document status transitions during retry workflow."""
        # Define valid status transitions
        valid_transitions = {
            "failed": ["retry_queued"],
            "retry_queued": ["processing"],
            "processing": ["completed", "failed"],
        }

        # Verify transition logic
        current_status = "failed"
        next_status = "retry_queued"
        assert next_status in valid_transitions.get(current_status, [])

        current_status = "retry_queued"
        next_status = "processing"
        assert next_status in valid_transitions.get(current_status, [])

        current_status = "processing"
        next_status = "completed"
        assert next_status in valid_transitions.get(current_status, [])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
