# Azure AI Foundry Agent - Expense Assistant Deployment Script
#
# This script deploys an expense-agent to Azure AI Foundry programmatically.
#
# Steps performed:
#    Step 1: List existing agents - Checks what agents already exist in the project
#    Step 2: Create or get agent - Creates a new agent if it doesn't exist, or reuses existing one
#    Step 3: Upload policy file - Uploads Expenses_Policy.docx to the project
#    Step 4: Create or get vector store - Creates a vector store named "default" for file search
#    Step 5: Add file to vector store - Links the uploaded policy file to the vector store
#    Step 6: Update agent with tools - Enables file_search and code_interpreter tools on the agent
#    Step 7: Test the agent - Runs 3 test conversations to verify the agent works
#
# Prerequisites:
#    pip install azure-ai-projects azure-identity python-dotenv openai requests
#
# Required environment variables (see .env file):
#    AZURE_EXISTING_AIPROJECT_ENDPOINT - Foundry project endpoint
#    AZURE_EXISTING_AGENT_ID - Agent name (expense-agent)

import os
import json
import requests
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, AzureCliCredential
from azure.ai.projects import AIProjectClient

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# CONFIGURATION - Matching Readme.md values
# =============================================================================
PROJECT_ENDPOINT = os.getenv("AZURE_EXISTING_AIPROJECT_ENDPOINT")
AGENT_NAME = os.getenv("AZURE_EXISTING_AGENT_ID")

if not PROJECT_ENDPOINT or not AGENT_NAME:
    raise ValueError("Missing required environment variables: AZURE_EXISTING_AIPROJECT_ENDPOINT, AZURE_EXISTING_AGENT_ID")
MODEL_DEPLOYMENT = "gpt-4.1"
VECTOR_STORE_NAME = "default"
POLICY_FILE = "Expenses_Policy.docx"
API_VERSION = "2025-05-01"

AGENT_INSTRUCTIONS = """You are an AI assistant for corporate expenses. 
You answer questions about expenses based on the expenses policy data. 
If a user wants to submit an expense claim, you get their email address, 
a description of the claim, and the amount to be claimed and write the 
claim details to a text file that the user can download."""

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_access_token():
    """Get Azure AD access token for AI Foundry API."""
    credential = AzureCliCredential()
    token = credential.get_token("https://ai.azure.com/.default")
    return token.token

