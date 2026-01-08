// Cosmos DB Account with containers for structured data
// Supports Constitution Principles I (Data-First), II (Confidence Thresholds), III (Auditability)

@description('Cosmos DB account name')
param cosmosAccountName string

@description('Azure region')
param location string

@description('Resource tags')
param tags object

@description('Database name')
param databaseName string = 'financial-insights'

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-11-15' = {
  name: cosmosAccountName
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'  // Balance between consistency and performance
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    enableAutomaticFailover: false
    enableFreeTier: false
    publicNetworkAccess: 'Enabled'  // Update to 'Disabled' with private endpoints in production
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-11-15' = {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
    options: {
      autoscaleSettings: {
        maxThroughput: 4000  // Autoscale from 400 to 4000 RU/s
      }
    }
  }
}

// Container for extraction results
resource extractionResultsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: database
  name: 'extraction-results'
  properties: {
    resource: {
      id: 'extraction-results'
      partitionKey: {
        paths: ['/document_id']
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {path: '/*'}
        ]
      }
    }
  }
}

// Container for financial metrics
resource financialMetricsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: database
  name: 'financial-metrics'
  properties: {
    resource: {
      id: 'financial-metrics'
      partitionKey: {
        paths: ['/document_id']
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {path: '/*'}
        ]
      }
    }
  }
}

// Container for processing logs
resource processingLogsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: database
  name: 'processing-logs'
  properties: {
    resource: {
      id: 'processing-logs'
      partitionKey: {
        paths: ['/document_id']
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {path: '/*'}
        ]
      }
    }
  }
}

output cosmosAccountName string = cosmosAccount.name
output cosmosAccountId string = cosmosAccount.id
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
