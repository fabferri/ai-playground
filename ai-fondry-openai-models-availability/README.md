<properties
pageTitle= 'Azure OpenAI Model Availability Checker'
description= "Azure OpenAI Model Availability Checker"
documentationcenter= "https://github.com/fabferri"
services="AI Foundry"
authors="fabferri"
editor="fabferri"/>

<tags
   ms.service="configuration-Example"
   ms.devlang="python"
   ms.topic="article"
   ms.tgt_pltfrm="AI Foundry"
   ms.workload="OpenAI Model"
   ms.date="01/17/2026"
   ms.author="fabferri" />

# Azure OpenAI Model Availability Checker

A Python script to check the availability of Azure OpenAI models across different regions. This tool helps you identify which OpenAI models are available in specific Azure regions for your projects.

## Features

### Script core capabilities

- **Model Discovery**: Dynamically discovers OpenAI models using Azure APIs
- **Multi-Region Support**: Check availability across all Azure regions
- **Flexible Filtering**: Filter by model names, types, regions, or capabilities
- **Multiple Output Formats**: Console (with colors) and JSON
- **Error Handling**: Graceful handling of API limits and network issues

### Easy User Experience

- **Interactive Mode**: User-friendly menu system for easy model selection
- **Predefined Collections**: Quick access to common model groups (GPT, Llama, etc.)
- **Interrupt Handling**: Clean exit with Ctrl+C during long operations
- **Comprehensive Help**: Usage examples and troubleshooting guides

### Supported Model Types

| Model                         | Type           | Provider   | Cost (Relative)           | Performance                          | Recommended Usage                                      |
| ----------------------------- | -------------- | ---------- | ------------------------- | ------------------------------------ | ------------------------------------------------------ |
| gpt-5.1                       | Chat LLM       | Microsoft  | High                      | Excellent (advanced reasoning)       | Premium chatbots, complex reasoning, enterprise AI     |
| gpt-5.1-mini                  | Chat LLM       | Microsoft  | Moderate                  | Very Good (cost-effective next-gen)  | Real-time chat, cost-sensitive apps                    |
| text-embedding-4-large        | Embedding      | Microsoft  | Moderate                  | Best for embeddings                  | Semantic search, RAG pipelines                         |
| llama-4-scout-17b-instruct    | Chat LLM (MoE) | Meta       | Infra cost: Moderate      | Efficient (MoE routing)              | Cost-effective chat, mid-scale deployments             |
| llama-4-maverick-17b-instruct | Chat LLM (MoE) | Meta       | Infra cost: Low per token | Ultra-scalable (FP8 precision)       | Large-scale, low-latency chat systems                  |
| claude-sonnet-4-5             | Chat LLM       | Anthropic  | Moderate                  | Excellent (balanced)                 | General-purpose AI, coding, analysis                   |
| claude-opus-4-5               | Chat LLM       | Anthropic  | High                      | Best (complex reasoning)             | Complex reasoning, research, enterprise AI             |
| claude-haiku-4-5              | Chat LLM       | Anthropic  | Low                       | Good (fast, efficient)               | Real-time chat, high-volume, cost-sensitive apps       |

## Prerequisites

- Python 3.13 or higher
- Azure CLI installed and configured (`az login`)
- Appropriate Azure permissions to list AI/ML resources

## Installation & Setup

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```
in the file **requirements.txt** are listed the Azure SDK packages

## Usage

### Command Line Options

- `--all`: Check all available models in all regions (comprehensive scan)
- `--all-models`: Check all available models in specified regions
- `--all-regions`: Check specified models in all available regions
- `--models`: Comma-separated list of model names to check
- `--regions`: Comma-separated list of Azure regions to check
- `--interactive`: Launch interactive mode for easy selection
- `--list-models`: List all available models and exit
- `--list-regions`: List all available regions and exit
- `--output`: Output file path for JSON report
- `--help`: Show detailed help information

### Usage Examples

```python
# Check all models in all regions (comprehensive)
python model-availability-check.py --all

# Check all models in specific regions
python model-availability-check.py --all-models --regions "East US,West Europe,UK South"

# Check specific models in all regions
python model-availability-check.py --all-regions --models "gpt-5.1,llama-4-scout-17b-instruct"
```

#### Targeted Checks

```python
# Check specific models in specific regions
python model-availability-check.py --models "gpt-5.1,gpt-5.1-mini" --regions "East US,West Europe"

# Check specific models in specific regions
python model-availability-check.py --models "claude-sonnet-4-5,claude-opus-4-5,claude-haiku-4-5" --regions "swedencentral,uksouth"

# Check Llama models only
python model-availability-check.py --models "llama-4-scout-17b-instruct,llama-4-maverick-17b-instruct"

# Check embedding models
python model-availability-check.py --models "text-embedding-4-large"
```

#### Interactive and Output Options

```python
# Interactive mode with menu selection
python model-availability-check.py --interactive

# Export results to JSON
python model-availability-check.py --models "gpt-5.1" --regions "East US" --output results.json
```

#### Discovery and Information

```python
# List all available models
python model-availability-check.py --list-models

# List all available regions
python model-availability-check.py --list-regions

# Show help
python model-availability-check.py --help
```

### Interactive Mode

Launch interactive mode for easy model and region selection:

```python
python model-availability-check.py --interactive
```

Interactive mode provides:

- **Model Selection Menu**: Choose from predefined model groups or custom selection
- **Region Selection**: Select specific regions or use "All regions"
- **Common Selections**: Quick access to popular model combinations

Available interactive options:

1. **All models in all regions** - Comprehensive scan
2. **Common models** - GPT-5.1, GPT-5.1-mini, Llama 4, Claude 4
3. **GPT models only** - All GPT variants
4. **Llama models only** - All Llama variants
5. **Claude models only** - All Anthropic Claude variants
6. **Embedding models only** - Text embedding models
7. **Custom selection** - Choose specific models and regions


## Interrupt Handling

### Graceful Exit with Ctrl+C

The tool supports clean interruption during long-running operations:

- **Safe Termination**: Ctrl+C safely stops processing
- **Progress Preservation**: Completed checks are saved before exit
- **Resource Cleanup**: Proper cleanup of network connections
- **Partial Results**: Display results collected before interruption

## Troubleshooting

### Common Issues

#### Authentication Issues
```
Error: Unable to authenticate with Azure
```
**Solution:**
   1. Ensure Azure CLI is installed: `az --version`
   2. Login to Azure: `az login`
   3. Verify subscription access: `az account show`

#### Permission Issues
```
Error: Insufficient permissions to list models
```
**Solution:**
   1. Ensure your account has appropriate Azure permissions
   2. Check subscription access: `az account list`
   3. Contact your Azure administrator for AI/ML resource access

#### Network Issues
```
Error: Connection timeout or API rate limits
```
**Solution:**
   1. Check internet connection
   2. Wait a few minutes and retry (API rate limits)
   3. Check the log file for detailed error messages

### Debugging

#### Detailed Logging

Check the generated log file for detailed information:

```powershell
# The script automatically generates detailed logs
# Look for files like: model_availability_check_YYYYMMDD_HHMMSS.log
Get-Content model_availability_check_*.log
```

#### Check Dependencies

Verify all dependencies are installed:
```powershell
# Activate virtual environment first
.\.venv\Scripts\activate
pip list
```

#### Test Azure Connection

```powershell
# Test Azure CLI connection
az account show

# List available subscriptions
az account list
```

## License

This project is licensed under the MIT License - See [LICENSE](../LICENSE) file for details.

`Tag: Azure AI Foundry models, OpenAI` <br>
`date: 07-11-2025`
`date: 17-01-2026`
