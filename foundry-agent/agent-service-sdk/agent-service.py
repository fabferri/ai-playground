# =============================================================================
# Azure AI Foundry Agent Service SDK - Simple Agent Example
# =============================================================================
# This script demonstrates how to:
# 1. Connect to an Azure AI Foundry project
# 2. Create an agent with code interpreter tool
# 3. Create a conversation thread
# 4. Send a message and process the agent's response
# 5. Clean up by deleting the agent
# =============================================================================

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

# Configuration
ENDPOINT = "https://ai-services-89861.services.ai.azure.com/api/projects/prj-multiagent"

# Connect to your Azure AI Foundry project
project_client = AIProjectClient(
    endpoint=ENDPOINT,
    credential=DefaultAzureCredential()
)

# Create an agent with code interpreter tool
agent = project_client.agents.create_agent(
    model="gpt-4o",
    name="my-assistant",
    instructions="You are a helpful assistant that can analyze data and write code.",
    tools=[{"type": "code_interpreter"}]
)

# Create a thread for conversation
thread = project_client.agents.threads.create()

# Send a message
message = project_client.agents.messages.create(
    thread_id=thread.id,
    role="user",
    content="What is the square root of 144?"
)

# Run the agent and get response
run = project_client.agents.runs.create_and_process(
    thread_id=thread.id,
    agent_id=agent.id
)

# Check run status
print(f"\nRun status: {run.status}")
if run.status != "completed":
    print(f"Run failed or incomplete. Last error: {run.last_error}")

# Get the agent's response
print("\n--- Agent Response ---")
messages = list(project_client.agents.messages.list(thread_id=thread.id))
print(f"Total messages: {len(messages)}")

for msg in messages:
    print(f"Message role: {msg.role}")
    if msg.role == "assistant":
        print(f"Content items: {len(msg.content)}")
        for content_item in msg.content:
            print(f"Content type: {type(content_item)}")
            if hasattr(content_item, 'text'):
                print(content_item.text.value)
            elif hasattr(content_item, 'value'):
                print(content_item.value)
            else:
                print(f"Raw content: {content_item}")
        break
print("----------------------\n")

# Cleanup
project_client.agents.delete_agent(agent.id)