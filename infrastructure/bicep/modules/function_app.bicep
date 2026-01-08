// Azure Functions app for serverless document processing
// Python 3.11 runtime with managed identity for secure service access

@description('Function App name')
param functionAppName string

@description('Azure region')
param location string

@description('Resource tags')
param tags object

@description('Storage account name for Functions metadata')
param storageAccountName string

@description('Key Vault name for secrets')
param keyVaultName string

@description('Cosmos DB endpoint')
param cosmosDbEndpoint string

@description('Service Bus namespace')
param serviceBusNamespace string

// App Service Plan (Consumption Y1 for serverless)
resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: '${functionAppName}-plan'
  location: location
  tags: tags
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  properties: {
    reserved: true  // Required for Linux
  }
}

// Function App
resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
  name: functionAppName
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'  // Managed Identity for secure access
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true  // TLS enforcement
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      pythonVersion: '3.11'
      appSettings: [
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName};EndpointSuffix=${environment().suffixes.storage};AccountKey=${listKeys(resourceId('Microsoft.Storage/storageAccounts', storageAccountName), '2023-01-01').keys[0].value}'
        }
        {
          name: 'KEY_VAULT_URL'
          value: reference(resourceId('Microsoft.KeyVault/vaults', keyVaultName), '2023-07-01').vaultUri
        }
        {
          name: 'COSMOS_DB_ENDPOINT'
          value: cosmosDbEndpoint
        }
        {
          name: 'SERVICE_BUS_NAMESPACE'
          value: '${serviceBusNamespace}.servicebus.windows.net'
        }
        {
          name: 'STORAGE_ACCOUNT_NAME'
          value: storageAccountName
        }
      ]
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
      functionAppScaleLimit: 10  // Max concurrent instances
    }
  }
}

output functionAppName string = functionApp.name
output functionAppId string = functionApp.id
output functionAppPrincipalId string = functionApp.identity.principalId
