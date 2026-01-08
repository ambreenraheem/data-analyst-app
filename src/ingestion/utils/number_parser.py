"""
Number parser for financial values.

Handles various financial number formats including currency symbols,
thousands separators, negative numbers, and magnitude abbreviations (K/M/B).

Supports Constitution Principle I (Data-First) by parsing financial values
from extracted text with high accuracy.
"""

import re
from typing import Optional, Tuple


class NumberParser:
    """Parser for financial number formats."""

    # Currency symbols to strip
    CURRENCY_SYMBOLS = ["$", "€", "£", "¥", "₹", "USD", "EUR", "GBP", "JPY", "INR"]

    # Magnitude multipliers
    MAGNITUDE_MULTIPLIERS = {
        "K": 1_000,
        "M": 1_000_000,
        "B": 1_000_000_000,
        "T": 1_000_000_000_000,
        "THOUSAND": 1_000,
        "MILLION": 1_000_000,
        "BILLION": 1_000_000_000,
        "TRILLION": 1_000_000_000_000,
    }

    @staticmethod
    def parse_financial_number(text: str) -> Tuple[Optional[float], Optional[str]]:
        """
        Parse a financial number from text.

        Handles formats:
        - $10,000.00 or €10.000,00
        - (5,000) for negatives
        - 10M, 5.5B, 1.2K for magnitudes
        - 10 million, 5 billion
        - Plain numbers: 12345.67

        Args:
            text: Text containing a financial number

        Returns:
            Tuple of (parsed_value, detected_currency) or (None, None) if parsing fails

        Examples:
            >>> NumberParser.parse_financial_number("$10,000.00")
            (10000.0, "USD")
            >>> NumberParser.parse_financial_number("(5,000)")
            (-5000.0, None)
            >>> NumberParser.parse_financial_number("10.5M")
            (10500000.0, None)
            >>> NumberParser.parse_financial_number("€1.234,56")
            (1234.56, "EUR")
        """
        if not text or not isinstance(text, str):
            return None, None

        # Clean and normalize text
        text = text.strip()
        original_text = text

        # Detect currency
        currency = NumberParser._detect_currency(text)

        # Remove currency symbols
        for symbol in NumberParser.CURRENCY_SYMBOLS:
            text = text.replace(symbol, "")

        # Strip whitespace after removing currency
        text = text.strip()

        # Check if negative (parentheses notation)
        is_negative = text.startswith("(") and text.endswith(")")
        if is_negative:
            text = text[1:-1].strip()

        # Check for magnitude suffix (K, M, B, T)
        magnitude_multiplier = 1.0
        text_upper = text.upper()

        for suffix, multiplier in NumberParser.MAGNITUDE_MULTIPLIERS.items():
            if text_upper.endswith(suffix):
                magnitude_multiplier = multiplier
                text = text[: -len(suffix)].strip()
                break

        # Remove thousands separators (commas or periods depending on locale)
        # Strategy: If there are both commas and periods, identify which is decimal
        comma_count = text.count(",")
        period_count = text.count(".")

        if comma_count > 0 and period_count > 0:
            # Both present - determine which is decimal separator
            last_comma_pos = text.rfind(",")
            last_period_pos = text.rfind(".")

            if last_comma_pos > last_period_pos:
                # Comma is decimal separator (European format: 1.234,56)
                text = text.replace(".", "").replace(",", ".")
            else:
                # Period is decimal separator (US format: 1,234.56)
                text = text.replace(",", "")
        elif comma_count > 0:
            # Only commas - could be thousands separator or decimal
            last_comma_pos = text.rfind(",")
            chars_after_comma = len(text) - last_comma_pos - 1

            if chars_after_comma == 2:
                # Likely decimal separator (European format)
                text = text.replace(",", ".", 1).replace(",", "")
            else:
                # Likely thousands separator
                text = text.replace(",", "")
        # If only periods, assume decimal separator (handled by float conversion)

        # Try to parse as float
        try:
            value = float(text) * magnitude_multiplier

            if is_negative:
                value = -value

            return value, currency

        except ValueError:
            # Failed to parse
            return None, None

    @staticmethod
    def _detect_currency(text: str) -> Optional[str]:
        """
        Detect currency from text.

        Args:
            text: Text potentially containing currency symbol

        Returns:
            ISO currency code (USD, EUR, GBP, etc.) or None
        """
        currency_map = {
            "$": "USD",
            "€": "EUR",
            "£": "GBP",
            "¥": "JPY",
            "₹": "INR",
            "USD": "USD",
            "EUR": "EUR",
            "GBP": "GBP",
            "JPY": "JPY",
            "INR": "INR",
        }

        for symbol, code in currency_map.items():
            if symbol in text:
                return code

        return None

    @staticmethod
    def format_number(value: float, currency: Optional[str] = None) -> str:
        """
        Format a number for display.

        Args:
            value: Numeric value
            currency: Optional currency code

        Returns:
            Formatted string (e.g., "$10,000.00" or "10,000.00")
        """
        # Format with thousands separator
        formatted = f"{value:,.2f}"

        # Add currency symbol if provided
        if currency:
            currency_symbols = {
                "USD": "$",
                "EUR": "€",
                "GBP": "£",
                "JPY": "¥",
                "INR": "₹",
            }
            symbol = currency_symbols.get(currency, currency + " ")
            formatted = f"{symbol}{formatted}"

        return formatted


# Convenience function for backward compatibility
def parse_financial_number(text: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Parse a financial number from text.

    Args:
        text: Text containing a financial number

    Returns:
        Tuple of (parsed_value, detected_currency) or (None, None) if parsing fails
    """
    return NumberParser.parse_financial_number(text)
