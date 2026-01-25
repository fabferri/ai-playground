# Azure AI Foundry Agent - Expense Assistant Deployment Script (SDK Version)
#
# This script deploys an expense-agent to Azure AI Foundry using the SDK.
# It performs the same steps as expense.py but uses the Azure AI Projects SDK
# instead of direct REST API calls.
#
# Steps performed:
#    Step 1: List existing agents - Checks what agents already exist in the project
#    Step 2: Delete and recreate agent - Deletes existing agent if found, then creates a new one
#    Step 3: Upload policy file - Uploads Expenses_Policy.docx to the project
#    Step 4: Create or get vector store - Creates a vector store named "default" for file search
#    Step 5: Add file to vector store - Links the uploaded policy file to the vector store
#    Step 6: Update agent with tools - Enables file_search and code_interpreter tools on the agent
#    Step 7: Test the agent - Runs 3 test conversations to verify the agent works
#
# Prerequisites:
#    pip install azure-ai-projects azure-identity python-dotenv
#
# Required environment variables (see .env file):
#    AZURE_EXISTING_AIPROJECT_ENDPOINT - Foundry project endpoint
#    AZURE_EXISTING_AGENT_ID - Agent name (expense-agent)

import os
import time
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import (
    MessageRole,
    FileSearchToolDefinition,
    CodeInterpreterToolDefinition,
    ToolResources,
    FileSearchToolResource
)

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================
PROJECT_ENDPOINT = os.getenv("AZURE_EXISTING_AIPROJECT_ENDPOINT")
AGENT_NAME = os.getenv("AZURE_EXISTING_AGENT_ID")
MODEL_DEPLOYMENT = os.getenv("AZURE_MODEL_DEPLOYMENT", "gpt-4.1")

if not PROJECT_ENDPOINT or not AGENT_NAME:
    raise ValueError("Missing required environment variables: AZURE_EXISTING_AIPROJECT_ENDPOINT, AZURE_EXISTING_AGENT_ID")

VECTOR_STORE_NAME = "default"
POLICY_FILE = "Expenses_Policy.docx"

AGENT_INSTRUCTIONS = """You are an AI assistant for corporate expenses. 
You answer questions about expenses based on the expenses policy data. 
If a user wants to submit an expense claim, you get their email address, 
a description of the claim, and the amount to be claimed and write the 
claim details to a text file that the user can download."""

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_project_client():
    """Create and return an Azure AI Project client."""
    credential = DefaultAzureCredential()
    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=credential
    )
    return client

# =============================================================================
# STEP 1: Check existing agents
# =============================================================================

def list_agents(client):
    """List all existing agents."""
    print("\n" + "="*60)
    print("STEP 1: Checking existing agents")
    print("="*60)
    
    agents = list(client.agents.list_agents())
    print(f"  Found {len(agents)} existing agent(s):")
    for agent in agents:
        print(f"    - Name: '{agent.name}', ID: {agent.id}")
    return agents

# =============================================================================
# STEP 2: Delete existing agent and create new one
# =============================================================================

def create_agent(client, existing_agents):
    """Delete existing agent if found, then create a new one."""
    print("\n" + "="*60)
    print("STEP 2: Delete existing agent and create new one")
    print("="*60)
    
    # Check if agent already exists and delete it
    for agent in existing_agents:
        if agent.name == AGENT_NAME:
            print(f"  Found existing agent '{AGENT_NAME}' (ID: {agent.id})")
            print(f"  Deleting existing agent...")
            try:
                client.agents.delete_agent(agent_id=agent.id)
                print(f"  ✓ Existing agent deleted")
            except Exception as e:
                print(f"   Failed to delete agent: {e}")
            break
    
    # Create new agent
    print(f"  Creating new agent '{AGENT_NAME}'...")
    agent = client.agents.create_agent(
        model=MODEL_DEPLOYMENT,
        name=AGENT_NAME,
        instructions=AGENT_INSTRUCTIONS
    )
    print(f"  ✓ Agent created successfully (ID: {agent.id})")
    return agent

# =============================================================================
# STEP 3: Upload policy file
# =============================================================================

def upload_file(client):
    """Upload the Expenses_Policy.docx file."""
    print("\n" + "="*60)
    print("STEP 3: Upload policy file")
    print("="*60)
    
    # Check if file exists locally
    if not os.path.exists(POLICY_FILE):
        print(f"  ⚠ File '{POLICY_FILE}' not found in current directory")
        return None
    
    # List existing files to check if already uploaded
    existing_files = client.agents.files.list()
    for file in existing_files:
        # Handle both object and dict responses
        if hasattr(file, 'filename'):
            file_name = file.filename
            file_id = file.id
        elif isinstance(file, dict):
            file_name = file.get('filename')
            file_id = file.get('id')
        else:
            # If it's just a string ID, we need to get the file details
            try:
                file_details = client.agents.files.retrieve(file)
                file_name = file_details.filename if hasattr(file_details, 'filename') else None
                file_id = file
            except:
                continue
        
        if file_name == POLICY_FILE:
            print(f"  ✓ File '{POLICY_FILE}' already uploaded (ID: {file_id})")
            # Return the file object or create a simple object with the id
            return file if hasattr(file, 'id') else type('File', (), {'id': file_id, 'filename': file_name})()
    
    # Upload the file
    print(f"  Uploading '{POLICY_FILE}'...")
    with open(POLICY_FILE, "rb") as f:
        file_info = client.agents.files.upload(
            file=f,
            purpose="assistants"
        )
    print(f"  ✓ File uploaded successfully (ID: {file_info.id})")
    return file_info

