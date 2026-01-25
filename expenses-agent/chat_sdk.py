# Azure AI Foundry Agent - Interactive Chat (SDK Version)
#
# This script provides an interactive terminal interface to chat with the expense-agent.
# Uses the Azure AI Foundry SDK instead of REST API calls.
# Type 'quit' to exit.
#
# Prerequisites:
#    pip install azure-ai-projects azure-identity python-dotenv
#
# Required environment variables (see .env file):
#    AZURE_EXISTING_AIPROJECT_ENDPOINT - Foundry project endpoint
#
## NOTE:
## No API version needed - SDK manages it internally
## client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential)
## thread = client.agents.create_thread()  # SDK uses its built-in API version

import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import MessageRole

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================
PROJECT_ENDPOINT = os.getenv("AZURE_EXISTING_AIPROJECT_ENDPOINT")
AGENT_NAME = os.getenv("AZURE_EXISTING_AGENT_ID")
MODEL_DEPLOYMENT = os.getenv("AZURE_MODEL_DEPLOYMENT")

# Agent instructions for expense assistant
AGENT_INSTRUCTIONS = """You are an AI assistant for corporate expenses. 
You answer questions about expenses based on the expenses policy data. 
If a user wants to submit an expense claim, you get their email address, 
a description of the claim, and the amount to be claimed and write the 
claim details to a text file that the user can download."""

if not PROJECT_ENDPOINT or not AGENT_NAME or not MODEL_DEPLOYMENT:
    raise ValueError("Missing required environment variables: AZURE_EXISTING_AIPROJECT_ENDPOINT, AZURE_EXISTING_AGENT_ID, AZURE_MODEL_DEPLOYMENT")

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_project_client():
    """
    Create and return an Azure AI Project client.
    
    Initializes the AIProjectClient using DefaultAzureCredential which supports
    multiple authentication methods including Azure CLI, environment variables,
    managed identity, and Visual Studio Code credentials.
    
    Returns:
        AIProjectClient: An authenticated client for Azure AI Foundry operations.
    
    Raises:
        azure.identity.CredentialUnavailableError: If no valid credential is found.
    """
    credential = DefaultAzureCredential()
    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=credential
    )
    return client


def get_or_create_agent(client, agent_name):
    """
    Get the agent by name, or create it if it doesn't exist.
    
    Lists all available agents in the project and searches for one
    matching the specified name. If not found, creates a new agent
    with the configured instructions and model.
    
    Args:
        client (AIProjectClient): The authenticated project client.
        agent_name (str): The name of the agent to find or create.
    
    Returns:
        Agent: The existing or newly created agent object.
    
    Raises:
        Exception: If agent creation fails.
    """
    # First, try to find existing agent
    agents = client.agents.list_agents()
    for agent in agents:
        if agent.name == agent_name:
            return agent, False  # Return agent and flag indicating it existed
    
    # Agent not found, create it
    print(f"  Agent '{agent_name}' not found. Creating new agent...")
    
    agent = client.agents.create_agent(
        model=MODEL_DEPLOYMENT,
        name=agent_name,
        instructions=AGENT_INSTRUCTIONS,
        tools=[{"type": "code_interpreter"}]  # Enable code interpreter for file generation
    )
    
    return agent, True  # Return agent and flag indicating it was created


def create_thread(client):
    """
    Create a new conversation thread.
    
    Creates a new thread in the Azure AI Foundry service to maintain
    conversation context between the user and the agent. Each thread
    represents an independent conversation session.
    
    Args:
        client (AIProjectClient): The authenticated project client.
    
    Returns:
        AgentThread: The newly created thread object.
    """
    thread = client.agents.threads.create()
    return thread


def send_message(client, thread_id, message):
    """
    Send a user message to the thread.
    
    Adds a new user message to the specified conversation thread.
    The message becomes part of the thread's history and will be
    processed when the agent is run.
    
    Args:
        client (AIProjectClient): The authenticated project client.
        thread_id (str): The unique identifier of the conversation thread.
        message (str): The text message content to send.
    
    Returns:
        ThreadMessage: The created message object.
    """
    thread_message = client.agents.messages.create(
        thread_id=thread_id,
        role=MessageRole.USER,
        content=message
    )
    return thread_message


def run_agent_and_wait(client, thread_id, agent_id):
    """
    Run the agent on the thread and wait for completion.
    
    Uses the SDK's create_and_process_run method which handles the
    polling internally, simplifying the code compared to manual polling.
    Displays a progress indicator while waiting.
    
    Args:
        client (AIProjectClient): The authenticated project client.
        thread_id (str): The unique identifier of the conversation thread.
        agent_id (str): The unique identifier of the agent to run.
    
    Returns:
        ThreadRun: The completed run object, or None if failed.
    """
    print("  Thinking...", end="", flush=True)
    
    # create_and_process handles polling internally
    run = client.agents.runs.create_and_process(
        thread_id=thread_id,
        agent_id=agent_id
    )
    
    print()  # New line after thinking
    
    if run.status == "completed":
        return run
    else:
        print(f"\n  Error: Run {run.status}")
        if run.last_error:
            print(f"  Details: {run.last_error}")
        return None


