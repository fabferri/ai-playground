"""
Azure AI Foundry Client - Multi-Model Deployment Support

This script creates an Azure AI Foundry resource and project, then deploys multiple OpenAI models
including GPT-4o, GPT-4o Mini, GPT-4, and GPT-3.5 Turbo in a parametric, configurable way.

Key Features:
- Support for multiple OpenAI models natively supported in Azure AI Foundry
- Parametric configuration for easy model selection
- Automatic deployment with proper error handling
- Configuration persistence for other scripts

Usage Examples:

1. Deploy both GPT-4o and GPT-4o Mini:
   MODELS_TO_DEPLOY = ["gpt-4o", "gpt-4o-mini"]

2. Deploy only GPT-4o:
   MODELS_TO_DEPLOY = ["gpt-4o"]

3. Deploy GPT-3.5 Turbo:
   MODELS_TO_DEPLOY = ["gpt-35-turbo"]

4. Add custom model programmatically:
   add_custom_model("my-gpt4", {
       "name": "gpt-4",
       "version": "1106-preview", 
       "format": "OpenAI",
       "sku": {"name": "Standard", "capacity": 1},
       "deployment_suffix": "my-gpt4-deployment"
   })

5. Configure models at runtime:
   configure_models_to_deploy(["gpt-4o"])
"""

from azure.identity import DefaultAzureCredential
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.resource import ResourceManagementClient
import logging
import json
import requests
import time
import signal
import sys
import datetime

