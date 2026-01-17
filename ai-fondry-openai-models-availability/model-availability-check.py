"""
Azure AI Model Availability Checker

This script checks if specific AI models are available in a given Azure region.
It helps validate model availability before attempting deployments to avoid failures.

Key Features:
- Check model availability by region
- Support for multiple model types (GPT-5.1, Llama 4, Claude 4.5, etc.)
- Detailed availability reports with deployment recommendations
- Interactive region and model selection
- Export results to JSON for documentation

Usage Examples:

1. Check all models in a specific region:
   python model-availability-check.py --region "uksouth"

2. Check specific models in multiple regions:
   python model-availability-check.py --models "gpt-5.1,gpt-5.1-mini" --regions "uksouth,westus,eastus"

2b. Check Llama models:
   python model-availability-check.py --models "llama-4-scout-17b-instruct,llama-4-maverick-17b-instruct" --regions "uksouth,westus"

3. Check ALL models in ALL regions (comprehensive):
   python model-availability-check.py --all

4. Check ALL models in specific regions:
   python model-availability-check.py --all-models --regions "uksouth,westus,eastus"

5. Check specific models in ALL regions:
   python model-availability-check.py --all-regions --models "gpt-5.1,llama-4-scout-17b-instruct"

6. Interactive mode:
   python model-availability-check.py --interactive

7. Export results to JSON:
   python model-availability-check.py --all --output comprehensive_availability_report.json
"""

import logging
import json
import argparse
import sys
import os
import signal
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Set UTF-8 encoding for Windows compatibility
if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    # Also set environment variable for subprocess calls
    os.environ['PYTHONIOENCODING'] = 'utf-8'

try:
    from azure.identity import DefaultAzureCredential
    from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
    from azure.mgmt.subscription import SubscriptionClient
    from azure.mgmt.resource import ResourceManagementClient
    from azure.mgmt.compute import ComputeManagementClient
except ImportError as e:
    print(f"ERROR: Missing Azure SDK dependencies: {e}")
    print("Please install required packages:")
    print("pip install azure-identity azure-mgmt-cognitiveservices azure-mgmt-subscription azure-mgmt-resource")
    sys.exit(1)

# Configure logging to write to file only (no console output for detailed logs)
log_filename = f"model_availability_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.DEBUG,  # Capture all details in log file
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Create separate logger for user messages (terminal output)
console_logger = logging.getLogger('console')
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(message)s')
console_handler.setFormatter(console_formatter)
console_logger.addHandler(console_handler)
console_logger.setLevel(logging.INFO)
console_logger.propagate = False

# Log initial setup details (file only)
logger.info("="*80)
logger.info("AZURE AI MODEL AVAILABILITY CHECKER - SESSION START")
logger.info("="*80)
logger.info(f"Log file: {log_filename}")
logger.info(f"Session started at: {datetime.now().isoformat()}")
logger.info(f"Python version: {sys.version}")
logger.info("="*80)

# Model configurations to check
# Updated January 2026 - Removed retired models (GPT-3.5, GPT-4, GPT-4o series)
MODELS_TO_CHECK = {
    # GPT-5 Series - Latest generation
    "gpt-5.1": {
        "name": "gpt-5.1",
        "version": "2025-12-01",
        "format": "OpenAI",
        "provider": "Microsoft",
        "description": "GPT-5.1 - Latest flagship model with advanced reasoning"
    },
    "gpt-5.1-mini": {
        "name": "gpt-5.1-mini",
        "version": "2025-12-01",
        "format": "OpenAI",
        "provider": "Microsoft",
        "description": "GPT-5.1 Mini - Cost-effective next-gen model"
    },
    
    # Embedding Models
    "text-embedding-4-large": {
        "name": "text-embedding-4-large",
        "version": "1",
        "format": "OpenAI",
        "provider": "Microsoft", 
        "description": "Text Embedding 4 Large - Latest advanced embeddings model"
    },
    
    # Llama 4 Models - Current generation in Azure AI Foundry
    # These models are deployed via Serverless API endpoints
    "llama-4-scout-17b-instruct": {
        "name": "Llama-4-Scout-17B-16E-Instruct", 
        "version": "latest",
        "format": "Serverless",
        "provider": "Meta",
        "description": "Llama 4 Scout 17B - Llama 4 variant optimized for efficiency"
    },
    "llama-4-maverick-17b-instruct": {
        "name": "Llama-4-Maverick-17B-128E-Instruct-FP8",
        "version": "latest", 
        "format": "Serverless",
        "provider": "Meta",
        "description": "Llama 4 Maverick 17B - FP8 optimized Llama 4 variant for high throughput"
    },
    
    # Claude Models - Anthropic models via Azure AI Foundry
    "claude-sonnet-4-5": {
        "name": "claude-sonnet-4-5",
        "version": "latest",
        "format": "Serverless",
        "provider": "Anthropic",
        "description": "Claude Sonnet 4.5 - Anthropic's latest balanced model for intelligence and speed"
    },
    "claude-opus-4-5": {
        "name": "claude-opus-4-5",
        "version": "latest",
        "format": "Serverless",
        "provider": "Anthropic",
        "description": "Claude Opus 4.5 - Anthropic's most capable model for complex reasoning"
    },
    "claude-haiku-4-5": {
        "name": "claude-haiku-4-5",
        "version": "latest",
        "format": "Serverless",
        "provider": "Anthropic",
        "description": "Claude Haiku 4.5 - Anthropic's fastest and most cost-effective model"
    }
}

