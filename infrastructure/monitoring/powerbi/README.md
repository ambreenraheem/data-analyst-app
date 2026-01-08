# Power BI Dashboard for Document Ingestion Monitoring

This directory contains templates and setup instructions for creating a Power BI dashboard to monitor the Document Ingestion Pipeline.

## Dashboard Overview

The dashboard provides real-time monitoring of:
- **Processing Metrics**: Upload rate, extraction success rate, processing latency
- **Quality Metrics**: OCR confidence distribution, validation failure rate
- **System Health**: Queue depths, error rates, throughput
- **Document Analytics**: Document types processed, metrics extracted per document

## Prerequisites

- Power BI Desktop (latest version)
- Access to Azure Application Insights
- Access to Azure Cosmos DB (for detailed metrics)
- Power BI Pro license (for publishing to Power BI Service)

## Setup Instructions

### Step 1: Install Power BI Desktop

Download and install from: https://powerbi.microsoft.com/desktop/

### Step 2: Configure Data Sources

#### Application Insights Connection

1. Open Power BI Desktop
2. Click "Get Data" → "Azure" → "Azure Application Insights"
3. Enter your Application Insights credentials:
   - Application ID: `<your-app-insights-app-id>`
   - API Key: `<your-api-key>` (generate from Azure Portal)

#### Cosmos DB Connection (Optional - for detailed metrics)

1. Click "Get Data" → "Azure" → "Azure Cosmos DB"
2. Enter connection details:
   - Endpoint: `https://<your-cosmosdb>.documents.azure.com:443/`
   - Key: `<your-cosmos-key>`
   - Database: `financial-advisor`
   - Containers: `extraction-results`, `financial-metrics`, `processing-logs`

### Step 3: Import Dashboard Template

Option A: Use included PBIX template
```bash
# Open the template file
powershell -command "Start-Process 'dashboard-template.pbix'"
```

Option B: Build from scratch using queries below

### Step 4: Configure Refresh Schedule

1. Publish to Power BI Service
2. Go to dataset settings
3. Configure refresh schedule:
   - Frequency: Every 15 minutes (or as needed)
   - Time zone: Your local time zone

---

## Key Visualizations

### 1. Processing Overview (Top Row)

**Metrics Cards:**
- Total Documents Uploaded (Last 24 hours)
- Processing Success Rate (%)
- Average Processing Time (seconds)
- Average OCR Confidence (%)

### 2. Processing Timeline (Middle Row)

**Line Chart: Documents Processed Over Time**
- X-axis: Time (hourly buckets)
- Y-axis: Count of documents
- Legend: Status (Queued, Processing, Completed, Failed)

**Column Chart: Extraction Success vs. Failures**
- X-axis: Hour
- Y-axis: Count
- Series: Success (green), Failed (red)

### 3. Quality Metrics (Bottom Left)

**Gauge: Average OCR Confidence**
- Min: 0.0
- Max: 1.0
- Target: > 0.85
- Zones: Red (< 0.70), Yellow (0.70-0.85), Green (> 0.85)

**Histogram: Confidence Distribution**
- X-axis: Confidence score bins (0.0-0.5, 0.5-0.7, 0.7-0.85, 0.85-1.0)
- Y-axis: Document count

### 4. System Health (Bottom Right)

**Gauge: Queue Depth**
- Min: 0
- Max: 500
- Target: < 100
- Zones: Green (< 100), Yellow (100-300), Red (> 300)

**Donut Chart: Error Distribution**
- Slices: Error types (Extraction Failed, Validation Failed, Timeout, Other)
- Values: Count

---

## Power Query (M) Queries

### Query 1: Processing Metrics

```powerquery
let
    Source = ApplicationInsights.Analytics(
        "https://api.applicationinsights.io/v1",
        "customEvents
        | where timestamp > ago(24h)
        | where name in ('document_uploaded', 'extraction_completed', 'validation_completed', 'processing_failed')
        | project timestamp, name, document_id = tostring(customDimensions.document_id)
        | summarize count() by bin(timestamp, 1h), name"
    )
in
    Source
```

### Query 2: OCR Confidence Over Time

```powerquery
let
    Source = ApplicationInsights.Analytics(
        "https://api.applicationinsights.io/v1",
        "customMetrics
        | where timestamp > ago(7d)
        | where name == 'ocr_confidence'
        | project timestamp, confidence = value
        | summarize avg_confidence = avg(confidence) by bin(timestamp, 1h)"
    )
in
    Source
```

### Query 3: Queue Depth

```powerquery
let
    Source = ApplicationInsights.Analytics(
        "https://api.applicationinsights.io/v1",
        "customMetrics
        | where timestamp > ago(24h)
        | where name == 'queue_depth'
        | project timestamp, queue_name = tostring(customDimensions.queue_name), depth = value
        | summarize max(depth) by bin(timestamp, 5m), queue_name"
    )
in
    Source
```

