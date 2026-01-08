"""
Unit tests for validator.py

Tests data quality validation including completeness, range checks,
confidence thresholds, and relationship validation.
"""

import pytest
from src.ingestion.services.validator import Validator, ValidationResult


class TestValidationResult:
    """Test suite for ValidationResult class."""

    def test_initial_state(self):
        """Test ValidationResult initial state."""
        result = ValidationResult()
        assert result.errors == []
        assert result.warnings == []
        assert result.validation_status == "passed"
        assert result.is_valid() is True
        assert result.requires_manual_review() is False

    def test_add_error(self):
        """Test adding error changes status to failed."""
        result = ValidationResult()
        result.add_error("Test error")
        assert len(result.errors) == 1
        assert result.validation_status == "failed"
        assert result.is_valid() is False
        assert result.requires_manual_review() is True

    def test_add_warning(self):
        """Test adding warning changes status to flagged."""
        result = ValidationResult()
        result.add_warning("Test warning")
        assert len(result.warnings) == 1
        assert result.validation_status == "flagged"
        assert result.is_valid() is True
        assert result.requires_manual_review() is True


class TestCompletenessValidation:
    """Test suite for completeness validation."""

    def test_valid_complete_metrics(self):
        """Test validation passes with all required metrics."""
        metrics = [
            {"metric_type": "revenue", "value": 1000000},
            {"metric_type": "net_income", "value": 100000},
            {"metric_type": "cogs", "value": 600000},
        ]
        extraction_result = {}

        result = Validator.validate_completeness(metrics, extraction_result)

        assert result.is_valid()
        assert len(result.errors) == 0

    def test_missing_required_revenue(self):
        """Test validation fails with missing revenue."""
        metrics = [
            {"metric_type": "net_income", "value": 100000},
        ]
        extraction_result = {}

        result = Validator.validate_completeness(metrics, extraction_result)

        assert not result.is_valid()
        assert any("revenue" in error.lower() for error in result.errors)

    def test_missing_required_net_income(self):
        """Test validation fails with missing net income."""
        metrics = [
            {"metric_type": "revenue", "value": 1000000},
        ]
        extraction_result = {}

        result = Validator.validate_completeness(metrics, extraction_result)

        assert not result.is_valid()
        assert any("net_income" in error.lower() for error in result.errors)

    def test_missing_recommended_metrics(self):
        """Test validation warns for missing recommended metrics."""
        metrics = [
            {"metric_type": "revenue", "value": 1000000},
            {"metric_type": "net_income", "value": 100000},
        ]
        extraction_result = {}

        result = Validator.validate_completeness(metrics, extraction_result)

        assert result.is_valid()
        assert len(result.warnings) > 0
        assert any("cogs" in warning.lower() for warning in result.warnings)

    def test_few_metrics_warning(self):
        """Test validation warns when very few metrics extracted."""
        metrics = [
            {"metric_type": "revenue", "value": 1000000},
            {"metric_type": "net_income", "value": 100000},
        ]
        extraction_result = {}

        result = Validator.validate_completeness(metrics, extraction_result)

        assert result.is_valid()
        assert any("only 2" in warning.lower() for warning in result.warnings)