# Common Azure regions
AZURE_REGIONS = {
    "uksouth": "UK South",
    "ukwest": "UK West", 
    "westus": "West US",
    "westus2": "West US 2",
    "westus3": "West US 3",
    "eastus": "East US",
    "eastus2": "East US 2",
    "centralus": "Central US",
    "northcentralus": "North Central US",
    "southcentralus": "South Central US",
    "westeurope": "West Europe",
    "northeurope": "North Europe",
    "francecentral": "France Central",
    "germanywestcentral": "Germany West Central",
    "switzerlandnorth": "Switzerland North",
    "swedencentral": "Sweden Central",
    "norwayeast": "Norway East",
    "canadacentral": "Canada Central",
    "canadaeast": "Canada East",
    "brazilsouth": "Brazil South",
    "japaneast": "Japan East",
    "japanwest": "Japan West",
    "koreacentral": "Korea Central",
    "southeastasia": "Southeast Asia",
    "eastasia": "East Asia",
    "australiaeast": "Australia East",
    "australiasoutheast": "Australia Southeast",
    "centralindia": "Central India",
    "southindia": "South India",
    "westindia": "West India",
    "southafricanorth": "South Africa North"
}

class ModelAvailabilityChecker:
    """Check model availability across Azure regions."""
    
    def __init__(self, subscription_name: str = None, credential=None):
        """Initialize the checker with Azure credentials."""
        self.credential = credential or DefaultAzureCredential()
        self.subscription_name = subscription_name
        self.subscription_id = None
        
    def get_subscription_id(self, subscription_name: str) -> str:
        """Get subscription ID by name."""
        try:
            print(f"Finding subscription: {subscription_name}")
            logger.info(f"Searching for subscription: {subscription_name}")
            subscription_client = SubscriptionClient(credential=self.credential)
            
            # Log all available subscriptions for debugging
            all_subscriptions = list(subscription_client.subscriptions.list())
            logger.debug(f"All available subscriptions: {[sub.display_name for sub in all_subscriptions if sub.display_name]}")
            
            for subscription in all_subscriptions:
                if subscription.display_name and subscription.display_name.lower() == subscription_name.lower():
                    print(f"Found subscription: {subscription.display_name}")
                    logger.info(f"Found subscription: {subscription.display_name} (ID: {subscription.subscription_id})")
                    return subscription.subscription_id
            
            # List available subscriptions if not found
            available_subs = [sub.display_name for sub in all_subscriptions if sub.display_name]
            logger.error(f"Subscription '{subscription_name}' not found. Available: {available_subs}")
            raise ValueError(f"No subscription found with name '{subscription_name}'. Available: {available_subs}")
            
        except Exception as e:
            logger.error(f"Error retrieving subscription ID: {str(e)}")
            raise

    def check_model_availability_in_region(self, region: str, model_key: str, model_config: dict) -> dict:
        """
        Check if a specific model is available in a given region.
        
        Args:
            region (str): Azure region code
            model_key (str): Model identifier
            model_config (dict): Model configuration
            
        Returns:
            dict: Availability result with status and details
        """
        try:
            if not self.subscription_id:
                raise ValueError("Subscription ID not set. Call get_subscription_id first.")
                
            # Create cognitive services client for the region
            client = CognitiveServicesManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )
            
            # Get available models for the region using multiple API approaches
            try:
                logger.info(f"Querying Azure AI services for region {region}")
                
                # Try different approaches based on model type
                model_found = False
                deployment_info = {}
                
                # Approach 1: Use Azure AI Studio/Foundry models API
                try:
                    available_models = client.models.list(location=region)
                    
                    # Log all available models in this region for debugging
                    model_list = []
                    for available_model in available_models:
                        if available_model.model:
                            model_info = f"{available_model.model.name}:{getattr(available_model.model, 'version', 'unknown')}"
                            model_list.append(model_info)
                    
                    logger.debug(f"Available models via models.list in {region}: {model_list}")
                    
                    # Parse the model list that we logged - this contains the working format
                    target_name = model_config["name"]
                    target_version = model_config["version"]
                    
                    # Check for exact match in the parsed model list
                    target_model_string = f"{target_name}:{target_version}"
                    if target_model_string in model_list:
                        logger.info(f"EXACT MATCH: Model {model_key} found in {region} - {target_model_string}")
                        model_found = True
                        deployment_info = {
                            "sku_name": "Standard",
                            "max_capacity": "Unknown",
                            "deployment_types": ["Standard"],
                            "matched_name": target_name,
                            "matched_version": target_version,
                            "discovery_method": "exact_match_models_api"
                        }
                    
                    # If exact match not found, try fuzzy matching
                    if not model_found:
                        for model_info in model_list:
                            if ':' in model_info:
                                available_name, available_version = model_info.split(':', 1)
                                available_name_lower = available_name.lower()
                                target_name_lower = target_name.lower()
                                
                                # Handle common variations in model names
                                if (target_name_lower in available_name_lower or 
                                    available_name_lower in target_name_lower or
                                    target_name_lower.replace("-", "") == available_name_lower.replace("-", "") or
                                    target_name_lower.replace(".", "") == available_name_lower.replace(".", "")):
                                    
                                    logger.info(f"FUZZY MATCH: Model {model_key} matched {model_info} in {region}")
                                    model_found = True
                                    deployment_info = {
                                        "sku_name": "Standard", 
                                        "max_capacity": "Unknown",
                                        "deployment_types": ["Standard"],
                                        "matched_name": available_name,
                                        "matched_version": available_version,
                                        "discovery_method": "fuzzy_match_models_api"
                                    }
                                    break
                
                except Exception as models_api_error:
                    logger.warning(f"Models API failed for {region}: {str(models_api_error)}")
                
                # Approach 2: Query Azure OpenAI Service accounts directly
                if not model_found and model_config["provider"] == "Microsoft" and model_config["format"] == "OpenAI":
                    try:
                        # List all Azure OpenAI accounts in the subscription
                        accounts_list = list(client.accounts.list())
                        region_accounts = [acc for acc in accounts_list if acc.location.lower() == region.lower()]
                        
                        logger.debug(f"Found {len(region_accounts)} Azure OpenAI accounts in {region}")
                        
                        if region_accounts:
                            # Check model availability through each account
                            for account in region_accounts:
                                try:
                                    # Get available models for this account
                                    account_models = client.models.list(
                                        resource_group_name=account.id.split('/')[4],  # Extract RG from resource ID
                                        account_name=account.name
                                    )
                                    
                                    for model in account_models:
                                        model_name = model.model.name if model.model else ""
                                        model_version = getattr(model.model, 'version', '') if model.model else ""
                                        
                                        # Check for exact or close match
                                        if (model_name == model_config["name"] or
                                            model_name.lower() == model_config["name"].lower() or
                                            model_config["name"].lower() in model_name.lower()):
                                            
                                            logger.info(f"ACCOUNT API: Model {model_key} found via account {account.name} in {region}")
                                            model_found = True
                                            deployment_info = {
                                                "discovery_method": "azure_openai_account_api",
                                                "account_name": account.name,
                                                "account_endpoint": getattr(account, 'endpoint', ''),
                                                "model_name_found": model_name,
                                                "model_version_found": model_version,
                                                "sku_name": getattr(model.model, 'sku_name', 'Standard') if model.model else 'Standard'
                                            }
                                            break
                                    
                                    if model_found:
                                        break
                                        
                                except Exception as account_error:
                                    logger.debug(f"Failed to check account {account.name}: {str(account_error)}")
                                    continue
                        
                        # If no accounts found but we want to check if the service is available in region
                        if not model_found and not region_accounts:
                            try:
                                # Try to check if Azure OpenAI service is available in the region
                                # by attempting to create a client for that region
                                logger.debug(f"No existing accounts found, checking service availability in {region}")
                                
                                # Check if we can query available SKUs for the region (indicates service availability)
                                try:
                                    skus = client.resource_skus.list(filter=f"location eq '{region}'")
                                    openai_skus = [sku for sku in skus if 'openai' in sku.resource_type.lower()]
                                    
                                    if openai_skus:
                                        logger.info(f"SERVICE DISCOVERY: Azure OpenAI service available in {region} (found {len(openai_skus)} SKUs)")
                                        # Since the service is available but no specific model info, mark as likely available
                                        model_found = True
                                        deployment_info = {
                                            "discovery_method": "service_sku_discovery",
                                            "available_skus": len(openai_skus),
                                            "note": f"Azure OpenAI service detected in {region}, model likely deployable",
                                            "confidence": "medium"
                                        }
                                    
                                except Exception as sku_error:
                                    logger.debug(f"SKU discovery failed for {region}: {str(sku_error)}")
                            
                            except Exception as service_check_error:
                                logger.debug(f"Service availability check failed for {region}: {str(service_check_error)}")
                    
                    except Exception as openai_check_error:
                        logger.warning(f"Azure OpenAI discovery failed for {region}: {str(openai_check_error)}")
                
                # Approach 3: Dynamic discovery for serverless models (Llama, etc.)
                if not model_found and model_config["format"] == "Serverless":
                    try:
                        # Try Azure AI Foundry serverless endpoints discovery
                        resource_client = ResourceManagementClient(self.credential, self.subscription_id)
                        
                        # Look for AI Foundry/AI Studio resources in the region
                        ai_resources = []
                        try:
                            resources = resource_client.resources.list(filter=f"location eq '{region}'")
                            ai_resources = [r for r in resources if 
                                          'machinelearning' in r.type.lower() or 
                                          'cognitive' in r.type.lower() or
                                          'ai' in r.type.lower()]
                            
                            logger.debug(f"Found {len(ai_resources)} AI-related resources in {region}")
                            
                        except Exception as resource_error:
                            logger.debug(f"Resource discovery failed for {region}: {str(resource_error)}")
                        
                        # Check for Azure AI Hub/Project resources specifically
                        if ai_resources:
                            for resource in ai_resources:
                                if 'hub' in resource.name.lower() or 'project' in resource.name.lower() or 'workspace' in resource.type.lower():
                                    logger.info(f"AI HUB DISCOVERY: Found AI resource {resource.name} in {region}")
                                    model_found = True
                                    deployment_info = {
                                        "discovery_method": "ai_hub_discovery",
                                        "resource_name": resource.name,
                                        "resource_type": resource.type,
                                        "note": f"AI Hub/Project found in {region}, serverless models likely available",
                                        "confidence": "high"
                                    }
                                    break
                        
                        # Alternative: Check Machine Learning workspaces
                        if not model_found:
                            try:
                                try:
                                    from azure.mgmt.machinelearningservices import MachineLearningServicesManagementClient
                                    ml_client = MachineLearningServicesManagementClient(self.credential, self.subscription_id)
                                except ImportError:
                                    logger.debug("Azure ML SDK not available for workspace discovery")
                                    raise
                                workspaces = list(ml_client.workspaces.list())
                                region_workspaces = [ws for ws in workspaces if ws.location.lower() == region.lower()]
                                
                                if region_workspaces:
                                    logger.info(f"ML WORKSPACE DISCOVERY: Found {len(region_workspaces)} ML workspaces in {region}")
                                    model_found = True
                                    deployment_info = {
                                        "discovery_method": "ml_workspace_discovery",
                                        "workspace_count": len(region_workspaces),
                                        "workspace_names": [ws.name for ws in region_workspaces[:3]],  # First 3 names
                                        "note": f"ML workspaces found in {region}, serverless endpoints likely supported",
                                        "confidence": "medium"
                                    }
                                
                            except ImportError:
                                logger.debug("Azure ML SDK not available for workspace discovery")
                            except Exception as ml_error:
                                logger.debug(f"ML workspace discovery failed for {region}: {str(ml_error)}")
                        
                        # Fallback: Check for compute quotas in the region (indicates AI services availability)
                        if not model_found:
                            try:
                                compute_client = ComputeManagementClient(self.credential, self.subscription_id)
                                quotas = compute_client.usage.list(location=region)
                                gpu_quotas = [q for q in quotas if 'gpu' in q.name.value.lower() or 'standard_n' in q.name.value.lower()]
                                
                                if gpu_quotas and any(q.current_value < q.limit for q in gpu_quotas):
                                    logger.info(f"COMPUTE QUOTA DISCOVERY: GPU compute available in {region}")
                                    model_found = True
                                    deployment_info = {
                                        "discovery_method": "compute_quota_discovery",
                                        "gpu_quotas_available": len(gpu_quotas),
                                        "note": f"GPU compute quotas found in {region}, suitable for serverless AI models",
                                        "confidence": "low"
                                    }
                                
                            except ImportError:
                                logger.debug("Azure Compute SDK not available for quota discovery")
                            except Exception as compute_error:
                                logger.debug(f"Compute quota discovery failed for {region}: {str(compute_error)}")
                    
                    except Exception as serverless_discovery_error:
                        logger.warning(f"Serverless model discovery failed for {region}: {str(serverless_discovery_error)}")
                
                if model_found:
                    logger.info(f"Model {model_key} determined available in {region}")
                    return {
                        "status": "available",
                        "region": region,
                        "region_display": AZURE_REGIONS.get(region, region),
                        "model_key": model_key,
                        "model_name": model_config["name"],
                        "model_version": model_config["version"],
                        "format": model_config["format"],
                        "provider": model_config["provider"],
                        "description": model_config["description"],
                        "deployment_info": deployment_info,
                        "checked_at": datetime.now().isoformat()
                    }
                
                # Model not found in available models
                logger.info(f"Model {model_key} ({model_config['name']}:{model_config['version']}) not found in {region}")
                logger.debug(f"Searched for {model_config['name']}:{model_config['version']} but only found: {model_list}")
                
                return {
                    "status": "not_available",
                    "region": region,
                    "region_display": AZURE_REGIONS.get(region, region),
                    "model_key": model_key,
                    "model_name": model_config["name"],
                    "model_version": model_config["version"],
                    "format": model_config["format"],
                    "provider": model_config["provider"],
                    "description": model_config["description"],
                    "reason": "Model not found in region's available models list",
                    "checked_at": datetime.now().isoformat()
                }
                
            except Exception as api_error:
                logger.error(f"API error checking {model_key} in {region}: {str(api_error)}")
                logger.debug(f"Full API error details: {repr(api_error)}")
                return {
                    "status": "error",
                    "region": region,
                    "region_display": AZURE_REGIONS.get(region, region),
                    "model_key": model_key,
                    "model_name": model_config["name"],
                    "model_version": model_config["version"],
                    "format": model_config["format"],
                    "provider": model_config["provider"],
                    "description": model_config["description"],
                    "error": str(api_error),
                    "checked_at": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error checking model {model_key} in region {region}: {str(e)}")
            return {
                "status": "error",
                "region": region,
                "region_display": AZURE_REGIONS.get(region, region),
                "model_key": model_key,
                "error": str(e),
                "checked_at": datetime.now().isoformat()
            }

    def check_multiple_models_regions(self, models: List[str], regions: List[str]) -> Dict[str, Dict[str, dict]]:
        """
        Check availability of multiple models across multiple regions.
        
        Args:
            models (List[str]): List of model keys to check
            regions (List[str]): List of Azure regions to check
            
        Returns:
            Dict: Results organized by region and model
        """
        results = {}
        
        print(f"\nChecking {len(models)} model(s) across {len(regions)} region(s)...")
        logger.info(f"Starting availability check: {len(models)} models across {len(regions)} regions")
        logger.debug(f"Models to check: {models}")
        logger.debug(f"Regions to check: {regions}")
        
        total_checks = len(models) * len(regions)
        current_check = 0
        
        try:
            for region in regions:
                print(f"\n{region.upper()} ({AZURE_REGIONS.get(region, region)})")
                logger.info(f"Starting checks for region: {region} ({AZURE_REGIONS.get(region, region)})")
                results[region] = {}
                
                for model_key in models:
                    current_check += 1
                    progress = f"[{current_check}/{total_checks}]"
                    
                    if model_key not in MODELS_TO_CHECK:
                        print(f"  {progress} WARNING: {model_key} - Unknown model")
                        logger.warning(f"Unknown model: {model_key}")
                        results[region][model_key] = {
                            "status": "unknown_model",
                            "region": region,
                            "model_key": model_key,
                            "error": f"Model {model_key} not in known models list"
                        }
                        continue
                    
                    model_config = MODELS_TO_CHECK[model_key]
                    print(f"  {progress} Checking {model_key}...", end=" ", flush=True)
                    logger.info(f"Checking {model_key} ({model_config['name']} v{model_config['version']}) in {region}")
                    
                    result = self.check_model_availability_in_region(region, model_key, model_config)
                    results[region][model_key] = result
                
                # Print concise result to terminal
                if result["status"] == "available":
                    print("[AVAILABLE]")
                elif result["status"] == "not_available":
                    print("[NOT AVAILABLE]")
                else:
                    print("[ERROR]")
                
                # Log detailed result to file
                logger.info(f"Result for {model_key} in {region}: {result['status']}")
                if result.get("error"):
                    logger.error(f"Error details for {model_key} in {region}: {result['error']}")
                if result.get("deployment_info"):
                    logger.debug(f"Deployment info for {model_key} in {region}: {result['deployment_info']}")
        
        except KeyboardInterrupt:
            print(f"\n\nInterrupted by user. Returning partial results...")
            logger.warning(f"Model checking interrupted at check {current_check}/{total_checks}")
            logger.info("Returning partial results collected so far")
            # Re-raise to be caught by the main handler
            raise
        
        return results

    def generate_availability_report(self, results: Dict[str, Dict[str, dict]]) -> dict:
        """Generate a comprehensive availability report."""
        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_regions_checked": len(results),
                "total_models_checked": len(set().union(*(results[region].keys() for region in results))),
                "regions_checked": list(results.keys())
            },
            "model_availability": {},
            "region_summary": {},
            "recommendations": [],
            "detailed_results": results
        }
        
        # Model availability summary
        all_models = set().union(*(results[region].keys() for region in results))
        for model_key in all_models:
            available_regions = []
            not_available_regions = []
            error_regions = []
            
            for region in results:
                if model_key in results[region]:
                    status = results[region][model_key]["status"]
                    if status == "available":
                        available_regions.append(region)
                    elif status == "not_available":
                        not_available_regions.append(region)
                    else:
                        error_regions.append(region)
            
            report["model_availability"][model_key] = {
                "available_in": available_regions,
                "not_available_in": not_available_regions,
                "errors_in": error_regions,
                "availability_rate": len(available_regions) / len(results) * 100 if results else 0
            }
        
        # Region summary
        for region in results:
            available_count = sum(1 for model_result in results[region].values() if model_result["status"] == "available")
            total_count = len(results[region])
            
            report["region_summary"][region] = {
                "region_display": AZURE_REGIONS.get(region, region),
                "models_available": available_count,
                "models_checked": total_count,
                "availability_rate": (available_count / total_count * 100) if total_count > 0 else 0
            }
        
        # Generate recommendations
        recommendations = []
        
        # Find best regions for each model
        for model_key, availability in report["model_availability"].items():
            if availability["available_in"]:
                recommendations.append(f"{model_key}: Available in {len(availability['available_in'])} region(s) - {', '.join(availability['available_in'])}")
            else:
                recommendations.append(f"{model_key}: Not available in any checked region")
        
        # Find best regions overall
        best_regions = sorted(
            report["region_summary"].items(),
            key=lambda x: x[1]["availability_rate"],
            reverse=True
        )[:3]
        
        if best_regions:
            recommendations.append("\nBest regions for model availability:")
            for region, summary in best_regions:
                recommendations.append(f"  {region} ({summary['region_display']}): {summary['availability_rate']:.1f}% ({summary['models_available']}/{summary['models_checked']})")
        
        report["recommendations"] = recommendations
        
        return report

