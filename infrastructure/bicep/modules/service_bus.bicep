// Service Bus namespace with queues for asynchronous processing
// Supports event-driven architecture for document ingestion pipeline

@description('Service Bus namespace name')
param serviceBusNamespaceName string

@description('Azure region')
param location string

@description('Resource tags')
param tags object

resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: serviceBusNamespaceName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'  // Update with private endpoints in production
  }
}

// Ingestion queue (receives upload events)
resource ingestionQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: serviceBusNamespace
  name: 'ingestion-queue'
  properties: {
    maxDeliveryCount: 3  // Move to dead-letter after 3 failed attempts
    lockDuration: 'PT5M'  // 5-minute lock duration
    defaultMessageTimeToLive: 'P1D'  // Messages expire after 1 day
    deadLetteringOnMessageExpiration: true
    enablePartitioning: false
    requiresDuplicateDetection: true
    duplicateDetectionHistoryTimeWindow: 'PT10M'
  }
}

// Extraction queue (receives documents ready for OCR)
resource extractionQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: serviceBusNamespace
  name: 'extraction-queue'
  properties: {
    maxDeliveryCount: 3
    lockDuration: 'PT10M'  // 10-minute lock (OCR can take time)
    defaultMessageTimeToLive: 'P1D'
    deadLetteringOnMessageExpiration: true
    enablePartitioning: false
    requiresDuplicateDetection: true
    duplicateDetectionHistoryTimeWindow: 'PT10M'
  }
}

// Validation queue (receives extracted data for validation)
resource validationQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: serviceBusNamespace
  name: 'validation-queue'
  properties: {
    maxDeliveryCount: 3
    lockDuration: 'PT5M'
    defaultMessageTimeToLive: 'P1D'
    deadLetteringOnMessageExpiration: true
    enablePartitioning: false
    requiresDuplicateDetection: true
    duplicateDetectionHistoryTimeWindow: 'PT10M'
  }
}

output serviceBusNamespace string = serviceBusNamespace.name
output serviceBusNamespaceId string = serviceBusNamespace.id
output ingestionQueueName string = ingestionQueue.name
output extractionQueueName string = extractionQueue.name
output validationQueueName string = validationQueue.name
