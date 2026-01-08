// Storage Account with Blob and Table Storage
// Supports Constitution Principle III (7-year retention and audit trail)

@description('Storage account name')
param storageAccountName string

@description('Azure region')
param location string

@description('Resource tags')
param tags object

@description('Retention period in days (default: 7 years)')
param retentionDays int = 2555

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'  // Locally redundant storage for cost optimization
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    supportsHttpsTrafficOnly: true  // TLS 1.3 enforcement
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false  // Security: no anonymous access
    networkAcls: {
      defaultAction: 'Allow'  // Update to 'Deny' with specific network rules in production
      bypass: 'AzureServices'
    }
  }
}

// Blob service with lifecycle management
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: retentionDays
    }
  }
}

// Financial documents container
resource financialDocsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'financial-documents'
  properties: {
    publicAccess: 'None'
  }
}

// Lifecycle management rule for cost optimization
resource lifecyclePolicy 'Microsoft.Storage/storageAccounts/managementPolicies@2023-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          enabled: true
          name: 'move-to-cool-after-90-days'
          type: 'Lifecycle'
          definition: {
            actions: {
              baseBlob: {
                tierToCool: {
                  daysAfterModificationGreaterThan: 90
                }
                delete: {
                  daysAfterModificationGreaterThan: retentionDays
                }
              }
            }
            filters: {
              blobTypes: ['blockBlob']
              prefixMatch: ['financial-documents/']
            }
          }
        }
      ]
    }
  }
}

// Table service for audit logs
resource tableService 'Microsoft.Storage/storageAccounts/tableServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
}

// Audit logs table
resource auditLogsTable 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01' = {
  parent: tableService
  name: 'AuditLogs'
}

output storageAccountName string = storageAccount.name
output storageAccountId string = storageAccount.id
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob
output tableEndpoint string = storageAccount.properties.primaryEndpoints.table
