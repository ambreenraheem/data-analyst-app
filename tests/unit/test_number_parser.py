"""
Unit tests for number_parser.py

Tests financial number parsing including currency symbols,
thousands separators, magnitude abbreviations, and negative numbers.
"""

import pytest
from src.ingestion.utils.number_parser import NumberParser


class TestNumberParser:
    """Test suite for NumberParser class."""

    def test_parse_simple_number(self):
        """Test parsing simple numeric values."""
        value, currency = NumberParser.parse_financial_number("12345.67")
        assert value == 12345.67
        assert currency is None

    def test_parse_us_format_with_commas(self):
        """Test parsing US format numbers with thousands separators."""
        value, currency = NumberParser.parse_financial_number("1,234,567.89")
        assert value == 1234567.89
        assert currency is None

    def test_parse_european_format(self):
        """Test parsing European format numbers (comma as decimal)."""
        value, currency = NumberParser.parse_financial_number("1.234.567,89")
        assert value == 1234567.89
        assert currency is None

    def test_parse_with_dollar_sign(self):
        """Test parsing numbers with dollar sign."""
        value, currency = NumberParser.parse_financial_number("$10,000.00")
        assert value == 10000.0
        assert currency == "USD"

    def test_parse_with_euro_sign(self):
        """Test parsing numbers with euro sign."""
        value, currency = NumberParser.parse_financial_number("€1.234,56")
        assert value == 1234.56
        assert currency == "EUR"

    def test_parse_negative_parentheses(self):
        """Test parsing negative numbers in parentheses notation."""
        value, currency = NumberParser.parse_financial_number("(5,000)")
        assert value == -5000.0
        assert currency is None

    def test_parse_magnitude_k(self):
        """Test parsing numbers with K (thousands) suffix."""
        value, currency = NumberParser.parse_financial_number("10K")
        assert value == 10000.0

        value, currency = NumberParser.parse_financial_number("5.5K")
        assert value == 5500.0

    def test_parse_magnitude_m(self):
        """Test parsing numbers with M (millions) suffix."""
        value, currency = NumberParser.parse_financial_number("10M")
        assert value == 10000000.0

        value, currency = NumberParser.parse_financial_number("1.5M")
        assert value == 1500000.0

    def test_parse_magnitude_b(self):
        """Test parsing numbers with B (billions) suffix."""
        value, currency = NumberParser.parse_financial_number("10B")
        assert value == 10000000000.0

        value, currency = NumberParser.parse_financial_number("2.5B")
        assert value == 2500000000.0

    def test_parse_magnitude_million_word(self):
        """Test parsing numbers with 'million' word."""
        value, currency = NumberParser.parse_financial_number("10 million")
        assert value == 10000000.0

    def test_parse_complex_currency_format(self):
        """Test parsing complex formats with currency and magnitude."""
        value, currency = NumberParser.parse_financial_number("$10.5M")
        assert value == 10500000.0
        assert currency == "USD"

    def test_parse_negative_with_currency(self):
        """Test parsing negative numbers with currency symbols."""
        value, currency = NumberParser.parse_financial_number("($1,234.56)")
        assert value == -1234.56
        assert currency == "USD"

    def test_parse_empty_string(self):
        """Test parsing empty string returns None."""
        value, currency = NumberParser.parse_financial_number("")
        assert value is None
        assert currency is None

    def test_parse_invalid_text(self):
        """Test parsing invalid text returns None."""
        value, currency = NumberParser.parse_financial_number("not a number")
        assert value is None
        assert currency is None

    def test_parse_none(self):
        """Test parsing None returns None."""
        value, currency = NumberParser.parse_financial_number(None)
        assert value is None
        assert currency is None

    def test_format_number_simple(self):
        """Test formatting simple numbers."""
        formatted = NumberParser.format_number(12345.67)
        assert formatted == "12,345.67"

    def test_format_number_with_currency(self):
        """Test formatting numbers with currency."""
        formatted = NumberParser.format_number(12345.67, "USD")
        assert formatted == "$12,345.67"

    def test_detect_currency_pound(self):
        """Test detecting British pound currency."""
        value, currency = NumberParser.parse_financial_number("£500")
        assert value == 500.0
        assert currency == "GBP"

    def test_detect_currency_yen(self):
        """Test detecting Japanese yen currency."""
        value, currency = NumberParser.parse_financial_number("¥1000")
        assert value == 1000.0
        assert currency == "JPY"
