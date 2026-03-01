# Agents in Azure AI Foundry

Question: **"What Python libraries can I use to build an agent that runs in Azure AI Foundry?"**

Answer: There are three practical SDK choices you can use today. Before diving in, it is important to understand how they relate to each other.

---

## Architecture: How the SDKs Relate

The **Microsoft Agent Framework** is not a single SDK — it is the overarching umbrella that unifies two independent, open-source Python SDKs under one vision:

| Component       | Package(s) | Role |
|-----------------|------------|------|
| **AutoGen**     | `autogen-agentchat`, `autogen-ext` | Multi-agent orchestration (teams, group chat, A2A) |
| **Semantic Kernel** | `semantic-kernel` | Agent orchestration (single & multi-agent, plugins, memory, MCP) |

Separately, the **Azure AI Foundry Agent Service SDK** (`azure-ai-projects`) provides a **managed, server-side agent runtime** — it is not part of the Agent Framework but can be used alongside it.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                           Microsoft Agent Framework (umbrella)                               │
│                                     open-source                                              │
│                                                                                              │
│  ┌─────────────────────────────┐           ┌──────────────────────────────────┐              │
│  │          AutoGen            │           │         Semantic Kernel          │              │
│  │  autogen-agentchat          │           │         semantic-kernel          │              │
│  │  autogen-ext                │           │                                  │              │
│  │                             │           │  Single & multi-agent            │              │
│  │  Multi-agent orchestration  │           │  Plugins · Memory · Planners     │              │
│  │  Teams · Group Chat · Swarm │           │  Auto function calling · MCP     │              │
│  │  A2A protocol · MCP         │           │                                  │              │
│  └──────────────┬──────────────┘           └────────────────┬─────────────────┘              │
│                 │                                           │                                │
└─────────────────┼───────────────────────────────────────────┼────────────────────────────────┘
                  │                                           │
                  │ calls models                              ├── AzureAIAgent (bridge) ──────┐
                  │                                           │ calls models                  │
                  │                                           │                               │
                  │                                           │   ┌───────────────────────────┴────┐
                  │                                           │   │  Azure AI Foundry Agent        │
                  │                                           │   │  Service SDK                   │
                  │                                           │   │  azure-ai-projects             │
                  │                                           │   │                                │
                  │                                           │   │  Managed server-side runtime   │
                  │                                           │   └───────────────┬────────────────┘
                  │                                           │                   │ calls service
                  ▼                                           ▼                   ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                          │
│                                Azure AI Foundry                                          │
│                            Models · Tools · Security                                     │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

