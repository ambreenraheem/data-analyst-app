"""
Azure Document Intelligence service wrapper.

Provides PDF table extraction using Azure Document Intelligence
prebuilt-layout model with source reference tracking.

Supports Constitution Principle I (Data-First with source traceability)
and Principle II (Confidence scoring for autonomous reasoning).
"""

import logging
from typing import Any, Dict, List, Optional

from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential

from src.shared.config import config
from src.shared.exceptions import ExtractionFailedError


logger = logging.getLogger("document_intelligence")
logger.setLevel(logging.INFO)


class DocumentIntelligenceService:
    """Service for Azure Document Intelligence operations."""

    def __init__(self) -> None:
        """Initialize Document Intelligence client with authentication."""
        # Try to get API key from environment or Key Vault
        try:
            # In production, retrieve from Key Vault
            # For now, use Managed Identity
            credential = DefaultAzureCredential()
            self.client = DocumentAnalysisClient(
                endpoint=config.document_intelligence_endpoint,
                credential=credential
            )
        except Exception as e:
            logger.warning(f"Failed to initialize with Managed Identity, trying Key Vault: {e}")
            try:
                # Fallback to API key from Key Vault
                api_key = config.get_secret("document-intelligence-api-key")
                self.client = DocumentAnalysisClient(
                    endpoint=config.document_intelligence_endpoint,
                    credential=AzureKeyCredential(api_key)
                )
            except Exception as e:
                logger.error(f"Failed to initialize Document Intelligence client: {e}")
                raise

    def extract_tables_from_pdf(
        self, blob_url: str, document_id: str, use_enhanced_ocr: bool = False
    ) -> Dict[str, Any]:
        """
        Extract tables from PDF using Document Intelligence prebuilt-layout model.

        Args:
            blob_url: Azure Blob Storage URL of the PDF
            document_id: Unique document identifier
            use_enhanced_ocr: Whether to use enhanced OCR settings for better quality

        Returns:
            Dictionary containing:
            {
                "tables": [...],  # List of extracted tables
                "model_version": "prebuilt-layout-2024-02-29",
                "page_count": 10,
                "overall_confidence": 0.92
            }

        Raises:
            ExtractionFailedError: If extraction fails
        """
        logger.info(
            f"Starting PDF extraction for document: {document_id}, "
            f"enhanced_ocr={use_enhanced_ocr}"
        )

        try:
            # Configure analysis options
            # Enhanced OCR uses higher quality settings but takes longer
            analysis_options = {}
            if use_enhanced_ocr:
                # Enable high-resolution mode for better accuracy on low-quality scans
                analysis_options["features"] = ["ocr.highResolution"]
                logger.info("Using enhanced OCR with high-resolution mode")

            # Begin analysis with prebuilt-layout model
            poller = self.client.begin_analyze_document_from_url(
                model_id="prebuilt-layout",
                document_url=blob_url,
                **analysis_options
            )

            # Wait for completion (with timeout)
            result = poller.result()

            logger.info(f"Document analysis completed for: {document_id}")

            # Extract tables with source references
            tables = self._extract_tables_with_references(result)

            # Calculate overall confidence
            overall_confidence = self._calculate_overall_confidence(result)

            return {
                "tables": tables,
                "model_version": result.model_id,
                "page_count": len(result.pages),
                "overall_confidence": overall_confidence,
            }

        except Exception as e:
            logger.error(f"PDF extraction failed for document {document_id}: {e}")
            raise ExtractionFailedError(
                document_id=document_id,
                reason=f"Document Intelligence extraction failed: {str(e)}",
                retry_eligible=True
            )

    def _extract_tables_with_references(self, result: Any) -> List[Dict[str, Any]]:
        """
        Extract tables with source references from analysis result.

        Args:
            result: Document analysis result

        Returns:
            List of table dictionaries with cells and source references
        """
        tables = []

        for table_idx, table in enumerate(result.tables):
            table_data = {
                "table_id": f"table-{table_idx + 1}",
                "row_count": table.row_count,
                "column_count": table.column_count,
                "page_number": self._get_table_page_number(table),
                "bounding_regions": self._extract_bounding_regions(table),
                "cells": []
            }

            # Extract cells with source references
            for cell in table.cells:
                cell_data = {
                    "row_index": cell.row_index,
                    "column_index": cell.column_index,
                    "row_span": cell.row_span if hasattr(cell, 'row_span') else 1,
                    "column_span": cell.column_span if hasattr(cell, 'column_span') else 1,
                    "content": cell.content,
                    "confidence": self._get_cell_confidence(cell),
                    "bounding_box": self._extract_bounding_box(cell),
                    "kind": cell.kind if hasattr(cell, 'kind') else "content"
                }
                table_data["cells"].append(cell_data)

            tables.append(table_data)

        logger.info(f"Extracted {len(tables)} tables from document")
        return tables

    def _get_table_page_number(self, table: Any) -> Optional[int]:
        """Get the page number where the table appears."""
        if hasattr(table, 'bounding_regions') and table.bounding_regions:
            # Return the first page number (1-indexed)
            return table.bounding_regions[0].page_number
        return None

    def _extract_bounding_regions(self, table: Any) -> List[Dict[str, Any]]:
        """Extract bounding regions for a table."""
        regions = []
        if hasattr(table, 'bounding_regions'):
            for region in table.bounding_regions:
                regions.append({
                    "page_number": region.page_number,
                    "polygon": [{"x": point.x, "y": point.y} for point in region.polygon] if hasattr(region, 'polygon') else []
                })
        return regions

    def _get_cell_confidence(self, cell: Any) -> float:
        """
        Get confidence score for a cell.

        Azure Document Intelligence provides confidence at the span level.
        We aggregate confidence from all spans in the cell.
        """
        if hasattr(cell, 'confidence') and cell.confidence is not None:
            return cell.confidence

        # Fallback: aggregate from spans
        if hasattr(cell, 'spans') and cell.spans:
            confidences = []
            for span in cell.spans:
                if hasattr(span, 'confidence') and span.confidence is not None:
                    confidences.append(span.confidence)
            if confidences:
                return sum(confidences) / len(confidences)

        # Default confidence if not available
        return 0.8  # Conservative default

    def _extract_bounding_box(self, cell: Any) -> Optional[List[float]]:
        """
        Extract bounding box coordinates for a cell.

        Returns [x1, y1, x2, y2] or None if not available.
        """
        if hasattr(cell, 'bounding_regions') and cell.bounding_regions:
            region = cell.bounding_regions[0]
            if hasattr(region, 'polygon') and len(region.polygon) >= 4:
                # Convert polygon to bounding box [x1, y1, x2, y2]
                x_coords = [point.x for point in region.polygon]
                y_coords = [point.y for point in region.polygon]
                return [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]

        return None

    def _calculate_overall_confidence(self, result: Any) -> float:
        """
        Calculate overall confidence for the document extraction.

        Args:
            result: Document analysis result

        Returns:
            Average confidence score (0.0-1.0)
        """
        confidences = []

        # Collect confidence from all table cells
        for table in result.tables:
            for cell in table.cells:
                confidence = self._get_cell_confidence(cell)
                confidences.append(confidence)

        if not confidences:
            return 0.0

        return sum(confidences) / len(confidences)


# Global service instance
document_intelligence_service = DocumentIntelligenceService()
