#!/usr/bin/env python3
"""
Populate .env file with values from ARM template deployment outputs.

Usage:
    python populate_env.py --resource-group <rg-name> --deployment-name <deployment-name>
    
Or to read from parameters.json:
    python populate_env.py --resource-group <rg-name> --deployment-name <deployment-name> --parameters parameters.json
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Resolve the Azure CLI executable (az.cmd on Windows, az on Linux/macOS)
AZ_CLI = shutil.which("az")


def run_az_command(args: list[str]) -> dict:
    """Execute an Azure CLI command and return JSON output."""
    try:
        result = subprocess.run(
            [AZ_CLI] + args + ["--output", "json"],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error running Azure CLI: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}", file=sys.stderr)
        sys.exit(1)


def get_deployment_outputs(resource_group: str, deployment_name: str) -> dict:
    """Retrieve deployment outputs from ARM template."""
    print(f"Fetching deployment outputs for '{deployment_name}' in resource group '{resource_group}'...")
    
    deployment = run_az_command([
        "deployment", "group", "show",
        "--resource-group", resource_group,
        "--name", deployment_name
    ])
    
    if "properties" not in deployment or "outputs" not in deployment["properties"]:
        print("Error: No outputs found in deployment", file=sys.stderr)
        sys.exit(1)
    
    outputs = deployment["properties"]["outputs"]
    return {key: val["value"] for key, val in outputs.items()}


def load_parameters(parameters_file: str) -> dict:
    """Load parameters from parameters.json file."""
    params_path = Path(parameters_file)
    if not params_path.exists():
        print(f"Warning: Parameters file '{parameters_file}' not found")
        return {}
    
    with open(params_path, "r") as f:
        params_data = json.load(f)
    
    # Extract parameter values from ARM parameters format
    if "parameters" in params_data:
        return {key: val.get("value", "") for key, val in params_data["parameters"].items()}
    return params_data


def write_env_file(env_path: Path, outputs: dict, params: dict):
    """Write .env file with deployment outputs and parameters."""
    print(f"Writing .env file to {env_path}...")
    
    # Get values from outputs (preferred) or parameters (fallback)
    endpoint = outputs.get("foundryAccountEndpoint", params.get("projectEndpoint", ""))
    # Convert cognitiveservices.azure.com endpoint to services.ai.azure.com
    project_endpoint = re.sub(
        r"\.cognitiveservices\.azure\.com",
        ".services.ai.azure.com",
        endpoint.rstrip("/")
    )
    model_deployment = outputs.get("modelDeploymentName", params.get("modelDeploymentName", ""))
    mcp_server_url = "http://localhost:8000/mcp"
    
    env_content = f"""PROJECT_ENDPOINT="{project_endpoint}"
MODEL_DEPLOYMENT_NAME="{model_deployment}"
MCP_SERVER_URL="{mcp_server_url}"
"""
    
    env_path.write_text(env_content)
    print("✓ .env file updated successfully")
    print(f"\nConfiguration:")
    print(f"  PROJECT_ENDPOINT: {project_endpoint}")
    print(f"  MODEL_DEPLOYMENT_NAME: {model_deployment}")
    print(f"  MCP_SERVER_URL: {mcp_server_url}")


def main():
    parser = argparse.ArgumentParser(
        description="Populate .env file from ARM deployment outputs"
    )
    parser.add_argument(
        "--resource-group", "-g",
        required=True,
        help="Azure resource group name"
    )
    parser.add_argument(
        "--deployment-name", "-d",
        required=True,
        help="ARM deployment name"
    )
    parser.add_argument(
        "--parameters", "-p",
        default="parameters.json",
        help="Path to parameters.json file (default: parameters.json)"
    )
    parser.add_argument(
        "--output", "-o",
        default=".env",
        help="Output .env file path (default: .env)"
    )
    
    args = parser.parse_args()
    
    # Check Azure CLI is available
    if not AZ_CLI:
        print("Error: Azure CLI not found. Please install it first.", file=sys.stderr)
        print("Visit: https://docs.microsoft.com/cli/azure/install-azure-cli", file=sys.stderr)
        sys.exit(1)
    
    # Get deployment outputs
    outputs = get_deployment_outputs(args.resource_group, args.deployment_name)
    
    # Load parameters if available
    params = load_parameters(args.parameters)
    
    # Write .env file
    env_path = Path(args.output)
    write_env_file(env_path, outputs, params)
    
    print(f"\nNext steps:")
    print(f"1. Verify the values in {env_path}")
    print(f"2. Test the MCP server locally: python server.py")
    print(f"3. Run the MCP client: python client.py")


if __name__ == "__main__":
    main()
