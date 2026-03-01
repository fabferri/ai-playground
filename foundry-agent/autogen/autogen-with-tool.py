"""
AutoGen Agent with Custom Tool Example
=======================================
This script demonstrates how to create an AutoGen assistant agent with a custom tool.
The agent uses Azure OpenAI GPT-4o model and can call the get_weather tool to 
retrieve weather information for a specified city.

Authentication: Uses Azure AD (DefaultAzureCredential) for secure access.
"""

import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# Azure AI Services endpoint
ENDPOINT = "https://ai-services-89861.services.ai.azure.com"


# Define a custom tool that the agent can invoke
def get_weather(city: str) -> str:
    """
    Get the current weather for a city.
    
    Args:
        city: The name of the city to get weather for.
        
    Returns:
        A string describing the current weather conditions.
    """
    # Simulated weather data (replace with actual API call in production)
    return f"The weather in {city} is sunny, 22°C"


# Create token provider for Azure AD authentication
credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")


# Configure Azure OpenAI model client
model_client = AzureOpenAIChatCompletionClient(
    azure_deployment="gpt-4o",
    azure_endpoint=ENDPOINT,
    api_version="2024-10-21",
    model="gpt-4o-2024-11-20",
    azure_ad_token_provider=token_provider
)

# Create an assistant agent with the weather tool
weather_agent = AssistantAgent(
    name="WeatherBot",
    model_client=model_client,
    tools=[get_weather],  # Register the tool with the agent
    system_message="You help users check the weather. Use the get_weather tool when asked."
)


async def main():
    """Run the agent with a weather query and display the response."""
    response = await weather_agent.run(task="What's the weather in London?")
    
    # Print each message in the conversation
    for msg in response.messages:
        print(f"{msg.source}: {msg.content}")


# Entry point
asyncio.run(main())
