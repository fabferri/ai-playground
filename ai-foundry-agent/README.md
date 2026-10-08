# Agents in Azure AI Foundry

The **Azure AI Foundry Agent Service SDK** (`azure-ai-projects`) provides a **managed, server-side agent runtime** — it is not part of the Agent Framework but can be used alongside it.

```


                            ├── AzureAIAgent (bridge) ──────┐
                                                            │
                                                            │
                                ┌───────────────────────────┴────┐
                                │  Azure AI Foundry Agent        │
                                │  Service SDK                   │
                                │  azure-ai-projects             │
                                │                                │
                                │  Managed server-side runtime   │
                                └───────────────┬────────────────┘
                                                │ calls service
                                                ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                          │
│                                Azure AI Foundry                                          │
│                            Models · Tools · Security                                     │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

SK additionally offers `AzureAIAgent`, which bridges into the managed Foundry Agent Service runtime (SDK #1). You can use either independently or combine them.

---

## Three SDK Choices

From a practical standpoint, you choose between three SDK options:

1) **Azure AI Foundry Agent Service SDK (Python)**

   - Package: `azure-ai-projects` (PyPI: [azure-ai-projects](https://pypi.org/project/azure-ai-projects/)), which installs `azure-ai-agents` (PyPI: [azure-ai-agents](https://pypi.org/project/azure-ai-agents/)) as a dependency for agent operations.
   - What it is: A Python SDK that wraps the Foundry Agent Service **REST API**. Your code sends HTTP calls to the Foundry service; the service runs the agent, manages conversation state (threads), and executes tools **server-side**. You never run an agent loop locally.
   - Core API surface: `AIProjectClient` → `.agents` returns an `AgentsClient` with nested sub-clients:
     - `.agents.create_agent()` / `.agents.delete_agent()`
     - `.agents.threads.create()`
     - `.agents.messages.create()` / `.agents.messages.list()`
     - `.agents.runs.create_and_process()` (synchronous, blocking — polls until the run completes)
     - An async client is also available via `azure.ai.projects.aio`.
   - Built-in tool types (typed objects from `azure.ai.agents.models`): `CodeInterpreterTool`, `FileSearchTool`, `BingGroundingTool` (web search), `AzureAISearchTool`, `AzureFunctionTool`, `OpenApiTool`. Tools are passed via `tools=tool.definitions` and `tool_resources=tool.resources`.
   - State management: **Server-side** — threads and messages persist in the Foundry service. Your client is stateless.
   - Endpoint: Requires the **Foundry project endpoint** (e.g., `https://<ai-services-account>.services.ai.azure.com/api/projects/<project-name>`).
   - Authentication: `DefaultAzureCredential` passed directly to `AIProjectClient`.
   - When to use: You want a fully managed agent runtime where Microsoft hosts the inference loop, tool execution, and conversation state.


---

## Code Examples

### Azure AI Foundry Agent Service SDK (Python) - Managed Agent Runtime

A simple agent using the managed Foundry Agent Service. Note: `runs.create_and_process()` is **synchronous** — it polls the service until the server-side agent completes.

Since v1.0.0 GA, `azure-ai-projects` installs `azure-ai-agents` as a dependency. The `.agents` property on `AIProjectClient` returns an authenticated `AgentsClient` with nested sub-clients (`.threads`, `.messages`, `.runs`).

```python
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import CodeInterpreterTool
from azure.identity import DefaultAzureCredential

# Foundry project endpoint (NOT the Azure AI Services/OpenAI endpoint)
# Format: https://<ai-services-account>.services.ai.azure.com/api/projects/<project-name>
ENDPOINT = "<your-project-endpoint>"

# Connect to your Azure AI Foundry project
project_client = AIProjectClient(
    endpoint=ENDPOINT,
    credential=DefaultAzureCredential()
)

# project_client.agents returns an AgentsClient (from azure-ai-agents package)
agents = project_client.agents

# Create an agent with code interpreter tool (typed tool object)
code_interpreter = CodeInterpreterTool()
agent = agents.create_agent(
    model="gpt-4o",
    name="my-assistant",
    instructions="You are a helpful assistant that can analyze data and write code.",
    tools=code_interpreter.definitions,
)

# Create a thread for conversation (nested sub-client: .threads)
thread = agents.threads.create()

# Send a message (nested sub-client: .messages)
message = agents.messages.create(
    thread_id=thread.id,
    role="user",
    content="What is the square root of 144?"
)

# Run the agent — synchronous, blocks until the server-side run completes
run = agents.runs.create_and_process(
    thread_id=thread.id,
    agent_id=agent.id
)

print("\n--- Agent Response ---")
messages = agents.messages.list(thread_id=thread.id)

# Print the assistant's answer
for msg in messages:
    if msg.role == "assistant":
        for text_msg in msg.text_messages:
            print(text_msg.text.value)
        break

# Cleanup
agents.delete_agent(agent.id)
```

**Install:** `pip install azure-ai-projects azure-identity`



---

`Tags: Azure AI Foundry, agent` <br>
`date: 01-03-2026` <br>