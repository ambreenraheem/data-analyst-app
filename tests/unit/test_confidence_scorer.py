"""
Unit tests for confidence_scorer.py

Tests OCR confidence scoring and quality assessment.
"""

import pytest
from src.ingestion.utils.confidence_scorer import ConfidenceScorer


class TestConfidenceScorer:
    """Test suite for ConfidenceScorer class."""

    def test_calculate_document_confidence(self):
        """Test calculating document-level confidence."""
        tables = [
            {
                "cells": [
                    {"confidence": 0.95},
                    {"confidence": 0.90},
                    {"confidence": 0.85},
                ]
            },
            {
                "cells": [
                    {"confidence": 0.92},
                    {"confidence": 0.88},
                ]
            },
        ]

        avg_confidence = ConfidenceScorer.calculate_document_confidence(tables)

        assert 0.89 <= avg_confidence <= 0.91  # Average should be ~0.90

    def test_calculate_table_confidence(self):
        """Test calculating table-level confidence."""
        table = {
            "cells": [
                {"confidence": 0.95},
                {"confidence": 0.90},
                {"confidence": 0.85},
            ]
        }

        avg_confidence = ConfidenceScorer.calculate_table_confidence(table)

        assert avg_confidence == 0.90

    def test_calculate_cell_confidence(self):
        """Test getting cell-level confidence."""
        cell = {"confidence": 0.92}

        confidence = ConfidenceScorer.calculate_cell_confidence(cell)

        assert confidence == 0.92

    def test_assess_quality_high(self):
        """Test quality assessment for high confidence."""
        quality = ConfidenceScorer.assess_quality(0.95)
        assert quality == "high"

    def test_assess_quality_medium(self):
        """Test quality assessment for medium confidence."""
        quality = ConfidenceScorer.assess_quality(0.75)
        assert quality == "medium"

    def test_assess_quality_low(self):
        """Test quality assessment for low confidence."""
        quality = ConfidenceScorer.assess_quality(0.65)
        assert quality == "low"

    def test_calculate_metric_confidence_success(self):
        """Test calculating metric confidence with successful parsing."""
        confidence = ConfidenceScorer.calculate_metric_confidence(
            extracted_value="$10,000",
            cell_confidence=0.90,
            parsing_success=True
        )

        assert confidence == 0.90

    def test_calculate_metric_confidence_parse_failure(self):
        """Test calculating metric confidence with failed parsing."""
        confidence = ConfidenceScorer.calculate_metric_confidence(
            extracted_value="???",
            cell_confidence=0.90,
            parsing_success=False
        )

        assert confidence == 0.45  # 50% penalty for parse failure

    def test_calculate_metric_confidence_short_value(self):
        """Test calculating metric confidence with very short value."""
        confidence = ConfidenceScorer.calculate_metric_confidence(
            extracted_value="1",
            cell_confidence=0.90,
            parsing_success=True
        )

        assert confidence == 0.63  # 30% penalty for short value

    def test_get_confidence_statistics(self):
        """Test getting confidence statistics."""
        confidences = [0.85, 0.90, 0.95, 0.80, 0.92]

        stats = ConfidenceScorer.get_confidence_statistics(confidences)

        assert stats["min"] == 0.80
        assert stats["max"] == 0.95
        assert 0.88 <= stats["mean"] <= 0.89
        assert stats["median"] == 0.90
        assert stats["count"] == 5

    def test_get_confidence_statistics_empty(self):
        """Test getting statistics for empty list."""
        stats = ConfidenceScorer.get_confidence_statistics([])

        assert stats["min"] == 0.0
        assert stats["max"] == 0.0
        assert stats["mean"] == 0.0
        assert stats["median"] == 0.0
        assert stats["count"] == 0

    def test_should_flag_for_review_low_confidence(self):
        """Test flagging for review with low confidence."""
        should_flag = ConfidenceScorer.should_flag_for_review(0.65)
        assert should_flag is True

    def test_should_flag_for_review_high_confidence(self):
        """Test not flagging for review with high confidence."""
        should_flag = ConfidenceScorer.should_flag_for_review(0.95)
        assert should_flag is False

    def test_get_confidence_label_very_high(self):
        """Test confidence label for very high confidence."""
        label = ConfidenceScorer.get_confidence_label(0.96)
        assert label == "Very High"

    def test_get_confidence_label_high(self):
        """Test confidence label for high confidence."""
        label = ConfidenceScorer.get_confidence_label(0.88)
        assert label == "High"

    def test_get_confidence_label_medium(self):
        """Test confidence label for medium confidence."""
        label = ConfidenceScorer.get_confidence_label(0.75)
        assert label == "Medium"

    def test_get_confidence_label_low(self):
        """Test confidence label for low confidence."""
        label = ConfidenceScorer.get_confidence_label(0.60)
        assert label == "Low"

    def test_get_confidence_label_very_low(self):
        """Test confidence label for very low confidence."""
        label = ConfidenceScorer.get_confidence_label(0.40)
        assert label == "Very Low"