# =============================================================================
# STEP 4: Create or get vector store
# =============================================================================

def create_or_get_vector_store(client):
    """Create or get the vector store."""
    print("\n" + "="*60)
    print("STEP 4: Create or get vector store")
    print("="*60)
    
    # List existing vector stores
    existing_stores = list(client.agents.vector_stores.list())
    for vs in existing_stores:
        if vs.name == VECTOR_STORE_NAME:
            print(f"  ✓ Vector store '{VECTOR_STORE_NAME}' already exists (ID: {vs.id})")
            return vs
    
    # Create new vector store
    print(f"  Creating vector store '{VECTOR_STORE_NAME}'...")
    vector_store = client.agents.vector_stores.create(
        name=VECTOR_STORE_NAME
    )
    print(f"  ✓ Vector store created (ID: {vector_store.id})")
    return vector_store

# =============================================================================
# STEP 5: Add file to vector store
# =============================================================================

def add_file_to_vector_store(client, vector_store_id, file_id):
    """Add the uploaded file to the vector store."""
    print("\n" + "="*60)
    print("STEP 5: Add file to vector store")
    print("="*60)
    
    # Check if file is already in vector store
    existing_files = list(client.agents.vector_store_files.list(vector_store_id=vector_store_id))
    for file in existing_files:
        if file.id == file_id:
            print(f"  ✓ File already in vector store")
            return file
    
    # Add file to vector store
    print(f"  Adding file to vector store...")
    result = client.agents.vector_store_files.create(
        vector_store_id=vector_store_id,
        file_id=file_id
    )
    print(f"  ✓ File added to vector store (Status: {result.status})")
    return result

# =============================================================================
# STEP 6: Update agent with tools (file_search + code_interpreter)
# =============================================================================

def update_agent_tools(client, agent_id, vector_store_id):
    """Update agent to enable file_search and code_interpreter tools."""
    print("\n" + "="*60)
    print("STEP 6: Update agent with tools")
    print("="*60)
    
    print("  Enabling file_search and code_interpreter tools...")
    updated_agent = client.agents.update_agent(
        agent_id=agent_id,
        tools=[
            FileSearchToolDefinition(),
            CodeInterpreterToolDefinition()
        ],
        tool_resources=ToolResources(
            file_search=FileSearchToolResource(
                vector_store_ids=[vector_store_id]
            )
        )
    )
    
    tools = [t.type for t in updated_agent.tools] if updated_agent.tools else []
    print(f"  ✓ Agent updated with tools: {tools}")
    return updated_agent

# =============================================================================
# STEP 7: Test the agent
# =============================================================================

def test_agent(client, agent):
    """Test the deployed agent using SDK."""
    print("\n" + "="*60)
    print("STEP 7: Test the agent")
    print("="*60)
    
    def run_test(test_name, user_message):
        """Helper to run a single test with the agent."""
        print(f"\n  {test_name}")
        print("  " + "-"*40)
        
        try:
            # Create a thread
            thread = client.agents.threads.create()
            thread_id = thread.id
            
            # Add the user message
            client.agents.messages.create(
                thread_id=thread_id,
                role=MessageRole.USER,
                content=user_message
            )
            
            # Run the agent and wait for completion
            run = client.agents.runs.create_and_process(
                thread_id=thread_id,
                agent_id=agent.id
            )
            
            if run.status == "completed":
                # Get the messages
                messages = client.agents.messages.list(thread_id=thread_id)
                
                # Get the last assistant message
                for msg in messages:
                    if msg.role == MessageRole.AGENT:
                        for content_item in msg.content:
                            if content_item.type == "text":
                                response_text = content_item.text.value
                                # Truncate long responses
                                if len(response_text) > 500:
                                    print(f"  Response: {response_text[:500]}...")
                                else:
                                    print(f"  Response: {response_text}")
                        break
            else:
                print(f"  Run status: {run.status}")
                if run.last_error:
                    print(f"  Error: {run.last_error}")
            
            # Clean up thread
            client.agents.threads.delete(thread_id=thread_id)
            
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
    print("AZURE AI FOUNDRY - EXPENSE AGENT DEPLOYMENT (SDK)")
    print("="*60)
    print(f"\nProject Endpoint: {PROJECT_ENDPOINT}")
    print(f"Agent Name: {AGENT_NAME}")
    print(f"Model: {MODEL_DEPLOYMENT}")
    
    # Create project client
    print("\nInitializing client...")
    try:
        client = get_project_client()
        print("  ✓ Client initialized successfully")
    except Exception as e:
        print(f"  ✗ Client initialization failed: {e}")
        return
    
    # Step 1: List existing agents
    existing_agents = list_agents(client)
    
    # Step 2: Delete existing and create new agent
    agent = create_agent(client, existing_agents)
    
    # Step 3: Upload policy file
    file_info = upload_file(client)
    
    if file_info:
        # Step 4: Create or get vector store
        vector_store = create_or_get_vector_store(client)
        
        if vector_store:
            # Step 5: Add file to vector store
            add_file_to_vector_store(client, vector_store.id, file_info.id)
            
            # Step 6: Update agent with tools
            update_agent_tools(client, agent.id, vector_store.id)
    
    # Step 7: Test the agent
    test_agent(client, agent)
    
    print("\n" + "="*60)
    print("DEPLOYMENT COMPLETE")
    print("="*60)
    print(f"\nAgent Details:")
    print(f"  Name: {agent.name}")
    print(f"  ID: {agent.id}")
    print(f"  Model: {agent.model}")
    print(f"  Endpoint: {PROJECT_ENDPOINT}")

if __name__ == "__main__":
    main()