> **Key insight:** AutoGen and Semantic Kernel are **not competing alternatives** — they are complementary halves of the same framework. AutoGen excels at advanced multi-agent team patterns (Swarm, SelectorGroupChat, A2A protocol); SK provides `GroupChatOrchestration` alongside its rich plugin/memory ecosystem. Both call Azure AI models directly for inference; SK additionally offers `AzureAIAgent`, which bridges into the managed Foundry Agent Service runtime (SDK #1). You can use either independently or combine them.

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

2) **AutoGen (Python) — part of the Microsoft Agent Framework**

   - Package: `autogen-agentchat`, `autogen-ext` (PyPI: [autogen-agentchat](https://pypi.org/project/autogen-agentchat/), [autogen-ext](https://pypi.org/project/autogen-ext/)). Depends on `autogen-core` (the low-level event-driven runtime), which is installed automatically.
   - What it is: The **multi-agent orchestration** component of the Microsoft Agent Framework. Originally from Microsoft Research, rewritten from v0.2 to the current v0.4+ architecture (latest: v0.7.x). Provides team patterns (`RoundRobinGroupChat`, `SelectorGroupChat`, `Swarm`), termination conditions, tool registration via Python callables, and protocol support for A2A ([Google Agent-to-Agent protocol](https://google.github.io/A2A/)) and MCP ([Model Context Protocol](https://modelcontextprotocol.io/)).
   - Core API surface: `AssistantAgent(name=..., model_client=..., tools=..., system_message=...)` → `await agent.run(task=...)` or `await team.run(task=...)`. For streaming: `agent.run_stream(task=...)`. All calls are **async** (`async`/`await` with `asyncio`).
   - State management: **Client-side, in-process** — agent memory and conversation history live in your Python process. No server-side persistence.
   - Endpoint: Requires the **Azure AI Services endpoint** (the OpenAI-compatible base URL, e.g., `https://<resource>.openai.azure.com` or `https://<ai-services>.services.ai.azure.com`).
   - Authentication: `get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")` → passed as `azure_ad_token_provider` parameter to `AzureOpenAIChatCompletionClient`.
   - When to use: You need multi-agent coordination (team patterns, agent-to-agent handoffs, parallel tool execution) running in your own compute.
   - Reference: [Introducing Microsoft Agent Framework](https://devblogs.microsoft.com/foundry/introducing-microsoft-agent-framework-the-open-source-engine-for-agentic-ai-apps/)

3) **Semantic Kernel (Python) — part of the Microsoft Agent Framework**

   - Package: `semantic-kernel` (PyPI: [semantic-kernel](https://pypi.org/project/semantic-kernel/))
   - What it is: The **agent orchestration and plugin** component of the Microsoft Agent Framework. Supports both single-agent and multi-agent scenarios. Provides a `Kernel` object that registers AI services and plugins (Python functions decorated as tools), with automatic function-calling dispatch. Multi-agent is available via `GroupChatOrchestration` with manager strategies (e.g., `RoundRobinGroupChatManager`). Also supports MCP as a plugin type.
   - Agent types available: `ChatCompletionAgent` (wraps any chat completion service), `OpenAIAssistantAgent` (wraps OpenAI Assistants API), `AzureAIAgent` (wraps Foundry Agent Service — bridges SK with SDK #1).
   - Core API surface: `Kernel()` → `kernel.add_service(AzureChatCompletion(...))` → `ChatCompletionAgent(kernel=kernel, name=..., instructions=...)` → `await agent.invoke(history)` or `await agent.get_response(input=...)`. Shorthand: `ChatCompletionAgent(service=AzureChatCompletion(...), name=..., instructions=...)` skips the kernel. All calls are **async** (`async for` iteration over responses).
   - State management: **Client-side, in-process** — you manage `ChatHistory` objects. No server-side persistence (unless using `AzureAIAgent`, which delegates to Foundry).
   - Endpoint: Requires the **Azure AI Services endpoint** (same as AutoGen).
   - Authentication: `get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")` → passed as `ad_token_provider` parameter to `AzureChatCompletion`. **Note:** the parameter name is `ad_token_provider` (not `azure_ad_token_provider` as in AutoGen).
   - When to use: You need structured plugin orchestration, memory, or planners running in your own compute — for a single agent or a group of agents. Also useful when you want to bridge into Foundry Agent Service via `AzureAIAgent`.

---

## Side-by-Side Comparison

| Aspect | #1 Foundry Agent Service SDK | #2 AutoGen | #3 Semantic Kernel |
|--------|------------------------------|------------|--------------------|
| **Package** | `azure-ai-projects` (+`azure-ai-agents`) | `autogen-agentchat`, `autogen-ext` | `semantic-kernel` |
| **Execution model** | Synchronous (blocking); async via `.aio` | Async (`asyncio`) | Async (`asyncio`) |
| **Agent runs on** | Foundry service (server-side) | Your process (client-side) | Your process (client-side) |
| **State persistence** | Server-side (threads) | In-process (no persistence) | In-process (no persistence) |
| **Multi-agent support** | No (single agent per thread) | Yes (teams, group chat, A2A) | Yes (`GroupChatOrchestration`, round-robin manager) |
| **Tool system** | Typed tool objects (`CodeInterpreterTool`, `FileSearchTool`, etc.) + OpenAPI | Python callables + MCP servers | Kernel plugins (decorated functions) + MCP |
| **Endpoint type** | Foundry project endpoint | Azure AI Services / OpenAI endpoint | Azure AI Services / OpenAI endpoint |
| **Token provider param** | N/A (credential on client) | `azure_ad_token_provider` | `ad_token_provider` |

**Tip — which one to pick:**

| Scenario | Pick |
|----------|------|
| Managed runtime, server-side state, built-in tools | **#1** Azure AI Foundry Agent Service SDK |
| Multi-agent with advanced team patterns (Swarm, SelectorGroupChat), A2A protocol | **#2** AutoGen |
| Agent + plugins/memory/MCP; simpler multi-agent via GroupChatOrchestration | **#3** Semantic Kernel |

---

## Code Examples

### #1 Azure AI Foundry Agent Service SDK (Python) - Managed Agent Runtime

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

### #2 AutoGen (Python) — Multi-Agent Orchestration

AutoGen is the multi-agent component of the Microsoft Agent Framework. It uses `autogen-agentchat` (agent types, team patterns, termination conditions) and `autogen-ext` (model clients, tool extensions). All calls are **async** — you must use `asyncio.run()`. Use `run()` for batch results or `run_stream()` for streaming.

**Example 2a — Multi-Agent Team (Round-Robin):**

Two agents collaborate in a `RoundRobinGroupChat`. The team alternates turns between agents until `TextMentionTermination` detects the word "APPROVE" or `max_turns` is reached.

```python
import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# Azure AI Services endpoint (OpenAI-compatible base URL, NOT the Foundry project endpoint)
ENDPOINT = "<your-azure-ai-services-endpoint>"

# Get token provider for Microsoft Entra ID authentication
# Scope "https://cognitiveservices.azure.com/.default" is required for Azure AI Services
credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")

# Configure Azure OpenAI model client
# Note: parameter is 'azure_ad_token_provider' (AutoGen naming)
model_client = AzureOpenAIChatCompletionClient(
    azure_deployment="gpt-4o",
    azure_endpoint=ENDPOINT,
    api_version="2024-10-21",
    model="gpt-4o",
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
```

**Install:** `pip install autogen-agentchat autogen-ext[azure]`

**Example 2b — Single Agent:**

A single `AssistantAgent` with no team — `agent.run(task)` sends one user message and returns the model's response.

```python
import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# Azure AI Services endpoint (OpenAI-compatible base URL)
ENDPOINT = "<your-azure-ai-services-endpoint>"

# Create token provider for Microsoft Entra ID authentication
credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")

# Configure Azure OpenAI model client
model_client = AzureOpenAIChatCompletionClient(
    azure_deployment="gpt-4o",
    azure_endpoint=ENDPOINT,
    api_version="2024-10-21",
    model="gpt-4o",
    azure_ad_token_provider=token_provider
)

# Create a coding assistant agent
coder = AssistantAgent(
    name="Coder",
    model_client=model_client,
    system_message="You are a Python coding expert. Write clean, efficient code with comments."
)

async def main():
    # Run a single-turn conversation
    response = await coder.run(task="Write a Python function to calculate fibonacci numbers.")
    
    # Print the response
    for message in response.messages:
        print(f"{message.source}: {message.content}")

asyncio.run(main())
```

**Example 2c — Single Agent with Tool Use (Function Calling):**

AutoGen registers Python callables as tools via the `tools=[fn]` parameter. The model decides when to call them; AutoGen handles the function-call → execute → feed-result-back loop automatically.

```python
import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# Azure AI Services endpoint
ENDPOINT = "<your-azure-ai-services-endpoint>"

# Define a custom tool that the agent can invoke
def get_weather(city: str) -> str:
    # Simulated weather data (replace with actual API call in production)
    return f"The weather in {city} is sunny, 22°C"

# Create token provider for Microsoft Entra ID authentication
credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")


# Configure Azure OpenAI model client
model_client = AzureOpenAIChatCompletionClient(
    azure_deployment="gpt-4o",
    azure_endpoint=ENDPOINT,
    api_version="2024-10-21",
    model="gpt-4o",
    azure_ad_token_provider=token_provider
)

# Create an assistant agent with the weather tool
weather_agent = AssistantAgent(
    name="WeatherBot",
    model_client=model_client,
    tools=[get_weather],  # Register the tool with the agent
    system_message="You help users check the weather. Use the get_weather tool when asked.",
    reflect_on_tool_use=True,  # Model summarizes tool output into natural language
)


async def main():
    """Run the agent with a weather query and display the response."""
    response = await weather_agent.run(task="What's the weather in London?")
    
    # Print each message in the conversation
    for msg in response.messages:
        print(f"{msg.source}: {msg.content}")


# Entry point
asyncio.run(main())
```

**Install:** `pip install autogen-agentchat autogen-ext[azure]`

---

### #3 Semantic Kernel (Python) — Agent Orchestration with Plugins

Semantic Kernel is the agent orchestration and plugin component of the Microsoft Agent Framework. It uses the `semantic-kernel` package and supports both single-agent and multi-agent scenarios (via `GroupChatOrchestration` with `RoundRobinGroupChatManager`). The architecture is: `Kernel` (registers AI services + plugins) → `ChatCompletionAgent` (wraps the kernel into an agent with a system prompt) → `agent.invoke(history)` (async iteration over responses). You can also create an agent directly with `service=AzureChatCompletion()` instead of a full kernel.

Agent types in Semantic Kernel:
- `ChatCompletionAgent` — wraps any registered chat completion service (used below)
- `OpenAIAssistantAgent` — wraps the OpenAI Assistants API
- `AzureAIAgent` — wraps the Foundry Agent Service (bridges SK with SDK #1)

```python
import asyncio
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.contents import ChatHistory

# Azure AI Services endpoint (OpenAI-compatible base URL, same as AutoGen)
# NOT the Foundry project endpoint used by SDK #1
ENDPOINT = "<your-azure-ai-services-endpoint>"

# Microsoft Entra ID token provider
# Same scope as AutoGen, but the parameter name differs (see below)
credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")

# Kernel: the central orchestrator — registers AI services and plugins
kernel = Kernel()

# Register Azure OpenAI chat completion service
# Note: parameter is 'ad_token_provider' (SK naming, NOT 'azure_ad_token_provider' as in AutoGen)
kernel.add_service(
    AzureChatCompletion(
        deployment_name="gpt-4o",
        endpoint=ENDPOINT,
        ad_token_provider=token_provider,
        api_version="2024-10-21"
    )
)

# ChatCompletionAgent wraps the kernel into an agent with a system prompt
# The agent delegates to the registered AzureChatCompletion service
agent = ChatCompletionAgent(
    kernel=kernel,
    name="Assistant",
    instructions="You are a helpful AI assistant that provides concise answers."
)

async def main():
    # ChatHistory: client-side conversation state (user + assistant messages)
    # Unlike SDK #1, there is no server-side thread — you manage history in-process
    history = ChatHistory()
    history.add_user_message("What are the benefits of using Azure AI Foundry?")
    
    # agent.invoke() returns an async iterator of response chunks
    async for response in agent.invoke(history):
        print(f"{response.name}: {response.content}")

asyncio.run(main())
```

**Install:** `pip install azure-identity semantic-kernel`

---

## Reference

[Agent Framework](https://aka.ms/AgentFramework)

---

`Tags: Azure AI Foundry, agent` <br>
`date: 01-03-2026` <br>