def interactive_model_selection() -> List[str]:
    """Interactive model selection."""
    print("\n" + "=" * 60)
    print("MODEL SELECTION")
    print("=" * 60)
    print("Available models to check:")
    
    model_keys = list(MODELS_TO_CHECK.keys())
    for i, key in enumerate(model_keys, 1):
        config = MODELS_TO_CHECK[key]
        print(f"{i}. {key}")
        print(f"   Name: {config['name']} (v{config['version']})")
        print(f"   Description: {config['description']}")
        print()
    
    print("Selection options:")
    print(f"{len(model_keys) + 1}. All models")
    print(f"{len(model_keys) + 2}. Common models (gpt-5.1, gpt-5.1-mini, llama-4-scout-17b-instruct)")
    print(f"{len(model_keys) + 3}. Llama models only")
    
    while True:
        try:
            user_input = input("\nSelect models (numbers separated by commas, 'all', or 'common'): ").strip()
            
            if user_input.lower() == 'all' or user_input == str(len(model_keys) + 1):
                return list(MODELS_TO_CHECK.keys())
            
            if user_input.lower() == 'common' or user_input == str(len(model_keys) + 2):
                return ['gpt-5.1', 'gpt-5.1-mini', 'llama-4-scout-17b-instruct']
            
            if user_input.lower() == 'llama' or user_input == str(len(model_keys) + 3):
                return [key for key in MODELS_TO_CHECK.keys() if 'llama' in key.lower()]
            
            # Parse individual selections
            selections = [int(x.strip()) for x in user_input.split(',')]
            selected_models = []
            
            for selection in selections:
                if 1 <= selection <= len(model_keys):
                    selected_models.append(model_keys[selection - 1])
                else:
                    print(f"Invalid selection: {selection}")
                    raise ValueError("Invalid selection")
            
            if selected_models:
                return selected_models
            else:
                print("No models selected. Please try again.")
                
        except (ValueError, IndexError):
            print("Invalid input. Please enter numbers separated by commas.")
            continue

