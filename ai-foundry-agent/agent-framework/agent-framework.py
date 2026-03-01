import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# Azure AI Services endpoint (base URL without path)
ENDPOINT = "https://ai-services-89861.services.ai.azure.com"

# Get token provider for Azure AI Services
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

# Create a writer agent
writer_agent = AssistantAgent(
    name="Writer",
    model_client=model_client,
    system_message="You are a creative writer. Write short content and ask Reviewer for feedback."
)

# Create a reviewer agent
reviewer_agent = AssistantAgent(
    name="Reviewer",
    model_client=model_client,
    system_message="You are a critical reviewer. Provide feedback. Say 'APPROVE' when satisfied."
)

# Create a multi-agent team with round-robin execution
termination = TextMentionTermination("APPROVE")
team = RoundRobinGroupChat(
    participants=[writer_agent, reviewer_agent],
    termination_condition=termination,
    max_turns=6
)

async def main():
    result = await team.run(task="Write a haiku about coding.")
    for message in result.messages:
        print(f"{message.source}: {message.content}\n")

asyncio.run(main())