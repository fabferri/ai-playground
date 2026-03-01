"""
Semantic Kernel Agent with Azure AI Foundry

This script demonstrates how to create a simple chat agent using Semantic Kernel
with Azure OpenAI services. It uses Azure Identity for authentication instead of
API keys, which is more secure and recommended for production scenarios.

Prerequisites:
    pip install azure-identity semantic-kernel

Authentication:
    Uses DefaultAzureCredential which tries multiple auth methods in order:
    1. Environment variables (AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_CLIENT_SECRET)
    2. Workload Identity (for Kubernetes)
    3. Managed Identity (in Azure VMs, App Service, Functions, etc.)
    4. Shared Token Cache
    5. Visual Studio Code credentials (requires Azure Account extension)
    6. Azure CLI credentials (az login)
    7. Azure PowerShell credentials (Connect-AzAccount)
    8. Azure Developer CLI credentials (azd auth login)
"""

import asyncio
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.contents import ChatHistory

# Azure AI Services endpoint (base URL without path)
ENDPOINT = "https://ai-services-89861.services.ai.azure.com"

# =============================================================================
# AUTHENTICATION SETUP
# =============================================================================
# DefaultAzureCredential automatically discovers available credentials
# get_bearer_token_provider creates a callable that returns access tokens
# The scope "https://cognitiveservices.azure.com/.default" is required for Azure OpenAI
credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")

# =============================================================================
# KERNEL CONFIGURATION
# =============================================================================
# The Kernel is the central orchestrator in Semantic Kernel
# It manages AI services, plugins, and function execution
kernel = Kernel()

# Register the Azure OpenAI chat completion service with the kernel
# - deployment_name: The model deployment name in Azure AI Services
# - endpoint: The Azure AI Services endpoint URL
# - ad_token_provider: Callable that provides Azure AD tokens for authentication
# - api_version: The Azure OpenAI API version to use
kernel.add_service(
    AzureChatCompletion(
        deployment_name="gpt-4o",
        endpoint=ENDPOINT,
        ad_token_provider=token_provider,
        api_version="2024-10-21"
    )
)

# =============================================================================
# AGENT CONFIGURATION
# =============================================================================
# ChatCompletionAgent wraps the kernel to provide agent-like behavior
# - kernel: The configured Semantic Kernel instance
# - name: Display name for the agent (appears in responses)
# - instructions: System prompt that defines the agent's behavior
agent = ChatCompletionAgent(
    kernel=kernel,
    name="Assistant",
    instructions="You are a helpful AI assistant that provides concise answers."
)

async def main():
    """Main async function to run the agent conversation."""
    
    # ChatHistory maintains the conversation context
    # It stores both user and assistant messages for multi-turn conversations
    history = ChatHistory()
    
    # Add the user's question to the chat history
    history.add_user_message("What are the benefits of using Azure AI Foundry?")
    
    # Invoke the agent and stream responses
    # The agent uses the kernel's AI service to generate a response
    async for response in agent.invoke(history):
        print(f"{response.name}: {response.content}")

# Entry point - run the async main function
asyncio.run(main())