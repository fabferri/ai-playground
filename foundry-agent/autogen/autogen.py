"""
AutoGen Assistant Agent Example
================================
This script demonstrates how to create a simple AutoGen assistant agent that
generates Python code using Azure OpenAI GPT-4o model.

The agent is configured as a Python coding expert and will respond to coding
tasks with clean, well-commented code.

Authentication: Uses Azure AD (DefaultAzureCredential) for secure access to
Azure AI Services without requiring API keys.
"""

import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# Azure AI Services endpoint (base URL without path)
ENDPOINT = "https://ai-services-89861.services.ai.azure.com"

# Create token provider for Azure AD authentication
# DefaultAzureCredential tries multiple auth methods: Azure CLI, managed identity, etc.
credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")

# Configure Azure OpenAI model client
# Uses the GPT-4o deployment with Azure AD token authentication
model_client = AzureOpenAIChatCompletionClient(
    azure_deployment="gpt-4o",              # The deployment name in Azure
    azure_endpoint=ENDPOINT,                # Azure AI Services endpoint
    api_version="2024-10-21",               # API version for Azure OpenAI
    model="gpt-4o-2024-11-20",              # Model identifier for token estimation
    azure_ad_token_provider=token_provider  # Azure AD authentication
)

# Create a coding assistant agent with a specialized system prompt
coder = AssistantAgent(
    name="Coder",
    model_client=model_client,
    system_message="You are a Python coding expert. Write clean, efficient code with comments."
)


async def main():
    """Run the agent with a coding task and display the response."""
    # Run a single-turn conversation with the agent
    response = await coder.run(task="Write a Python function to calculate fibonacci numbers.")
    
    # Print each message in the conversation (user query + agent response)
    for message in response.messages:
        print(f"{message.source}: {message.content}")


# Entry point - run the async main function
asyncio.run(main())