# Azure AI Foundry Agent - Interactive Chat
#
# This script provides an interactive terminal interface to chat with the expense-agent.
# Type 'quit' to exit.
#
# Prerequisites:
#    pip install azure-identity python-dotenv requests
#
# Required environment variables (see .env file):
#    AZURE_EXISTING_AIPROJECT_ENDPOINT - Foundry project endpoint

import os
import re
import time
import requests
from dotenv import load_dotenv
from azure.identity import AzureCliCredential

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================
PROJECT_ENDPOINT = os.getenv("AZURE_EXISTING_AIPROJECT_ENDPOINT")
AGENT_NAME = os.getenv("AZURE_EXISTING_AGENT_ID")
API_VERSION = os.getenv("AZURE_API_VERSION", "2025-05-01")

if not PROJECT_ENDPOINT or not AGENT_NAME:
    raise ValueError("Missing required environment variables: AZURE_EXISTING_AIPROJECT_ENDPOINT, AZURE_EXISTING_AGENT_ID")

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_access_token():
    """
    Get Azure AD access token for AI Foundry API.
    
    Authenticates using the Azure CLI credential, which requires the user
    to be logged in via 'az login'. The token is scoped for Azure AI services.
    
    Returns:
        str: The access token string to be used in API authorization headers.
    
    Raises:
        azure.identity.CredentialUnavailableError: If Azure CLI is not installed
            or user is not logged in.
    """
    credential = AzureCliCredential()
    token = credential.get_token("https://ai.azure.com/.default")
    return token.token

def get_headers(token):
    """
    Get HTTP headers for API requests.
    
    Constructs the standard headers required for Azure AI Foundry API calls,
    including Bearer token authorization and JSON content type.
    
    Args:
        token (str): The Azure AD access token.
    
    Returns:
        dict: A dictionary containing Authorization and Content-Type headers.
    """
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

def get_agent_id(token):
    """
    Get the agent ID by name.
    
    Queries the Azure AI Foundry API to list all available agents (assistants)
    and searches for the one matching the configured AGENT_NAME.
    
    Args:
        token (str): The Azure AD access token for API authentication.
    
    Returns:
        str: The unique identifier of the agent.
    
    Raises:
        ValueError: If no agent with the specified name is found.
        requests.HTTPError: If the API request fails.
    """
    headers = get_headers(token)
    url = f"{PROJECT_ENDPOINT}/assistants?api-version={API_VERSION}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    agents = response.json().get("data", [])
    for agent in agents:
        if agent.get("name") == AGENT_NAME:
            return agent["id"]
    
    raise ValueError(f"Agent '{AGENT_NAME}' not found")

def create_thread(token):
    """
    Create a new conversation thread.
    
    Creates a new thread in the Azure AI Foundry service to maintain
    conversation context between the user and the agent. Each thread
    represents an independent conversation session.
    
    Args:
        token (str): The Azure AD access token for API authentication.
    
    Returns:
        str: The unique identifier of the newly created thread.
    
    Raises:
        requests.HTTPError: If the API request fails.
    """
    headers = get_headers(token)
    url = f"{PROJECT_ENDPOINT}/threads?api-version={API_VERSION}"
    response = requests.post(url, headers=headers, json={})
    response.raise_for_status()
    return response.json()["id"]

def send_message(token, thread_id, message):
    """
    Send a message to the thread.
    
    Adds a new user message to the specified conversation thread.
    The message becomes part of the thread's history and will be
    processed when the agent is run.
    
    Args:
        token (str): The Azure AD access token for API authentication.
        thread_id (str): The unique identifier of the conversation thread.
        message (str): The text message content to send.
    
    Raises:
        requests.HTTPError: If the API request fails.
    """
    headers = get_headers(token)
    url = f"{PROJECT_ENDPOINT}/threads/{thread_id}/messages?api-version={API_VERSION}"
    body = {"role": "user", "content": message}
    response = requests.post(url, headers=headers, json=body)
    response.raise_for_status()

def run_agent(token, thread_id, agent_id):
    """
    Run the agent on the thread and wait for completion.
    
    Initiates an agent run on the specified thread and polls for completion.
    The agent processes all messages in the thread and generates a response.
    Displays a progress indicator (dots) while waiting.
    
    Args:
        token (str): The Azure AD access token for API authentication.
        thread_id (str): The unique identifier of the conversation thread.
        agent_id (str): The unique identifier of the agent to run.
    
    Returns:
        bool: True if the run completed successfully, False if it failed,
              was cancelled, expired, or timed out (2 minute limit).
    """
    headers = get_headers(token)
    
    # Start the run
    url = f"{PROJECT_ENDPOINT}/threads/{thread_id}/runs?api-version={API_VERSION}"
    body = {"assistant_id": agent_id}
    response = requests.post(url, headers=headers, json=body)
    response.raise_for_status()
    run_id = response.json()["id"]
    
    # Poll for completion
    status_url = f"{PROJECT_ENDPOINT}/threads/{thread_id}/runs/{run_id}?api-version={API_VERSION}"
    
    print("  Thinking", end="", flush=True)
    for _ in range(120):  # 2 minute timeout
        status_response = requests.get(status_url, headers=headers)
        status = status_response.json()
        
        if status.get("status") == "completed":
            print()  # New line after dots
            return True
        elif status.get("status") in ["failed", "cancelled", "expired"]:
            print()
            print(f"\n  Error: Run {status.get('status')}")
            if status.get("last_error"):
                print(f"  Details: {status.get('last_error')}")
            return False
        
        print(".", end="", flush=True)
        time.sleep(1)
    
    print("\n  Timeout waiting for response")
    return False