def interactive_region_selection() -> List[str]:
    """Interactive region selection."""
    print("\n" + "=" * 60)
    print("REGION SELECTION")
    print("=" * 60)
    print("Available Azure regions:")
    
    region_keys = list(AZURE_REGIONS.keys())
    for i, key in enumerate(region_keys, 1):
        display_name = AZURE_REGIONS[key]
        print(f"{i:2d}. {key:20s} ({display_name})")
        if i % 10 == 0:  # Add spacing every 10 items
            print()
    
    print("\nQuick selections:")
    print(f"{len(region_keys) + 1}. All regions")
    print(f"{len(region_keys) + 2}. Common regions (uksouth, westus, eastus, westeurope)")
    print(f"{len(region_keys) + 3}. US regions")
    print(f"{len(region_keys) + 4}. Europe regions")
    
    while True:
        try:
            user_input = input("\nSelect regions (numbers separated by commas or quick selection): ").strip()
            
            if user_input == str(len(region_keys) + 1):
                return list(AZURE_REGIONS.keys())
            
            if user_input == str(len(region_keys) + 2):
                return ['uksouth', 'westus', 'eastus', 'westeurope']
            
            if user_input == str(len(region_keys) + 3):
                return [r for r in region_keys if 'us' in r]
            
            if user_input == str(len(region_keys) + 4):
                return [r for r in region_keys if any(eu in r for eu in ['europe', 'uk', 'france', 'germany', 'switzerland', 'sweden', 'norway'])]
            
            # Parse individual selections
            selections = [int(x.strip()) for x in user_input.split(',')]
            selected_regions = []
            
            for selection in selections:
                if 1 <= selection <= len(region_keys):
                    selected_regions.append(region_keys[selection - 1])
                else:
                    print(f"Invalid selection: {selection}")
                    raise ValueError("Invalid selection")
            
            if selected_regions:
                return selected_regions
            else:
                print("No regions selected. Please try again.")
                
        except (ValueError, IndexError):
            print("Invalid input. Please enter numbers separated by commas.")
            continue

