"""Generate golden dataset PDF file for contract testing."""

from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

def create_sample_pdf():
    """Create sample_income_statement.pdf with financial data."""
    output_path = Path(__file__).parent.parent / "tests" / "contract" / "golden_datasets" / "sample_income_statement.pdf"

    # Create PDF document
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    story = []

    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=12,
        alignment=TA_CENTER
    )
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#4a4a4a'),
        spaceAfter=20,
        alignment=TA_CENTER
    )

    # Add title
    story.append(Paragraph("TechCorp Inc.", title_style))
    story.append(Paragraph("Income Statement", subtitle_style))
    story.append(Paragraph("For the Quarter Ended December 31, 2024", styles['Normal']))
    story.append(Spacer(1, 0.3 * inch))

    # Financial data (matching expected_outputs.json)
    data = [
        ['Line Item', 'Amount (USD)'],
        ['Total Revenue', '$15,750,000'],
        ['Cost of Goods Sold', '$6,300,000'],
        ['Gross Profit', '$9,450,000'],
        ['Operating Expenses', '$5,500,000'],
        ['EBITDA', '$3,950,000'],
        ['Depreciation & Amortization', '$850,000'],
        ['Operating Income', '$3,100,000'],
        ['Interest Expense', '$200,000'],
        ['Tax Expense', '$580,000'],
        ['Net Income', '$2,320,000'],
    ]

    # Create table
    table = Table(data, colWidths=[3.5 * inch, 2 * inch])

    # Style the table
    table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a90e2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),

        # Data rows
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),

        # Bold important rows (Gross Profit, EBITDA, Operating Income, Net Income)
        ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'),  # Gross Profit
        ('FONTNAME', (0, 5), (-1, 5), 'Helvetica-Bold'),  # EBITDA
        ('FONTNAME', (0, 7), (-1, 7), 'Helvetica-Bold'),  # Operating Income
        ('FONTNAME', (0, 10), (-1, 10), 'Helvetica-Bold'), # Net Income

        # Grid
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#4a90e2')),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
    ]))

    story.append(table)
    story.append(Spacer(1, 0.5 * inch))

    # Add footer notes
    notes_style = ParagraphStyle(
        'Notes',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#666666'),
        spaceAfter=6
    )
    story.append(Paragraph("Notes:", styles['Heading3']))
    story.append(Paragraph("1. All amounts are in US Dollars", notes_style))
    story.append(Paragraph("2. This is a sample financial statement for testing purposes", notes_style))
    story.append(Paragraph("3. EBITDA = Earnings Before Interest, Taxes, Depreciation, and Amortization", notes_style))

    # Build PDF
    doc.build(story)
    print(f"Created: {output_path}")

if __name__ == "__main__":
    create_sample_pdf()