def get_last_response(token, thread_id):
    """
    Get the last assistant response from the thread.
    
    Retrieves all messages from the thread and extracts the most recent
    assistant response, including any file attachments generated by the
    code interpreter (e.g., charts, reports, data files).
    
    Args:
        token (str): The Azure AD access token for API authentication.
        thread_id (str): The unique identifier of the conversation thread.
    
    Returns:
        tuple: A tuple containing:
            - response_text (str): The text content of the assistant's response.
            - file_ids (list): List of file IDs for any generated files.
    
    Raises:
        requests.HTTPError: If the API request fails.
    """
    headers = get_headers(token)
    url = f"{PROJECT_ENDPOINT}/threads/{thread_id}/messages?api-version={API_VERSION}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    messages = response.json().get("data", [])
    response_text = "No response received"
    file_ids = []
    
    for msg in messages:
        if msg.get("role") == "assistant":
            content = msg.get("content", [])
            for item in content:
                # Get text content
                if item.get("type") == "text" and item.get("text", {}).get("value"):
                    response_text = item["text"]["value"]
                # Get file annotations (code interpreter outputs)
                annotations = item.get("text", {}).get("annotations", [])
                for ann in annotations:
                    if ann.get("type") == "file_path":
                        file_id = ann.get("file_path", {}).get("file_id")
                        if file_id:
                            file_ids.append(file_id)
            break
    
    return response_text, file_ids

def download_file(token, file_id):
    """
    Download a file from the agent's sandbox.
    
    Retrieves a file generated by the agent's code interpreter and saves
    it to the current working directory. Common file types include charts
    (PNG), data exports (CSV, Excel), and text reports.
    
    Args:
        token (str): The Azure AD access token for API authentication.
        file_id (str): The unique identifier of the file to download.
    
    Returns:
        str: The absolute path where the file was saved locally.
    
    Raises:
        requests.HTTPError: If the file info or content request fails.
        IOError: If the file cannot be written to disk.
    """
    headers = get_headers(token)
    
    # Get file info
    info_url = f"{PROJECT_ENDPOINT}/files/{file_id}?api-version={API_VERSION}"
    info_response = requests.get(info_url, headers=headers)
    info_response.raise_for_status()
    file_info = info_response.json()
    filename = file_info.get("filename", f"{file_id}.txt")
    
    # Extract just the filename from sandbox path (e.g., /mnt/data/file.txt -> file.txt)
    filename = os.path.basename(filename)
    
    # Download file content
    content_url = f"{PROJECT_ENDPOINT}/files/{file_id}/content?api-version={API_VERSION}"
    content_response = requests.get(content_url, headers=headers)
    content_response.raise_for_status()
    
    # Save to current directory
    output_path = os.path.join(os.getcwd(), filename)
    with open(output_path, "wb") as f:
        f.write(content_response.content)
    
    return output_path

def delete_thread(token, thread_id):
    """
    Delete a conversation thread.
    
    Removes the specified thread and all its messages from the Azure AI
    Foundry service. This is called during cleanup to free resources.
    
    Args:
        token (str): The Azure AD access token for API authentication.
        thread_id (str): The unique identifier of the thread to delete.
    
    Note:
        This function does not raise exceptions on failure to allow
        graceful cleanup during error handling.
    """
    headers = get_headers(token)
    url = f"{PROJECT_ENDPOINT}/threads/{thread_id}?api-version={API_VERSION}"
    requests.delete(url, headers=headers)

# =============================================================================
# MAIN CHAT LOOP
# =============================================================================

def main():
    """
    Main entry point for the interactive chat application.
    
    Orchestrates the entire chat session including:
    1. Authenticating with Azure using CLI credentials
    2. Finding the configured expense agent
    3. Creating a new conversation thread
    4. Running an interactive loop for user input/agent responses
    5. Downloading any files generated by the agent
    6. Cleaning up the thread on exit
    
    The chat session continues until the user types 'quit'.
    Token refresh is attempted automatically on API errors.
    """
    print("=" * 60)
    print("EXPENSE AGENT - INTERACTIVE CHAT")
    print("=" * 60)
    print(f"\nConnecting to: {PROJECT_ENDPOINT}")
    print(f"Agent: {AGENT_NAME}")
    
    # Authenticate
    print("\nAuthenticating...")
    try:
        token = get_access_token()
        print("  ✓ Authentication successful")
    except Exception as e:
        print(f"  ✗ Authentication failed: {e}")
        return
    
    # Get agent ID
    print("Finding agent...")
    try:
        agent_id = get_agent_id(token)
        print(f"  ✓ Found agent: {agent_id}")
    except Exception as e:
        print(f"  ✗ Agent not found: {e}")
        return
    
    # Create a thread for the conversation
    print("Creating conversation thread...")
    try:
        thread_id = create_thread(token)
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
                send_message(token, thread_id, user_input)
                
                # Run the agent
                if run_agent(token, thread_id, agent_id):
                    # Get and display response
                    response_text, file_ids = get_last_response(token, thread_id)
                    print(f"\nAgent: {response_text}")
                    
                    # Download any files the agent created
                    if file_ids:
                        print("\n   Downloading files...")
                        for file_id in file_ids:
                            try:
                                saved_path = download_file(token, file_id)
                                print(f"  ✓ Saved: {saved_path}")
                            except Exception as e:
                                print(f"  ✗ Failed to download {file_id}: {e}")
                
            except Exception as e:
                print(f"\n  Error: {e}")
                # Try to refresh token
                try:
                    token = get_access_token()
                except:
                    print("  Token refresh failed. Please restart.")
                    break
    
    finally:
        # Clean up
        print("\nCleaning up...")
        try:
            delete_thread(token, thread_id)
            print("  ✓ Thread deleted")
        except:
            pass

if __name__ == "__main__":
    main()
