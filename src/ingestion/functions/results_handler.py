"""
Results Handler Azure Function.

HTTP trigger for GET /api/v1/documents/{document_id}/results endpoint.
Retrieves extracted financial metrics with full source references.

Supports Constitution Principle I (Data-First with source traceability)
and Principle III (Auditability).
"""

import json
import logging
from typing import Any, Dict, List

import azure.functions as func

from src.shared.exceptions import DocumentNotFoundError, StorageError
from src.shared.telemetry import telemetry
from src.ingestion.services.cosmos_manager import CosmosManager
from src.ingestion.utils.audit_logger import audit_logger


# Initialize services
cosmos_manager = CosmosManager()
logger = logging.getLogger("results_handler")
logger.setLevel(logging.INFO)


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Handle document results retrieval requests.

    Route: GET /api/v1/documents/{document_id}/results

    Query parameters:
    - include_low_confidence: bool (default: true) - Include metrics flagged for review
    - format: str (default: "detailed") - "detailed" or "summary"

    Response format (detailed):
    {
        "document_id": "doc-abc123",
        "document_name": "Q4_2024_Financial_Report.pdf",
        "extraction_status": "completed",
        "validation_status": "passed",
        "metrics": [
            {
                "metric_type": "revenue",
                "metric_name": "Total Revenue",
                "value": 15750000.0,
                "currency": "USD",
                "period": "Q4 2024",
                "confidence_score": 0.95,
                "flagged_for_review": false,
                "source_reference": {
                    "document_name": "Q4_2024_Financial_Report.pdf",
                    "page_number": 3,
                    "table_id": "table-1",
                    "cell_reference": "row:5,col:2"
                }
            },
            ...
        ],
        "summary": {
            "total_metrics": 25,
            "flagged_metrics": 2,
            "avg_confidence": 0.92
        }
    }

    Args:
        req: HTTP request with document_id in route

    Returns:
        HTTP response with extraction results
    """
    logger.info("Document results query received")

    try:
        # Extract document_id from route parameter
        document_id = req.route_params.get("document_id")
        if not document_id:
            return func.HttpResponse(
                body=json.dumps({"error": "document_id is required in URL path"}),
                status_code=400,
                mimetype="application/json",
            )

        # Extract user identity for audit logging
        user_id = req.headers.get("X-MS-CLIENT-PRINCIPAL-ID", "unknown-user")

        # Parse query parameters
        include_low_confidence = req.params.get("include_low_confidence", "true").lower() == "true"
        response_format = req.params.get("format", "detailed")

        # Check if processing is complete (T089)
        extraction_result = _get_extraction_result(document_id)

        if extraction_result["extraction_status"] != "completed":
            return func.HttpResponse(
                body=json.dumps({
                    "error": "Document processing is not complete",
                    "error_type": "processing_incomplete",
                    "current_status": extraction_result["extraction_status"],
                    "message": "Please check /status endpoint for processing status"
                }),
                status_code=409,  # Conflict
                mimetype="application/json",
            )

        # Retrieve financial metrics (T088)
        metrics = cosmos_manager.query_metrics_by_document(document_id=document_id)

        if not metrics:
            logger.warning(f"No metrics found for document: {document_id}")
            return func.HttpResponse(
                body=json.dumps({
                    "error": "No financial metrics found for this document",
                    "error_type": "no_metrics",
                    "message": "Document was processed but no financial metrics were extracted"
                }),
                status_code=404,
                mimetype="application/json",
            )

        # Filter metrics if requested
        if not include_low_confidence:
            metrics = [m for m in metrics if not m.get("flagged_for_review", False)]

        # Format response based on requested format
        if response_format == "summary":
            response_data = _format_summary_response(
                document_id=document_id,
                extraction_result=extraction_result,
                metrics=metrics
            )
        else:  # detailed
            response_data = _format_detailed_response(
                document_id=document_id,
                extraction_result=extraction_result,
                metrics=metrics
            )

        # Log audit event (T092)
        audit_logger.log_document_view(
            user_id=user_id,
            document_id=document_id,
            view_type="results"
        )

        logger.info(f"Results query completed for document: {document_id} ({len(metrics)} metrics)")

        return func.HttpResponse(
            body=json.dumps(response_data, default=str),
            status_code=200,
            mimetype="application/json",
        )

    except DocumentNotFoundError as e:
        logger.warning(f"Document not found: {e}")
        return func.HttpResponse(
            body=json.dumps(
                {"error": str(e), "error_type": "document_not_found"}
            ),
            status_code=404,
            mimetype="application/json",
        )

    except StorageError as e:
        logger.error(f"Storage error during results query: {e}")
        telemetry.track_exception(e, properties={"error_type": "storage"})
        return func.HttpResponse(
            body=json.dumps(
                {"error": "Failed to retrieve document results", "error_type": "storage_error"}
            ),
            status_code=500,
            mimetype="application/json",
        )

    except Exception as e:
        logger.exception(f"Unexpected error during results query: {e}")
        telemetry.track_exception(e, properties={"error_type": "unexpected"})
        return func.HttpResponse(
            body=json.dumps(
                {"error": "Internal server error", "error_type": "server_error"}
            ),
            status_code=500,
            mimetype="application/json",
        )


def _get_extraction_result(document_id: str) -> Dict[str, Any]:
    """
    Get extraction result for a document.

    Args:
        document_id: Document identifier

    Returns:
        Extraction result dictionary

    Raises:
        DocumentNotFoundError: If extraction result not found
    """
    try:
        query = "SELECT * FROM c WHERE c.document_id = @document_id"
        parameters = [{"name": "@document_id", "value": document_id}]

        results = list(
            cosmos_manager.extraction_results_container.query_items(
                query=query,
                parameters=parameters,
                partition_key=document_id,
                enable_cross_partition_query=False,
            )
        )

        if not results:
            raise DocumentNotFoundError(
                document_id=document_id,
                message=f"No extraction result found for document: {document_id}"
            )

        return results[0]

    except DocumentNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to get extraction result: {e}")
        raise StorageError(
            operation="query",
            resource=f"extraction-results/{document_id}",
            reason=str(e)
        )


def _format_detailed_response(
    document_id: str,
    extraction_result: Dict[str, Any],
    metrics: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Format detailed response with full metric information.

    Args:
        document_id: Document identifier
        extraction_result: Extraction result dictionary
        metrics: List of financial metrics

    Returns:
        Formatted response dictionary
    """
    # Format metrics with source references (T090)
    formatted_metrics = []

    for metric in metrics:
        formatted_metric = {
            "id": metric.get("id"),
            "metric_type": metric.get("metric_type"),
            "metric_name": metric.get("metric_name"),
            "value": metric.get("value"),
            "currency": metric.get("currency"),
            "period": metric.get("period"),
            "confidence_score": metric.get("confidence_score"),
            "flagged_for_review": metric.get("flagged_for_review", False),
            "source_reference": metric.get("source_reference", {}),
            "extracted_at": metric.get("extracted_at"),
        }
        formatted_metrics.append(formatted_metric)

    # Calculate summary statistics
    flagged_count = sum(1 for m in metrics if m.get("flagged_for_review", False))
    confidences = [m.get("confidence_score", 0) for m in metrics if m.get("confidence_score")]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    return {
        "document_id": document_id,
        "document_name": extraction_result.get("document_name"),
        "document_type": extraction_result.get("document_type"),
        "extraction_status": extraction_result.get("extraction_status"),
        "validation_status": extraction_result.get("validation_status"),
        "requires_manual_review": extraction_result.get("requires_manual_review", False),
        "validation_errors": extraction_result.get("validation_errors", []),
        "validation_warnings": extraction_result.get("validation_warnings", []),
        "metrics": formatted_metrics,
        "summary": {
            "total_metrics": len(metrics),
            "flagged_metrics": flagged_count,
            "avg_confidence": round(avg_confidence, 3),
            "tables_extracted": extraction_result.get("tables_extracted", 0),
        },
        "timestamps": {
            "extracted_at": extraction_result.get("extraction_completed_at"),
        }
    }


def _format_summary_response(
    document_id: str,
    extraction_result: Dict[str, Any],
    metrics: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Format summary response with aggregated metrics.

    Args:
        document_id: Document identifier
        extraction_result: Extraction result dictionary
        metrics: List of financial metrics

    Returns:
        Formatted summary response
    """
    # Group metrics by type
    metrics_by_type = {}
    for metric in metrics:
        metric_type = metric.get("metric_type")
        if metric_type not in metrics_by_type:
            metrics_by_type[metric_type] = []
        metrics_by_type[metric_type].append(metric)

    # Create summary for each metric type
    summary_metrics = []
    for metric_type, type_metrics in metrics_by_type.items():
        # Take the first metric of each type (or aggregate if multiple)
        representative = type_metrics[0]
        summary_metrics.append({
            "metric_type": metric_type,
            "metric_name": representative.get("metric_name"),
            "value": representative.get("value"),
            "currency": representative.get("currency"),
            "period": representative.get("period"),
            "confidence_score": representative.get("confidence_score"),
        })

    return {
        "document_id": document_id,
        "document_name": extraction_result.get("document_name"),
        "validation_status": extraction_result.get("validation_status"),
        "metrics_summary": summary_metrics,
        "total_metrics": len(metrics),
    }