class TestRangeValidation:
    """Test suite for range validation."""

    def test_valid_positive_revenue(self):
        """Test validation passes for positive revenue."""
        metrics = [
            {
                "metric_type": "revenue",
                "metric_name": "Total Revenue",
                "value": 1000000.0,
            }
        ]

        result = Validator.validate_ranges(metrics)

        assert result.is_valid()
        assert len(result.errors) == 0

    def test_negative_revenue_error(self):
        """Test validation fails for negative revenue."""
        metrics = [
            {
                "metric_type": "revenue",
                "metric_name": "Total Revenue",
                "value": -1000.0,
            }
        ]

        result = Validator.validate_ranges(metrics)

        assert not result.is_valid()
        assert any("must be positive" in error.lower() for error in result.errors)

    def test_zero_revenue_error(self):
        """Test validation fails for zero revenue."""
        metrics = [
            {
                "metric_type": "revenue",
                "metric_name": "Total Revenue",
                "value": 0.0,
            }
        ]

        result = Validator.validate_ranges(metrics)

        assert not result.is_valid()
        assert any("must be positive" in error.lower() for error in result.errors)

    def test_out_of_range_value(self):
        """Test validation fails for values outside reasonable range."""
        metrics = [
            {
                "metric_type": "revenue",
                "metric_name": "Total Revenue",
                "value": 2_000_000_000_000.0,  # $2 trillion (too large)
            }
        ]

        result = Validator.validate_ranges(metrics)

        assert not result.is_valid()
        assert any("outside reasonable range" in error.lower() for error in result.errors)

    def test_unusually_large_value_warning(self):
        """Test validation warns for unusually large values."""
        metrics = [
            {
                "metric_type": "revenue",
                "metric_name": "Total Revenue",
                "value": 150_000_000_000.0,  # $150 billion
            }
        ]

        result = Validator.validate_ranges(metrics)

        assert result.is_valid()
        assert any("unusually large" in warning.lower() for warning in result.warnings)

    def test_unusually_small_value_warning(self):
        """Test validation warns for unusually small values."""
        metrics = [
            {
                "metric_type": "revenue",
                "metric_name": "Total Revenue",
                "value": 500.0,  # $500
            }
        ]

        result = Validator.validate_ranges(metrics)

        assert result.is_valid()
        assert any("unusually small" in warning.lower() for warning in result.warnings)

    def test_negative_net_income_allowed(self):
        """Test validation allows negative net income (losses)."""
        metrics = [
            {
                "metric_type": "net_income",
                "metric_name": "Net Income",
                "value": -50000.0,
            }
        ]

        result = Validator.validate_ranges(metrics)

        assert result.is_valid()
        assert len(result.errors) == 0


class TestConfidenceValidation:
    """Test suite for confidence validation."""

    def test_high_confidence_passes(self):
        """Test validation passes with high confidence."""
        metrics = [
            {
                "metric_name": "Revenue",
                "confidence_score": 0.95,
            }
        ]
        extraction_result = {"ocr_confidence_avg": 0.92}

        result = Validator.validate_confidence(metrics, extraction_result)

        assert result.is_valid()
        assert len(result.warnings) == 0

    def test_low_document_confidence_warning(self):
        """Test validation warns for low document confidence."""
        metrics = []
        extraction_result = {"ocr_confidence_avg": 0.68}

        result = Validator.validate_confidence(metrics, extraction_result)

        assert result.is_valid()
        assert any("below threshold" in warning.lower() for warning in result.warnings)

    def test_critically_low_confidence_error(self):
        """Test validation fails for critically low confidence."""
        metrics = []
        extraction_result = {"ocr_confidence_avg": 0.55}

        result = Validator.validate_confidence(metrics, extraction_result)

        assert not result.is_valid()
        assert any("critically low" in error.lower() for error in result.errors)

    def test_low_metric_confidence_warning(self):
        """Test validation warns for low metric confidence."""
        metrics = [
            {
                "metric_name": "Revenue",
                "confidence_score": 0.65,
            }
        ]
        extraction_result = {"ocr_confidence_avg": 0.85}

        result = Validator.validate_confidence(metrics, extraction_result)

        assert result.is_valid()
        assert any("low confidence" in warning.lower() for warning in result.warnings)


class TestRelationshipValidation:
    """Test suite for relationship validation."""

    def test_valid_gross_profit_calculation(self):
        """Test validation passes when gross profit = revenue - cogs."""
        metrics = [
            {"metric_type": "revenue", "value": 1000000.0},
            {"metric_type": "cogs", "value": 600000.0},
            {"metric_type": "gross_profit", "value": 400000.0},
        ]

        result = Validator.validate_relationships(metrics)

        assert result.is_valid()
        assert len(result.warnings) == 0

    def test_gross_profit_mismatch_warning(self):
        """Test validation warns when gross profit calculation doesn't match."""
        metrics = [
            {"metric_type": "revenue", "value": 1000000.0},
            {"metric_type": "cogs", "value": 600000.0},
            {"metric_type": "gross_profit", "value": 450000.0},  # Should be 400000
        ]

        result = Validator.validate_relationships(metrics)

        assert result.is_valid()
        assert any("mismatch" in warning.lower() for warning in result.warnings)

    def test_negative_gross_profit_error(self):
        """Test validation fails when gross profit is negative but should be positive."""
        metrics = [
            {"metric_type": "revenue", "value": 1000000.0},
            {"metric_type": "cogs", "value": 600000.0},
            {"metric_type": "gross_profit", "value": -100000.0},
        ]

        result = Validator.validate_relationships(metrics)

        assert not result.is_valid()
        assert any("should be positive" in error.lower() for error in result.errors)
