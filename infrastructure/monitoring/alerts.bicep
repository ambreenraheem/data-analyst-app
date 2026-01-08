// Application Insights Alerts Configuration
// Bicep template for monitoring alerts

@description('Application Insights resource name')
param appInsightsName string

@description('Service Bus namespace name')
param serviceBusNamespace string

@description('Resource group location')
param location string = resourceGroup().location

@description('Email addresses for alert notifications (comma-separated)')
param alertEmails string = 'dev-team@company.com'

@description('Environment name')
param environment string = 'staging'

// Get existing Application Insights resource
resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: appInsightsName
}

// Get existing Service Bus namespace
resource serviceBus 'Microsoft.ServiceBus/namespaces@2021-11-01' existing = {
  name: serviceBusNamespace
}

// Create Action Group for notifications
resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: 'ag-document-ingestion-${environment}'
  location: 'global'
  properties: {
    groupShortName: 'DocIngest'
    enabled: true
    emailReceivers: [
      {
        name: 'DevTeam'
        emailAddress: alertEmails
        useCommonAlertSchema: true
      }
    ]
  }
}

// Alert 1: High Extraction Failure Rate
resource alertExtractionFailure 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-extraction-failure-${environment}'
  location: 'global'
  properties: {
    description: 'Alert when extraction failure rate exceeds 10% over 15 minutes'
    severity: 2
    enabled: true
    scopes: [
      appInsights.id
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'ExtractionFailures'
          metricName: 'customMetrics/extraction_failed'
          operator: 'GreaterThan'
          threshold: 10
          timeAggregation: 'Count'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

// Alert 2: High Queue Depth
resource alertQueueDepth 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-queue-depth-${environment}'
  location: 'global'
  properties: {
    description: 'Alert when extraction queue depth exceeds 100 messages'
    severity: 3
    enabled: true
    scopes: [
      '${serviceBus.id}/queues/extraction-queue'
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'ActiveMessages'
          metricName: 'ActiveMessages'
          operator: 'GreaterThan'
          threshold: 100
          timeAggregation: 'Average'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

// Alert 3: Low Average OCR Confidence
resource alertLowConfidence 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-low-confidence-${environment}'
  location: 'global'
  properties: {
    description: 'Alert when average OCR confidence drops below 0.75 over 1 hour'
    severity: 3
    enabled: true
    scopes: [
      appInsights.id
    ]
    evaluationFrequency: 'PT15M'
    windowSize: 'PT1H'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'OCRConfidence'
          metricName: 'customMetrics/ocr_confidence'
          operator: 'LessThan'
          threshold: 0.75
          timeAggregation: 'Average'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

// Alert 4: Slow Processing Time
resource alertSlowProcessing 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-slow-processing-${environment}'
  location: 'global'
  properties: {
    description: 'Alert when average processing time exceeds 10 minutes'
    severity: 3
    enabled: true
    scopes: [
      appInsights.id
    ]
    evaluationFrequency: 'PT10M'
    windowSize: 'PT30M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'ProcessingDuration'
          metricName: 'customMetrics/processing_duration_seconds'
          operator: 'GreaterThan'
          threshold: 600
          timeAggregation: 'Average'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

// Alert 5: High Exception Rate
resource alertExceptions 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-exceptions-${environment}'
  location: 'global'
  properties: {
    description: 'Alert when exception count exceeds 50 in 15 minutes'
    severity: 2
    enabled: true
    scopes: [
      appInsights.id
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'Exceptions'
          metricName: 'exceptions/count'
          operator: 'GreaterThan'
          threshold: 50
          timeAggregation: 'Count'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

// Alert 6: Function Availability
resource alertAvailability 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-availability-${environment}'
  location: 'global'
  properties: {
    description: 'Alert when function availability drops below 95%'
    severity: 1
    enabled: true
    scopes: [
      appInsights.id
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'Availability'
          metricName: 'availabilityResults/availabilityPercentage'
          operator: 'LessThan'
          threshold: 95
          timeAggregation: 'Average'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

// Outputs
output actionGroupId string = actionGroup.id
output actionGroupName string = actionGroup.name
output alertsConfigured array = [
  alertExtractionFailure.name
  alertQueueDepth.name
  alertLowConfidence.name
  alertSlowProcessing.name
  alertExceptions.name
  alertAvailability.name
]