### Query 4: Error Distribution

```powerquery
let
    Source = ApplicationInsights.Analytics(
        "https://api.applicationinsights.io/v1",
        "exceptions
        | where timestamp > ago(24h)
        | summarize count() by problemId, outerMessage
        | order by count_ desc
        | take 10"
    )
in
    Source
```

### Query 5: Processing Latency (Percentiles)

```powerquery
let
    Source = ApplicationInsights.Analytics(
        "https://api.applicationinsights.io/v1",
        "customMetrics
        | where timestamp > ago(24h)
        | where name == 'processing_duration_seconds'
        | summarize
            p50 = percentile(value, 50),
            p95 = percentile(value, 95),
            p99 = percentile(value, 99),
            avg = avg(value)
        by bin(timestamp, 1h)"
    )
in
    Source
```

---

## DAX Measures

### Measure 1: Processing Success Rate

```dax
Success Rate =
DIVIDE(
    CALCULATE(COUNT('ProcessingMetrics'[document_id]), 'ProcessingMetrics'[status] = "completed"),
    COUNT('ProcessingMetrics'[document_id]),
    0
) * 100
```

### Measure 2: Average Processing Time

```dax
Avg Processing Time (min) =
AVERAGE('ProcessingMetrics'[processing_duration_seconds]) / 60
```

### Measure 3: Documents At Risk (Low Confidence)

```dax
Low Confidence Docs =
CALCULATE(
    COUNT('ExtractionResults'[document_id]),
    'ExtractionResults'[ocr_confidence] < 0.75
)
```

### Measure 4: Validation Failure Rate

```dax
Validation Failure Rate =
DIVIDE(
    CALCULATE(COUNT('ProcessingMetrics'[document_id]), 'ProcessingMetrics'[validation_status] = "failed"),
    COUNT('ProcessingMetrics'[document_id]),
    0
) * 100
```

---

## Dashboard Filters

Add these slicers for interactive filtering:

1. **Date Range**
   - Field: `timestamp`
   - Type: Relative date (Last 24 hours, Last 7 days, Last 30 days)

2. **Document Type**
   - Field: `document_type`
   - Options: PDF, XLSX, All

3. **Status**
   - Field: `status`
   - Options: Queued, Processing, Completed, Failed, All

4. **Confidence Threshold**
   - Field: `ocr_confidence`
   - Type: Slider (0.0 - 1.0)

---

## Alert Thresholds

Configure visual alerts for:

| Metric | Warning | Critical |
|--------|---------|----------|
| Success Rate | < 95% | < 90% |
| Avg Processing Time | > 7 min | > 10 min |
| Queue Depth | > 100 | > 300 |
| OCR Confidence | < 0.80 | < 0.70 |
| Error Rate | > 5% | > 10% |

---

## Publishing to Power BI Service

1. Click "Publish" in Power BI Desktop
2. Select workspace
3. Configure row-level security (if needed)
4. Set up automatic refresh schedule
5. Share dashboard with stakeholders

### Row-Level Security (Optional)

If restricting access by team/department:

```dax
[User Department] = USERPRINCIPALNAME()
```

---

## Embedding in Applications

To embed dashboard in custom applications:

1. Get embed token from Power BI REST API
2. Use Power BI JavaScript SDK
3. Example:

```javascript
const embedConfig = {
    type: 'report',
    id: '<report-id>',
    embedUrl: 'https://app.powerbi.com/reportEmbed',
    accessToken: '<access-token>',
    permissions: 'Read'
};

powerbi.embed(element, embedConfig);
```

---

## Troubleshooting

### Issue: Data Not Refreshing

**Solution:**
- Verify Application Insights API key is valid
- Check firewall allows Power BI IP ranges
- Confirm refresh schedule is active

### Issue: Slow Query Performance

**Solution:**
- Reduce time range in queries (e.g., last 7 days instead of 30 days)
- Use aggregated data instead of raw events
- Enable query folding where possible

### Issue: Missing Metrics

**Solution:**
- Verify custom metrics are being logged in Application Insights
- Check metric names match exactly (case-sensitive)
- Confirm timestamps are within selected date range

---

## Maintenance

- **Weekly**: Review dashboard performance
- **Monthly**: Update thresholds based on trends
- **Quarterly**: Add new visualizations based on user feedback

---

## Resources

- [Power BI Documentation](https://docs.microsoft.com/power-bi/)
- [Application Insights Query Language](https://docs.microsoft.com/azure/azure-monitor/log-query/query-language)
- [Power BI REST API](https://docs.microsoft.com/rest/api/power-bi/)

For questions or issues, contact the development team.
