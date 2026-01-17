"""
Azure AI Foundry Deployment Upgrade Script

This script helps you upgrade your model deployments to handle higher rate limits.
It dynamically queries Azure for deployed models and lets you select which one to upgrade.
You can increase the capacity or change the SKU tier for better performance.

Usage: python 04_upgrade-deployment.py
"""

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.mgmt.subscription import SubscriptionClient
import requests
import logging
import json
import time
import signal
import sys
from datetime import datetime

# Global variable to store log filename
_log_filename = None

def setup_logging():
    """
    Set up dual logging system - detailed logs to file, essential info to console.
    
    Returns:
        str: Path to the log file
    """
    global _log_filename
    
    # Create timestamp for log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    _log_filename = f"deployment_upgrade_log_{timestamp}.log"
    
    # Remove any existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set root logger to DEBUG to capture everything
    root_logger.setLevel(logging.DEBUG)
    
    # File handler - captures DEBUG and above (detailed logs)
    file_handler = logging.FileHandler(_log_filename, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler - only WARNING and above (essential info)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Suppress verbose Azure SDK logging
    logging.getLogger('azure').setLevel(logging.WARNING)
    logging.getLogger('azure.core').setLevel(logging.WARNING)
    logging.getLogger('azure.identity').setLevel(logging.WARNING)
    
    return _log_filename

def get_log_filename():
    """
    Get the current log filename.
    
    Returns:
        str: Path to the log file or None if logging not initialized
    """
    return _log_filename

def signal_handler(sig, frame):
    """Handle CTRL-C gracefully"""
    print("\n\n" + "=" * 70)
    print("OPERATION CANCELLED BY USER (CTRL-C)")
    print("=" * 70)
    if _log_filename:
        print(f"Detailed logs saved to: {_log_filename}")
    print("Exiting gracefully...")
    sys.exit(0)

# Initialize logging and get logger
setup_logging()
logger = logging.getLogger(__name__)

# Register signal handler
signal.signal(signal.SIGINT, signal_handler)

def load_project_config(config_file: str = "init.json") -> dict:
    """
    Load project configuration from JSON file.
    
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
        return config
        
    except FileNotFoundError:
        logger.error(f"ERROR: {config_file} not found in current directory")
        raise FileNotFoundError(f"{config_file} not found. Please create it with required configuration.")
    except json.JSONDecodeError as e:
        logger.error(f"ERROR: Invalid JSON in {config_file}: {str(e)}")
        raise ValueError(f"Invalid JSON format in {config_file}")
    except Exception as e:
        logger.error(f"ERROR: Failed to load configuration: {str(e)}")
        raise

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
        subscription_client = SubscriptionClient(credential=credential)
        
        logger.debug(f"Searching for subscription with name: '{subscription_name}'")
        
        matching_subscriptions = []
        for subscription in subscription_client.subscriptions.list():
            if subscription.display_name and subscription.display_name.lower() == subscription_name.lower():
                matching_subscriptions.append(subscription)
        
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
        raise
    except Exception as e:
        logger.error(f"Error retrieving subscription ID: {str(e)}")
        raise Exception(f"Failed to retrieve subscription ID for '{subscription_name}': {str(e)}")

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

def get_deployment_details_from_management_api(deployment_name: str, config: dict, credential) -> dict:
    """
    Fetch deployment details from Azure Management API to get accurate model version.
    
    Args:
        deployment_name (str): Name of the deployment
        config (dict): Configuration with subscription_id, resource_group_name, foundry_resource_name
        credential: Azure credential object
        
    Returns:
        dict: Deployment details with model name, version, format
    """
    try:
        # Get access token
        token_response = credential.get_token("https://management.azure.com/.default")
        access_token = token_response.token
        
        # Azure Management API endpoint
        api_version = "2024-10-01"
        deployment_url = (
            f"https://management.azure.com/subscriptions/{config['subscription_id']}/"
            f"resourceGroups/{config['resource_group_name']}/providers/Microsoft.CognitiveServices/"
            f"accounts/{config['foundry_resource_name']}/deployments/{deployment_name}?api-version={api_version}"
        )
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        logger.debug(f"Fetching deployment details from Management API: {deployment_name}")
        response = requests.get(deployment_url, headers=headers)
        
        if response.status_code == 200:
            deployment_data = response.json()
            model_info = deployment_data.get('properties', {}).get('model', {})
            
            result = {
                'name': model_info.get('name', 'unknown'),
                'version': model_info.get('version', 'unknown'),
                'format': model_info.get('format', 'OpenAI')
            }
            logger.debug(f"Retrieved model details: {result}")
            return result
        else:
            logger.warning(f"Failed to fetch deployment details: {response.status_code}")
            return {'name': 'unknown', 'version': 'unknown', 'format': 'OpenAI'}
            
    except Exception as e:
        logger.warning(f"Error fetching deployment details from Management API: {str(e)}")
        return {'name': 'unknown', 'version': 'unknown', 'format': 'OpenAI'}

def get_deployments_dynamically(project, config, credential):
    """
    Dynamically query Azure AI Foundry to get deployed models.
    
    Args:
        project: AIProjectClient instance
        config (dict): Project configuration
        credential: Azure credential object
        
    Returns:
        list: List of deployment information dictionaries
    """
    deployments = []
    
    try:
        logger.info("Querying Azure for deployed models...")
        
        # Get list of deployments from Azure
        azure_deployments = list(project.deployments.list())
        
        if azure_deployments:
            for deployment in azure_deployments:
                deployment_name = deployment.name
                
                # Extract model information - try multiple paths
                model_info = {
                    'name': 'unknown',
                    'version': 'unknown',
                    'format': 'OpenAI'
                }
                current_sku = {
                    'name': 'Standard',
                    'capacity': 1
                }
                
                # Try to get model info from properties
                if hasattr(deployment, 'properties') and deployment.properties:
                    props = deployment.properties
                    if hasattr(props, 'model') and props.model:
                        if hasattr(props.model, 'name'):
                            model_info['name'] = props.model.name
                        if hasattr(props.model, 'version'):
                            model_info['version'] = props.model.version
                        if hasattr(props.model, 'format'):
                            model_info['format'] = props.model.format
                    
                    # Get current capacity info
                    if hasattr(props, 'currentCapacity'):
                        current_sku['capacity'] = props.currentCapacity
                
                # Try to get SKU info
                if hasattr(deployment, 'sku') and deployment.sku:
                    if hasattr(deployment.sku, 'name'):
                        current_sku['name'] = deployment.sku.name
                    if hasattr(deployment.sku, 'capacity'):
                        current_sku['capacity'] = deployment.sku.capacity
                
                # Fallback: Extract model name from deployment name if still unknown
                if model_info['name'] == 'unknown':
                    # Try to extract model name from deployment name patterns like:
                    # fabfoundryresource1-gpt-4o-deployment -> gpt-4o
                    # fabfoundryresource1-gpt35-turbo-deployment -> gpt-35-turbo
                    name_lower = deployment_name.lower()
                    if 'gpt-4o-mini' in name_lower:
                        model_info['name'] = 'gpt-4o-mini'
                    elif 'gpt-4o' in name_lower:
                        model_info['name'] = 'gpt-4o'
                    elif 'gpt4o' in name_lower:
                        model_info['name'] = 'gpt-4o'
                    elif 'gpt-4' in name_lower:
                        model_info['name'] = 'gpt-4'
                    elif 'gpt35-turbo' in name_lower or 'gpt-35-turbo' in name_lower:
                        model_info['name'] = 'gpt-35-turbo'
                    elif 'gpt-3.5-turbo' in name_lower:
                        model_info['name'] = 'gpt-35-turbo'
                    else:
                        # Use deployment name as fallback
                        model_info['name'] = deployment_name
                
                # If version is still unknown, try to get it from Management API
                if model_info['version'] == 'unknown':
                    logger.info(f"Fetching accurate version for {deployment_name} from Management API...")
                    management_model_info = get_deployment_details_from_management_api(
                        deployment_name, config, credential
                    )
                    # Update with Management API data if available
                    if management_model_info['version'] != 'unknown':
                        model_info['version'] = management_model_info['version']
                        if management_model_info['name'] != 'unknown':
                            model_info['name'] = management_model_info['name']
                        model_info['format'] = management_model_info['format']
                
                # Try to get version from config file if still unknown
                if model_info['version'] == 'unknown' and 'supported_models' in config:
                    for model_key, model_config in config['supported_models'].items():
                        if model_key == model_info['name'] or model_config.get('name') == model_info['name']:
                            model_info['version'] = model_config.get('version', 'unknown')
                            if model_info['format'] == 'OpenAI':
                                model_info['format'] = model_config.get('format', 'OpenAI')
                            break
                
                deployments.append({
                    'model_key': model_info['name'],
                    'deployment_name': deployment_name,
                    'model_config': model_info,
                    'current_sku': current_sku
                })
                logger.info(f"Found deployment: {deployment_name} - {model_info['name']} (SKU: {current_sku['name']}, Capacity: {current_sku['capacity']})")
        
        logger.info(f"Found {len(deployments)} deployment(s)")
        
    except Exception as e:
        logger.error(f"Could not dynamically fetch deployments: {str(e)}", exc_info=True)
        logger.info("Attempting fallback to configuration file...")
        
        # Fallback to config file if dynamic query fails
        if 'deployed_models' in config and config['deployed_models']:
            for model_key, deployment_info in config['deployed_models'].items():
                if deployment_info.get('status') == 'success':
                    deployment_name = deployment_info.get('deployment_name')
                    model_config = config.get('supported_models', {}).get(model_key, {})
                    
                    if deployment_name and model_config:
                        deployments.append({
                            'model_key': model_key,
                            'deployment_name': deployment_name,
                            'model_config': model_config,
                            'current_sku': model_config.get('sku', {})
                        })
    
    return deployments

def select_deployment_to_upgrade(deployments):
    """
    Interactive selection of deployment to upgrade.
    
    Args:
        deployments (list): List of available deployments
        
    Returns:
        dict: Selected deployment info or None
    """
    if not deployments:
        print("\n" + "="*70)
        print("NO DEPLOYMENTS FOUND")
        print("="*70)
        print("No model deployments were found in your Azure AI Foundry project.")
        print("\nTo deploy models, run: python 01_client.py")
        print("="*70)
        return None
    
    print("\n" + "="*70)
    print("DEPLOYED MODELS AVAILABLE FOR UPGRADE")
    print("="*70)
    
    if len(deployments) == 1:
        deployment = deployments[0]
        model_key = deployment['model_key']
        deployment_name = deployment['deployment_name']
        model_config = deployment.get('model_config', {})
        current_sku = deployment['current_sku']
        
        print(f"\nFound 1 deployment:")
        print(f"  Model: {model_key}")
        print(f"  Deployment: {deployment_name}")
        print(f"  Version: {model_config.get('version', 'unknown')}")
        print(f"  Current SKU: {current_sku.get('name', 'Unknown')}")
        print(f"  Current Capacity: {current_sku.get('capacity', 'Unknown')}")
        print()
        
        confirm = input("Upgrade this deployment? (y/N): ").strip().lower()
        return deployments[0] if confirm == 'y' else None
    
    print(f"\nFound {len(deployments)} deployments. Please select one to upgrade:\n")
    
    for i, deployment in enumerate(deployments, 1):
        model_key = deployment['model_key']
        deployment_name = deployment['deployment_name']
        model_config = deployment.get('model_config', {})
        current_sku = deployment['current_sku']
        
        print(f"{i}. {model_key}")
        print(f"   Deployment: {deployment_name}")
        print(f"   Version: {model_config.get('version', 'unknown')}")
        print(f"   Current SKU: {current_sku.get('name', 'Unknown')} (Capacity: {current_sku.get('capacity', 1)})")
        print()
    
    print("-" * 70)
    
    while True:
        try:
            choice = input(f"Select deployment to upgrade (1-{len(deployments)}) or 'q' to quit: ").strip().lower()
            
            if choice == 'q':
                print("Upgrade cancelled.")
                return None
            
            index = int(choice) - 1
            if 0 <= index < len(deployments):
                selected = deployments[index]
                print(f"\nSelected: {selected['model_key']} ({selected['deployment_name']})")
                print("="*70 + "\n")
                return selected
            else:
                print(f"Invalid selection. Please enter a number between 1 and {len(deployments)}")
        except ValueError:
            print(f"Invalid input. Please enter a number between 1 and {len(deployments)} or 'q' to quit.")
        except KeyboardInterrupt:
            print("\nUpgrade cancelled.")
            return None

def upgrade_deployment_capacity(deployment_info=None, new_capacity: int = 2, new_sku: str = "Standard"):
    """
    Upgrade the deployment capacity to handle more requests per minute.
    
    Args:
        deployment_info (dict): Deployment information to upgrade
        new_capacity (int): New capacity level (1-10 for Standard, 1-100 for GlobalStandard)
        new_sku (str): SKU name ("Standard" or "GlobalStandard")
    """
    try:
        # Load project configuration
        config = load_project_config()
        credential = DefaultAzureCredential()
        
        # Get subscription ID from subscription name
        subscription_id = get_subscription_id_by_name(config['subscription_name'], credential)
        config['subscription_id'] = subscription_id
        
        # Deployment info should be provided by caller
        if not deployment_info:
            logger.error("No deployment information provided")
            print("Error: No deployment information provided.")
            return False
        
        deployment_name = deployment_info['deployment_name']
        model_config = deployment_info['model_config']
        
        print(f"\nUpgrading deployment: {deployment_name}")
        print(f"Model: {model_config['name']} ({model_config['version']})")
        print(f"New SKU: {new_sku} with capacity {new_capacity}")
        print("This will increase your rate limits and reduce rate limiting errors.")
        print()
        
        # Confirm upgrade
        confirm = input("Do you want to proceed with the upgrade? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Upgrade cancelled.")
            return False
        
        # Get access token
        token_response = credential.get_token("https://management.azure.com/.default")
        access_token = token_response.token
        
        # Azure Management API endpoint for updating deployment
        api_version = "2024-10-01"
        deployment_url = (
            f"https://management.azure.com/subscriptions/{config['subscription_id']}/"
            f"resourceGroups/{config['resource_group_name']}/providers/Microsoft.CognitiveServices/"
            f"accounts/{config['foundry_resource_name']}/deployments/{deployment_name}?api-version={api_version}"
        )
        
        # Updated deployment configuration using model config
        upgrade_data = {
            "sku": {
                "name": new_sku,
                "capacity": new_capacity
            },
            "properties": {
                "model": {
                    "format": model_config['format'],
                    "name": model_config['name'],
                    "version": model_config['version']
                }
            }
        }
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        logger.info("Sending deployment upgrade request...")
        logger.debug(f"Request URL: {deployment_url}")
        logger.debug(f"Request payload: {json.dumps(upgrade_data, indent=2)}")
        
        response = requests.put(deployment_url, headers=headers, json=upgrade_data)
        
        if response.status_code in [200, 201]:
            logger.info("Deployment upgrade initiated successfully!")
            response_data = response.json()
            logger.debug(f"Response data: {json.dumps(response_data, indent=2)}")
            
            # Monitor upgrade progress
            print("\nWaiting for deployment upgrade to complete...")
            upgrade_status = monitor_deployment_upgrade(deployment_url, headers)
            
            if upgrade_status == "Succeeded":
                print(f"\nSUCCESS! Deployment upgraded to {new_sku} SKU with capacity {new_capacity}")
                print_upgrade_benefits(new_capacity, new_sku)
                return True
            else:
                logger.warning(f"Upgrade status: {upgrade_status}")
                print(f"\nUpgrade completed with status: {upgrade_status}")
                return False
                
        else:
            logger.error(f"Failed to upgrade deployment: {response.status_code} - {response.text}")
            print(f"\nFailed to upgrade deployment. HTTP {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error during deployment upgrade: {str(e)}", exc_info=True)
        print(f"\nError during deployment upgrade: {str(e)}")
        return False

def monitor_deployment_upgrade(deployment_url: str, headers: dict, timeout_minutes: int = 5):
    """Monitor the deployment upgrade progress."""
    timeout_seconds = timeout_minutes * 60
    start_time = time.time()
    poll_interval = 15  # Check every 15 seconds
    
    logger.info(f"Monitoring deployment upgrade (timeout: {timeout_minutes} minutes)")
    
    while (time.time() - start_time) < timeout_seconds:
        try:
            response = requests.get(deployment_url, headers=headers)
            
            if response.status_code == 200:
                deployment_info = response.json()
                state = deployment_info.get('properties', {}).get('provisioningState', 'Unknown')
                
                logger.info(f"Upgrade status: {state}")
                print(f"  Status: {state}")
                
                if state == 'Succeeded':
                    logger.info("Deployment upgrade succeeded")
                    return state
                elif state in ['Failed', 'Canceled']:
                    logger.error(f"Deployment upgrade failed with state: {state}")
                    return state
                elif state in ['Creating', 'Updating', 'Running']:
                    logger.debug(f"Upgrade in progress, waiting {poll_interval} seconds...")
                    time.sleep(poll_interval)
                else:
                    logger.warning(f"Unknown upgrade state: {state}")
                    time.sleep(poll_interval)
            else:
                logger.warning(f"Could not check upgrade status: {response.status_code}")
                time.sleep(poll_interval)
                
        except Exception as e:
            logger.warning(f"Error checking upgrade status: {str(e)}")
            time.sleep(poll_interval)
    
    logger.warning(f"Upgrade monitoring timed out after {timeout_minutes} minutes")
    return "Timeout"

def print_upgrade_benefits(capacity: int, sku: str):
    """Print the benefits of the upgrade."""
    print("\nUPGRADE BENEFITS:")
    
    if sku == "Standard":
        estimated_requests = capacity * 20
        estimated_tokens = capacity * 10000
        print(f"   - Rate limit increased to ~{estimated_requests} requests/minute")
        print(f"   - Token limit increased to ~{estimated_tokens:,} tokens/minute")
    elif sku == "GlobalStandard":
        print("   - Global load balancing across Azure regions")
        print("   - Higher availability and better performance")
        print("   - Premium rate limits and throughput")
    
    print("   - Reduced rate limiting errors in your chat application")
    print("   - Better user experience with faster responses")
    print("   - Ability to handle more concurrent users")
    
    print("\nCOST IMPACT:")
    print(f"   - Capacity increased from 1 to {capacity}")
    print("   - Cost will scale proportionally with capacity")
    print("   - Monitor usage in Azure portal to optimize costs")

def show_upgrade_options():
    """Display available upgrade options."""
    print("\nUPGRADE OPTIONS:")
    print()
    print("1. MODERATE UPGRADE (Recommended for testing)")
    print("   - Standard SKU, Capacity 2")
    print("   - ~40 requests/minute, ~20K tokens/minute")
    print("   - 2x current performance")
    print()
    print("2. SIGNIFICANT UPGRADE (Good for production)")
    print("   - Standard SKU, Capacity 5")
    print("   - ~100 requests/minute, ~50K tokens/minute")
    print("   - 5x current performance")
    print()
    print("3. PREMIUM UPGRADE (Best performance)")
    print("   - GlobalStandard SKU, Capacity 2")
    print("   - Global load balancing + premium limits")
    print("   - Best availability and performance")
    print()

def main():
    """Main function to handle deployment upgrades."""
    try:
        print("\n" + "="*70)
        print("AZURE AI FOUNDRY DEPLOYMENT UPGRADE TOOL")
        print("="*70)
        print("This tool dynamically queries your Azure AI Foundry project for")
        print("deployed models and helps you increase rate limits and capacity.")
        print("="*70)
        print(f"\nDetailed logs: {get_log_filename()}")
        print("="*70)
        
        # Step 1: Load configuration and connect to Azure
        logger.info("Loading project configuration from init.json")
        config = load_project_config()
        logger.debug(f"Configuration loaded: {json.dumps({k: v for k, v in config.items() if k != 'endpoint'}, indent=2)}")
        
        logger.info("Initializing Azure credentials")
        credential = DefaultAzureCredential()
        
        # Get subscription ID from subscription name
        logger.info(f"Resolving subscription ID for: {config['subscription_name']}")
        subscription_id = get_subscription_id_by_name(config['subscription_name'], credential)
        config['subscription_id'] = subscription_id
        logger.info(f"Subscription ID: {subscription_id}")
        
        # Generate endpoint from resource and project names
        endpoint = generate_foundry_endpoint(
            config['foundry_resource_name'], 
            config['foundry_project_name']
        )
        
        logger.info(f"Connecting to Azure AI Foundry project...")
        project = AIProjectClient(
            endpoint=endpoint,
            credential=credential,
        )
        logger.info("Successfully connected to Azure AI Foundry project")
        
        # Step 2: Get and display all deployed models
        deployments = get_deployments_dynamically(project, config, credential)
        
        if not deployments:
            print("\n" + "="*70)
            print("NO DEPLOYMENTS FOUND")
            print("="*70)
            print("No model deployments were found in your Azure AI Foundry project.")
            print("\nTo deploy models, run: python 01_client.py")
            print("="*70)
            return
        
        # Step 3: User selects which model to upgrade
        selected_deployment = select_deployment_to_upgrade(deployments)
        
        if not selected_deployment:
            print("No deployment selected for upgrade.")
            return
        
        # Step 4: Show upgrade options
        show_upgrade_options()
        
        print("Choose an upgrade option:")
        print("1. Moderate (Standard SKU, Capacity 2)")
        print("2. Significant (Standard SKU, Capacity 5)")
        print("3. Premium (GlobalStandard SKU, Capacity 2)")
        print("4. Custom")
        print("5. Cancel")
        
        choice = input("\nEnter your choice (1-5): ").strip()
        
        if choice == "1":
            success = upgrade_deployment_capacity(deployment_info=selected_deployment, new_capacity=2, new_sku="Standard")
        elif choice == "2":
            success = upgrade_deployment_capacity(deployment_info=selected_deployment, new_capacity=5, new_sku="Standard")
        elif choice == "3":
            success = upgrade_deployment_capacity(deployment_info=selected_deployment, new_capacity=2, new_sku="GlobalStandard")
        elif choice == "4":
            print("\nCustom upgrade:")
            sku = input("Enter SKU (Standard/GlobalStandard): ").strip()
            if sku not in ["Standard", "GlobalStandard"]:
                print("Invalid SKU. Must be 'Standard' or 'GlobalStandard'")
                return
            
            try:
                capacity = int(input("Enter capacity (1-10 for Standard, 1-100 for GlobalStandard): "))
                if capacity < 1 or (sku == "Standard" and capacity > 10) or (sku == "GlobalStandard" and capacity > 100):
                    print("Invalid capacity for the selected SKU")
                    return
            except ValueError:
                print("Invalid capacity. Must be a number.")
                return
                
            success = upgrade_deployment_capacity(deployment_info=selected_deployment, new_capacity=capacity, new_sku=sku)
        elif choice == "5":
            print("Upgrade cancelled.")
            return
        else:
            print("Invalid choice.")
            return
        
        if success:
            print("\n" + "="*70)
            print("DEPLOYMENT UPGRADE SUCCESSFUL")
            print("="*70)
            print("\nNext steps:")
            print("1. Test your chat application - rate limits should be much better")
            print("2. Run 'python 03_check-deployment.py' to verify the upgrade")
            print("3. Monitor usage in Azure portal to track improvements")
            print(f"\nDetailed logs saved to: {get_log_filename()}")
            print("="*70)
        else:
            print("\n" + "="*70)
            print("DEPLOYMENT UPGRADE FAILED")
            print("="*70)
            print(f"Check detailed logs in: {get_log_filename()}")
            print("You can also upgrade manually in the Azure portal.")
            print("="*70)
    
    except KeyboardInterrupt:
        print("\n\n" + "=" * 70)
        print("OPERATION CANCELLED BY USER (CTRL-C)")
        print("=" * 70)
        print(f"Detailed logs saved to: {get_log_filename()}")
        print("Exiting gracefully...")
        sys.exit(0)
            
    except Exception as e:
        logger.error(f"Failed to run upgrade tool: {str(e)}", exc_info=True)
        print("\n" + "="*70)
        print("ERROR OCCURRED")
        print("="*70)
        print(f"Check detailed logs in: {get_log_filename()}")
        print("\nMake sure you have:")
        print("1. Proper Azure authentication (az login)")
        print("2. Owner or Contributor permissions on the Azure AI resource")
        print("="*70)
        print("3. Sufficient quota in your Azure subscription")

if __name__ == "__main__":
    main()