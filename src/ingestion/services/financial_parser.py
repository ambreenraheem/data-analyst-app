"""
Financial parser service.

Identifies financial statement types (income statement, balance sheet, etc.)
and extracts specific financial line items with semantic understanding.

Supports Constitution Principle I (Data-First with precise metric identification).
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from src.ingestion.utils.number_parser import NumberParser


logger = logging.getLogger("financial_parser")
logger.setLevel(logging.INFO)


class FinancialParser:
    """Parser for identifying and extracting financial statement data."""

    # Income statement keywords (in order of preference)
    INCOME_STATEMENT_KEYWORDS = [
        "income statement", "statement of income", "profit and loss", "p&l",
        "statement of operations", "operating statement", "earnings statement"
    ]

    # Line item patterns for income statements
    REVENUE_PATTERNS = [
        r"total\s+revenue", r"net\s+revenue", r"revenue", r"sales",
        r"total\s+sales", r"net\s+sales", r"operating\s+revenue"
    ]

    COGS_PATTERNS = [
        r"cost\s+of\s+goods\s+sold", r"cogs", r"cost\s+of\s+revenue",
        r"cost\s+of\s+sales", r"direct\s+costs"
    ]

    GROSS_PROFIT_PATTERNS = [
        r"gross\s+profit", r"gross\s+income", r"gross\s+margin"
    ]

    OPERATING_EXPENSES_PATTERNS = [
        r"operating\s+expenses", r"opex", r"total\s+operating\s+expenses",
        r"selling.*general.*administrative", r"sg&a", r"sga"
    ]

    OPERATING_INCOME_PATTERNS = [
        r"operating\s+income", r"operating\s+profit", r"ebit",
        r"earnings\s+before\s+interest\s+and\s+tax"
    ]

    EBITDA_PATTERNS = [
        r"ebitda", r"earnings\s+before\s+interest.*tax.*depreciation.*amortization"
    ]

    NET_INCOME_PATTERNS = [
        r"net\s+income", r"net\s+profit", r"net\s+earnings",
        r"profit\s+for\s+the\s+period", r"bottom\s+line"
    ]

    @staticmethod
    def detect_income_statement(table: Dict[str, Any]) -> bool:
        """
        Detect if a table contains an income statement.

        Args:
            table: Table dictionary with cells

        Returns:
            True if table appears to be an income statement
        """
        # Collect all text content from table
        content_text = " ".join(
            [cell.get("content", "").lower() for cell in table.get("cells", [])]
        )

        # Check for income statement keywords
        for keyword in FinancialParser.INCOME_STATEMENT_KEYWORDS:
            if keyword in content_text:
                logger.info(f"Detected income statement (keyword: {keyword})")
                return True

        # Check for presence of key line items
        has_revenue = any(
            re.search(pattern, content_text)
            for pattern in FinancialParser.REVENUE_PATTERNS
        )
        has_expenses = any(
            re.search(pattern, content_text)
            for pattern in FinancialParser.OPERATING_EXPENSES_PATTERNS
        )
        has_net_income = any(
            re.search(pattern, content_text)
            for pattern in FinancialParser.NET_INCOME_PATTERNS
        )

        if has_revenue and (has_expenses or has_net_income):
            logger.info("Detected income statement (based on line items)")
            return True

        return False

    @staticmethod
    def extract_income_statement_metrics(
        table: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract income statement line items from a table.

        Args:
            table: Table dictionary with cells

        Returns:
            List of extracted metrics with values and source references
        """
        metrics = []

        # Define metric definitions
        metric_definitions = [
            ("revenue", "Total Revenue", FinancialParser.REVENUE_PATTERNS),
            ("cogs", "Cost of Goods Sold", FinancialParser.COGS_PATTERNS),
            ("gross_profit", "Gross Profit", FinancialParser.GROSS_PROFIT_PATTERNS),
            ("operating_expenses", "Operating Expenses", FinancialParser.OPERATING_EXPENSES_PATTERNS),
            ("operating_income", "Operating Income", FinancialParser.OPERATING_INCOME_PATTERNS),
            ("ebitda", "EBITDA", FinancialParser.EBITDA_PATTERNS),
            ("net_income", "Net Income", FinancialParser.NET_INCOME_PATTERNS),
        ]

        # Extract each metric type
        for metric_type, metric_name, patterns in metric_definitions:
            extracted = FinancialParser._extract_metric_from_table(
                table=table,
                metric_type=metric_type,
                metric_name=metric_name,
                patterns=patterns
            )
            if extracted:
                metrics.extend(extracted)

        logger.info(f"Extracted {len(metrics)} income statement metrics from table {table.get('table_id')}")
        return metrics

    @staticmethod
    def _extract_metric_from_table(
        table: Dict[str, Any],
        metric_type: str,
        metric_name: str,
        patterns: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Extract a specific metric from a table.

        Args:
            table: Table dictionary
            metric_type: Type identifier (e.g., "revenue")
            metric_name: Display name (e.g., "Total Revenue")
            patterns: List of regex patterns to match

        Returns:
            List of extracted metric dictionaries
        """
        cells = table.get("cells", [])
        metrics = []

        # Search for label cells matching patterns
        for cell in cells:
            content = cell.get("content", "").lower().strip()

            # Check if this cell contains the metric label
            for pattern in patterns:
                if re.search(pattern, content):
                    # Found a label - now look for the value in adjacent cells
                    value_cells = FinancialParser._find_value_cells(
                        cells=cells,
                        label_cell=cell,
                        table=table
                    )

                    for value_cell in value_cells:
                        value_text = value_cell.get("content", "")
                        parsed_value, currency = NumberParser.parse_financial_number(value_text)

                        if parsed_value is not None:
                            metrics.append({
                                "metric_type": metric_type,
                                "metric_name": metric_name,
                                "value": parsed_value,
                                "currency": currency or "USD",
                                "label_cell": cell,
                                "value_cell": value_cell,
                                "confidence": value_cell.get("confidence", 1.0),
                            })

                    break  # Found a match, stop searching patterns

        return metrics

    @staticmethod
    def _find_value_cells(
        cells: List[Dict[str, Any]],
        label_cell: Dict[str, Any],
        table: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Find value cells associated with a label cell.

        Searches in the same row (to the right) and adjacent columns.

        Args:
            cells: All cells in the table
            label_cell: Cell containing the metric label
            table: Table dictionary

        Returns:
            List of potential value cells
        """
        label_row = label_cell.get("row_index")
        label_col = label_cell.get("column_index")

        value_cells = []

        # Search in the same row (columns to the right)
        for cell in cells:
            cell_row = cell.get("row_index")
            cell_col = cell.get("column_index")

            # Same row, column to the right
            if cell_row == label_row and cell_col > label_col:
                content = cell.get("content", "").strip()
                # Check if it looks like a number
                if content and FinancialParser._looks_like_number(content):
                    value_cells.append(cell)

        return value_cells

    @staticmethod
    def _looks_like_number(text: str) -> bool:
        """
        Check if text looks like a financial number.

        Args:
            text: Text to check

        Returns:
            True if text appears to be a number
        """
        # Remove common number characters
        cleaned = text.replace(",", "").replace(".", "").replace("$", "").replace("(", "").replace(")", "").replace("-", "").replace(" ", "")

        # Check if remaining characters are mostly digits
        if not cleaned:
            return False

        digit_count = sum(c.isdigit() for c in cleaned)
        return digit_count / len(cleaned) > 0.5

    @staticmethod
    def identify_reporting_period(table: Dict[str, Any]) -> Optional[str]:
        """
        Identify the reporting period from table content.

        Looks for patterns like "Q4 2024", "FY 2024", "December 31, 2024".

        Args:
            table: Table dictionary

        Returns:
            Reporting period string or None
        """
        # Collect text from first few rows (headers)
        header_cells = [
            cell for cell in table.get("cells", [])
            if cell.get("row_index", 999) < 3
        ]
        header_text = " ".join([cell.get("content", "") for cell in header_cells])

        # Patterns for reporting periods
        period_patterns = [
            r"Q[1-4]\s+20\d{2}",  # Q4 2024
            r"FY\s*20\d{2}",  # FY 2024
            r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+20\d{2}",  # December 31, 2024
            r"20\d{2}",  # 2024
        ]

        for pattern in period_patterns:
            match = re.search(pattern, header_text, re.IGNORECASE)
            if match:
                return match.group(0)

        return None


# Global parser instance
financial_parser = FinancialParser()
