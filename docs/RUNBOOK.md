# Operations Runbook

Operational procedures for the Financial Insight & Risk Advisor Agent - Document Ingestion Pipeline

## Table of Contents

1. [System Overview](#system-overview)
2. [Common Operations](#common-operations)
3. [Troubleshooting](#troubleshooting)
4. [Monitoring & Alerts](#monitoring--alerts)
5. [Disaster Recovery](#disaster-recovery)

## System Overview

### Architecture Components

- **Azure Functions**: Serverless processing (Python 3.11)
- **Azure Blob Storage**: Raw document storage (7-year retention)
- **Azure Cosmos DB**: Structured data storage
- **Azure Service Bus**: Message queueing
- **Azure Document Intelligence**: OCR and table extraction
- **Application Insights**: Monitoring and telemetry

### Processing Pipeline

```
Upload → Ingestion → Extraction → Validation → Results
   ↓         ↓            ↓            ↓
 Blob    Service Bus  Service Bus  Service Bus
Storage    Queue        Queue        Queue
```

## Common Operations

### 1. Monitor Document Processing

**Check overall processing metrics:**

```bash
# Query Application Insights for processing metrics
az monitor app-insights metrics show \
  --app your-app-insights \
  --metric customMetrics/document_uploaded \
  --aggregation count \
  --interval PT1H
```

**Check queue depths:**

```bash
# Check Service Bus queue depths
az servicebus queue show \
  --resource-group your-rg \
  --namespace-name your-sb \
  --name extraction-queue \
  --query messageCount
```

### 2. Re-ingest Failed Documents

**Find failed documents:**

```sql
-- Query Cosmos DB for failed documents
SELECT c.document_id, c.event_data.error
FROM c
WHERE c.event_type = "failed"
AND c.event_timestamp > "2024-01-01T00:00:00Z"
ORDER BY c.event_timestamp DESC
```

**Retry via API:**

```bash
# Retry with enhanced OCR
curl -X POST https://your-app.azurewebsites.net/api/v1/documents/{doc_id}/retry \
  -H "x-functions-key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"enhanced_ocr": true}'
```

**Bulk retry (PowerShell):**

```powershell
# Bulk retry failed documents
$failedDocs = @("doc-123", "doc-456", "doc-789")
foreach ($docId in $failedDocs) {
    Invoke-RestMethod `
        -Method Post `
        -Uri "https://your-app.azurewebsites.net/api/v1/documents/$docId/retry" `
        -Headers @{"x-functions-key"="YOUR_KEY"} `
        -ContentType "application/json" `
        -Body '{"enhanced_ocr": true}'
}
```

### 3. Adjust Confidence Thresholds

**Update environment variables:**

```bash
# Update Function App settings
az functionapp config appsettings set \
  --name your-function-app \
  --resource-group your-rg \
  --settings \
    OCR_CONFIDENCE_THRESHOLD_DOCUMENT=0.80 \
    OCR_CONFIDENCE_THRESHOLD_METRIC=0.75
```

**Restart Functions:**

```bash
# Restart to apply new settings
az functionapp restart \
  --name your-function-app \
  --resource-group your-rg
```

### 4. Clear Processing Queues

**Purge dead-letter queues:**

```bash
# View dead-letter queue messages
az servicebus queue show \
  --resource-group your-rg \
  --namespace-name your-sb \
  --name extraction-queue/$DeadLetterQueue \
  --query messageCount

# Purge dead-letter queue
az servicebus queue purge \
  --resource-group your-rg \
  --namespace-name your-sb \
  --name extraction-queue/$DeadLetterQueue
```

### 5. Manual Document Deletion

**Delete document and associated data:**

```bash
# 1. Delete from Blob Storage
az storage blob delete \
  --account-name your-storage \
  --container-name financial-documents \
  --name 2024/01/doc-abc123.pdf

# 2. Delete from Cosmos DB (extraction results)
az cosmosdb sql item delete \
  --account-name your-cosmosdb \
  --database-name financial-insights \
  --container-name extraction-results \
  --partition-key doc-abc123 \
  --id extraction-xyz

# 3. Delete metrics
# Query and delete all metrics for document_id
```

### 6. Scale Functions

**Manually scale Function App:**

```bash
# Scale out to 10 instances
az functionapp plan update \
  --name your-plan \
  --resource-group your-rg \
  --max-burst 10

# Scale down
az functionapp plan update \
  --name your-plan \
  --resource-group your-rg \
  --max-burst 3
```

## Troubleshooting

### Issue: Documents Stuck in "Processing"

**Symptoms:**
- Status shows "processing" for > 15 minutes
- No recent processing logs

**Diagnosis:**

```bash
# Check last processing log
az cosmosdb sql item read \
  --account-name your-cosmosdb \
  --database-name financial-insights \
  --container-name processing-logs \
  --partition-key doc-abc123 \
  --id log-latest
```

**Resolution:**

1. Check if Function is running:
   ```bash
   az functionapp show --name your-app --resource-group your-rg --query state
   ```

2. Check Service Bus queue:
   ```bash
   az servicebus queue show --name extraction-queue ...
   ```

3. Retry the document:
   ```bash
   curl -X POST .../documents/doc-abc123/retry
   ```

### Issue: Low OCR Confidence

**Symptoms:**
- Many documents with confidence < 0.75
- High rate of validation warnings

**Diagnosis:**

```sql
-- Query for low confidence documents
SELECT c.document_id, c.ocr_confidence_avg
FROM c
WHERE c.ocr_confidence_avg < 0.75
ORDER BY c.event_timestamp DESC
```

**Resolution:**

1. **Improve source quality**: Request higher quality scans (300 DPI minimum)
2. **Use enhanced OCR**: Retry with `enhanced_ocr: true`
3. **Adjust thresholds**: Lower thresholds if appropriate for use case

### Issue: High Extraction Failure Rate

**Symptoms:**
- > 10% extraction failures
- Timeout errors in logs

**Diagnosis:**

```bash
# Check Application Insights for errors
az monitor app-insights query \
  --app your-app-insights \
  --analytics-query "exceptions | where timestamp > ago(1h) | summarize count() by problemId"
```

**Resolution:**

1. **Check Document Intelligence quota**:
   - Verify requests/second limit not exceeded
   - Check Azure portal for throttling

2. **Increase timeout**:
   ```bash
   az functionapp config appsettings set \
     --name your-app \
     --settings PROCESSING_TIMEOUT_MINUTES=15
   ```

3. **Scale Document Intelligence**:
   - Upgrade to higher tier if needed

### Issue: Validation Failures

**Symptoms:**
- Many documents with `validation_status: failed`
- Missing required metrics

**Diagnosis:**

```sql
-- Query validation errors
SELECT c.document_id, c.validation_errors
FROM c
WHERE c.validation_status = "failed"
```

**Resolution:**

1. **Review validation rules**: May be too strict
2. **Check document format**: Ensure documents match expected structure
3. **Adjust validation**: Modify `validator.py` rules if needed

## Monitoring & Alerts

### Key Metrics to Monitor

1. **Processing Success Rate**
   - Target: > 95%
   - Alert if: < 90% for 15 minutes

2. **Average Processing Time**
   - Target: < 5 minutes
   - Alert if: > 10 minutes average

3. **Queue Depth**
   - Target: < 100 messages
   - Alert if: > 500 messages

4. **OCR Confidence**
   - Target: > 0.85 average
   - Alert if: < 0.75 for 50+ documents

5. **Error Rate**
   - Target: < 5%
   - Alert if: > 10% for 1 hour

### Application Insights Queries

**Processing success rate:**
```kusto
customEvents
| where name == "document_uploaded" or name == "validation_completed"
| summarize uploaded = countif(name == "document_uploaded"),
            completed = countif(name == "validation_completed")
| extend success_rate = (completed * 100.0) / uploaded
```

**Average processing time:**
```kusto
customMetrics
| where name == "extraction_duration_seconds"
| summarize avg(value), percentile(value, 95)
```

**Failed documents:**
```kusto
traces
| where severityLevel >= 3
| where message contains "failed"
| summarize count() by bin(timestamp, 1h)
```

### Configure Alerts

```bash
# Create alert for high error rate
az monitor metrics alert create \
  --name "High Extraction Failure Rate" \
  --resource-group your-rg \
  --scopes /subscriptions/.../Microsoft.Insights/components/your-appinsights \
  --condition "count customMetrics/extraction_failed > 10" \
  --window-size 15m \
  --evaluation-frequency 5m \
  --action email your-team@company.com
```

## Disaster Recovery

### Backup Strategy

1. **Blob Storage**: Geo-redundant storage (GRS) with 7-year retention
2. **Cosmos DB**: Continuous backup enabled, 30-day retention
3. **Configuration**: Bicep templates in source control

### Recovery Procedures

**Restore from Cosmos DB backup:**

```bash
# Restore Cosmos DB to point in time
az cosmosdb sql database restore \
  --account-name your-cosmosdb \
  --name financial-insights \
  --restore-timestamp "2024-01-15T10:00:00Z"
```

**Redeploy infrastructure:**

```bash
# Deploy from Bicep
az deployment group create \
  --resource-group your-rg \
  --template-file infrastructure/bicep/main.bicep \
  --parameters infrastructure/bicep/parameters/production.parameters.json
```

**Restore Function App:**

```bash
# Deploy from source
func azure functionapp publish your-function-app
```

### Incident Response

1. **Acknowledge**: Confirm incident and assess impact
2. **Investigate**: Check logs, metrics, and queue status
3. **Mitigate**: Apply immediate fixes (scale, restart, etc.)
4. **Communicate**: Update stakeholders on status
5. **Resolve**: Implement permanent fix
6. **Document**: Post-mortem and lessons learned

## Performance Tuning

### Optimize Processing Speed

1. **Adjust concurrency**:
   ```json
   // In host.json
   "serviceBus": {
     "maxConcurrentCalls": 64
   }
   ```

2. **Increase Function instances**: Scale out plan

3. **Optimize queries**: Add Cosmos DB indexes for frequent queries

### Reduce Costs

1. **Blob lifecycle**: Verify Cool tier after 90 days
2. **Cosmos RU/s**: Use autoscale, review usage patterns
3. **Function plan**: Use Consumption for variable load

## Maintenance Windows

**Planned maintenance checklist:**

- [ ] Notify users 24 hours in advance
- [ ] Stop incoming uploads (maintenance page)
- [ ] Allow current processing to complete
- [ ] Deploy updates
- [ ] Run smoke tests
- [ ] Resume operations
- [ ] Monitor for issues

## Contact Information

- **On-call**: Pager duty rotation
- **Dev Team**: dev-team@company.com
- **Azure Support**: Open ticket via portal

---

**Last Updated**: 2024-01-15
**Version**: 1.0
