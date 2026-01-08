"""
Validator service for data quality validation.

Validates extracted financial data for completeness, reasonableness,
and confidence thresholds.

Supports Constitution Principle II (Confidence Thresholds) and
Principle VI (Human-in-the-Loop for High-Stakes Decisions).
"""

import logging
from typing import Any, Dict, List, Tuple

from src.shared.config import config


logger = logging.getLogger("validator")
logger.setLevel(logging.INFO)


class ValidationResult:
    """Result of validation with errors and warnings."""

    def __init__(self) -> None:
        """Initialize validation result."""
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.validation_status: str = "passed"  # passed, flagged, failed

    def add_error(self, error: str) -> None:
        """Add a validation error."""
        self.errors.append(error)
        self.validation_status = "failed"

    def add_warning(self, warning: str) -> None:
        """Add a validation warning."""
        self.warnings.append(warning)
        if self.validation_status == "passed":
            self.validation_status = "flagged"

    def is_valid(self) -> bool:
        """Check if validation passed (no errors)."""
        return len(self.errors) == 0

    def requires_manual_review(self) -> bool:
        """Check if manual review is required."""
        return self.validation_status in ["flagged", "failed"]


class Validator:
    """Validator for extracted financial data quality."""

    # Required metrics for income statement
    REQUIRED_INCOME_STATEMENT_METRICS = [
        "revenue",
        "net_income"
    ]

    # Highly recommended metrics (generate warnings if missing)
    RECOMMENDED_INCOME_STATEMENT_METRICS = [
        "cogs",
        "gross_profit",
        "operating_expenses"
    ]

    # Reasonable value ranges (in USD)
    VALUE_RANGES = {
        "revenue": (0, 1_000_000_000_000),  # $0 to $1 trillion
        "cogs": (0, 1_000_000_000_000),
        "gross_profit": (-1_000_000_000_000, 1_000_000_000_000),  # Can be negative in rare cases
        "operating_expenses": (0, 1_000_000_000_000),
        "operating_income": (-1_000_000_000_000, 1_000_000_000_000),  # Can be negative
        "ebitda": (-1_000_000_000_000, 1_000_000_000_000),  # Can be negative
        "net_income": (-1_000_000_000_000, 1_000_000_000_000),  # Can be negative
    }

    @staticmethod
    def validate_completeness(
        metrics: List[Dict[str, Any]],
        extraction_result: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate completeness of extracted metrics.

        Checks for required metrics and recommends additional metrics.

        Args:
            metrics: List of extracted financial metrics
            extraction_result: Extraction result dictionary

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult()

        # Group metrics by type
        metric_types = {metric["metric_type"] for metric in metrics}

        # Check for required metrics
        for required_metric in Validator.REQUIRED_INCOME_STATEMENT_METRICS:
            if required_metric not in metric_types:
                result.add_error(
                    f"Missing required metric: {required_metric}. "
                    f"Income statement must include revenue and net income."
                )

        # Check for recommended metrics
        for recommended_metric in Validator.RECOMMENDED_INCOME_STATEMENT_METRICS:
            if recommended_metric not in metric_types:
                result.add_warning(
                    f"Missing recommended metric: {recommended_metric}. "
                    f"Consider verifying if this metric should be present in the document."
                )

        # Warn if very few metrics extracted
        if len(metrics) < 3:
            result.add_warning(
                f"Only {len(metrics)} financial metrics extracted. "
                f"Expected at least 3-5 metrics for a complete income statement."
            )

        logger.info(
            f"Completeness validation: {len(metrics)} metrics, "
            f"{len(result.errors)} errors, {len(result.warnings)} warnings"
        )

        return result

    @staticmethod
    def validate_ranges(metrics: List[Dict[str, Any]]) -> ValidationResult:
        """
        Validate that metric values are within reasonable ranges.

        Args:
            metrics: List of extracted financial metrics

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult()

        for metric in metrics:
            metric_type = metric.get("metric_type")
            value = metric.get("value")
            metric_name = metric.get("metric_name")

            if metric_type not in Validator.VALUE_RANGES:
                continue

            min_value, max_value = Validator.VALUE_RANGES[metric_type]

            # Check if value is outside reasonable range
            if value < min_value or value > max_value:
                result.add_error(
                    f"{metric_name}: Value {value:,.2f} is outside reasonable range "
                    f"[{min_value:,.2f}, {max_value:,.2f}]. "
                    f"This may indicate OCR extraction error or data quality issue."
                )

            # Specific validations
            if metric_type == "revenue" and value <= 0:
                result.add_error(
                    f"{metric_name}: Revenue must be positive (got {value:,.2f}). "
                    f"Negative or zero revenue indicates extraction error."
                )

            # Warn about unusually large values
            if abs(value) > 100_000_000_000:  # > $100 billion
                result.add_warning(
                    f"{metric_name}: Value {value:,.2f} is unusually large (> $100B). "
                    f"Please verify this is correct."
                )

            # Warn about very small values
            if abs(value) < 1000 and metric_type in ["revenue", "cogs", "operating_expenses"]:
                result.add_warning(
                    f"{metric_name}: Value {value:,.2f} is unusually small (< $1,000). "
                    f"Verify the correct magnitude was extracted (check for K/M/B suffixes)."
                )

        logger.info(
            f"Range validation: {len(metrics)} metrics checked, "
            f"{len(result.errors)} errors, {len(result.warnings)} warnings"
        )

        return result

    @staticmethod
    def validate_confidence(
        metrics: List[Dict[str, Any]],
        extraction_result: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate OCR confidence thresholds.

        Checks document-level and metric-level confidence against thresholds
        per Constitution Principle II.

        Args:
            metrics: List of extracted financial metrics
            extraction_result: Extraction result dictionary

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult()

        # Check document-level confidence
        doc_confidence = extraction_result.get("ocr_confidence_avg", 0.0)
        doc_threshold = config.ocr_confidence_threshold_document

        if doc_confidence < doc_threshold:
            result.add_warning(
                f"Document OCR confidence {doc_confidence:.2f} is below threshold {doc_threshold}. "
                f"Extracted data may require manual verification. "
                f"Consider re-scanning with higher quality or enhanced OCR."
            )

        # Check metric-level confidence
        metric_threshold = config.ocr_confidence_threshold_metric
        low_confidence_metrics = []

        for metric in metrics:
            confidence = metric.get("confidence_score", 0.0)
            metric_name = metric.get("metric_name")

            if confidence < metric_threshold:
                low_confidence_metrics.append(
                    f"{metric_name} (confidence: {confidence:.2f})"
                )

        if low_confidence_metrics:
            result.add_warning(
                f"{len(low_confidence_metrics)} metric(s) have low confidence (< {metric_threshold}): "
                f"{', '.join(low_confidence_metrics[:3])}"
                + ("..." if len(low_confidence_metrics) > 3 else "")
            )

        # Warn if overall confidence is very low
        if doc_confidence < 0.60:
            result.add_error(
                f"Document OCR confidence {doc_confidence:.2f} is critically low (< 0.60). "
                f"Extraction results are unreliable and require manual data entry."
            )

        logger.info(
            f"Confidence validation: document={doc_confidence:.2f}, "
            f"low_confidence_metrics={len(low_confidence_metrics)}, "
            f"{len(result.errors)} errors, {len(result.warnings)} warnings"
        )

        return result

    @staticmethod
    def validate_relationships(metrics: List[Dict[str, Any]]) -> ValidationResult:
        """
        Validate relationships between financial metrics.

        Checks mathematical relationships (e.g., Revenue - COGS = Gross Profit).

        Args:
            metrics: List of extracted financial metrics

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult()

        # Create a lookup by metric type
        metric_lookup = {
            metric["metric_type"]: metric["value"]
            for metric in metrics
        }

        # Validate: Revenue - COGS = Gross Profit (with tolerance)
        if all(k in metric_lookup for k in ["revenue", "cogs", "gross_profit"]):
            revenue = metric_lookup["revenue"]
            cogs = metric_lookup["cogs"]
            gross_profit = metric_lookup["gross_profit"]
            calculated_gross_profit = revenue - cogs

            # Allow 1% tolerance for rounding
            tolerance = abs(calculated_gross_profit) * 0.01
            if abs(gross_profit - calculated_gross_profit) > max(tolerance, 1000):
                result.add_warning(
                    f"Gross Profit mismatch: Expected {calculated_gross_profit:,.2f} "
                    f"(Revenue {revenue:,.2f} - COGS {cogs:,.2f}), "
                    f"but got {gross_profit:,.2f}. "
                    f"Verify extraction accuracy."
                )

        # Validate: Gross Profit > 0 if Revenue > COGS
        if "revenue" in metric_lookup and "cogs" in metric_lookup:
            if metric_lookup["revenue"] > metric_lookup["cogs"]:
                if "gross_profit" in metric_lookup and metric_lookup["gross_profit"] <= 0:
                    result.add_error(
                        f"Gross Profit should be positive when Revenue > COGS. "
                        f"Got Gross Profit={metric_lookup['gross_profit']:,.2f}"
                    )

        logger.info(
            f"Relationship validation: {len(result.errors)} errors, {len(result.warnings)} warnings"
        )

        return result

    @staticmethod
    def validate_all(
        metrics: List[Dict[str, Any]],
        extraction_result: Dict[str, Any]
    ) -> ValidationResult:
        """
        Run all validation checks.

        Args:
            metrics: List of extracted financial metrics
            extraction_result: Extraction result dictionary

        Returns:
            Combined ValidationResult
        """
        combined_result = ValidationResult()

        # Run all validations
        completeness_result = Validator.validate_completeness(metrics, extraction_result)
        range_result = Validator.validate_ranges(metrics)
        confidence_result = Validator.validate_confidence(metrics, extraction_result)
        relationship_result = Validator.validate_relationships(metrics)

        # Combine results
        combined_result.errors.extend(completeness_result.errors)
        combined_result.errors.extend(range_result.errors)
        combined_result.errors.extend(confidence_result.errors)
        combined_result.errors.extend(relationship_result.errors)

        combined_result.warnings.extend(completeness_result.warnings)
        combined_result.warnings.extend(range_result.warnings)
        combined_result.warnings.extend(confidence_result.warnings)
        combined_result.warnings.extend(relationship_result.warnings)

        # Determine overall status
        if combined_result.errors:
            combined_result.validation_status = "failed"
        elif combined_result.warnings:
            combined_result.validation_status = "flagged"
        else:
            combined_result.validation_status = "passed"

        logger.info(
            f"Validation complete: status={combined_result.validation_status}, "
            f"errors={len(combined_result.errors)}, warnings={len(combined_result.warnings)}"
        )

        return combined_result


# Global validator instance
validator = Validator()