def print_results_summary(report: dict):
    """Print a concise summary to terminal and detailed info to log."""
    
    # Log detailed report to file
    logger.info("="*80)
    logger.info("DETAILED AVAILABILITY REPORT")
    logger.info("="*80)
    logger.info(f"Generated: {report['generated_at']}")
    logger.info(f"Regions checked: {report['summary']['total_regions_checked']}")
    logger.info(f"Models checked: {report['summary']['total_models_checked']}")
    
    # Print concise summary to terminal
    print(f"\nAVAILABILITY SUMMARY")
    print("-" * 50)
    
    total_available = 0
    total_checks = 0
    
    for model_key, availability in report["model_availability"].items():
        available_count = len(availability['available_in'])
        total_count = len(availability['available_in']) + len(availability['not_available_in']) + len(availability['errors_in'])
        total_available += available_count
        total_checks += total_count
        
        # Concise terminal output
        status_icon = "[AVAIL]" if available_count > 0 else "[NONE] "
        print(f"{status_icon} {model_key}: {available_count}/{total_count} regions ({availability['availability_rate']:.0f}%)")
        
        # Detailed logging
        logger.info(f"\nModel: {model_key}")
        logger.info(f"  Available in: {availability['available_in']}")
        logger.info(f"  Not available in: {availability['not_available_in']}")
        logger.info(f"  Errors in: {availability['errors_in']}")
        logger.info(f"  Availability rate: {availability['availability_rate']:.1f}%")
    
    # Overall summary
    overall_rate = (total_available / total_checks * 100) if total_checks > 0 else 0
    print(f"\nOverall: {total_available}/{total_checks} ({overall_rate:.0f}%) model-region combinations available")
    
    # Log region summary details
    logger.info("\nREGION SUMMARY:")
    for region, summary in report["region_summary"].items():
        logger.info(f"  {region} ({summary['region_display']}): {summary['availability_rate']:.1f}% ({summary['models_available']}/{summary['models_checked']})")
    
    # Log recommendations
    logger.info("\nRECOMMENDATIONS:")
    for recommendation in report["recommendations"]:
        logger.info(f"  {recommendation}")
        
    # Find and display best regions (terminal)
    if report["region_summary"]:
        best_regions = sorted(
            report["region_summary"].items(),
            key=lambda x: x[1]["availability_rate"],
            reverse=True
        )[:3]
        
        print(f"\nTop regions:")
        for region, summary in best_regions:
            print(f"   {region}: {summary['availability_rate']:.0f}% available")
    
    logger.info("="*80)

