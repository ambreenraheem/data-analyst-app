"""
Extraction Worker Azure Function.

Service Bus trigger for extraction-queue.
Handles PDF and Excel extraction, financial metric identification,
and persistence with source references.

Supports Constitution Principles I (Data-First), II (Confidence Thresholds),
and III (Auditability).
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List

import azure.functions as func
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.identity import DefaultAzureCredential

from src.shared.config import config
from src.shared.exceptions import ExtractionFailedError, StorageError
from src.shared.telemetry import telemetry
from src.ingestion.services.storage_manager import StorageManager
from src.ingestion.services.cosmos_manager import CosmosManager
from src.ingestion.services.document_intelligence import document_intelligence_service
from src.ingestion.services.excel_parser import excel_parser
from src.ingestion.services.financial_parser import financial_parser
from src.ingestion.utils.confidence_scorer import ConfidenceScorer
from src.ingestion.models.extraction_result import ExtractionResult
from src.ingestion.models.financial_metric import FinancialMetric
from src.ingestion.models.source_reference import SourceReference
from src.ingestion.models.processing_log import ProcessingLog


# Initialize services
storage_manager = StorageManager()
cosmos_manager = CosmosManager()
confidence_scorer = ConfidenceScorer()

logger = logging.getLogger("extraction_worker")
logger.setLevel(logging.INFO)


def main(msg: func.ServiceBusMessage) -> None:
    """
    Process extraction queue messages.

    Message format:
    {
        "document_id": "doc-abc123",
        "blob_url": "https://...",
        "document_name": "report.pdf",
        "document_type": "PDF",
        "queued_at": "2024-01-15T10:30:00Z"
    }

    Args:
        msg: Service Bus message from extraction-queue
    """
    start_time = datetime.utcnow()

    try:
        # Parse message
        message_body = msg.get_body().decode("utf-8")
        message_data = json.loads(message_body)

        document_id = message_data["document_id"]
        blob_url = message_data["blob_url"]
        document_name = message_data["document_name"]
        document_type = message_data["document_type"]
        enhanced_ocr = message_data.get("enhanced_ocr", False)
        retry_count = message_data.get("retry_count", 0)

        logger.info(
            f"Starting extraction for document: {document_id} ({document_type}), "
            f"enhanced_ocr={enhanced_ocr}, retry_count={retry_count}"
        )

        # Create extraction result record
        extraction_result_id = f"extraction-{uuid.uuid4()}"

        # Log extraction started
        _create_processing_log(
            document_id=document_id,
            event_type="extraction_started",
            event_data={
                "extraction_result_id": extraction_result_id,
                "document_name": document_name,
                "document_type": document_type,
                "enhanced_ocr": enhanced_ocr,
                "retry_count": retry_count,
            },
        )

        # Route to appropriate extraction method
        if document_type == "PDF":
            extraction_data = _extract_pdf(blob_url, document_id, document_name, enhanced_ocr)
        elif document_type == "XLSX":
            extraction_data = _extract_excel(blob_url, document_id, document_name)
        else:
            raise ExtractionFailedError(
                document_id=document_id,
                reason=f"Unsupported document type: {document_type}",
                retry_eligible=False
            )

        # Extract financial metrics from tables
        financial_metrics = _extract_financial_metrics(
            tables=extraction_data["tables"],
            document_id=document_id,
            document_name=document_name,
            document_type=document_type
        )

        # Create extraction result
        extraction_result = _create_extraction_result(
            extraction_result_id=extraction_result_id,
            document_id=document_id,
            document_name=document_name,
            document_type=document_type,
            extraction_data=extraction_data,
            metrics_count=len(financial_metrics),
            start_time=start_time
        )

        # Persist extraction result to Cosmos DB
        cosmos_manager.create_extraction_result(extraction_result.model_dump(mode="json"))
        logger.info(f"Persisted extraction result: {extraction_result_id}")

        # Persist financial metrics to Cosmos DB
        for metric in financial_metrics:
            cosmos_manager.create_financial_metric(metric.model_dump(mode="json"))

        logger.info(f"Persisted {len(financial_metrics)} financial metrics")

        # Queue to validation queue
        _enqueue_to_validation_queue(
            document_id=document_id,
            extraction_result_id=extraction_result_id
        )

        # Log extraction completed
        duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        _create_processing_log(
            document_id=document_id,
            event_type="extraction_completed",
            event_data={
                "extraction_result_id": extraction_result_id,
                "metrics_extracted": len(financial_metrics),
                "tables_extracted": len(extraction_data["tables"]),
                "avg_confidence": extraction_data["overall_confidence"],
                "duration_seconds": duration_seconds,
            },
        )

        # Track telemetry
        telemetry.track_extraction_completed(
            document_id=document_id,
            duration_seconds=duration_seconds,
            metrics_extracted=len(financial_metrics),
            avg_confidence=extraction_data["overall_confidence"],
        )

        logger.info(f"Extraction completed for document: {document_id}")

    except ExtractionFailedError as e:
        logger.error(f"Extraction failed: {e}")
        telemetry.track_exception(e, properties={"error_type": "extraction_failed"})
        _create_processing_log(
            document_id=message_data.get("document_id", "unknown"),
            event_type="failed",
            event_data={
                "error": str(e),
                "error_type": "extraction_failed",
                "retry_eligible": e.retry_eligible
            },
        )
        if not e.retry_eligible:
            # Don't retry - complete the message
            return
        raise  # Let Service Bus retry

    except Exception as e:
        logger.exception(f"Unexpected error during extraction: {e}")
        telemetry.track_exception(e, properties={"error_type": "unexpected"})
        _create_processing_log(
            document_id=message_data.get("document_id", "unknown"),
            event_type="failed",
            event_data={"error": str(e), "error_type": "unexpected_error"},
        )
        raise  # Let Service Bus retry


def _extract_pdf(
    blob_url: str, document_id: str, document_name: str, enhanced_ocr: bool = False
) -> Dict[str, Any]:
    """
    Extract data from PDF using Document Intelligence.

    Args:
        blob_url: URL of the PDF in Blob Storage
        document_id: Unique document identifier
        document_name: Original filename
        enhanced_ocr: Whether to use enhanced OCR settings (higher quality, slower)

    Returns:
        Extraction data dictionary
    """
    logger.info(f"Extracting PDF: {document_id}, enhanced_ocr={enhanced_ocr}")

    # Pass enhanced_ocr flag to Document Intelligence service
    # Enhanced OCR uses higher quality settings for difficult documents
    return document_intelligence_service.extract_tables_from_pdf(
        blob_url, document_id, use_enhanced_ocr=enhanced_ocr
    )


def _extract_excel(blob_url: str, document_id: str, document_name: str) -> Dict[str, Any]:
    """Extract data from Excel file."""
    logger.info(f"Extracting Excel: {document_id}")

    # Download Excel file from blob storage
    file_extension = ".xlsx"
    file_bytes = storage_manager.download_document(document_id, file_extension)

    return excel_parser.extract_tables_from_excel(file_bytes, document_id, document_name)


def _extract_financial_metrics(
    tables: List[Dict[str, Any]],
    document_id: str,
    document_name: str,
    document_type: str
) -> List[FinancialMetric]:
    """
    Extract financial metrics from tables.

    Args:
        tables: List of extracted tables
        document_id: Document identifier
        document_name: Original filename
        document_type: Document type (PDF or XLSX)

    Returns:
        List of FinancialMetric objects
    """
    financial_metrics = []

    for table in tables:
        # Check if this table contains an income statement
        if financial_parser.detect_income_statement(table):
            logger.info(f"Found income statement in table: {table.get('table_id')}")

            # Extract metrics
            metrics = financial_parser.extract_income_statement_metrics(table)

            # Identify reporting period
            reporting_period = financial_parser.identify_reporting_period(table)

            # Convert to FinancialMetric objects
            for metric_data in metrics:
                # Create source reference
                value_cell = metric_data["value_cell"]
                source_ref = SourceReference(
                    document_id=document_id,
                    document_name=document_name,
                    page_number=table.get("page_number") if document_type == "PDF" else None,
                    sheet_name=table.get("sheet_name") if document_type == "XLSX" else None,
                    table_id=table.get("table_id"),
                    cell_reference=value_cell.get("cell_reference") or f"row:{value_cell['row_index']},col:{value_cell['column_index']}",
                    bounding_box=value_cell.get("bounding_box"),
                )

                # Calculate confidence
                confidence = confidence_scorer.calculate_metric_confidence(
                    extracted_value=value_cell.get("content", ""),
                    cell_confidence=metric_data["confidence"],
                    parsing_success=True
                )

                # Determine if should flag for review
                flagged_for_review = confidence_scorer.should_flag_for_review(
                    confidence=confidence,
                    metric_threshold=config.ocr_confidence_threshold_metric
                )

                # Create FinancialMetric
                financial_metric = FinancialMetric(
                    id=f"metric-{uuid.uuid4()}",
                    document_id=document_id,
                    metric_type=metric_data["metric_type"],
                    metric_name=metric_data["metric_name"],
                    value=metric_data["value"],
                    currency=metric_data.get("currency", "USD"),
                    period=reporting_period,
                    confidence_score=confidence,
                    source_reference=source_ref,
                    extracted_at=datetime.utcnow(),
                    flagged_for_review=flagged_for_review,
                )

                financial_metrics.append(financial_metric)

    return financial_metrics


def _create_extraction_result(
    extraction_result_id: str,
    document_id: str,
    document_name: str,
    document_type: str,
    extraction_data: Dict[str, Any],
    metrics_count: int,
    start_time: datetime
) -> ExtractionResult:
    """Create an ExtractionResult object."""
    end_time = datetime.utcnow()

    return ExtractionResult(
        id=extraction_result_id,
        document_id=document_id,
        document_name=document_name,
        document_type=document_type,
        extraction_status="completed",
        ocr_confidence_avg=extraction_data["overall_confidence"],
        tables_extracted=len(extraction_data["tables"]),
        metrics_extracted=metrics_count,
        extraction_started_at=start_time,
        extraction_completed_at=end_time,
        document_intelligence_model_version=extraction_data.get("model_version"),
        validation_status=None,  # Will be updated by validation worker
        validation_errors=[],
        validation_warnings=[],
        requires_manual_review=extraction_data["overall_confidence"] < config.ocr_confidence_threshold_document,
        error_message=None,
    )


def _create_processing_log(
    document_id: str, event_type: str, event_data: Dict[str, Any]
) -> None:
    """Create a processing log entry."""
    try:
        log_entry = ProcessingLog(
            id=f"log-{uuid.uuid4()}",
            document_id=document_id,
            event_type=event_type,
            event_timestamp=datetime.utcnow(),
            event_data=event_data,
            function_name="extraction_worker",
            execution_id=None,
        )

        cosmos_manager.create_processing_log(log_entry.model_dump(mode="json"))

    except Exception as e:
        logger.error(f"Failed to create processing log: {e}")


def _enqueue_to_validation_queue(document_id: str, extraction_result_id: str) -> None:
    """Enqueue document to validation queue."""
    try:
        credential = DefaultAzureCredential()
        fully_qualified_namespace = config.service_bus_namespace

        with ServiceBusClient(
            fully_qualified_namespace=fully_qualified_namespace, credential=credential
        ) as client:
            with client.get_queue_sender(
                queue_name=config.service_bus_validation_queue
            ) as sender:
                message_body = {
                    "document_id": document_id,
                    "extraction_result_id": extraction_result_id,
                    "queued_at": datetime.utcnow().isoformat(),
                }

                message = ServiceBusMessage(
                    body=json.dumps(message_body),
                    content_type="application/json",
                    message_id=document_id,
                )

                sender.send_messages(message)
                logger.info(f"Enqueued document to validation queue: {document_id}")

    except Exception as e:
        logger.error(f"Failed to enqueue message to validation queue: {e}")
        raise
