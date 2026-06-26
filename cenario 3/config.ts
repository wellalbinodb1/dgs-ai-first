export const config = {
  cosmosConnectionString: process.env.COSMOS_CONNECTION_STRING ?? "",
  azureOpenAiEndpoint: process.env.AZURE_OPENAI_ENDPOINT ?? "",
  azureSearchEndpoint: process.env.AZURE_SEARCH_ENDPOINT ?? "",
  azureSearchKey: process.env.AZURE_SEARCH_KEY ?? "",
};