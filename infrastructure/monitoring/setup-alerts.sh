#!/bin/bash
# Application Insights Alert Configuration Script
# Sets up monitoring alerts for the Document Ingestion Pipeline

set -e

# Configuration variables
RESOURCE_GROUP="${RESOURCE_GROUP:-your-resource-group}"
APP_INSIGHTS_NAME="${APP_INSIGHTS_NAME:-your-app-insights}"
ACTION_GROUP_NAME="${ACTION_GROUP_NAME:-document-ingestion-alerts}"
EMAIL_RECEIVERS="${EMAIL_RECEIVERS:-dev-team@company.com}"

# Get Application Insights resource ID
APP_INSIGHTS_ID=$(az monitor app-insights component show \
  --app "$APP_INSIGHTS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query id \
  --output tsv)

echo "Configuring alerts for Application Insights: $APP_INSIGHTS_NAME"
echo "Resource ID: $APP_INSIGHTS_ID"

# Create Action Group for notifications
echo "Creating action group: $ACTION_GROUP_NAME"
az monitor action-group create \
  --name "$ACTION_GROUP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --short-name "DocIngest" \
  --email-receiver name="DevTeam" email-address="$EMAIL_RECEIVERS"

ACTION_GROUP_ID=$(az monitor action-group show \
  --name "$ACTION_GROUP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query id \
  --output tsv)

echo "Action group created: $ACTION_GROUP_ID"

# Alert 1: High Extraction Failure Rate
echo "Creating alert: High Extraction Failure Rate"
az monitor metrics alert create \
  --name "High Extraction Failure Rate" \
  --resource-group "$RESOURCE_GROUP" \
  --scopes "$APP_INSIGHTS_ID" \
  --condition "count customMetrics/extraction_failed > 10" \
  --description "Alert when extraction failure rate exceeds 10% over 15 minutes" \
  --window-size 15m \
  --evaluation-frequency 5m \
  --severity 2 \
  --action "$ACTION_GROUP_ID"

# Alert 2: High Queue Depth
echo "Creating alert: High Queue Depth"
SERVICE_BUS_ID=$(az servicebus namespace show \
  --name "${SERVICE_BUS_NAMESPACE:-your-servicebus}" \
  --resource-group "$RESOURCE_GROUP" \
  --query id \
  --output tsv)

az monitor metrics alert create \
  --name "High Queue Depth" \
  --resource-group "$RESOURCE_GROUP" \
  --scopes "$SERVICE_BUS_ID/queues/extraction-queue" \
  --condition "avg ActiveMessages > 100" \
  --description "Alert when extraction queue depth exceeds 100 messages" \
  --window-size 15m \
  --evaluation-frequency 5m \
  --severity 3 \
  --action "$ACTION_GROUP_ID"

# Alert 3: Low Average Confidence
echo "Creating alert: Low Average Confidence"
az monitor metrics alert create \
  --name "Low Average OCR Confidence" \
  --resource-group "$RESOURCE_GROUP" \
  --scopes "$APP_INSIGHTS_ID" \
  --condition "avg customMetrics/ocr_confidence < 0.75" \
  --description "Alert when average OCR confidence drops below 0.75 over 1 hour" \
  --window-size 1h \
  --evaluation-frequency 15m \
  --severity 3 \
  --action "$ACTION_GROUP_ID"

# Alert 4: Slow Processing Time
echo "Creating alert: Slow Processing Time"
az monitor metrics alert create \
  --name "Slow Document Processing" \
  --resource-group "$RESOURCE_GROUP" \
  --scopes "$APP_INSIGHTS_ID" \
  --condition "avg customMetrics/processing_duration_seconds > 600" \
  --description "Alert when average processing time exceeds 10 minutes" \
  --window-size 30m \
  --evaluation-frequency 10m \
  --severity 3 \
  --action "$ACTION_GROUP_ID"

# Alert 5: Function Errors
echo "Creating alert: High Error Rate"
az monitor metrics alert create \
  --name "High Function Error Rate" \
  --resource-group "$RESOURCE_GROUP" \
  --scopes "$APP_INSIGHTS_ID" \
  --condition "count exceptions > 50" \
  --description "Alert when exception count exceeds 50 in 15 minutes" \
  --window-size 15m \
  --evaluation-frequency 5m \
  --severity 2 \
  --action "$ACTION_GROUP_ID"

# Alert 6: Validation Failures
echo "Creating alert: High Validation Failure Rate"
az monitor metrics alert create \
  --name "High Validation Failure Rate" \
  --resource-group "$RESOURCE_GROUP" \
  --scopes "$APP_INSIGHTS_ID" \
  --condition "count customEvents where name == 'validation_failed' > 20" \
  --description "Alert when validation failures exceed 20 in 1 hour" \
  --window-size 1h \
  --evaluation-frequency 15m \
  --severity 3 \
  --action "$ACTION_GROUP_ID"

echo "All alerts configured successfully!"
echo ""
echo "Configured alerts:"
echo "  1. High Extraction Failure Rate (> 10 failures in 15 min)"
echo "  2. High Queue Depth (> 100 messages)"
echo "  3. Low Average OCR Confidence (< 0.75)"
echo "  4. Slow Document Processing (> 10 minutes avg)"
echo "  5. High Function Error Rate (> 50 exceptions in 15 min)"
echo "  6. High Validation Failure Rate (> 20 failures in 1 hour)"
echo ""
echo "Notifications will be sent to: $EMAIL_RECEIVERS"
