"""
MCP Server with Azure AI Foundry Integration

This module implements a Model Context Protocol (MCP) server that exposes AI-powered tools
via HTTP transport. The server integrates with Azure AI Foundry to provide URL summarization
capabilities using deployed language models.

Key Features:
- MCP Protocol: Implements MCP over HTTP using FastMCP framework (JSON-RPC 2.0)
- Azure Integration: Uses Azure AI Foundry (AIProjectClient) for model inference
- Authentication: Passwordless authentication via Azure DefaultAzureCredential
- Tool: summarize_url - Fetches web content and generates AI-powered summaries
- Health Checks: /health (basic) and /healthz (Foundry connectivity verification)
- Transport: HTTP on port 8000 with MCP endpoint at /mcp

Architecture:
    Client (VS Code/IDE) → HTTP POST /mcp → MCP Server → Azure AI Foundry → LLM

Environment Variables Required:
- PROJECT_ENDPOINT: Azure AI Foundry project endpoint (e.g., https://<project>.<region>.api.azureml.ms/foundry)
- MODEL_DEPLOYMENT_NAME: Name of deployed model (default: gpt-4.1-mini)

Usage:
    python server.py
    
    # Or in container:
    docker run -p 8000:8000 -e PROJECT_ENDPOINT=<endpoint> mcp-server

MCP Tool Available:
- summarize_url(url: str) -> str
  Fetches content from a URL and returns an AI-generated summary using Azure AI Foundry models.
  
Security:
- Uses Azure Managed Identity or az login credentials (no API keys in code)
- URL validation and content-type checking
- Content length limiting (50KB max) to prevent token overflow
- Timeout protection on HTTP requests (30s)

Author: Azure Container Apps MCP Example
License: MIT
"""

import os
import logging
import asyncio
from typing import Optional, Any
from urllib.parse import urlparse
from dotenv import load_dotenv
import httpx
from fastmcp import FastMCP
from mcp.types import TextContent
from fastapi import HTTPException, status
from starlette.requests import Request
from starlette.responses import JSONResponse
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
import trafilatura
from trafilatura import extract

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ---- Foundry config (export these) ----
# PROJECT_ENDPOINT: e.g., https://<your-project>.<region>.api.azureml.ms/foundry
# MODEL_DEPLOYMENT_NAME: e.g., gpt-4.1-mini
PROJECT_ENDPOINT = os.environ.get("PROJECT_ENDPOINT")
MODEL_DEPLOYMENT_NAME = os.environ.get("MODEL_DEPLOYMENT_NAME")

if not PROJECT_ENDPOINT:
    logger.error("PROJECT_ENDPOINT environment variable is required")
    raise ValueError("PROJECT_ENDPOINT environment variable must be set")

# Auth: for local dev, you can use AZ login + DefaultAzureCredential or a token
# See Foundry quickstart for details on auth flows.
logger.info("Initializing Azure credential and Foundry client...")
credential = DefaultAzureCredential()

# Foundry Projects v2 client (preview; see quickstart)
try:
    project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential)
    openai_client = project.get_openai_client()
    logger.info(f"Connected to Foundry endpoint: {PROJECT_ENDPOINT}")
except Exception as e:
    logger.error(f"Failed to initialize Foundry client: {e}")
    raise

mcp = FastMCP("Foundry Summarizer (MCP)")

# Configuration constants
MAX_CONTENT_LENGTH = 50000  # Maximum characters to send to model
HTTP_TIMEOUT = 30.0  # Timeout for HTTP requests
OPENAI_TIMEOUT = 180.0  # Timeout for OpenAI API calls (3 minutes for reasoning models)
MIN_EXTRACTED_LENGTH = 400  # Minimum length to consider extraction successful
JS_RENDER_ENABLED = os.environ.get("ENABLE_JS_RENDER", "false").lower() in ("1", "true", "yes")
JS_RENDER_TIMEOUT = float(os.environ.get("JS_RENDER_TIMEOUT", "20"))

@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request):
    return JSONResponse({"status": "ok"})

@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(_request: Request):
    """Health check with Foundry connectivity verification."""
    try:
        # Test Foundry connectivity with a minimal request
        result = openai_client.models.list()
        models = [m.id for m in result.data]
        
        logger.info(f"Healthz check passed: {len(models)} models available")
        return JSONResponse({
            "status": "ok",
            "foundry": "connected",
            "models_available": len(models),
            "model_deployment": MODEL_DEPLOYMENT_NAME
        })
    except Exception as e:
        logger.error(f"Healthz check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "degraded",
                "foundry": "disconnected",
                "error": str(e)
            }
        )

