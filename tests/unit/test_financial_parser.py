"""
Unit tests for financial_parser.py

Tests income statement detection and financial metric extraction.
"""

import pytest
from src.ingestion.services.financial_parser import FinancialParser


class TestIncomeStatementDetection:
    """Test suite for income statement detection."""

    def test_detect_by_title(self):
        """Test detection by income statement title."""
        table = {
            "cells": [
                {"content": "Income Statement", "row_index": 0, "column_index": 0},
                {"content": "Q4 2024", "row_index": 0, "column_index": 1},
            ]
        }

        is_income_statement = FinancialParser.detect_income_statement(table)
        assert is_income_statement is True

    def test_detect_by_profit_and_loss(self):
        """Test detection by P&L title."""
        table = {
            "cells": [
                {"content": "Profit and Loss", "row_index": 0, "column_index": 0},
            ]
        }

        is_income_statement = FinancialParser.detect_income_statement(table)
        assert is_income_statement is True

    def test_detect_by_line_items(self):
        """Test detection by presence of revenue and net income."""
        table = {
            "cells": [
                {"content": "Revenue", "row_index": 0, "column_index": 0},
                {"content": "10000000", "row_index": 0, "column_index": 1},
                {"content": "Operating Expenses", "row_index": 1, "column_index": 0},
                {"content": "5000000", "row_index": 1, "column_index": 1},
                {"content": "Net Income", "row_index": 2, "column_index": 0},
                {"content": "3000000", "row_index": 2, "column_index": 1},
            ]
        }

        is_income_statement = FinancialParser.detect_income_statement(table)
        assert is_income_statement is True

    def test_not_income_statement(self):
        """Test detection returns False for non-income statement tables."""
        table = {
            "cells": [
                {"content": "Employee Directory", "row_index": 0, "column_index": 0},
                {"content": "Name", "row_index": 1, "column_index": 0},
                {"content": "Department", "row_index": 1, "column_index": 1},
            ]
        }

        is_income_statement = FinancialParser.detect_income_statement(table)
        assert is_income_statement is False


class TestReportingPeriodIdentification:
    """Test suite for reporting period identification."""

    def test_identify_quarterly_period(self):
        """Test identifying quarterly period (Q4 2024)."""
        table = {
            "cells": [
                {"content": "Income Statement", "row_index": 0, "column_index": 0},
                {"content": "Q4 2024", "row_index": 0, "column_index": 1},
            ]
        }

        period = FinancialParser.identify_reporting_period(table)
        assert period == "Q4 2024"

    def test_identify_fiscal_year(self):
        """Test identifying fiscal year (FY 2024)."""
        table = {
            "cells": [
                {"content": "Annual Report", "row_index": 0, "column_index": 0},
                {"content": "FY 2024", "row_index": 0, "column_index": 1},
            ]
        }

        period = FinancialParser.identify_reporting_period(table)
        assert period == "FY 2024"

    def test_identify_calendar_year(self):
        """Test identifying calendar year (2024)."""
        table = {
            "cells": [
                {"content": "Financial Summary", "row_index": 0, "column_index": 0},
                {"content": "Year ending 2024", "row_index": 0, "column_index": 1},
            ]
        }

        period = FinancialParser.identify_reporting_period(table)
        assert "2024" in period

    def test_identify_specific_date(self):
        """Test identifying specific date period."""
        table = {
            "cells": [
                {"content": "Financial Position as of", "row_index": 0, "column_index": 0},
                {"content": "December 31, 2024", "row_index": 0, "column_index": 1},
            ]
        }

        period = FinancialParser.identify_reporting_period(table)
        assert "December 31, 2024" in period

    def test_no_period_found(self):
        """Test returns None when no period found."""
        table = {
            "cells": [
                {"content": "Revenue", "row_index": 0, "column_index": 0},
                {"content": "Amount", "row_index": 0, "column_index": 1},
            ]
        }

        period = FinancialParser.identify_reporting_period(table)
        assert period is None


class TestLooksLikeNumber:
    """Test suite for _looks_like_number helper."""

    def test_simple_number(self):
        """Test simple number is recognized."""
        assert FinancialParser._looks_like_number("12345") is True

    def test_formatted_number(self):
        """Test formatted number with commas."""
        assert FinancialParser._looks_like_number("1,234,567") is True

    def test_currency_number(self):
        """Test number with currency symbol."""
        assert FinancialParser._looks_like_number("$10,000") is True

    def test_negative_number(self):
        """Test negative number in parentheses."""
        assert FinancialParser._looks_like_number("(5,000)") is True

    def test_text_only(self):
        """Test text-only string is not recognized as number."""
        assert FinancialParser._looks_like_number("Total Revenue") is False

    def test_empty_string(self):
        """Test empty string is not recognized as number."""
        assert FinancialParser._looks_like_number("") is False
