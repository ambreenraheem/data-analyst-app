"""
Azure Cosmos DB manager for structured data persistence.

Provides CRUD operations for extraction results, financial metrics, and processing logs
supporting Constitution Principles I (Data-First), II (Confidence Thresholds),
and III (Auditability).
"""

from typing import Any, Dict, List, Optional

from azure.cosmos import CosmosClient, PartitionKey, exceptions
from azure.identity import DefaultAzureCredential

from src.shared.config import config
from src.shared.exceptions import DocumentNotFoundError, StorageError


class CosmosManager:
    """Manager for Azure Cosmos DB operations on structured financial data."""

    def __init__(self) -> None:
        """Initialize Cosmos DB client with Managed Identity authentication."""
        credential = DefaultAzureCredential()
        self.client = CosmosClient(url=config.cosmos_db_endpoint, credential=credential)
        self.database_name = config.cosmos_db_database
        self.database = self.client.get_database_client(self.database_name)

        # Container references
        self.extraction_results_container = self.database.get_container_client(
            config.cosmos_container_extraction_results
        )
        self.financial_metrics_container = self.database.get_container_client(
            config.cosmos_container_financial_metrics
        )
        self.processing_logs_container = self.database.get_container_client(
            config.cosmos_container_processing_logs
        )

    def create_extraction_result(self, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create an extraction result document.

        Args:
            extraction_result: Extraction result data (should match ExtractionResult model)

        Returns:
            Created extraction result document with Cosmos DB metadata

        Raises:
            StorageError: If creation fails
        """
        try:
            return self.extraction_results_container.create_item(body=extraction_result)
        except Exception as e:
            raise StorageError(
                operation="create",
                resource=f"extraction-results/{extraction_result.get('id', 'unknown')}",
                reason=str(e),
            )

    def get_extraction_result(self, result_id: str, document_id: str) -> Dict[str, Any]:
        """
        Get an extraction result by ID.

        Args:
            result_id: Extraction result ID
            document_id: Document ID (partition key)

        Returns:
            Extraction result document

        Raises:
            DocumentNotFoundError: If extraction result doesn't exist
            StorageError: If query fails
        """
        try:
            return self.extraction_results_container.read_item(
                item=result_id, partition_key=document_id
            )
        except exceptions.CosmosResourceNotFoundError:
            raise DocumentNotFoundError(document_id, f"Extraction result {result_id} not found")
        except Exception as e:
            raise StorageError(
                operation="read",
                resource=f"extraction-results/{result_id}",
                reason=str(e),
            )

    def update_extraction_result(
        self, result_id: str, document_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an extraction result document.

        Args:
            result_id: Extraction result ID
            document_id: Document ID (partition key)
            updates: Dictionary of fields to update

        Returns:
            Updated extraction result document

        Raises:
            DocumentNotFoundError: If extraction result doesn't exist
            StorageError: If update fails
        """
        try:
            # Read existing document
            existing_doc = self.get_extraction_result(result_id, document_id)

            # Merge updates
            existing_doc.update(updates)

            # Replace document
            return self.extraction_results_container.replace_item(
                item=result_id, body=existing_doc
            )
        except DocumentNotFoundError:
            raise
        except Exception as e:
            raise StorageError(
                operation="update",
                resource=f"extraction-results/{result_id}",
                reason=str(e),
            )

    def create_financial_metric(self, metric: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a financial metric document.

        Args:
            metric: Financial metric data (should match FinancialMetric model)

        Returns:
            Created metric document with Cosmos DB metadata

        Raises:
            StorageError: If creation fails
        """
        try:
            return self.financial_metrics_container.create_item(body=metric)
        except Exception as e:
            raise StorageError(
                operation="create",
                resource=f"financial-metrics/{metric.get('id', 'unknown')}",
                reason=str(e),
            )

    def query_metrics_by_document(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Query all financial metrics for a specific document.

        Args:
            document_id: Document ID to query

        Returns:
            List of financial metric documents

        Raises:
            StorageError: If query fails
        """
        try:
            query = "SELECT * FROM c WHERE c.document_id = @document_id"
            parameters = [{"name": "@document_id", "value": document_id}]

            items = list(
                self.financial_metrics_container.query_items(
                    query=query,
                    parameters=parameters,
                    partition_key=document_id,
                    enable_cross_partition_query=False,
                )
            )
            return items
        except Exception as e:
            raise StorageError(
                operation="query",
                resource=f"financial-metrics (document_id={document_id})",
                reason=str(e),
            )

    def create_processing_log(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a processing log entry.

        Args:
            log_entry: Processing log data (should match ProcessingLog model)

        Returns:
            Created log entry document with Cosmos DB metadata

        Raises:
            StorageError: If creation fails
        """
        try:
            return self.processing_logs_container.create_item(body=log_entry)
        except Exception as e:
            raise StorageError(
                operation="create",
                resource=f"processing-logs/{log_entry.get('id', 'unknown')}",
                reason=str(e),
            )

    def query_processing_logs_by_document(
        self, document_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Query processing logs for a specific document, ordered by timestamp descending.

        Args:
            document_id: Document ID to query
            limit: Maximum number of logs to return (None for all)

        Returns:
            List of processing log documents

        Raises:
            StorageError: If query fails
        """
        try:
            query = (
                "SELECT * FROM c WHERE c.document_id = @document_id "
                "ORDER BY c.event_timestamp DESC"
            )
            if limit:
                query += f" OFFSET 0 LIMIT {limit}"

            parameters = [{"name": "@document_id", "value": document_id}]

            items = list(
                self.processing_logs_container.query_items(
                    query=query,
                    parameters=parameters,
                    partition_key=document_id,
                    enable_cross_partition_query=False,
                )
            )
            return items
        except Exception as e:
            raise StorageError(
                operation="query",
                resource=f"processing-logs (document_id={document_id})",
                reason=str(e),
            )

    def query_by_file_hash(self, file_hash: str, container_name: str = "extraction-results") -> List[Dict[str, Any]]:
        """
        Query documents by file hash for duplicate detection.

        Args:
            file_hash: SHA256 file hash to search for
            container_name: Container to search (default: extraction-results)

        Returns:
            List of matching documents

        Raises:
            StorageError: If query fails
        """
        try:
            container = self.database.get_container_client(container_name)
            query = "SELECT * FROM c WHERE c.file_hash_sha256 = @file_hash"
            parameters = [{"name": "@file_hash", "value": file_hash}]

            items = list(
                container.query_items(
                    query=query,
                    parameters=parameters,
                    enable_cross_partition_query=True,
                )
            )
            return items
        except Exception as e:
            raise StorageError(
                operation="query",
                resource=f"{container_name} (file_hash={file_hash})",
                reason=str(e),
            )
