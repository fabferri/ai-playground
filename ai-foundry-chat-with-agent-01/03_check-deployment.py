"""
Azure AI Foundry Deployment Checker and Optimizer

This script dynamically fetches and analyzes:
1. Currently deployed models from Azure AI Foundry
2. Rate limits and capacity for each deployment
3. Quota usage and availability
4. Optimization recommendations

Configuration: Loads from init.json (subscription_name, resource_group_name, 
              foundry_resource_name, foundry_project_name, location)

Usage: python 03_check-deployment.py
"""

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.mgmt.subscription import SubscriptionClient
import requests
import logging
import json
import re
import sys
import datetime

# Configure dual logging - detailed logs to file, essential info to console
log_filename = f"deployment_check_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.propagate = False

# Remove any existing handlers
logger.handlers.clear()

# File handler - captures ALL logs (DEBUG level)
file_handler = logging.FileHandler(log_filename, mode='w', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Console handler - only essential info (WARNING level and above)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.WARNING)
console_formatter = logging.Formatter('%(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Suppress Azure SDK verbose logging to console
logging.getLogger('azure').setLevel(logging.WARNING)
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
logging.getLogger('azure.identity').setLevel(logging.WARNING)

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

def get_deployed_models_dynamically(project):
    """
    Dynamically query Azure AI Foundry to get actually deployed models with details.
    
    Args:
        project: AIProjectClient instance
        
    Returns:
        list: List of deployment dictionaries with model information
    """
    try:
        deployments = []
        deployment_list = project.deployments.list()
        
        for deployment in deployment_list:
            deployment_name = deployment.name if hasattr(deployment, 'name') else str(deployment)
            
            # Extract model name from deployment name if not provided by API
            model_name = "unknown"
            if hasattr(deployment, 'model') and deployment.model:
                model_name = deployment.model
            else:
                # Try to extract from deployment name (e.g., "resource-gpt-4o-deployment" -> "gpt-4o")
                match = re.search(r'-(gpt-[^-]+(?:-[^-]+)?)-deployment', deployment_name)
                if match:
                    model_name = match.group(1)
            
            deployments.append({
                'deployment_name': deployment_name,
                'model_name': model_name,
                'deployment': deployment
            })
        
        return deployments
        
    except Exception as e:
        logger.error(f"Error querying deployed models: {str(e)}")
        return []

def get_deployment_details_from_management_api(subscription_id, resource_group_name, foundry_resource_name, credential):
    """
    Get detailed deployment information from Azure Management API including SKU and capacity.
    
    Args:
        subscription_id: Azure subscription ID
        resource_group_name: Resource group name
        foundry_resource_name: AI Foundry resource name
        credential: Azure credential
        
    Returns:
        dict: Dictionary mapping deployment names to their details
    """
    try:
        # Get access token
        token_response = credential.get_token("https://management.azure.com/.default")
        access_token = token_response.token
        
        # Query Azure Management API
        api_version = "2024-10-01"
        deployments_url = (
            f"https://management.azure.com/subscriptions/{subscription_id}/"
            f"resourceGroups/{resource_group_name}/providers/Microsoft.CognitiveServices/"
            f"accounts/{foundry_resource_name}/deployments?api-version={api_version}"
        )
        
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(deployments_url, headers=headers)
        
        if response.status_code == 200:
            deployments = response.json()
            deployment_details = {}
            
            for deployment in deployments.get('value', []):
                name = deployment['name']
                properties = deployment.get('properties', {})
                sku = deployment.get('sku', {})
                model = properties.get('model', {})
                
                deployment_details[name] = {
                    'model_name': model.get('name', 'N/A'),
                    'model_version': model.get('version', 'N/A'),
                    'status': properties.get('provisioningState', 'Unknown'),
                    'sku_name': sku.get('name', 'Unknown'),
                    'capacity': sku.get('capacity', 0),
                    'capabilities': properties.get('capabilities', {})
                }
            
            return deployment_details
        else:
            logger.error(f"Failed to query Management API: {response.status_code} - {response.text}")
            return {}
            
    except Exception as e:
        logger.error(f"Error querying Management API: {str(e)}")
        return {}

def check_deployment_status(init_config, subscription_id, credential):
    """
    Dynamically check the current status and configuration of all deployed models.
    
    Args:
        init_config: Configuration from init.json
        subscription_id: Azure subscription ID
        credential: Azure credential
    """
    try:
        foundry_resource_name = init_config['foundry_resource_name']
        foundry_project_name = init_config['foundry_project_name']
        resource_group_name = init_config['resource_group_name']
        location = init_config['location']
        
        print("\n" + "="*70)
        print("AZURE AI FOUNDRY DEPLOYMENT STATUS")
        print("="*70)
        print(f"Project: {foundry_project_name}")
        print(f"Resource: {foundry_resource_name}")
        print(f"Location: {location}")
        print("="*70 + "\n")
        
        # Generate endpoint dynamically
        endpoint = generate_foundry_endpoint(foundry_resource_name, foundry_project_name)
        
        # Create AI Project client to query deployed models
        project = AIProjectClient(
            endpoint=endpoint,
            credential=credential
        )
        
        # Get deployed models dynamically
        print("Querying Azure for deployed models...")
        logger.info("Querying Azure for deployed models...")
        deployed_models = get_deployed_models_dynamically(project)
        
        if not deployed_models:
            print("No deployments found in this project.")
            print("Run '01_client.py' to create and deploy models.")
            return
        
        print(f"Found {len(deployed_models)} deployment(s)")
        print("Fetching deployment details...\n")
        logger.info("Fetching deployment details from Management API...")
        deployment_details = get_deployment_details_from_management_api(
            subscription_id, resource_group_name, foundry_resource_name, credential
        )
        
        # Display deployments in table format
        print("DEPLOYMENT SUMMARY TABLE")
        print("=" * 120)
        print(f"{'#':<3} {'Model':<20} {'Version':<20} {'Status':<12} {'SKU':<18} {'Capacity':<8}")
        print("=" * 120)
        
        for idx, model_info in enumerate(deployed_models, 1):
            deployment_name = model_info['deployment_name']
            model_name = model_info['model_name']
            
            # Get detailed info from Management API
            if deployment_name in deployment_details:
                details = deployment_details[deployment_name]
                version = details['model_version']
                status = details['status']
                sku = details['sku_name']
                capacity = str(details['capacity'])
            else:
                version = 'N/A'
                status = 'Unknown'
                sku = 'N/A'
                capacity = 'N/A'
            
            print(f"{idx:<3} {model_name:<20} {version:<20} {status:<12} {sku:<18} {capacity:<8}")
        
        print("=" * 120)
        print()
        
        # Display detailed analysis for each deployment
        print("DETAILED DEPLOYMENT ANALYSIS")
        print("=" * 70)
        
        for idx, model_info in enumerate(deployed_models, 1):
            deployment_name = model_info['deployment_name']
            model_name = model_info['model_name']
            
            print(f"\n{idx}. Deployment: {deployment_name}")
            
            # Get detailed info from Management API
            if deployment_name in deployment_details:
                details = deployment_details[deployment_name]
                
                # Analyze configuration for rate limits
                analyze_deployment_config(
                    deployment_name, 
                    {'name': details['sku_name'], 'capacity': details['capacity']},
                    {'name': model_name}
                )
            else:
                print("   (Detailed SKU/capacity info not available)")
            
            print("-" * 70)
            
    except Exception as e:
        logger.error(f"Error checking deployment status: {str(e)}")
        import traceback
        traceback.print_exc()

def calculate_rate_limits(sku_name: str, capacity: int, model_name: str):
    """
    Calculate estimated rate limits based on SKU, capacity, and model.
    
    Args:
        sku_name: SKU name (Standard, GlobalStandard, etc.)
        capacity: Capacity units
        model_name: Model name
        
    Returns:
        dict: Rate limit estimates
    """
    # Base rates per capacity unit (approximate values)
    base_rates = {
        'Standard': {
            'requests_per_min': 20,
            'tokens_per_min': 10000
        },
        'GlobalStandard': {
            'requests_per_min': 30,  # Higher for GlobalStandard
            'tokens_per_min': 15000
        }
    }
    
    # Get base rates
    rates = base_rates.get(sku_name, {'requests_per_min': 20, 'tokens_per_min': 10000})
    
    return {
        'requests_per_min': rates['requests_per_min'] * capacity,
        'tokens_per_min': rates['tokens_per_min'] * capacity,
        'requests_per_day': rates['requests_per_min'] * capacity * 60 * 24,
        'tokens_per_day': rates['tokens_per_min'] * capacity * 60 * 24
    }

def analyze_deployment_config(deployment_name: str, sku: dict, model: dict):
    """
    Analyze the deployment configuration and provide detailed rate limit information.
    """
    sku_name = sku.get('name', 'Unknown')
    capacity = sku.get('capacity', 0)
    model_name = model.get('name', 'Unknown')
    
    # Calculate rate limits
    limits = calculate_rate_limits(sku_name, capacity, model_name)
    
    # Display configuration and rate limits in table format
    print(f"\n   Configuration & Rate Limits:")
    print("   " + "-" * 80)
    print(f"   {'Metric':<30} {'Per Minute':<20} {'Per Day':<20}")
    print("   " + "-" * 80)
    print(f"   {'SKU Type':<30} {sku_name:<20} {'-':<20}")
    print(f"   {'Capacity Units':<30} {capacity:<20} {'-':<20}")
    
    req_per_min = f"~{limits['requests_per_min']:,}"
    req_per_day = f"~{limits['requests_per_day']:,}"
    tok_per_min = f"~{limits['tokens_per_min']:,}"
    tok_per_day = f"~{limits['tokens_per_day']:,}"
    
    print(f"   {'Requests Limit':<30} {req_per_min:<20} {req_per_day:<20}")
    print(f"   {'Tokens Limit':<30} {tok_per_min:<20} {tok_per_day:<20}")
    print("   " + "-" * 80)
    
    # Provide analysis based on current configuration
    if sku_name == 'Standard':
        if capacity == 1:
            print(f"\n   STATUS: Minimum Configuration")
            print(f"   WARNING: This is the lowest capacity setting")
            print(f"   WARNING: May experience rate limiting with moderate usage")
            print(f"\n   RECOMMENDATIONS:")
            print(f"   → Increase capacity to 2-5 for better throughput")
            print(f"   → Consider GlobalStandard SKU for premium performance")
            print(f"   → Use 04_upgrade-deployment.py to upgrade capacity")
        elif capacity <= 3:
            print(f"\n   STATUS: Moderate Configuration")
            print(f"   ✓ Suitable for development and testing")
            print(f"   INFO: May need more capacity for production workloads")
            print(f"\n   RECOMMENDATIONS:")
            print(f"   → Monitor usage patterns in Azure portal")
            print(f"   → Consider capacity 5+ for production")
        else:
            print(f"\n   STATUS: Good Configuration")
            print(f"   ✓ Higher capacity provides better rate limits")
            print(f"   ✓ Suitable for production workloads")
    elif sku_name == 'GlobalStandard':
        print(f"\n   STATUS: Premium Configuration")
        print(f"   ✓ Best availability and rate limits")
        print(f"   ✓ Global load balancing across regions")
        print(f"   ✓ Recommended for production")
    else:
        print(f"\n   STATUS: {sku_name} SKU (capacity: {capacity})")
        print(f"   INFO: Check Azure documentation for specific rate limit details")

def get_usage_recommendations():
    """
    Provide usage recommendations to minimize rate limiting.
    """
    print("\n" + "="*70)
    print("USAGE OPTIMIZATION RECOMMENDATIONS")
    print("="*70)
    
    print("1. REQUEST TIMING:")
    print("   - Wait 1-2 seconds between requests (already implemented)")
    print("   - Avoid rapid-fire testing scenarios")
    print("   - Use longer delays during peak usage hours")
    print()
    
    print("2. MESSAGE OPTIMIZATION:")
    print("   - Keep messages concise to reduce token usage")
    print("   - Break complex requests into smaller parts")
    print("   - Avoid very long context windows when possible")
    print()
    
    print("3. ERROR HANDLING:")
    print("   - Implement exponential backoff (already implemented)")
    print("   - Monitor error patterns in logs")
    print("   - Consider circuit breaker patterns for production use")
    print()
    
    print("4. MONITORING:")
    print("   - Check Azure portal for usage metrics")
    print("   - Set up alerts for approaching quota limits")
    print("   - Review cost and usage reports regularly")
    print()
    
    print("5. SCALING OPTIONS:")
    print("   - Vertical scaling: Increase deployment capacity")
    print("   - Horizontal scaling: Multiple deployments with load balancing")
    print("   - Geographic scaling: Deployments in multiple regions")

def get_quota_summary(subscription_id, resource_group_name, foundry_resource_name, credential):
    """
    Get quota and usage summary from Azure Management API.
    
    Args:
        subscription_id: Azure subscription ID
        resource_group_name: Resource group name
        foundry_resource_name: AI Foundry resource name
        credential: Azure credential
    """
    try:
        print("\n" + "="*70)
        print("QUOTA AND USAGE SUMMARY")
        print("="*70 + "\n")
        
        # Get access token
        token_response = credential.get_token("https://management.azure.com/.default")
        access_token = token_response.token
        
        # Query usages API
        api_version = "2024-10-01"
        usages_url = (
            f"https://management.azure.com/subscriptions/{subscription_id}/"
            f"resourceGroups/{resource_group_name}/providers/Microsoft.CognitiveServices/"
            f"accounts/{foundry_resource_name}/usages?api-version={api_version}"
        )
        
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(usages_url, headers=headers)
        
        if response.status_code == 200:
            usages = response.json()
            usage_list = usages.get('value', [])
            
            if usage_list:
                for usage in usage_list:
                    name = usage.get('name', {})
                    current_value = usage.get('currentValue', 0)
                    limit = usage.get('limit', 0)
                    unit = usage.get('unit', 'Count')
                    
                    usage_name = name.get('localizedValue', name.get('value', 'Unknown'))
                    percentage = (current_value / limit * 100) if limit > 0 else 0
                    
                    print(f"• {usage_name}")
                    print(f"  Current: {current_value:,} / {limit:,} {unit} ({percentage:.1f}% used)")
                    
                    if percentage > 80:
                        print(f"  WARNING: High usage! Consider upgrading capacity")
                    elif percentage > 60:
                        print(f"  INFO: Moderate usage - monitor closely")
                    print()
            else:
                print("No quota information available.")
                print("Usage data may take time to populate after deployment.")
        else:
            logger.debug(f"Quota API returned: {response.status_code} - {response.text}")
            print("Quota information not available at this time.")
            print("This is normal for new deployments.")
            
    except Exception as e:
        logger.debug(f"Error fetching quota: {str(e)}")
        print("Quota information temporarily unavailable.")

def main():
    """Main function to run all checks and recommendations."""
    try:
        print("\n" + "="*70)
        print("AZURE AI FOUNDRY DEPLOYMENT CHECKER")
        print("="*70)
        print(f"Detailed logs: {log_filename}")
        print("Dynamically querying your deployed models, rate limits, and quotas...")
        print("Loading configuration from init.json...")
        print()
        
        # Load configuration from init.json
        init_config = load_init_config()
        credential = DefaultAzureCredential()
        
        # Get subscription ID from subscription name
        print(f"Resolving subscription ID for: {init_config['subscription_name']}")
        logger.info(f"Resolving subscription ID for: {init_config['subscription_name']}")
        subscription_id = get_subscription_id_by_name(init_config['subscription_name'], credential)
        logger.info(f"Subscription ID: {subscription_id}")
        
        # Check deployment status (fetches models dynamically)
        check_deployment_status(init_config, subscription_id, credential)
        
        # Get quota summary
        get_quota_summary(
            subscription_id,
            init_config['resource_group_name'],
            init_config['foundry_resource_name'],
            credential
        )
        
        # Ask user if they want to see usage recommendations
        print("\n" + "="*70)
        try:
            response = input("Would you like to see usage optimization recommendations? (y/n): ").strip().lower()
            if response in ['y', 'yes']:
                get_usage_recommendations()
        except KeyboardInterrupt:
            print("\nSkipping recommendations...")
        
        print("\n" + "="*70)
        print("NEXT STEPS")
        print("="*70)
        print("• To upgrade capacity: python 04_upgrade-deployment.py")
        print("• To chat with models: python 02_chat-with-agent.py")
        print("• To redeploy: python 01_client.py")
        print("="*70 + "\n")
        
    except FileNotFoundError as e:
        print("\n❌ ERROR: init.json not found")
        print("\nPlease create init.json with the following structure:")
        print(json.dumps({
            "subscription_name": "your-subscription-name",
            "resource_group_name": "your-resource-group",
            "foundry_resource_name": "your-foundry-resource",
            "foundry_project_name": "your-project-name",
            "location": "your-azure-region"
        }, indent=2))
        print("\nThen run '01_client.py' to create and deploy the infrastructure.")
    except Exception as e:
        logger.error(f"Failed to run deployment check: {str(e)}")
        print("\n❌ Error occurred. Make sure you have:")
        print("1. Created init.json with required configuration")
        print("2. Proper Azure authentication (az login)")
        print("3. Appropriate permissions on the Azure AI resource")
        print(f"\nError details: {str(e)}")

if __name__ == "__main__":
    main()