def get_last_response(client, thread_id):
    """
    Get the last assistant response from the thread.
    
    Retrieves all messages from the thread and extracts the most recent
    assistant response, including any file attachments generated by the
    code interpreter (e.g., charts, reports, data files).
    
    Args:
        client (AIProjectClient): The authenticated project client.
        thread_id (str): The unique identifier of the conversation thread.
    
    Returns:
        tuple: A tuple containing:
            - response_text (str): The text content of the assistant's response.
            - file_ids (list): List of file IDs for any generated files.
    """
    messages = client.agents.messages.list(thread_id=thread_id)
    
    response_text = "No response received"
    file_ids = []
    
    for msg in messages:
        if msg.role == MessageRole.AGENT:
            for content_item in msg.content:
                # Get text content
                if content_item.type == "text":
                    response_text = content_item.text.value
                    # Check for file annotations
                    if content_item.text.annotations:
                        for annotation in content_item.text.annotations:
                            if annotation.type == "file_path":
                                file_id = annotation.file_path.file_id
                                if file_id:
                                    file_ids.append(file_id)
            break  # Only get the most recent assistant message
    
    return response_text, file_ids


def download_file(client, file_id):
    """
    Download a file from the agent's sandbox.
    
    Retrieves a file generated by the agent's code interpreter and saves
    it to the current working directory. Common file types include charts
    (PNG), data exports (CSV, Excel), and text reports.
    
    Args:
        client (AIProjectClient): The authenticated project client.
        file_id (str): The unique identifier of the file to download.
    
    Returns:
        str: The absolute path where the file was saved locally.
    
    Raises:
        Exception: If the file cannot be retrieved or written to disk.
    """
    # Get file info
    file_info = client.agents.files.get(file_id=file_id)
    filename = file_info.filename or f"{file_id}.txt"
    
    # Extract just the filename from sandbox path
    filename = os.path.basename(filename)
    
    # Download file content
    file_content = client.agents.files.get_content(file_id=file_id)
    
    # Save to current directory
    output_path = os.path.join(os.getcwd(), filename)
    with open(output_path, "wb") as f:
        # file_content is a generator, iterate through it
        for chunk in file_content:
            f.write(chunk)
    
    return output_path


def delete_thread(client, thread_id):
    """
    Delete a conversation thread.
    
    Removes the specified thread and all its messages from the Azure AI
    Foundry service. This is called during cleanup to free resources.
    
    Args:
        client (AIProjectClient): The authenticated project client.
        thread_id (str): The unique identifier of the thread to delete.
    
    Note:
        This function does not raise exceptions on failure to allow
        graceful cleanup during error handling.
    """
    try:
        client.agents.threads.delete(thread_id=thread_id)
    except Exception:
        pass  # Ignore errors during cleanup


# =============================================================================
# MAIN CHAT LOOP
# =============================================================================

def main():
    """
    Main entry point for the interactive chat application.
    
    Orchestrates the entire chat session including:
    1. Creating the Azure AI Project client with authentication
    2. Finding or creating the configured expense agent
    3. Creating a new conversation thread
    4. Running an interactive loop for user input/agent responses
    5. Downloading any files generated by the agent
    6. Cleaning up the thread on exit
    
    The chat session continues until the user types 'quit'.
    """
    print("=" * 60)
    print("EXPENSE AGENT - INTERACTIVE CHAT (SDK Version)")
    print("=" * 60)
    print(f"\nConnecting to: {PROJECT_ENDPOINT}")
    print(f"Agent: {AGENT_NAME}")
    
    # Create project client
    print("\nInitializing client...")
    try:
        client = get_project_client()
        print("  ✓ Client initialized successfully")
    except Exception as e:
        print(f"  ✗ Client initialization failed: {e}")
        return
    
    # Get or create agent
    print("Finding agent...")
    try:
        agent, was_created = get_or_create_agent(client, AGENT_NAME)
        if was_created:
            print(f"  ✓ Created new agent: {agent.id}")
        else:
            print(f"  ✓ Found existing agent: {agent.id}")
    except Exception as e:
        print(f"  ✗ Failed to get or create agent: {e}")
        return
    
    # Create a thread for the conversation
    print("Creating conversation thread...")
    try:
        thread = create_thread(client)
        thread_id = thread.id
        print(f"  ✓ Thread created: {thread_id}")
    except Exception as e:
        print(f"  ✗ Failed to create thread: {e}")
        return
    
    print("\n" + "-" * 60)
    print("Chat started! Type 'quit' to exit.")
    print("-" * 60)
    
    try:
        while True:
            # Get user input
            print()
            user_input = input("You: ").strip()
            
            # Check for quit command
            if user_input.lower() == "quit":
                print("\nGoodbye!")
                break
            
            # Skip empty input
            if not user_input:
                continue
            
            try:
                # Send message
                send_message(client, thread_id, user_input)
                
                # Run the agent
                run_result = run_agent_and_wait(client, thread_id, agent.id)
                
                if run_result:
                    # Get and display response
                    response_text, file_ids = get_last_response(client, thread_id)
                    print(f"\nAgent: {response_text}")
                    
                    # Download any files the agent created
                    if file_ids:
                        print("\n   Downloading files...")
                        for file_id in file_ids:
                            try:
                                saved_path = download_file(client, file_id)
                                print(f"  ✓ Saved: {saved_path}")
                            except Exception as e:
                                print(f"  ✗ Failed to download {file_id}: {e}")
                
            except Exception as e:
                print(f"\n  Error: {e}")
    
    finally:
        # Clean up
        print("\nCleaning up...")
        delete_thread(client, thread_id)
        print("  ✓ Thread deleted")


if __name__ == "__main__":
    main()
