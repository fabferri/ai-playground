from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import ListSortOrder, FilePurpose
import logging
import time
import json
from datetime import datetime

# Configure dual logging system
# Create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.propagate = False

# Remove any existing handlers
logger.handlers.clear()

# Create log filename with timestamp
log_filename = f"chat_session_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# File handler - captures all logs (DEBUG level)
file_handler = logging.FileHandler(log_filename, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Console handler - only essential information (INFO level)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Print log file location
print("="*70)
print("AI AGENT CHAT SESSION")
print("="*70)
print(f"Full logs: {log_filename}")
print("="*70 + "\n")

def load_init_config(config_file: str = "init.json") -> dict:
    """
    Load initial configuration from JSON file.
    
    Args:
        config_file (str): Path to the init configuration file (default: init.json)
        
    Returns:
        dict: Configuration dictionary with foundry_resource_name and foundry_project_name
              
    Raises:
        FileNotFoundError: If init.json file is not found
        ValueError: If required fields are missing in the configuration
    """
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        # Validate required fields for chat
        required_fields = [
            'foundry_resource_name', 
            'foundry_project_name'
        ]
        
        missing_fields = [field for field in required_fields if field not in config]
        if missing_fields:
            raise ValueError(f"Missing required fields in {config_file}: {missing_fields}")
        
        logger.debug(f"Configuration loaded from {config_file}")
        logger.debug(f"  Foundry Resource: {config['foundry_resource_name']}")
        logger.debug(f"  Project: {config['foundry_project_name']}")
        
        return config
        
    except FileNotFoundError:
        logger.error(f"ERROR: {config_file} not found in current directory")
        logger.error(f"Please create {config_file} with the following structure:")
        logger.error(json.dumps({
            "foundry_resource_name": "your-foundry-resource",
            "foundry_project_name": "your-project-name"
        }, indent=2))
        raise FileNotFoundError(f"{config_file} not found. Please create it with required configuration.")
    except json.JSONDecodeError as e:
        logger.error(f"ERROR: Invalid JSON in {config_file}: {str(e)}")
        raise ValueError(f"Invalid JSON format in {config_file}")
    except Exception as e:
        logger.error(f"ERROR: Failed to load configuration: {str(e)}")
        raise

def generate_foundry_endpoint(foundry_resource_name: str, foundry_project_name: str) -> str:
    """
    Generate the Azure AI Foundry project endpoint URL.
    
    Args:
        foundry_resource_name (str): The name of the AI Foundry resource
        foundry_project_name (str): The name of the AI Foundry project
    
    Returns:
        str: The complete AI Foundry project endpoint URL
    """
    endpoint = f"https://{foundry_resource_name}.services.ai.azure.com/api/projects/{foundry_project_name}"
    logger.debug(f"Generated AI Foundry endpoint: {endpoint}")
    return endpoint

def get_deployed_models_dynamically(project):
    """
    Dynamically query Azure AI Foundry to get actually deployed models.
    
    Args:
        project: AIProjectClient instance
        
    Returns:
        list: List of tuples (model_key, deployment_name, model_info) for deployed models
    """
    import re
    deployed_models = []
    
    try:
        logger.debug("Querying Azure AI Foundry for deployed models...")
        
        # Get list of deployments from Azure using the deployments API
        deployments = list(project.deployments.list())
        
        if deployments:
            for deployment in deployments:
                deployment_name = deployment.name if hasattr(deployment, 'name') else str(deployment)
                
                # Extract model information from deployment properties
                model_name = None
                model_format = 'OpenAI'
                sku_name = 'unknown'
                
                # Try to get model info from deployment properties
                if hasattr(deployment, 'properties') and deployment.properties:
                    props = deployment.properties
                    if hasattr(props, 'model') and props.model:
                        if hasattr(props.model, 'name'):
                            model_name = props.model.name
                        if hasattr(props.model, 'format'):
                            model_format = props.model.format
                
                # Get SKU info if available
                if hasattr(deployment, 'sku') and deployment.sku:
                    if hasattr(deployment.sku, 'name'):
                        sku_name = deployment.sku.name
                
                # If model name not in properties, extract from deployment name
                # Common patterns: "resource-gpt-4o-deployment", "fabfoundryresource1-gpt-4o-mini-deployment"
                if not model_name:
                    match = re.search(r'-(gpt-[^-]+(?:-[^-]+)?)-deployment', deployment_name)
                    if match:
                        model_name = match.group(1)
                        logger.debug(f"Extracted model name '{model_name}' from deployment name")
                    else:
                        # Fallback: use deployment name
                        model_name = deployment_name
                        logger.debug(f"Could not extract model name, using deployment name")
                
                model_info = {
                    'name': model_name,
                    'format': model_format,
                    'sku': sku_name
                }
                
                # Use model_name as key for consistency
                model_key = model_name
                
                deployed_models.append((model_key, deployment_name, model_info))
                logger.debug(f"Found deployed model: {model_key} -> {deployment_name} (SKU: {sku_name})")
        
        logger.info(f"Found {len(deployed_models)} deployed model(s) in Azure")
        
    except Exception as e:
        logger.warning(f"Could not dynamically fetch deployments: {str(e)}")
        logger.debug(f"Error details: {type(e).__name__}: {str(e)}")
        import traceback
        logger.debug(traceback.format_exc())
    
    return deployed_models

def select_model_interactive(deployed_models):
    """
    Allow user to select a model from available deployed models.
    
    Args:
        deployed_models (list): List of tuples (model_key, deployment_name, model_info)
        
    Returns:
        tuple: Selected (model_key, deployment_name, model_info) or None if cancelled
    """
    if not deployed_models:
        return None
    
    # If only one model, return it directly
    if len(deployed_models) == 1:
        model_key, deployment_name, model_info = deployed_models[0]
        logger.debug(f"Only one model available, auto-selecting: {deployment_name}")
        return deployed_models[0]
    
    # Multiple models available - show selection menu
    print("\n" + "="*70)
    print("MULTIPLE MODELS AVAILABLE")
    print("="*70)
    print("Please select which model you want to use for the chat session:\n")
    
    for idx, (model_key, deployment_name, model_info) in enumerate(deployed_models, 1):
        model_name = model_info.get('name', model_key)
        print(f"{idx}. {model_key}")
        print(f"   Model: {model_name}")
        print(f"   Deployment: {deployment_name}")
        print()
    
    print("-" * 70)
    
    # Get user selection
    while True:
        try:
            choice = input(f"Select model (1-{len(deployed_models)}) or 'q' to quit: ").strip().lower()
            
            if choice == 'q':
                print("Model selection cancelled.")
                return None
            
            choice_num = int(choice)
            if 1 <= choice_num <= len(deployed_models):
                selected = deployed_models[choice_num - 1]
                model_key, deployment_name, model_info = selected
                print(f"\nSelected: {model_key} ({deployment_name})")
                print("="*70 + "\n")
                return selected
            else:
                print(f"Please enter a number between 1 and {len(deployed_models)}")
        except ValueError:
            print(f"Invalid input. Please enter a number between 1 and {len(deployed_models)} or 'q' to quit.")
        except KeyboardInterrupt:
            print("\nModel selection cancelled.")
            return None

def handle_rate_limit_guidance():
    """
    Provide comprehensive guidance for rate limit and quota issues.
    """
    print("\n" + "="*60)
    print("RATE LIMIT / QUOTA GUIDANCE")
    print("="*60)
    print("If you're experiencing rate limits or quota issues:")
    print()
    print("IMMEDIATE ACTIONS:")
    print("1. Wait 10-30 seconds between requests")
    print("2. Avoid sending long or complex messages that require more tokens")
    print("3. Consider shorter conversation sessions")
    print()
    print("AZURE PORTAL CHECKS:")
    print("1. Check your Azure subscription quota:")
    print("   - Visit: https://portal.azure.com")
    print("   - Navigate to 'Subscriptions' → Your subscription")
    print("   - Go to 'Usage + quotas'")
    print("   - Search for 'Cognitive Services'")
    print()
    print("2. Monitor your token usage:")
    print("   - Visit Azure AI Foundry portal: https://ai.azure.com")
    print("   - Check your project's usage metrics")
    print("   - Review billing and usage reports")
    print()
    print("UPGRADE OPTIONS:")
    print("3. Consider upgrading your deployment:")
    print("   - Current: Standard SKU (capacity: 1)")
    print("   - Options: Increase capacity to 2-10 for higher throughput")
    print("   - Alternative: Use GlobalStandard SKU for better availability")
    print()
    print("4. Rate limiting is automatic in this app (1-second delays)")
    print("   - Longer waits after rate limit errors (10 seconds)")
    print("   - This helps prevent cascading failures")
    print("="*60 + "\n")

# Load and display project configuration
try:
    logger.debug("Loading AI Foundry project configuration from init.json...")
    init_config = load_init_config()
    
    # Generate endpoint dynamically
    foundry_resource_name = init_config['foundry_resource_name']
    foundry_project_name = init_config['foundry_project_name']
    endpoint = generate_foundry_endpoint(foundry_resource_name, foundry_project_name)
    
    # Display project info
    print("Project Configuration:")
    print(f"  Resource: {foundry_resource_name}")
    print(f"  Project: {foundry_project_name}")
    print(f"  Endpoint: {endpoint}")
    print()
    
    logger.info(f"Connecting to project: {foundry_project_name}")
    
except FileNotFoundError as e:
    logger.error(f"Configuration file not found: {str(e)}")
    print("\n" + "="*70)
    print("ERROR: init.json not found")
    print("="*70)
    print("\nPlease create init.json with the following structure:")
    print(json.dumps({
        "foundry_resource_name": "your-foundry-resource",
        "foundry_project_name": "your-project-name"
    }, indent=2))
    print("\nOr run '01_client.py' first to:")
    print("1. Create Azure AI Foundry project")
    print("2. Deploy models")
    print("="*70 + "\n")
    exit(1)
except Exception as e:
    logger.error(f"Configuration error: {str(e)}")
    print("\n" + "="*70)
    print(f"ERROR: Failed to load configuration")
    print("="*70)
    print(f"\nError details: {str(e)}")
    print("\nPlease check:")
    print("1. init.json exists in the current directory")
    print("2. The file has valid JSON format")
    print("3. Required fields are present (foundry_resource_name, foundry_project_name)")
    print("="*70 + "\n")
    import traceback
    traceback.print_exc()
    exit(1)

try:
    project = AIProjectClient(
        endpoint=endpoint,
        credential=DefaultAzureCredential(),
    )
    logger.info("Successfully connected to AI Foundry project")
except Exception as e:
    logger.error(f"Failed to connect to AI Foundry project: {str(e)}")
    print("\n" + "="*70)
    print("ERROR: Failed to connect to Azure AI Foundry")
    print("="*70)
    print(f"\nEndpoint: {endpoint}")
    print(f"Error: {str(e)}")
    print("\nPlease verify:")
    print("1. You are logged in to Azure (run: az login)")
    print("2. The endpoint URL is correct")
    print("3. Your Azure credentials have access to this project")
    print("="*70 + "\n")
    import traceback
    traceback.print_exc()
    exit(1)
    logger.info("Possible issues:")
    logger.info("1. The AI Foundry resource may not exist yet")
    logger.info("2. The resource may still be deploying")
    logger.info("3. Network connectivity issues")
    logger.info("4. Authentication problems")
    logger.info(f"Endpoint being used: {endpoint}")
    raise

# Pre-flight check: Verify models are available
logger.info("Checking for available models...")
try:
    deployments = list(project.deployments.list())
    if not deployments:
        print("\n" + "="*70)
        print("WARNING: NO MODELS DEPLOYED")
        print("="*70)
        print("Your Azure AI Foundry project has no deployed models.")
        print("AI agents require deployed models to function.")
        print("\nQUICK FIX:")
        print("1. Visit: https://ai.azure.com")
        print("2. Go to your project → 'Models + endpoints'")
        print("3. Deploy a GPT model (gpt-4o, gpt-4, or gpt-35-turbo)")
        print("4. Come back and run this script again")
        print("\nTIP: Run 'python discover_models.py' for detailed instructions")
        print("="*70)
        
        choice = input("\nContinue anyway? (y/N): ").strip().lower()
        if choice != 'y':
            print("Exiting. Please deploy models first.")
            exit(1)
    else:
        logger.debug(f"Found {len(deployments)} model deployment(s)")
except Exception as e:
    logger.warning(f"Could not check model deployments: {str(e)}")
    logger.debug("Proceeding anyway - will attempt to create agent...")

logger.debug("Querying Azure for deployed models...")
# Get deployed models dynamically from Azure
deployed_models = get_deployed_models_dynamically(project)

# Check if any models are available
if not deployed_models:
    logger.error("No deployed models found in configuration")
    print("\n" + "="*70)
    print("NO COMPATIBLE MODELS FOUND")
    print("="*70)
    print("Your Azure AI Foundry project doesn't have any deployed models.")
    print("\nTO FIX THIS:")
    print("1. Visit Azure AI Foundry portal: https://ai.azure.com")
    print("2. Navigate to your project:", foundry_project_name)
    print("3. Go to 'Models + endpoints' → 'Model deployments'")
    print("4. Click 'Deploy model' and select:")
    print("   - gpt-4o (recommended)")
    print("   - gpt-4o-mini (cost-effective)")
    print("   - gpt-35-turbo (fast)")
    print("5. Complete the deployment wizard")
    print("6. Run this script again")
    print("\nTIP: Run 'python 01_client.py' to deploy models automatically")
    print("="*70)
    exit(1)

# Allow user to select model if multiple are available
logger.info("Presenting model selection to user...")
selected_model = select_model_interactive(deployed_models)

if selected_model is None:
    logger.info("Model selection cancelled by user")
    print("Exiting...")
    exit(0)

model_key, deployment_name, model_info = selected_model

# Create agent with selected model
logger.debug(f"Creating AI agent with model: {deployment_name}")
agent = None
try:
    agent = project.agents.create_agent(
        model=deployment_name,
        name="my-agent",
        instructions="You are a helpful writing assistant"
    )
    logger.debug(f"Agent created successfully! Agent ID: {agent.id}")
    logger.info(f"Agent ready: {model_key}")
    print(f"Agent created with model: {model_key}")
    print(f"  Model name: {model_info.get('name', 'unknown')}")
    print()
except Exception as e:
    error_message = str(e)
    logger.error(f"Failed to create agent with model '{deployment_name}': {error_message}")
    print("\n" + "="*70)
    print("FAILED TO CREATE AGENT")
    print("="*70)
    print(f"Could not create agent with the selected model: {model_key}")
    print(f"Deployment name: {deployment_name}")
    print(f"\nError: {error_message}")
    print("\nPOSSIBLE CAUSES:")
    print("1. The model deployment may not be fully provisioned yet")
    print("2. There may be a temporary service issue")
    print("3. The deployment name may have changed")
    print("\nTO FIX THIS:")
    print("1. Wait a few minutes and try again (deployments can take time)")
    print("2. Visit Azure AI Foundry portal: https://ai.azure.com")
    print("3. Navigate to your project:", foundry_project_name)
    print("4. Verify the model deployment status in 'Models + endpoints'")
    print("5. Run 'python 01_client.py' to redeploy if needed")
    print("="*70)
    raise Exception(f"Unable to create AI agent with model {model_key}")

logger.debug("Creating conversation thread...")
thread = project.agents.threads.create()
logger.debug(f"Thread created: {thread.id}")

# Interactive chat loop
print("\n" + "="*60)
print("AI AGENT CHAT SESSION")
print("="*60)
print("Type your messages below. Press Ctrl+C to exit the chat.")
print("="*60 + "\n")

try:
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()
            
            # Skip empty messages
            if not user_input:
                continue
            
            # Handle help commands
            if user_input.lower() == "help quota":
                handle_rate_limit_guidance()
                continue
            elif user_input.lower() in ["help", "?"]:
                print("Available commands:")
                print("  help quota  - Show guidance for rate limits and quota issues")
                print("  Ctrl+C      - Exit the chat")
                print("  Otherwise, just type your message to chat with the AI agent")
                print()
                continue
                
            print()  # Add blank line for readability
            
            # Add moderate delay to prevent rapid-fire requests that could hit rate limits
            # This helps avoid overwhelming the Azure AI service
            time.sleep(1.0)  # Increased from 0.5 to 1.0 second
            
            # Send message to agent
            logger.debug("Sending message to agent...")
            message = project.agents.messages.create(
                thread_id=thread.id, 
                role="user", 
                content=user_input
            )

            # Process agent response
            logger.debug("Processing agent response...")
            run = project.agents.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)
            
            if run.status == "failed":
                error_details = str(run.last_error) if run.last_error else "Unknown error"
                logger.error(f"Agent run failed: {error_details}")
                
                # Enhanced error handling with specific guidance
                if "rate_limit_exceeded" in error_details.lower():
                    logger.warning("Rate limit exceeded - implementing exponential backoff...")
                    print("Agent: Rate limit reached. Waiting 10 seconds before you can send another message...")
                    print("TIP: Type 'help quota' for guidance on managing rate limits.")
                    # Implement exponential backoff - wait longer to avoid immediate re-triggering
                    time.sleep(10)  # Increased from 5 to 10 seconds
                elif "quota" in error_details.lower():
                    logger.error("Quota exceeded - check your Azure subscription limits")
                    print("Agent: Quota exceeded. Please check your Azure subscription limits.")
                    print("TIP: Type 'help quota' for detailed guidance.")
                elif "authentication" in error_details.lower():
                    logger.error("Authentication error - check your Azure credentials")
                    print("Agent: Authentication error. Please check your Azure credentials and permissions.")
                elif "network" in error_details.lower() or "timeout" in error_details.lower():
                    logger.error("Network or timeout error")
                    print("Agent: Network error occurred. Please check your internet connection and try again.")
                else:
                    logger.info("For rate limit issues, check your quota in Azure portal.")
                    print("Agent: Sorry, I encountered an error processing your message.")
                    print("TIP: Type 'help quota' if you're experiencing repeated issues.")
            else:
                logger.debug(f"Agent run completed with status: {run.status}")
                
                # Get the latest messages from the thread
                messages = project.agents.messages.list(thread_id=thread.id, order=ListSortOrder.DESCENDING)
                
                # Find and display the agent's response
                for message in messages:
                    if message.run_id == run.id and message.role == "assistant" and message.text_messages:
                        agent_response = message.text_messages[0].text.value
                        print(f"Agent: {agent_response}")
                        break
                        
            print()  # Add blank line for readability
            
        except EOFError:
            # Handle Ctrl+D on Unix systems
            print("\nExiting chat session...")
            break
            
except KeyboardInterrupt:
    # Handle Ctrl+C
    print("\n\nChat session interrupted by user.")
    print("Exiting gracefully...")

print("\n" + "="*60)
print("CHAT SESSION SUMMARY")
print("="*60)

# Get final message count
try:
    final_messages = project.agents.messages.list(thread_id=thread.id)
    message_count = len([msg for msg in final_messages if msg.text_messages])
    print(f"Total messages exchanged: {message_count}")
    print(f"Thread ID: {thread.id}")
    print(f"Agent ID: {agent.id}")
except Exception as e:
    logger.warning(f"Could not retrieve message count: {str(e)}")

print("="*60)

# Delete the agent once done
logger.debug("Cleaning up agent and resources...")
try:
    project.agents.delete_agent(agent.id)
    logger.debug("Agent deleted successfully")
    print("Chat session ended. Agent resources cleaned up.")
except Exception as e:
    logger.error(f"Error cleaning up agent: {str(e)}")
    print("Chat session ended. Note: Agent cleanup may have failed.")

print("Thank you for using the AI Agent Chat!")