def _validate_url(url: str) -> bool:
    """Validate URL scheme and format."""
    try:
        result = urlparse(url)
        return all([result.scheme in ('http', 'https'), result.netloc])
    except Exception:
        return False

async def _render_html_with_playwright(url: str) -> Optional[str]:
    """Render JavaScript-heavy pages using Playwright (optional)."""
    try:
        from playwright.async_api import async_playwright
    except Exception as e:
        logger.warning(f"Playwright not available for JS rendering: {e}")
        return None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=int(JS_RENDER_TIMEOUT * 1000))
                return await page.content()
            finally:
                await browser.close()
    except Exception as e:
        logger.warning(f"Playwright rendering failed for {url}: {e}")
        return None

async def _fetch_text(url: str) -> str:
    """Fetch and extract main article content from URL with intelligent HTML processing."""
    if not _validate_url(url):
        raise ValueError(f"Invalid URL: {url}")
    
    logger.info(f"Fetching content from: {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MCP-Summarizer/1.0; +https://example.com)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        try:
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            
            # Check content type
            content_type = r.headers.get('content-type', '').lower()
            if not any(t in content_type for t in ['text/', 'html', 'xml', 'json']):
                logger.warning(f"Non-text content type: {content_type}")
            
            # Extract main content using trafilatura (removes boilerplate, ads, navigation)
            # This is much more efficient than sending raw HTML
            extracted = extract(r.text, include_comments=False, favor_precision=True)
            
            if extracted and len(extracted) >= MIN_EXTRACTED_LENGTH:
                content = extracted
                logger.info(f"Content extracted: ~{len(content)} characters (from raw HTML)")
            else:
                content = None
                if JS_RENDER_ENABLED:
                    logger.info("Extraction short/empty. Trying JS render for dynamic content...")
                    rendered_html = await _render_html_with_playwright(url)
                    if rendered_html:
                        extracted = extract(rendered_html, include_comments=False, favor_precision=True)
                        if extracted and len(extracted) >= MIN_EXTRACTED_LENGTH:
                            content = extracted
                            logger.info(f"Content extracted from rendered HTML: ~{len(content)} characters")
                        else:
                            content = rendered_html
                            logger.warning("Rendered HTML extraction failed, using rendered HTML")

                if content is None:
                    # Fallback: if extraction fails, use raw text (less ideal but works)
                    logger.warning("Trafilatura extraction failed, using raw HTML")
                    content = r.text
            
            # Truncate if too long
            if len(content) > MAX_CONTENT_LENGTH:
                logger.info(f"Truncating content from {len(content)} to {MAX_CONTENT_LENGTH} characters")
                content = content[:MAX_CONTENT_LENGTH] + "\n\n[Content truncated...]"
            
            return content
        except httpx.TimeoutException:
            logger.error(f"Timeout fetching URL: {url}")
            raise ValueError(f"Request timeout for URL: {url}")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for URL: {url}")
            raise ValueError(f"HTTP {e.response.status_code} error fetching URL: {url}")
        except httpx.RequestError as e:
            logger.error(f"Request error for URL {url}: {e}")
            raise ValueError(f"Failed to fetch URL: {url}")


def _extract_text_fragments(value: Any) -> str:
    """Extract text from known SDK response shapes (string, list parts, objects)."""
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
                continue

            if isinstance(item, dict):
                text_value = item.get("text")
                if isinstance(text_value, str) and text_value.strip():
                    parts.append(text_value)
                continue

            text_value = getattr(item, "text", None)
            if isinstance(text_value, str) and text_value.strip():
                parts.append(text_value)

        return "\n".join(parts).strip()

    text_value = getattr(value, "text", None)
    if isinstance(text_value, str):
        return text_value.strip()

    return ""


def _extract_chat_completion_summary(result: Any) -> str:
    """Extract summary text from chat completions responses."""
    if not result or not getattr(result, "choices", None):
        return ""

    message = getattr(result.choices[0], "message", None)
    if message is None:
        return ""

    return _extract_text_fragments(getattr(message, "content", None))


def _call_responses_api_summary(content: str) -> str:
    """Fallback for deployments that return empty chat message content."""
    try:
        response = openai_client.responses.create(
            model=MODEL_DEPLOYMENT_NAME,
            input=[
                {"role": "system", "content": "You are a concise technical summariser."},
                {"role": "user", "content": f"Summarise the following content:\n\n{content}"}
            ],
            max_output_tokens=1000,
            timeout=OPENAI_TIMEOUT,
        )
    except Exception as e:
        logger.warning(f"Responses API fallback failed: {e}")
        return ""

    output_text = getattr(response, "output_text", None)
    summary = _extract_text_fragments(output_text)
    if summary:
        return summary

    # Additional fallback for SDK variants where text is nested in output/content parts.
    output = getattr(response, "output", None)
    if isinstance(output, list):
        nested_parts: list[str] = []
        for item in output:
            content_parts = getattr(item, "content", None)
            nested_text = _extract_text_fragments(content_parts)
            if nested_text:
                nested_parts.append(nested_text)
        return "\n".join(nested_parts).strip()

    return ""

@mcp.tool(name="summarize_url", description="Summarise the main content from a URL using a Foundry model")
async def summarize_url(url: str) -> list[TextContent]:
    """Return a concise summary of the given URL's content."""
    try:
        logger.info(f"Summarizing URL: {url}")
        
        # Fetch and validate content
        content = await _fetch_text(url)
        
        if not content.strip():
            logger.warning(f"Empty content fetched from URL: {url}")
            return [TextContent(type="text", text="Error: The URL returned empty content.")]
        
        # Call Foundry model using chat completions API with retry on capacity throttling
        logger.info(f"Calling Foundry model: {MODEL_DEPLOYMENT_NAME}")
        max_attempts = 3
        backoff_seconds = 5
        result = None
        for attempt in range(1, max_attempts + 1):
            try:
                result = openai_client.chat.completions.create(
                    model=MODEL_DEPLOYMENT_NAME,
                    messages=[
                        {"role": "system", "content": "You are a concise technical summariser."},
                        {"role": "user", "content": f"Summarise the following content:\n\n{content}"}
                    ],
                    temperature=0.3,
                    max_completion_tokens=1000,  # Reasonable limit for summaries
                    timeout=OPENAI_TIMEOUT  # Explicit timeout for long-running reasoning models
                )
                break
            except Exception as e:
                message = str(e)
                is_capacity = "NoCapacity" in message or "429" in message
                if attempt == max_attempts or not is_capacity:
                    raise

                logger.warning(
                    f"Capacity throttled (attempt {attempt}/{max_attempts}). "
                    f"Retrying in {backoff_seconds}s..."
                )
                await asyncio.sleep(backoff_seconds)
                backoff_seconds *= 2

        if result is None:
            return [TextContent(type="text", text="Error: Model request failed after retries.")]
        
        # Debug: Log full response
        logger.info(f"Full response: {result}")
        logger.info(f"Number of choices: {len(result.choices)}")
        if result.choices:
            logger.info(f"Finish reason: {result.choices[0].finish_reason}")
            logger.info(f"Stop reason: {getattr(result.choices[0], 'stop_reason', 'N/A')}")
        
        # Extract summary from response
        if not result.choices:
            logger.error("No choices returned from model")
            return [TextContent(type="text", text="Error: Model did not return a response.")]
        
        message = result.choices[0].message
        logger.info(f"Message object type: {type(message)}")
        logger.info(f"Message.content: {repr(message.content)}")
        logger.info(f"Message.refusal: {repr(message.refusal)}")
        logger.info(f"Message.role: {repr(message.role)}")
        
        # Check for refusal first
        if message.refusal:
            logger.warning(f"Model refused to generate summary: {message.refusal}")
            return [TextContent(type="text", text=f"Model refusal: {message.refusal}")]
        
        summary = _extract_chat_completion_summary(result)

        if not summary.strip():
            logger.warning("Chat completion returned empty content. Trying Responses API fallback.")
            summary = _call_responses_api_summary(content)

        if not summary.strip():
            logger.error(f"Empty content from model response. Full message: {message}")
            return [TextContent(type="text", text="Error: Model returned empty content.")]
        
        # Debug: Log the actual summary content
        logger.info(f"Summary content length: {len(summary)}")
        logger.info(f"Summary preview: {summary[:200]}")
        
        logger.info(f"Successfully generated summary for {url}")
        return [TextContent(type="text", text=summary)]
        
    except ValueError as e:
        # URL validation or fetch errors
        error_msg = f"Failed to fetch URL: {str(e)}"
        logger.error(error_msg)
        return [TextContent(type="text", text=error_msg)]
    except Exception as e:
        # Model or other errors
        error_msg = f"Error generating summary: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return [TextContent(type="text", text=error_msg)]

if __name__ == "__main__":
    # Expose MCP server over Streamable HTTP at /mcp (FastMCP: transport="http")
    logger.info(f"Starting MCP server on port 8000 with model: {MODEL_DEPLOYMENT_NAME}")
    logger.info(f"Foundry endpoint: {PROJECT_ENDPOINT}")
    mcp.run(transport="http", host="0.0.0.0", port=8000, path="/mcp")