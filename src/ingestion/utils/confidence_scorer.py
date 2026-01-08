"""
Confidence scorer for OCR quality assessment.

Analyzes OCR confidence scores at document, table, and cell levels
to support Constitution Principle II (Autonomous Reasoning with Confidence Thresholds).
"""

from typing import Dict, List, Optional, Any
from statistics import mean


class ConfidenceScorer:
    """Analyzer for OCR confidence scores."""

    @staticmethod
    def calculate_document_confidence(tables: List[Dict[str, Any]]) -> float:
        """
        Calculate average confidence across all tables in a document.

        Args:
            tables: List of table dictionaries with 'cells' containing confidence scores

        Returns:
            Average confidence (0.0-1.0) across all cells in all tables
        """
        all_confidences = []

        for table in tables:
            cells = table.get("cells", [])
            for cell in cells:
                confidence = cell.get("confidence")
                if confidence is not None:
                    all_confidences.append(confidence)

        if not all_confidences:
            return 0.0

        return mean(all_confidences)

    @staticmethod
    def calculate_table_confidence(table: Dict[str, Any]) -> float:
        """
        Calculate average confidence for a single table.

        Args:
            table: Table dictionary with 'cells' containing confidence scores

        Returns:
            Average confidence (0.0-1.0) for all cells in the table
        """
        cells = table.get("cells", [])
        confidences = [cell.get("confidence") for cell in cells if cell.get("confidence") is not None]

        if not confidences:
            return 0.0

        return mean(confidences)

    @staticmethod
    def calculate_cell_confidence(cell: Dict[str, Any]) -> float:
        """
        Get confidence score for a single cell.

        Args:
            cell: Cell dictionary with 'confidence' field

        Returns:
            Confidence score (0.0-1.0) or 0.0 if not available
        """
        return cell.get("confidence", 0.0)

    @staticmethod
    def assess_quality(confidence: float, threshold_high: float = 0.85, threshold_low: float = 0.70) -> str:
        """
        Assess OCR quality based on confidence score.

        Args:
            confidence: Confidence score (0.0-1.0)
            threshold_high: High confidence threshold (default: 0.85)
            threshold_low: Low confidence threshold (default: 0.70)

        Returns:
            Quality assessment: "high", "medium", or "low"
        """
        if confidence >= threshold_high:
            return "high"
        elif confidence >= threshold_low:
            return "medium"
        else:
            return "low"

    @staticmethod
    def calculate_metric_confidence(
        extracted_value: str,
        cell_confidence: float,
        parsing_success: bool
    ) -> float:
        """
        Calculate confidence for an extracted financial metric.

        Combines OCR confidence with parsing success to determine overall
        confidence in the extracted metric value.

        Args:
            extracted_value: Extracted text value
            cell_confidence: OCR confidence for the cell (0.0-1.0)
            parsing_success: Whether number parsing succeeded

        Returns:
            Adjusted confidence score (0.0-1.0)
        """
        # Start with OCR confidence
        confidence = cell_confidence

        # Penalize if parsing failed
        if not parsing_success:
            confidence *= 0.5  # Reduce confidence by 50%

        # Penalize if extracted value is very short (likely incomplete)
        if len(extracted_value.strip()) < 2:
            confidence *= 0.7  # Reduce confidence by 30%

        # Ensure confidence stays within bounds
        confidence = max(0.0, min(1.0, confidence))

        return confidence

    @staticmethod
    def get_confidence_statistics(confidences: List[float]) -> Dict[str, float]:
        """
        Calculate confidence statistics for a set of confidence scores.

        Args:
            confidences: List of confidence scores

        Returns:
            Dictionary with min, max, mean, and median confidence scores
        """
        if not confidences:
            return {
                "min": 0.0,
                "max": 0.0,
                "mean": 0.0,
                "median": 0.0,
                "count": 0
            }

        sorted_confidences = sorted(confidences)
        n = len(sorted_confidences)
        median = (
            sorted_confidences[n // 2]
            if n % 2 == 1
            else (sorted_confidences[n // 2 - 1] + sorted_confidences[n // 2]) / 2
        )

        return {
            "min": min(confidences),
            "max": max(confidences),
            "mean": mean(confidences),
            "median": median,
            "count": n
        }

    @staticmethod
    def should_flag_for_review(
        confidence: float,
        document_threshold: float = 0.75,
        metric_threshold: float = 0.70
    ) -> bool:
        """
        Determine if a metric should be flagged for manual review.

        Supports Constitution Principle VI (Human-in-the-Loop for High-Stakes Decisions).

        Args:
            confidence: Confidence score to evaluate
            document_threshold: Document-level confidence threshold (default: 0.75)
            metric_threshold: Metric-level confidence threshold (default: 0.70)

        Returns:
            True if should be flagged for review, False otherwise
        """
        return confidence < metric_threshold

    @staticmethod
    def get_confidence_label(confidence: float) -> str:
        """
        Get a human-readable label for a confidence score.

        Args:
            confidence: Confidence score (0.0-1.0)

        Returns:
            Label: "Very High", "High", "Medium", "Low", "Very Low"
        """
        if confidence >= 0.95:
            return "Very High"
        elif confidence >= 0.85:
            return "High"
        elif confidence >= 0.70:
            return "Medium"
        elif confidence >= 0.50:
            return "Low"
        else:
            return "Very Low"


# Convenience functions
def calculate_average_confidence(confidences: List[float]) -> float:
    """Calculate average confidence from a list of scores."""
    if not confidences:
        return 0.0
    return mean(confidences)


def is_high_confidence(confidence: float, threshold: float = 0.85) -> bool:
    """Check if confidence score is high."""
    return confidence >= threshold
