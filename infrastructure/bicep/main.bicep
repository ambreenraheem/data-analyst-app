// Main infrastructure template for Document Ingestion Pipeline
// Orchestrates all Azure resources required for the financial insights platform

targetScope = 'resourceGroup'

@description('Environment name (dev, staging, production)')
param environmentName string = 'dev'

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Base name for all resources')
param baseName string = 'fininsights'

@description('Tags to apply to all resources')
param tags object = {
  Environment: environmentName
  Project: 'FinancialInsightsRiskAdvisor'
  Component: 'DocumentIngestion'
}

// Storage module
module storage 'modules/storage.bicep' = {
  name: 'storage-deployment'
  params: {
    storageAccountName: '${baseName}${environmentName}sa'
    location: location
    tags: tags
    retentionDays: 2555  // 7 years
  }
}

// Cosmos DB module
module cosmosDb 'modules/cosmos.bicep' = {
  name: 'cosmos-deployment'
  params: {
    cosmosAccountName: '${baseName}-${environmentName}-cosmos'
    location: location
    tags: tags
    databaseName: 'financial-insights'
  }
}

// Service Bus module
module serviceBus 'modules/service_bus.bicep' = {
  name: 'servicebus-deployment'
  params: {
    serviceBusNamespaceName: '${baseName}-${environmentName}-sb'
    location: location
    tags: tags
  }
}

// Key Vault module
module keyVault 'modules/key_vault.bicep' = {
  name: 'keyvault-deployment'
  params: {
    keyVaultName: '${baseName}-${environmentName}-kv'
    location: location
    tags: tags
  }
}

// Azure Functions module
module functionApp 'modules/function_app.bicep' = {
  name: 'functionapp-deployment'
  params: {
    functionAppName: '${baseName}-${environmentName}-func'
    location: location
    tags: tags
    storageAccountName: storage.outputs.storageAccountName
    keyVaultName: keyVault.outputs.keyVaultName
    cosmosDbEndpoint: cosmosDb.outputs.cosmosEndpoint
    serviceBusNamespace: serviceBus.outputs.serviceBusNamespace
  }
}

// Outputs for reference
output storageAccountName string = storage.outputs.storageAccountName
output cosmosDbEndpoint string = cosmosDb.outputs.cosmosEndpoint
output serviceBusNamespace string = serviceBus.outputs.serviceBusNamespace
output keyVaultName string = keyVault.outputs.keyVaultName
output functionAppName string = functionApp.outputs.functionAppName