def get_headers(token):
    """Get HTTP headers for REST API calls."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

def api_call(method, endpoint, token, data=None, files=None):
    """Make REST API call to Foundry API."""
    headers = {"Authorization": f"Bearer {token}"}
    if data and not files:
        headers["Content-Type"] = "application/json"
        response = requests.request(method, endpoint, headers=headers, json=data)
    elif files:
        response = requests.request(method, endpoint, headers=headers, files=files, data=data)
    else:
        response = requests.request(method, endpoint, headers=headers)
    
    if response.status_code >= 400:
        print(f"  ⚠ Error {response.status_code}: {response.text}")
        return None
    
    if response.text:
        return response.json()
    return {}

# =============================================================================
# STEP 1: Check existing agents
# =============================================================================

def list_agents(token):
    """List all existing agents."""
    print("\n" + "="*60)
    print("STEP 1: Checking existing agents")
    print("="*60)
    
    url = f"{PROJECT_ENDPOINT}/assistants?api-version={API_VERSION}"
    result = api_call("GET", url, token)
    
    if result and "data" in result:
        agents = result["data"]
        print(f"  Found {len(agents)} existing agent(s):")
        for agent in agents:
            print(f"    - Name: '{agent['name']}', ID: {agent['id']}")
        return agents
    return []

# =============================================================================
# STEP 2: Create or get the agent
# =============================================================================

def create_or_get_agent(token, existing_agents):
    """Create new agent or return existing one."""
    print("\n" + "="*60)
    print("STEP 2: Create or get the expense-agent")
    print("="*60)
    
    # Check if agent already exists
    for agent in existing_agents:
        if agent["name"] == AGENT_NAME:
            print(f"  ✓ Agent '{AGENT_NAME}' already exists (ID: {agent['id']})")
            return agent
    
    # Create new agent
    print(f"  Creating new agent '{AGENT_NAME}'...")
    url = f"{PROJECT_ENDPOINT}/assistants?api-version={API_VERSION}"
    data = {
        "name": AGENT_NAME,
        "model": MODEL_DEPLOYMENT,
        "instructions": AGENT_INSTRUCTIONS
    }
    
    result = api_call("POST", url, token, data)
    if result:
        print(f"  ✓ Agent created successfully (ID: {result['id']})")
        return result
    
    raise Exception("Failed to create agent")

# =============================================================================
# STEP 3: Upload policy file
# =============================================================================

def upload_file(token):
    """Upload the Expenses_Policy.docx file."""
    print("\n" + "="*60)
    print("STEP 3: Upload policy file")
    print("="*60)
    
    # Check if file exists
    if not os.path.exists(POLICY_FILE):
        print(f"  ⚠ File '{POLICY_FILE}' not found in current directory")
        return None
    
    # List existing files to check if already uploaded
    url = f"{PROJECT_ENDPOINT}/files?api-version={API_VERSION}"
    result = api_call("GET", url, token)
    
    if result and "data" in result:
        for file in result["data"]:
            if file["filename"] == POLICY_FILE:
                print(f"  ✓ File '{POLICY_FILE}' already uploaded (ID: {file['id']})")
                return file
    
    # Upload the file
    print(f"  Uploading '{POLICY_FILE}'...")
    url = f"{PROJECT_ENDPOINT}/files?api-version={API_VERSION}"
    
    with open(POLICY_FILE, "rb") as f:
        files = {"file": (POLICY_FILE, f)}
        data = {"purpose": "assistants"}
        result = api_call("POST", url, token, data=data, files=files)
    
    if result:
        print(f"  ✓ File uploaded successfully (ID: {result['id']})")
        return result
    
    return None

# =============================================================================
# STEP 4: Create or get vector store
# =============================================================================

def create_or_get_vector_store(token):
    """Create or get the vector store."""
    print("\n" + "="*60)
    print("STEP 4: Create or get vector store")
    print("="*60)
    
    # List existing vector stores
    url = f"{PROJECT_ENDPOINT}/vector_stores?api-version={API_VERSION}"
    result = api_call("GET", url, token)
    
    if result and "data" in result:
        for vs in result["data"]:
            if vs["name"] == VECTOR_STORE_NAME:
                print(f"  ✓ Vector store '{VECTOR_STORE_NAME}' already exists (ID: {vs['id']})")
                return vs
    
    # Create new vector store
    print(f"  Creating vector store '{VECTOR_STORE_NAME}'...")
    url = f"{PROJECT_ENDPOINT}/vector_stores?api-version={API_VERSION}"
    data = {"name": VECTOR_STORE_NAME}
    
    result = api_call("POST", url, token, data)
    if result:
        print(f"  ✓ Vector store created (ID: {result['id']})")
        return result
    
    return None

# =============================================================================
# STEP 5: Add file to vector store
# =============================================================================

def add_file_to_vector_store(token, vector_store_id, file_id):
    """Add the uploaded file to the vector store."""
    print("\n" + "="*60)
    print("STEP 5: Add file to vector store")
    print("="*60)
    
    # Check if file is already in vector store
    url = f"{PROJECT_ENDPOINT}/vector_stores/{vector_store_id}/files?api-version={API_VERSION}"
    result = api_call("GET", url, token)
    
    if result and "data" in result:
        for file in result["data"]:
            if file["id"] == file_id:
                print(f"  ✓ File already in vector store")
                return file
    
    # Add file to vector store
    print(f"  Adding file to vector store...")
    url = f"{PROJECT_ENDPOINT}/vector_stores/{vector_store_id}/files?api-version={API_VERSION}"
    data = {"file_id": file_id}
    
    result = api_call("POST", url, token, data)
    if result:
        print(f"  ✓ File added to vector store (Status: {result.get('status', 'unknown')})")
        return result
    
    return None

# =============================================================================
# STEP 6: Update agent with tools (file_search + code_interpreter)
# =============================================================================

def update_agent_tools(token, agent_id, vector_store_id):
    """Update agent to enable file_search and code_interpreter tools."""
    print("\n" + "="*60)
    print("STEP 6: Update agent with tools")
    print("="*60)
    
    print("  Enabling file_search and code_interpreter tools...")
    url = f"{PROJECT_ENDPOINT}/assistants/{agent_id}?api-version={API_VERSION}"
    data = {
        "tools": [
            {"type": "file_search"},
            {"type": "code_interpreter"}
        ],
        "tool_resources": {
            "file_search": {
                "vector_store_ids": [vector_store_id]
            }
        }
    }
    
    result = api_call("POST", url, token, data)
    if result:
        tools = [t["type"] for t in result.get("tools", [])]
        print(f"  ✓ Agent updated with tools: {tools}")
        return result
    
    return None

# =============================================================================
# STEP 7: Test the agent
# =============================================================================

def test_agent(agent):
    """Test the deployed agent using REST API."""
    print("\n" + "="*60)
    print("STEP 7: Test the agent")
    print("="*60)
    
    token = get_access_token()
    headers = get_headers(token)
    
    def run_test(test_name, user_message):
        """Helper to run a single test with the agent."""
        print(f"\n  {test_name}")
        print("  " + "-"*40)
        
        try:
            # Create a thread
            thread_url = f"{PROJECT_ENDPOINT}/threads?api-version={API_VERSION}"
            thread_response = requests.post(thread_url, headers=headers, json={})
            thread_response.raise_for_status()
            thread = thread_response.json()
            thread_id = thread["id"]
            
            # Add the user message
            message_url = f"{PROJECT_ENDPOINT}/threads/{thread_id}/messages?api-version={API_VERSION}"
            message_body = {"role": "user", "content": user_message}
            requests.post(message_url, headers=headers, json=message_body)
            
            # Run the assistant
            run_url = f"{PROJECT_ENDPOINT}/threads/{thread_id}/runs?api-version={API_VERSION}"
            run_body = {"assistant_id": agent["id"]}
            run_response = requests.post(run_url, headers=headers, json=run_body)
            run_response.raise_for_status()
            run = run_response.json()
            run_id = run["id"]
            
            # Poll for completion (with timeout)
            import time
            for _ in range(60):  # 60 second timeout
                status_url = f"{PROJECT_ENDPOINT}/threads/{thread_id}/runs/{run_id}?api-version={API_VERSION}"
                status_response = requests.get(status_url, headers=headers)
                status = status_response.json()
                
                if status.get("status") in ["completed", "failed", "cancelled", "expired"]:
                    break
                time.sleep(1)
            
            if status.get("status") == "completed":
                # Get the messages
                messages_url = f"{PROJECT_ENDPOINT}/threads/{thread_id}/messages?api-version={API_VERSION}"
                messages_response = requests.get(messages_url, headers=headers)
                messages = messages_response.json()
                
                # Get the last assistant message
                for msg in messages.get("data", []):
                    if msg.get("role") == "assistant":
                        content = msg.get("content", [])
                        if content and content[0].get("text", {}).get("value"):
                            response_text = content[0]["text"]["value"]
                            # Truncate long responses
                            if len(response_text) > 500:
                                print(f"  Response: {response_text[:500]}...")
                            else:
                                print(f"  Response: {response_text}")
                        break
            else:
                print(f"  Run status: {status.get('status')}")
                if status.get("last_error"):
                    print(f"  Error: {status.get('last_error')}")
            
            # Clean up thread
            delete_url = f"{PROJECT_ENDPOINT}/threads/{thread_id}?api-version={API_VERSION}"
            requests.delete(delete_url, headers=headers)
            
        except Exception as e:
            print(f"  Error: {e}")
    
    # Test 1: Ask what the agent can help with
    run_test("Test 1: Agent capabilities", "Tell me what you can help with.")
    
    # Test 2: Ask about expense policy (file_search)
    run_test("Test 2: Expense policy question (file_search)", 
             "What is the maximum amount for meal expenses according to the policy?")
    
    # Test 3: Submit expense claim (code_interpreter)
    run_test("Test 3: Submit expense claim (code_interpreter)",
             "I need to submit an expense report for a business lunch that cost $65.50 on January 20, 2026. My email is john.doe@company.com.")

# =============================================================================
# MAIN DEPLOYMENT FLOW
# =============================================================================

def main():
    print("="*60)
    print("AZURE AI FOUNDRY - EXPENSE AGENT DEPLOYMENT")
    print("="*60)
    print(f"\nProject Endpoint: {PROJECT_ENDPOINT}")
    print(f"Agent Name: {AGENT_NAME}")
    print(f"Model: {MODEL_DEPLOYMENT}")
    
    # Get access token
    print("\nAuthenticating...")
    token = get_access_token()
    print("  ✓ Authentication successful")
    
    # Step 1: List existing agents
    existing_agents = list_agents(token)
    
    # Step 2: Create or get agent
    agent = create_or_get_agent(token, existing_agents)
    
    # Step 3: Upload policy file
    file_info = upload_file(token)
    
    if file_info:
        # Step 4: Create or get vector store
        vector_store = create_or_get_vector_store(token)
        
        if vector_store:
            # Step 5: Add file to vector store
            add_file_to_vector_store(token, vector_store["id"], file_info["id"])
            
            # Step 6: Update agent with tools
            update_agent_tools(token, agent["id"], vector_store["id"])
    
    # Step 7: Test the agent
    test_agent(agent)
    
    print("\n" + "="*60)
    print("DEPLOYMENT COMPLETE")
    print("="*60)
    print(f"\nAgent Details:")
    print(f"  Name: {agent['name']}")
    print(f"  ID: {agent['id']}")
    print(f"  Model: {agent['model']}")
    print(f"  Endpoint: {PROJECT_ENDPOINT}")

if __name__ == "__main__":
    main()