def signal_handler(signum, frame):
    """Handle interrupt signals (CTRL-C) gracefully."""
    print(f"\n\nReceived interrupt signal. Shutting down gracefully...")
    print(f"Tip: Use --output to save partial results before interruption")
    sys.exit(130)  # Standard exit code for SIGINT

def main():
    """Main execution function."""
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    parser = argparse.ArgumentParser(description="Check Azure AI model availability by region")
    parser.add_argument("--subscription", help="Azure subscription name")
    parser.add_argument("--regions", help="Comma-separated list of Azure regions")
    parser.add_argument("--models", help="Comma-separated list of model keys to check")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode for selection")
    parser.add_argument("--all", action="store_true", help="Check all models in all regions (comprehensive check)")
    parser.add_argument("--all-models", action="store_true", help="Check all models in specified regions")
    parser.add_argument("--all-regions", action="store_true", help="Check specified models in all regions")
    parser.add_argument("--output", help="Output file path for JSON report")
    parser.add_argument("--list-models", action="store_true", help="List all available models")
    parser.add_argument("--list-regions", action="store_true", help="List all available regions")
    
    args = parser.parse_args()
    
    # Handle list commands
    if args.list_models:
        print("Available models to check:")
        for key, config in MODELS_TO_CHECK.items():
            print(f"  {key:25s} - {config['description']}")
        return
    
    if args.list_regions:
        print("Available Azure regions:")
        for key, display in AZURE_REGIONS.items():
            print(f"  {key:25s} - {display}")
        return
    
    try:
        # Initialize checker
        subscription_name = args.subscription or "Hybrid-PM-Test-2"  # Default subscription name
        print(f"Azure AI Model Availability Checker")
        print(f"Target subscription: {subscription_name}")
        logger.info(f"Initializing checker for subscription: {subscription_name}")
        
        checker = ModelAvailabilityChecker(subscription_name)
        
        # Get subscription ID
        checker.subscription_id = checker.get_subscription_id(subscription_name)
        
        # Determine models and regions to check
        if args.interactive:
            models_to_check = interactive_model_selection()
            regions_to_check = interactive_region_selection()
        elif args.all:
            # Check all models in all regions
            models_to_check = list(MODELS_TO_CHECK.keys())
            regions_to_check = list(AZURE_REGIONS.keys())
            print(f"Comprehensive Check: {len(models_to_check)} models × {len(regions_to_check)} regions = {len(models_to_check) * len(regions_to_check)} checks")
            print("This may take 10-15 minutes...")
            logger.info(f"ALL MODE: Checking {len(models_to_check)} models in {len(regions_to_check)} regions")
        elif args.all_models:
            # Check all models in specified regions
            models_to_check = list(MODELS_TO_CHECK.keys())
            regions_to_check = args.regions.split(',') if args.regions else ['uksouth']
            print(f"All Models Check: {len(models_to_check)} models in {len(regions_to_check)} specified regions")
            logger.info(f"ALL MODELS MODE: Checking all models in regions: {regions_to_check}")
        elif args.all_regions:
            # Check specified models in all regions
            models_to_check = args.models.split(',') if args.models else ['gpt-5.1', 'gpt-5.1-mini', 'llama-4-scout-17b-instruct']
            regions_to_check = list(AZURE_REGIONS.keys())
            print(f"Global Check: {len(models_to_check)} models across {len(regions_to_check)} regions")
            logger.info(f"ALL REGIONS MODE: Checking models {models_to_check} in all regions")
        else:
            models_to_check = args.models.split(',') if args.models else ['gpt-5.1', 'gpt-5.1-mini', 'llama-4-scout-17b-instruct']
            regions_to_check = args.regions.split(',') if args.regions else ['uksouth']
        
        # Clean up inputs
        models_to_check = [m.strip() for m in models_to_check]
        regions_to_check = [r.strip() for r in regions_to_check]
        
        print(f"\nModels: {', '.join(models_to_check)}")
        print(f"Regions: {', '.join(regions_to_check)}")
        logger.info(f"Starting check for models: {models_to_check} in regions: {regions_to_check}")
        
        # Check availability
        results = checker.check_multiple_models_regions(models_to_check, regions_to_check)
        
        # Generate report
        print(f"\nGenerating availability report...")
        logger.info("Generating comprehensive availability report")
        report = checker.generate_availability_report(results)
        
        # Print results
        print_results_summary(report)
        
        # Save to file if requested
        if args.output:
            print(f"\nSaving detailed report...")
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"Report saved: {args.output}")
            logger.info(f"JSON report saved to: {args.output}")
        
        print(f"\nCheck completed successfully!")
        print(f"Detailed logs: {log_filename}")
        logger.info("Model availability check completed successfully")
        logger.info(f"Total API calls made: {len(models_to_check) * len(regions_to_check)}")
        
    except KeyboardInterrupt:
        print(f"\n\nOperation cancelled by user (CTRL-C)")
        print(f"Partial results may be available in log: {log_filename}")
        logger.warning("Model availability check interrupted by user (KeyboardInterrupt)")
        logger.info("Exiting gracefully...")
        sys.exit(130)  # Standard exit code for SIGINT (CTRL-C)
        
    except Exception as e:
        print(f"\nCheck failed: {str(e)}")
        print(f"See log file for details: {log_filename}")
        logger.error(f"Fatal error during availability check: {str(e)}")
        logger.exception("Full error traceback:")
        sys.exit(1)

if __name__ == "__main__":
    main()