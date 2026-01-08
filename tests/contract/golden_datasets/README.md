# Golden Dataset Documentation

This directory contains golden dataset files used for contract testing and validation.

## Purpose

Golden datasets provide:
1. **Known-good input documents** with predictable financial data
2. **Expected extraction outputs** for validating end-to-end processing
3. **Regression testing** to ensure consistency across code changes
4. **Performance benchmarks** for extraction and validation

## Files

### Input Documents

#### `sample_income_statement.pdf`
- **Company**: TechCorp Inc.
- **Period**: Q4 2024
- **Format**: PDF with table layout
- **Content**: Standard income statement with:
  - Total Revenue: $15,750,000
  - Cost of Goods Sold: $6,300,000
  - Gross Profit: $9,450,000
  - Operating Expenses: $5,500,000
  - EBITDA: $3,950,000
  - Depreciation & Amortization: $850,000
  - Operating Income: $3,100,000
  - Interest Expense: $200,000
  - Tax Expense: $580,000
  - Net Income: $2,320,000

**To generate this PDF:**
```bash
# Option 1: Use a tool like wkhtmltopdf
wkhtmltopdf sample_income_statement.html sample_income_statement.pdf

# Option 2: Export from Excel/Google Sheets as PDF
# Create spreadsheet with above data, then File > Download > PDF
```

#### `sample_excel_report.xlsx`
- **Company**: RetailCo LLC
- **Period**: FY 2024
- **Format**: Excel with multiple sheets
- **Sheets**:
  - **Income Statement**: Standard P&L
  - **Balance Sheet**: Assets, Liabilities, Equity
  - **Cash Flow**: Operating, Investing, Financing activities

**Income Statement Data** (Sheet 1):
- Revenue: $42,500,000
- COGS: $25,500,000
- Gross Profit: $17,000,000
- Operating Expenses: $12,000,000
- Operating Income: $5,000,000
- Net Income: $3,400,000

**To generate this Excel file:**
```bash
# Use Python script to create Excel with openpyxl
python scripts/generate_golden_excel.py
```

### Expected Outputs

#### `expected_outputs.json`
Contains expected extraction results for both sample documents:
- Extracted metrics with values, types, periods
- Expected confidence scores
- Source references (pages, tables, cells)
- Validation status expectations

## Usage in Tests

```python
# Example: Load golden dataset in integration test
import json
from pathlib import Path

GOLDEN_DIR = Path(__file__).parent / "golden_datasets"

def test_pdf_extraction_matches_golden():
    # Upload sample PDF
    with open(GOLDEN_DIR / "sample_income_statement.pdf", "rb") as f:
        response = client.post("/api/v1/documents/upload", files={"file": f})

    # Load expected output
    with open(GOLDEN_DIR / "expected_outputs.json") as f:
        expected = json.load(f)["sample_income_statement"]

    # Compare actual vs expected
    assert_metrics_match(actual_metrics, expected["metrics"])
```

## Updating Golden Datasets

When to update:
1. **Breaking changes** to extraction logic or data models
2. **Improved accuracy** that changes expected outputs
3. **New metric types** added to system

Process:
1. Update input documents if needed
2. Run extraction manually and review outputs
3. Update `expected_outputs.json` with new baseline
4. Document changes in git commit message
5. Run all contract tests to verify

## Maintenance

- **Review quarterly**: Ensure datasets reflect current business requirements
- **Version control**: All changes must be committed with explanation
- **Audit trail**: Document why expected outputs changed