# Configure logging - full logs to file, essential info to console
log_filename = f"deployment_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# File handler - captures ALL logs (DEBUG level)
file_handler = logging.FileHandler(log_filename, mode='w', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# Console handler - only essential info (INFO level)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(message)s')
console_handler.setFormatter(console_formatter)

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Prevent propagation to root logger to avoid duplicate messages
logger.propagate = False

# Signal handler for graceful exit on CTRL-C
def signal_handler(sig, frame):
    """Handle CTRL-C gracefully"""
    logger.info("\n\n" + "=" * 60)
    logger.info("OPERATION CANCELLED BY USER (CTRL-C)")
    logger.info("=" * 60)
    logger.info(f"Full logs saved to: {log_filename}")
    logger.info("Exiting gracefully...")
    sys.exit(0)

# Register signal handler
signal.signal(signal.SIGINT, signal_handler)

# Load configuration from init.json
def load_init_config(config_file: str = "init.json") -> dict:
    """
    Load initial deployment configuration from JSON file.
    
    Args:
        config_file (str): Path to the init configuration file (default: init.json)
        
    Returns:
        dict: Configuration dictionary with subscription_name, resource_group_name, 
              foundry_resource_name, foundry_project_name, and location
              
    Raises:
        FileNotFoundError: If init.json file is not found
        ValueError: If required fields are missing in the configuration
    """
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        # Validate required fields
        required_fields = [
            'subscription_name', 
            'resource_group_name', 
            'foundry_resource_name', 
            'foundry_project_name', 
            'location'
        ]
        
        missing_fields = [field for field in required_fields if field not in config]
        if missing_fields:
            raise ValueError(f"Missing required fields in {config_file}: {missing_fields}")
        
        logger.debug(f"Configuration loaded from {config_file}")
        logger.debug(f"  Subscription: {config['subscription_name']}")
        logger.debug(f"  Resource Group: {config['resource_group_name']}")
        logger.debug(f"  Foundry Resource: {config['foundry_resource_name']}")
        logger.debug(f"  Project: {config['foundry_project_name']}")
        logger.debug(f"  Location: {config['location']}")
        
        return config
        
    except FileNotFoundError:
        logger.error(f"ERROR: {config_file} not found in current directory")
        logger.error(f"Please create {config_file} with the following structure:")
        logger.error(json.dumps({
            "subscription_name": "your-subscription-name",
            "resource_group_name": "your-resource-group",
            "foundry_resource_name": "your-foundry-resource",
            "foundry_project_name": "your-project-name",
            "location": "your-azure-region"
        }, indent=2))
        raise FileNotFoundError(f"{config_file} not found. Please create it with required configuration.")
    except json.JSONDecodeError as e:
        logger.error(f"ERROR: Invalid JSON in {config_file}: {str(e)}")
        raise ValueError(f"Invalid JSON format in {config_file}")
    except Exception as e:
        logger.error(f"ERROR: Failed to load configuration: {str(e)}")
        raise

# Load configuration from init.json
try:
    init_config = load_init_config()
    subscription_name = init_config['subscription_name']
    resource_group_name = init_config['resource_group_name']
    foundry_resource_name = init_config['foundry_resource_name']
    foundry_project_name = init_config['foundry_project_name']
    location = init_config['location']
except Exception as e:
    logger.error(f"Failed to load init.json: {str(e)}")
    logger.info(f"Full logs saved to: {log_filename}")
    sys.exit(1)

# Model configurations - supports multiple models with their specific parameters
# Only OpenAI models natively supported in Azure AI Foundry
SUPPORTED_MODELS = {
    "gpt-4o": {
        "name": "gpt-4o",
        "version": "2024-11-20",
        "format": "OpenAI",
        "sku": {"name": "Standard", "capacity": 1},
        "deployment_suffix": "gpt-4o-deployment",
        "status": "available"
    },
    "gpt-4o-mini": {
        "name": "gpt-4o-mini",
        "version": "2024-07-18",
        "format": "OpenAI",
        "sku": {"name": "GlobalStandard", "capacity": 1},
        "deployment_suffix": "gpt-4o-mini-deployment",
        "status": "available",
        "note": "Uses GlobalStandard SKU for UK South region compatibility"
    },
    "gpt-4.1": {
        "name": "gpt-4",
        "version": "turbo-2024-04-09", 
        "format": "OpenAI",
        "sku": {"name": "GlobalStandard", "capacity": 1},
        "deployment_suffix": "gpt-4-turbo-deployment",
        "status": "available",
        "note": "GPT-4 Turbo GA model - uses GlobalStandard SKU for better regional availability"
    },
    "gpt-35-turbo": {
        "name": "gpt-35-turbo",
        "version": "0125",
        "format": "OpenAI", 
        "sku": {"name": "Standard", "capacity": 1},
        "deployment_suffix": "gpt35-turbo-deployment",
        "status": "available"
    }
}

# Models to deploy - modify this list to choose which models to deploy
# Available options: ["gpt-4o"], ["gpt-4o-mini"], ["gpt-4.1"], ["gpt-35-turbo"] or combinations
# All models use OpenAI format and are natively supported in Azure AI Foundry
MODELS_TO_DEPLOY = ["gpt-4o"]  

def configure_models_to_deploy(models: list = None, interactive: bool = False):
    """
    Configure which models to deploy. 
    
    Args:
        models (list): List of model keys to deploy. If None, uses interactive selection.
        interactive (bool): If True, prompts user for model selection
        
    Returns:
        list: Updated list of models to deploy
    """
    global MODELS_TO_DEPLOY
    
    if models is not None:
        # Validate provided models
        invalid_models = [m for m in models if m not in SUPPORTED_MODELS]
        if invalid_models:
            raise ValueError(f"Invalid models: {invalid_models}. Available: {list(SUPPORTED_MODELS.keys())}")
        MODELS_TO_DEPLOY = models
        logger.info(f"Models configured for deployment: {MODELS_TO_DEPLOY}")
        return MODELS_TO_DEPLOY
    
    if interactive:
        return interactive_model_selection()
    
    # Display current configuration
    logger.info("Available models:")
    for i, (key, config) in enumerate(SUPPORTED_MODELS.items(), 1):
        status = "SELECTED" if key in MODELS_TO_DEPLOY else "AVAILABLE"
        logger.info(f"  [{status}] {i}. {key} - {config['name']} ({config['version']})")
    
    return MODELS_TO_DEPLOY

def interactive_model_selection(show_availability_note: bool = True):
    """
    Interactive model selection for the user.
    
    Args:
        show_availability_note (bool): Show note about dynamic availability checking
    
    Returns:
        list: Selected models to deploy
    """
    global MODELS_TO_DEPLOY
    
    print("\n" + "=" * 60)
    print("MODEL SELECTION FOR DEPLOYMENT")
    print("=" * 60)
    if show_availability_note:
        print("Availability status has been checked dynamically")
    print("\nAvailable models:")
    print()
    
    model_keys = list(SUPPORTED_MODELS.keys())
    for i, key in enumerate(model_keys, 1):
        config = SUPPORTED_MODELS[key]
        status = config.get('status', 'unknown')
        if status == 'available':
            status_indicator = "[AVAILABLE]"
        elif status == 'not_supported':
            status_indicator = "[NOT SUPPORTED]"
        elif status == 'not_available_region':
            status_indicator = "[REGION LIMITED]"
        else:
            status_indicator = "[? UNKNOWN]"
        
        print(f"{i}. {key:20s} {status_indicator}")
        print(f"   Model: {config['name']} (Version: {config['version']})")
        print(f"   Format: {config['format']}")
        
        if 'note' in config:
            print(f"   Note: {config['note']}")
        elif status == 'not_supported':
            print(f"   Note: Not currently supported in Azure AI Foundry")
        elif status == 'not_available_region':
            print(f"   Note: Not available in current region")
        print()
    
    print("-" * 60)
    print("Quick options:")
    print(f"{len(model_keys) + 1}. Deploy ALL AVAILABLE models")
    print(f"{len(model_keys) + 2}. Use current configuration: {MODELS_TO_DEPLOY}")
    print("-" * 60)
    
    while True:
        try:
            print("\n" + "=" * 60)
            print("How to select:")
            print("  • Single model: Enter a number (e.g., 1)")
            print("  • Multiple models: Enter numbers separated by commas (e.g., 1,2,4)")
            print("  • All models: Enter 'all' or quick option number")
            print("  • Default: Press Enter to use current configuration")
            print("  • Cancel: Press CTRL-C")
            print("=" * 60)
            
            user_input = input("\nYour selection: ").strip()
            
            if not user_input:
                # Use current configuration
                print(f"\nUsing current configuration: {MODELS_TO_DEPLOY}")
                print(f"  Total models selected: {len(MODELS_TO_DEPLOY)}")
                return MODELS_TO_DEPLOY
            
            if user_input.lower() == 'all' or user_input == str(len(model_keys) + 1):
                # Deploy all models
                MODELS_TO_DEPLOY = list(SUPPORTED_MODELS.keys())
                print(f"\nSelected ALL models: {MODELS_TO_DEPLOY}")
                print(f"  Total models selected: {len(MODELS_TO_DEPLOY)}")
                return MODELS_TO_DEPLOY
            
            if user_input == str(len(model_keys) + 2):
                # Use current configuration
                print(f"\nUsing current configuration: {MODELS_TO_DEPLOY}")
                print(f"  Total models selected: {len(MODELS_TO_DEPLOY)}")
                return MODELS_TO_DEPLOY
            
            # Parse individual selections
            selections = [int(x.strip()) for x in user_input.split(',')]
            selected_models = []
            
            print()  # Add spacing
            for selection in selections:
                if 1 <= selection <= len(model_keys):
                    model_key = model_keys[selection - 1]
                    selected_models.append(model_key)
                    print(f"  Added: {model_key}")
                else:
                    print(f"  Invalid selection: {selection}")
                    raise ValueError("Invalid selection")
            
            if selected_models:
                MODELS_TO_DEPLOY = selected_models
                print(f"\nFinal selection: {MODELS_TO_DEPLOY}")
                print(f"  Total models selected: {len(MODELS_TO_DEPLOY)}")
                return MODELS_TO_DEPLOY
            else:
                print("\nNo models selected. Please try again.")
                
        except KeyboardInterrupt:
            # CTRL-C pressed during input
            logger.info("\n\nOperation cancelled by user")
            sys.exit(0)
        except (ValueError, IndexError) as e:
            print(f"\nInvalid input: {str(e)}")
            print("Please enter valid numbers separated by commas (e.g., 1,2,3), 'all', or press Enter.")
            print("Press CTRL-C to cancel.\n")
            continue

def add_custom_model(model_key: str, model_config: dict):
    """
    Add a custom model configuration to the supported models.
    
    Args:
        model_key (str): Unique identifier for the model
        model_config (dict): Model configuration with required fields:
            - name: Model name
            - version: Model version
            - format: Model format (OpenAI, Anthropic, etc.)
            - sku: SKU configuration with name and capacity
            - deployment_suffix: Suffix for deployment naming
    
    Example:
        add_custom_model("my-custom-gpt", {
            "name": "gpt-4",
            "version": "1106-preview",
            "format": "OpenAI",
            "sku": {"name": "Standard", "capacity": 2},
            "deployment_suffix": "my-gpt4-deployment"
        })
    """
    required_fields = ["name", "version", "format", "sku", "deployment_suffix"]
    missing_fields = [field for field in required_fields if field not in model_config]
    
    if missing_fields:
        raise ValueError(f"Missing required fields in model_config: {missing_fields}")
    
    if "name" not in model_config["sku"] or "capacity" not in model_config["sku"]:
        raise ValueError("sku must contain 'name' and 'capacity' fields")
    
    SUPPORTED_MODELS[model_key] = model_config
    logger.info(f"Added custom model: {model_key}")
    
    return model_config

def get_subscription_id_by_name(subscription_name: str, credential=None) -> str:
    """
    Retrieve Azure subscription ID by subscription display name.
    
    Args:
        subscription_name (str): The display name of the Azure subscription
        credential: Azure credential object (optional, defaults to DefaultAzureCredential)
    
    Returns:
        str: The subscription ID
        
    Raises:
        ValueError: If subscription name is not found or multiple matches exist
        Exception: For authentication or Azure API errors
    """
    if not credential:
        credential = DefaultAzureCredential()
    
    try:
        # Create subscription client
        subscription_client = SubscriptionClient(credential=credential)
        
        logger.debug(f"Searching for subscription with name: '{subscription_name}'")
        
        # List all subscriptions and find matching name
        matching_subscriptions = []
        for subscription in subscription_client.subscriptions.list():
            if subscription.display_name and subscription.display_name.lower() == subscription_name.lower():
                matching_subscriptions.append(subscription)
                logger.debug(f"Found matching subscription: {subscription.display_name} (ID: {subscription.subscription_id})")
        
        # Validate results
        if len(matching_subscriptions) == 0:
            available_subs = [sub.display_name for sub in subscription_client.subscriptions.list() if sub.display_name]
            raise ValueError(f"No subscription found with name '{subscription_name}'. Available subscriptions: {available_subs}")
        
        if len(matching_subscriptions) > 1:
            sub_ids = [sub.subscription_id for sub in matching_subscriptions]
            raise ValueError(f"Multiple subscriptions found with name '{subscription_name}': {sub_ids}")
        
        subscription_id = matching_subscriptions[0].subscription_id
        logger.debug(f"Successfully retrieved subscription ID: {subscription_id}")
        return subscription_id
        
    except ValueError:
        # Re-raise validation errors
        raise
    except Exception as e:
        logger.error(f"Error retrieving subscription ID: {str(e)}")
        raise Exception(f"Failed to retrieve subscription ID for '{subscription_name}': {str(e)}")

def ensure_cognitive_services_resource_exists(subscription_id: str, resource_group_name: str, 
                                            foundry_resource_name: str, location: str, credential=None):
    """
    Ensure that a Cognitive Services resource exists, creating it if necessary.
    
    Args:
        subscription_id (str): The Azure subscription ID
        resource_group_name (str): The name of the resource group
        foundry_resource_name (str): The name of the foundry resource
        location (str): The Azure region location
        credential: Azure credential object (optional, defaults to DefaultAzureCredential)
    
    Returns:
        bool: True if resource exists or was created successfully
        
    Raises:
        Exception: For Azure API errors during creation
    """
    if not credential:
        credential = DefaultAzureCredential()
    
    try:
        # Create cognitive services management client
        client = CognitiveServicesManagementClient(
            credential=credential, 
            subscription_id=subscription_id,
            api_version="2025-04-01-preview"
        )
        
        # Check if resource already exists
        try:
            existing_resource = client.accounts.get(
                resource_group_name=resource_group_name,
                account_name=foundry_resource_name
            )
            logger.debug(f"Cognitive Services resource '{foundry_resource_name}' already exists in location '{existing_resource.location}'")
            return True, client
        except Exception:
            # Resource doesn't exist, create it
            logger.info(f"Creating Cognitive Services resource '{foundry_resource_name}'...")
            
            resource = client.accounts.begin_create(
                resource_group_name=resource_group_name,
                account_name=foundry_resource_name,
                account={
                    "location": location,
                    "kind": "AIServices",
                    "sku": {"name": "S0"},
                    "identity": {"type": "SystemAssigned"},
                    "properties": {
                        "allowProjectManagement": True,
                        "customSubDomainName": foundry_resource_name
                    }
                }
            )
            
            # Wait for the resource creation to complete
            resource_result = resource.result()
            logger.info(f"Resource created successfully")
            return True, client
            
    except Exception as e:
        # Check if it's a soft-delete issue
        if "FlagMustBeSetForRestore" in str(e):
            logger.debug(f"Resource is soft-deleted: {str(e)}")
            logger.info("Restoring soft-deleted resource...")
            try:
                # Attempt to restore the resource
                resource = client.accounts.begin_create(
                    resource_group_name=resource_group_name,
                    account_name=foundry_resource_name,
                    account={
                        "location": location,
                        "kind": "AIServices", 
                        "sku": {"name": "S0"},
                        "identity": {"type": "SystemAssigned"},
                        "properties": {
                            "allowProjectManagement": True,
                            "customSubDomainName": foundry_resource_name,
                            "restore": True
                        }
                    }
                )
                resource_result = resource.result()
                logger.info(f"Resource restored successfully")
                return True, client
            except Exception as restore_error:
                logger.error(f"Failed to restore resource: {str(restore_error)}")
                raise Exception(f"Resource needs manual intervention. Please restore or purge the soft-deleted resource '{foundry_resource_name}' in the Azure portal.")
        
        # If it's not a soft-delete issue, log the error and raise
        logger.error(f"Error managing Cognitive Services resource '{foundry_resource_name}': {str(e)}")
        raise Exception(f"Failed to ensure Cognitive Services resource '{foundry_resource_name}' exists: {str(e)}")

def ensure_resource_group_exists(subscription_id: str, resource_group_name: str, location: str, credential=None):
    """
    Ensure that a resource group exists, creating it if necessary.
    
    Args:
        subscription_id (str): The Azure subscription ID
        resource_group_name (str): The name of the resource group
        location (str): The Azure region location
        credential: Azure credential object (optional, defaults to DefaultAzureCredential)
    
    Returns:
        bool: True if resource group exists or was created successfully
        
    Raises:
        Exception: For Azure API errors during creation
    """
    if not credential:
        credential = DefaultAzureCredential()
    
    try:
        # Create resource management client
        resource_client = ResourceManagementClient(credential=credential, subscription_id=subscription_id)
        
        # Check if resource group exists
        try:
            rg = resource_client.resource_groups.get(resource_group_name)
            logger.debug(f"Resource group '{resource_group_name}' already exists in location '{rg.location}'")
            return True
        except Exception:
            # Resource group doesn't exist, create it
            logger.info(f"Creating resource group '{resource_group_name}'...")
            
            resource_group_params = {
                'location': location,
                'tags': {
                    'created_by': 'ai-foundry-client',
                    'purpose': 'foundry-resources'
                }
            }
            
            result = resource_client.resource_groups.create_or_update(
                resource_group_name=resource_group_name,
                parameters=resource_group_params
            )
            
            logger.info(f"Resource group created")
            return True
            
    except Exception as e:
        logger.error(f"Error managing resource group '{resource_group_name}': {str(e)}")
        raise Exception(f"Failed to ensure resource group '{resource_group_name}' exists: {str(e)}")

def generate_foundry_endpoint(foundry_resource_name: str, foundry_project_name: str, location: str = None) -> str:
    """
    Generate the Azure AI Foundry project endpoint URL.
    
    Args:
        foundry_resource_name (str): The name of the AI Foundry resource
        foundry_project_name (str): The name of the AI Foundry project
        location (str): Azure region (optional, used for validation)
    
    Returns:
        str: The complete AI Foundry project endpoint URL
    """
    try:
        # Generate the endpoint URL based on Azure AI Foundry naming conventions
        # Correct format: https://<resource-name>.services.ai.azure.com/api/projects/<project-name>
        endpoint = f"https://{foundry_resource_name}.services.ai.azure.com/api/projects/{foundry_project_name}"
        logger.debug(f"Generated AI Foundry endpoint: {endpoint}")
        return endpoint
        
    except Exception as e:
        logger.error(f"Error generating endpoint: {str(e)}")
        raise Exception(f"Failed to generate endpoint: {str(e)}")

def save_project_config(foundry_resource_name: str, foundry_project_name: str, 
                       subscription_id: str, resource_group_name: str, location: str, 
                       config_file: str = "project_config.json", 
                       deployment_results: dict = None):
    """
    Save project configuration including endpoint to a JSON file.
    
    Args:
        foundry_resource_name (str): The name of the AI Foundry resource
        foundry_project_name (str): The name of the AI Foundry project  
        subscription_id (str): Azure subscription ID
        resource_group_name (str): Resource group name
        location (str): Azure region
        config_file (str): Configuration file name (default: project_config.json)
    """
    try:
        endpoint = generate_foundry_endpoint(foundry_resource_name, foundry_project_name, location)
        
        import datetime
        
        config = {
            "endpoint": endpoint,
            "subscription_id": subscription_id,
            "resource_group_name": resource_group_name,
            "foundry_resource_name": foundry_resource_name,
            "foundry_project_name": foundry_project_name,
            "location": location,
            "supported_models": SUPPORTED_MODELS,
            "deployed_models": deployment_results if deployment_results else {},
            "models_to_deploy": MODELS_TO_DEPLOY,
            "created_timestamp": datetime.datetime.now().isoformat(),
            "description": "Azure AI Foundry project configuration generated by 01_client.py"
        }
        
        # Save to JSON file
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
            
        logger.debug(f"Project configuration saved to '{config_file}'")
        logger.debug(f"Endpoint: {endpoint}")
        
        return config
        
    except Exception as e:
        logger.error(f"Error saving project configuration: {str(e)}")
        raise Exception(f"Failed to save project configuration: {str(e)}")

def deploy_model_to_foundry_resource(
    subscription_id: str, 
    resource_group_name: str, 
    foundry_resource_name: str, 
    model_deployment_name: str, 
    model_config: dict,
    credential=None
):
    """
    Deploy a model to an Azure AI Foundry resource using the Azure Management API.
    Supports OpenAI models including GPT-4o, GPT-4o Mini, GPT-4, and GPT-3.5 Turbo.
    
    Args:
        subscription_id (str): Azure subscription ID
        resource_group_name (str): Resource group name
        foundry_resource_name (str): The name of the AI Foundry resource (not project)
        model_deployment_name (str): Custom name for the deployment
        model_config (dict): Model configuration containing name, version, format, and sku
        credential: Azure credential object
        
    Returns:
        dict: Deployment response
        
    Raises:
        Exception: If deployment fails
    """
    if not credential:
        credential = DefaultAzureCredential()
    
    # Extract model configuration parameters
    model_name = model_config["name"]
    model_version = model_config["version"]
    model_format = model_config["format"]
    sku_config = model_config["sku"]
    
    try:
        logger.info(f"  Deploying {model_name}...")
        
        # Get access token for Azure Management API
        token_response = credential.get_token("https://management.azure.com/.default")
        access_token = token_response.token
        
        # Azure Management API endpoint for model deployments
        api_version = "2024-10-01"
        deployment_url = (
            f"https://management.azure.com/subscriptions/{subscription_id}/"
            f"resourceGroups/{resource_group_name}/providers/Microsoft.CognitiveServices/"
            f"accounts/{foundry_resource_name}/deployments/{model_deployment_name}?api-version={api_version}"
        )
        
        # Deployment payload
        deployment_data = {
            "sku": {
                "name": sku_config["name"],
                "capacity": sku_config["capacity"]
            },
            "properties": {
                "model": {
                    "format": model_format,
                    "name": model_name,
                    "version": model_version
                }
            }
        }
        
        # Headers for the request
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        logger.debug(f"Sending deployment request to: {deployment_url}")
        logger.debug(f"Model: {model_name}, Version: {model_version}, Format: {model_format}, SKU: {sku_config['name']}")
        
        # Send PUT request to deploy model
        response = requests.put(deployment_url, headers=headers, json=deployment_data)
        
        if response.status_code in [200, 201]:
            logger.debug(f"Model deployment initiated successfully!")
            response_data = response.json()
            logger.debug(f"Deployment name: {model_deployment_name}")
            logger.debug(f"Status: {response_data.get('properties', {}).get('provisioningState', 'Unknown')}")
            
            # Wait for deployment to complete (optional)
            deployment_state = wait_for_deployment_completion(
                deployment_url, headers, model_deployment_name, timeout_minutes=10
            )
            
            return response_data
            
        else:
            error_msg = f"Failed to deploy model. Status: {response.status_code}, Response: {response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)
            
    except requests.RequestException as e:
        logger.error(f"Network error during model deployment: {str(e)}")
        raise Exception(f"Network error during model deployment: {str(e)}")
    except Exception as e:
        logger.error(f"Error deploying model: {str(e)}")
        raise Exception(f"Failed to deploy model: {str(e)}")

def wait_for_deployment_completion(deployment_url: str, headers: dict, deployment_name: str, timeout_minutes: int = 10):
    """
    Wait for model deployment to complete by polling the deployment status.
    
    Args:
        deployment_url (str): The deployment URL to poll
        headers (dict): Request headers including authorization
        deployment_name (str): Name of the deployment for logging
        timeout_minutes (int): Maximum time to wait in minutes
        
    Returns:
        str: Final deployment state
    """
    timeout_seconds = timeout_minutes * 60
    start_time = time.time()
    poll_interval = 30  # Poll every 30 seconds
    
    logger.debug(f"Waiting for deployment '{deployment_name}' to complete (timeout: {timeout_minutes} minutes)...")
    
    while (time.time() - start_time) < timeout_seconds:
        try:
            response = requests.get(deployment_url, headers=headers)
            
            if response.status_code == 200:
                deployment_info = response.json()
                state = deployment_info.get('properties', {}).get('provisioningState', 'Unknown')
                
                logger.debug(f"Deployment '{deployment_name}' status: {state}")
                
                if state == 'Succeeded':
                    logger.info(f"    Completed successfully")
                    return state
                elif state in ['Failed', 'Canceled']:
                    error_msg = f"Deployment '{deployment_name}' failed with state: {state}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                elif state in ['Creating', 'Updating', 'Running']:
                    # Still in progress, continue waiting
                    logger.debug(f"Deployment in progress... waiting {poll_interval}s before next check")
                    time.sleep(poll_interval)
                else:
                    logger.warning(f"Unknown deployment state: {state}")
                    time.sleep(poll_interval)
            else:
                logger.warning(f"Could not check deployment status: {response.status_code}")
                time.sleep(poll_interval)
                
        except Exception as e:
            logger.warning(f"Error checking deployment status: {str(e)}")
            time.sleep(poll_interval)
    
    # Timeout reached
    logger.warning(f"Deployment monitoring timed out after {timeout_minutes} minutes")
    logger.info("Deployment may still be in progress. Check Azure portal for status.")
    return "Timeout"

def deploy_multiple_models(
    subscription_id: str,
    resource_group_name: str, 
    foundry_resource_name: str,
    models_to_deploy: list = None,
    credential=None
):
    """
    Deploy multiple models to an Azure AI Foundry resource.
    
    Args:
        subscription_id (str): Azure subscription ID
        resource_group_name (str): Resource group name
        foundry_resource_name (str): The name of the AI Foundry resource
        models_to_deploy (list): List of model keys to deploy (from SUPPORTED_MODELS)
        credential: Azure credential object
        
    Returns:
        dict: Dictionary of deployment results for each model
    """
    if not models_to_deploy:
        models_to_deploy = MODELS_TO_DEPLOY
        
    if not credential:
        credential = DefaultAzureCredential()
    
    deployment_results = {}
    
    logger.info("")
    logger.info(f"Deploying {len(models_to_deploy)} model(s):")
    
    for model_key in models_to_deploy:
        if model_key not in SUPPORTED_MODELS:
            logger.error(f"  {model_key}: Unsupported model")
            logger.debug(f"Available models: {list(SUPPORTED_MODELS.keys())}")
            deployment_results[model_key] = {"status": "failed", "error": "Unsupported model"}
            continue
            
        model_config = SUPPORTED_MODELS[model_key]
        
        # Check if model is supported in Azure AI Foundry
        model_status = model_config.get('status')
        if model_status == 'not_supported':
            logger.warning(f"  WARNING: {model_key}: Not supported in Azure AI Foundry")
            if 'note' in model_config:
                logger.debug(f"Note: {model_config['note']}")
            deployment_results[model_key] = {
                "status": "failed", 
                "error": "Model not supported in Azure AI Foundry",
                "note": model_config.get('note', 'Not supported')
            }
            continue
        elif model_status == 'not_available_region':
            logger.warning(f"  WARNING: {model_key}: Not available in current region")
            if 'note' in model_config:
                logger.debug(f"Note: {model_config['note']}")
            deployment_results[model_key] = {
                "status": "failed", 
                "error": "Model not available in current region", 
                "note": model_config.get('note', 'Not available in current region')
            }
            continue
        deployment_name = f"{foundry_resource_name}-{model_config['deployment_suffix']}"
        
        logger.debug(f"\nDeploying {model_key}...")
        logger.debug(f"Model: {model_config['name']}")
        logger.debug(f"Version: {model_config['version']}")
        logger.debug(f"Format: {model_config['format']}")
        logger.debug(f"Deployment name: {deployment_name}")
        
        try:
            result = deploy_model_to_foundry_resource(
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                foundry_resource_name=foundry_resource_name,
                model_deployment_name=deployment_name,
                model_config=model_config,
                credential=credential
            )
            
            deployment_results[model_key] = {
                "status": "success", 
                "deployment_name": deployment_name,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"    Failed: {str(e)}")
            deployment_results[model_key] = {
                "status": "failed", 
                "deployment_name": deployment_name,
                "error": str(e)
            }
            
    return deployment_results

def check_models_availability(subscription_id: str, location: str, credential=None):
    """
    Dynamically check availability of all models in SUPPORTED_MODELS for the specified location.
    Updates the status field in SUPPORTED_MODELS dictionary.
    
    Args:
        subscription_id (str): Azure subscription ID
        location (str): Azure region to check
        credential: Azure credential object (optional)
        
    Returns:
        dict: Updated SUPPORTED_MODELS with current availability status
    """
    if not credential:
        credential = DefaultAzureCredential()
    
    try:
        logger.info("Checking model availability...")
        
        # Create cognitive services client
        client = CognitiveServicesManagementClient(
            credential=credential,
            subscription_id=subscription_id
        )
        
        # Get available models for the region
        logger.debug(f"Querying available models in {location}...")
        available_models = list(client.models.list(location=location))
        
        logger.debug(f"Found {len(available_models)} total models in region")
        
        # Check each model in SUPPORTED_MODELS
        available_count = 0
        for model_key, config in SUPPORTED_MODELS.items():
            model_name = config["name"]
            model_version = config["version"]
            
            # Search for this model in available models
            is_available = False
            for available_model in available_models:
                if (available_model.model and 
                    available_model.model.name == model_name and
                    available_model.model.version == model_version):
                    is_available = True
                    break
            
            # Update status
            old_status = config.get('status', 'unknown')
            if is_available:
                config['status'] = 'available'
                status_msg = "YES"
                available_count += 1
            else:
                config['status'] = 'not_available_region'
                status_msg = "NO"
                if 'note' not in config:
                    config['note'] = f"Not available in {location} region"
            
            logger.debug(f"{model_key:20s} ({model_name} v{model_version:15s}): {status_msg}")
        
        logger.info(f"{available_count}/{len(SUPPORTED_MODELS)} models available in {location}")
        return SUPPORTED_MODELS
        
    except Exception as e:
        logger.error(f"Error checking model availability: {str(e)}")
        logger.warning("Using default model availability status")
        return SUPPORTED_MODELS

def get_model_info(dynamic_check: bool = False, subscription_id: str = None, location: str = None, credential=None):
    """
    Display information about supported models.
    
    Args:
        dynamic_check (bool): If True, check availability dynamically via API
        subscription_id (str): Required if dynamic_check is True
        location (str): Required if dynamic_check is True
        credential: Azure credential object (optional)
    
    Returns:
        dict: Information about all supported models
    """
    # Optionally check availability dynamically
    if dynamic_check:
        if not subscription_id or not location:
            logger.warning("Cannot perform dynamic check: subscription_id and location required")
        else:
            check_models_availability(subscription_id, location, credential)
    
    logger.debug("=" * 60)
    logger.debug("SUPPORTED MODELS")
    logger.debug("=" * 60)
    
    for model_key, config in SUPPORTED_MODELS.items():
        status = config.get('status', 'unknown')
        if status == 'available':
            status_indicator = "[AVAILABLE]"
        elif status == 'not_available_region':
            status_indicator = "[REGION LIMITED]"
        else:
            status_indicator = "[UNKNOWN]"
        
        logger.debug(f"\n{model_key.upper()} {status_indicator}:")
        logger.debug(f"  Name: {config['name']}")
        logger.debug(f"  Version: {config['version']}")
        logger.debug(f"  Format: {config['format']}")
        logger.debug(f"  SKU: {config['sku']['name']} (Capacity: {config['sku']['capacity']})")
        logger.debug(f"  Deployment suffix: {config['deployment_suffix']}")
        if 'note' in config:
            logger.debug(f"  Note: {config['note']}")
    
    logger.debug(f"\nCurrently configured to deploy: {MODELS_TO_DEPLOY}")
    return SUPPORTED_MODELS

def main():
    """
    Main execution function that orchestrates the entire process.
    """
    logger.info("=" * 60)
    logger.info("AZURE AI FOUNDRY DEPLOYMENT")
    logger.info("=" * 60)
    logger.info(f"Full logs: {log_filename}")
    logger.info("")
    
    # Display configuration
    logger.debug(f"Subscription: {subscription_name}")
    logger.debug(f"Resource Group: {resource_group_name}")
    logger.debug(f"Foundry Resource: {foundry_resource_name}")
    logger.debug(f"Project: {foundry_project_name}")
    logger.debug(f"Location: {location}")
    
    # Collect the subscription ID using the function
    subscription_id = get_subscription_id_by_name(subscription_name)
    
    return subscription_id

def run_deployment():
    """
    Run the full deployment process
    """
    # Execute main function
    subscription_id = main()

    # Check model availability dynamically BEFORE selection
    logger.info("")
    logger.info("STEP 1: Checking Model Availability")
    logger.info("-" * 60)
    check_models_availability(subscription_id, location, DefaultAzureCredential())

    # Interactive model selection with updated availability info
    logger.info("")
    logger.info("STEP 2: Model Selection")
    logger.info("-" * 60)
    configure_models_to_deploy(interactive=True)

    # Ensure resource group exists before creating resources
    logger.info("")
    logger.info("STEP 3: Preparing Azure Resources")
    logger.info("-" * 60)
    ensure_resource_group_exists(subscription_id, resource_group_name, location)

    # Ensure Cognitive Services resource exists
    resource_exists, client = ensure_cognitive_services_resource_exists(
        subscription_id, resource_group_name, foundry_resource_name, location
    )

    # Ensure project exists
    try:
        # Check if project already exists
        project = client.projects.get(
            resource_group_name=resource_group_name,
            account_name=foundry_resource_name,
            project_name=foundry_project_name
        )
        logger.debug(f"Project '{foundry_project_name}' already exists")
    except Exception:
        # Project doesn't exist, create it
        logger.info(f"Creating project '{foundry_project_name}'...")
        project = client.projects.begin_create(
            resource_group_name=resource_group_name,
            account_name=foundry_resource_name,
            project_name=foundry_project_name,
            project={
                "location": location,
                "identity": {
                    "type": "SystemAssigned"
                },
                "properties": {}
            }
        )
        # Get the created project
        project = client.projects.get(
            resource_group_name=resource_group_name,
            account_name=foundry_resource_name,
            project_name=foundry_project_name
        )
        logger.info(f"Project created")

    logger.debug(f"Using project: {project.name}")

    # Save initial project configuration (will be updated after model deployment)
    try:
        config = save_project_config(
            foundry_resource_name=foundry_resource_name,
            foundry_project_name=foundry_project_name,
            subscription_id=subscription_id,
            resource_group_name=resource_group_name,
            location=location
        )
        logger.debug("Initial project configuration saved successfully!")
        logger.debug(f"Use this endpoint in other scripts: {config['endpoint']}")
    except Exception as e:
        logger.error(f"Failed to save project configuration: {str(e)}")
        logger.warning("You'll need to manually construct the endpoint for other scripts.")

    # Deploy selected models to the foundry resource
    logger.info("")
    logger.info("STEP 4: Deploying Models")
    logger.info("-" * 60)
    try:
        deployment_results = deploy_multiple_models(
            subscription_id=subscription_id,
            resource_group_name=resource_group_name,
            foundry_resource_name=foundry_resource_name,
            models_to_deploy=MODELS_TO_DEPLOY,
            credential=DefaultAzureCredential()
        )
        
        # Summary of deployments
        logger.info("")
        logger.info("=" * 60)
        logger.info("DEPLOYMENT SUMMARY")
        logger.info("=" * 60)
        
        successful_deployments = []
        failed_deployments = []
        
        for model_key, result in deployment_results.items():
            if result["status"] == "success":
                successful_deployments.append(model_key)
                logger.info(f"SUCCESS: {model_key}")
                logger.debug(f"  Deployment: {result['deployment_name']}")
            else:
                failed_deployments.append(model_key)
                logger.error(f"FAILED: {model_key}: {result.get('error', 'Unknown error')}")
        
        if successful_deployments:
            logger.info("")
            logger.info(f"Successfully deployed {len(successful_deployments)} model(s)")
            logger.info(f"  Models: {', '.join(successful_deployments)}")
        
        if failed_deployments:
            logger.info("")
            logger.warning(f"WARNING: Failed to deploy {len(failed_deployments)} model(s): {', '.join(failed_deployments)}")
            logger.info("  Manual deployment: https://ai.azure.com")
        
        # Update project configuration with deployment results
        try:
            final_config = save_project_config(
                foundry_resource_name=foundry_resource_name,
                foundry_project_name=foundry_project_name,
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                location=location,
                deployment_results=deployment_results
            )
            logger.info("")
            logger.info(f"Configuration saved to: project_config.json")
            logger.info(f"Full logs saved to: {log_filename}")
        except Exception as e:
            logger.warning(f"Failed to update project configuration: {str(e)}")
            
    except Exception as e:
        logger.error(f"Failed to deploy models: {str(e)}")
        logger.warning("You can manually deploy models via the Azure AI Foundry portal.")

    logger.info("")
    logger.info("=" * 60)
    logger.info("DEPLOYMENT COMPLETED")
    logger.info("=" * 60)


# Main execution - only run when script is executed directly
if __name__ == "__main__":
    run_deployment()



