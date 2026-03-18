#!/usr/bin/env bash
set -euo pipefail

RG=${1:-}
TEMPLATE=${2:-arm/main.json}
PARAMS=${3:-arm/parameters.json}

if [[ -z "$RG" ]]; then
  echo "Usage: $0 <resource-group> [template-file] [parameters-file]"
  exit 1
fi

az deployment group create   --resource-group "$RG"   --template-file "$TEMPLATE"   --parameters @"$PARAMS"
