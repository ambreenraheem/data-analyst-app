"""
Configuration management with Azure Key Vault integration.

This module provides centralized configuration loading from environment variables
and Azure Key Vault for secrets management following Constitution Principle V
(Secure Data Handling).
"""

import os
from typing import Optional

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient


class Config:
    """Application configuration with Key Vault secret retrieval."""

    def __init__(self) -> None:
        """Initialize configuration with environment variables and Key Vault client."""
        # Key Vault configuration
        self.key_vault_url = os.getenv("KEY_VAULT_URL", "")
        self._secret_client: Optional[SecretClient] = None

        # Storage configuration
        self.storage_account_name = os.getenv("STORAGE_ACCOUNT_NAME", "")
        self.blob_container_financial_docs = os.getenv(
            "BLOB_CONTAINER_FINANCIAL_DOCS", "financial-documents"
        )

        # Cosmos DB configuration
        self.cosmos_db_endpoint = os.getenv("COSMOS_DB_ENDPOINT", "")
        self.cosmos_db_database = os.getenv("COSMOS_DB_DATABASE", "financial-insights")
        self.cosmos_container_extraction_results = os.getenv(
            "COSMOS_CONTAINER_EXTRACTION_RESULTS", "extraction-results"
        )
        self.cosmos_container_financial_metrics = os.getenv(
            "COSMOS_CONTAINER_FINANCIAL_METRICS", "financial-metrics"
        )
        self.cosmos_container_processing_logs = os.getenv(
            "COSMOS_CONTAINER_PROCESSING_LOGS", "processing-logs"
        )

        # Service Bus configuration
        self.service_bus_namespace = os.getenv("SERVICE_BUS_NAMESPACE", "")
        self.service_bus_ingestion_queue = os.getenv(
            "SERVICE_BUS_INGESTION_QUEUE", "ingestion-queue"
        )
        self.service_bus_extraction_queue = os.getenv(
            "SERVICE_BUS_EXTRACTION_QUEUE", "extraction-queue"
        )
        self.service_bus_validation_queue = os.getenv(
            "SERVICE_BUS_VALIDATION_QUEUE", "validation-queue"
        )

        # Document Intelligence configuration
        self.document_intelligence_endpoint = os.getenv("DOCUMENT_INTELLIGENCE_ENDPOINT", "")

        # Application Insights
        self.appinsights_connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")

        # Application settings
        self.max_file_size_mb = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
        self.ocr_confidence_threshold_document = float(
            os.getenv("OCR_CONFIDENCE_THRESHOLD_DOCUMENT", "0.75")
        )
        self.ocr_confidence_threshold_metric = float(
            os.getenv("OCR_CONFIDENCE_THRESHOLD_METRIC", "0.70")
        )
        self.processing_timeout_minutes = int(os.getenv("PROCESSING_TIMEOUT_MINUTES", "10"))
        self.retention_days = int(os.getenv("RETENTION_DAYS", "2555"))  # 7 years

    @property
    def secret_client(self) -> SecretClient:
        """
        Get or create Azure Key Vault SecretClient using DefaultAzureCredential.

        Returns:
            SecretClient instance for retrieving secrets

        Raises:
            ValueError: If KEY_VAULT_URL is not configured
        """
        if not self.key_vault_url:
            raise ValueError("KEY_VAULT_URL environment variable is required")

        if self._secret_client is None:
            credential = DefaultAzureCredential()
            self._secret_client = SecretClient(vault_url=self.key_vault_url, credential=credential)

        return self._secret_client

    def get_secret(self, secret_name: str) -> str:
        """
        Retrieve a secret from Azure Key Vault.

        Args:
            secret_name: Name of the secret to retrieve

        Returns:
            Secret value as string

        Raises:
            azure.core.exceptions.ResourceNotFoundError: If secret doesn't exist
        """
        return self.secret_client.get_secret(secret_name).value


# Global configuration instance
config = Config()
