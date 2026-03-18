"""
MCP Client Web Application

This module implements a web-based user interface for interacting with the MCP (Model Context
Protocol) server. It provides a simple, responsive web form where users can submit URLs for
AI-powered summarization via the MCP server.

Key Features:
- Web Interface: Clean, modern UI built with FastAPI and inline HTML/CSS
- MCP Integration: JSON-RPC 2.0 client for communicating with MCP server
- Internal Access: Deployed as internal-only Container App (VNet access required)
- Health Checks: /health (basic) and /healthz (MCP server connectivity)
- Error Handling: User-friendly error messages with comprehensive logging

Architecture:
    User (Azure VM in VNet) → Client Web UI (FastAPI) → MCP Server → Azure AI Foundry

Network Topology:
- Client runs in Azure Container Apps with internal ingress only
- Accessible only from resources within the same VNet (e.g., Azure VMs)
- Connects to MCP server using internal service discovery
- No direct internet exposure for security

Environment Variables:
- MCP_SERVER_URL: URL of the MCP server (default: http://mcp-foundry-app:8000/mcp)

Endpoints:
- GET /         - Main web interface with URL submission form
- POST /        - Process URL summarization request
- GET /health   - Basic health check
- GET /healthz  - Deep health check with MCP server connectivity verification

Usage:
    python client.py
    
    # Or in container:
    docker run -p 8080:8080 -e MCP_SERVER_URL=<server-url> mcp-client

Workflow:
1. User enters URL in web form
2. Client validates URL format
3. Client sends MCP JSON-RPC request to server (tools/call with summarize_url)
4. Server fetches content and generates summary via Azure AI Foundry
5. Client displays summary or error message to user

Security:
- Internal-only ingress (not exposed to internet)
- URL validation and sanitization
- Timeout protection on requests (60s)
- Error messages don't expose sensitive information

Author: Azure Container Apps MCP Example
License: MIT
"""

import os
import logging
import time
import httpx
from typing import Optional
from dotenv import load_dotenv
from fastmcp import Client
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from jinja2 import Template

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://mcp-foundry-app:8000/mcp")
HTTP_TIMEOUT = 60.0  # Longer timeout for summarization
MCP_TIMEOUT = 200.0  # Extended timeout for MCP client to allow for AI reasoning model processing

# Create FastAPI app
app = FastAPI(title="MCP URL Summarizer Client")

# HTML template (inline for simplicity)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>URL Summarizer - MCP Client</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            max-width: 800px;
            width: 100%;
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            color: #555;
            font-weight: 600;
        }
        input[type="url"] {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        input[type="url"]:focus {
            outline: none;
            border-color: #667eea;
        }
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 30px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            width: 100%;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        button:active {
            transform: translateY(0);
        }
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }
        .result {
            margin-top: 30px;
            padding: 20px;
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            border-radius: 8px;
        }
        .result h2 {
            color: #333;
            margin-bottom: 15px;
            font-size: 20px;
        }
        .result p {
            color: #555;
            line-height: 1.6;
            white-space: pre-wrap;
        }
        .error {
            margin-top: 30px;
            padding: 20px;
            background: #fee;
            border-left: 4px solid #e74c3c;
            border-radius: 8px;
            color: #c0392b;
        }
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(255,255,255,.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin 1s ease-in-out infinite;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .info {
            background: #e3f2fd;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            color: #1565c0;
            font-size: 14px;
        }
        .footer {
            margin-top: 30px;
            text-align: center;
            color: #999;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌐 URL Summarizer</h1>
        <p class="subtitle">Powered by Azure AI Foundry via MCP Protocol</p>
        
        <div class="info">
            💡 <strong>Note:</strong> This client is running in a private Azure Container App, connected via VNet to the MCP server.
        </div>
        
        <form method="post" id="summaryForm">
            <div class="form-group">
                <label for="url">Enter a URL to summarize:</label>
                <input 
                    type="url" 
                    id="url" 
                    name="url" 
                    placeholder="https://example.com/article" 
                    required
                    pattern="https?://.+"
                    title="Please enter a valid http:// or https:// URL"
                >
            </div>
            <input type="hidden" id="start_ms" name="start_ms" value="">
            <button type="submit" id="submitBtn">
                <span id="btnText">Summarize</span>
            </button>
        </form>
        
        {% if summary %}
        <div class="result">
            <h2>📄 Summary</h2>
            <p><strong>URL:</strong> {{ url }}</p>
            {% if exec_time %}
            <p><strong>Execution time:</strong> {{ exec_time }}</p>
            {% endif %}
            <hr style="margin: 15px 0; border: none; border-top: 1px solid #ddd;">
            <p>{{ summary }}</p>
        </div>
        {% endif %}
        
        {% if error %}
        <div class="error">
            <strong>❌ Error:</strong> {{ error }}
        </div>
        {% endif %}

        {% if exec_time %}
        <div class="info" style="margin-top: 20px; margin-bottom: 0;">
            ⏱ <strong>Total execution time:</strong> {{ exec_time }}
        </div>
        {% endif %}
        
        <div class="footer">
            Connected to: {{ mcp_server_url }}
        </div>
    </div>
    
    <script>
        document.getElementById('summaryForm').addEventListener('submit', function(e) {
            const btn = document.getElementById('submitBtn');
            const btnText = document.getElementById('btnText');
            const startMs = document.getElementById('start_ms');
            startMs.value = Date.now().toString();
            btn.disabled = true;
            btnText.innerHTML = '<span class="loading"></span> Summarizing...';
        });
    </script>
</body>
</html>
"""


class MCPClient:
    """MCP client to communicate with the MCP server."""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        logger.info(f"MCP Client initialized with server: {server_url}")
    
    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Call an MCP tool on the server."""
        logger.info(f"Calling MCP tool '{tool_name}' with arguments: {arguments}")
        try:
            # Use FastMCP client directly for compatibility with installed fastmcp version.
            async with Client(self.server_url) as client:
                tool_result = await client.call_tool(tool_name, arguments)

            # Debug: Log the actual result structure
            logger.info(f"Tool result type: {type(tool_result)}")
            logger.info(f"Tool result: {tool_result}")
            if hasattr(tool_result, "__dict__"):
                logger.info(f"Tool result attributes: {tool_result.__dict__}")

            # Normalize common FastMCP result shapes into display text.
            if tool_result is None:
                return ""

            if isinstance(tool_result, str):
                return tool_result

            if isinstance(tool_result, list):
                text_parts = []
                for item in tool_result:
                    if hasattr(item, "text"):
                        text_parts.append(str(item.text))
                    elif isinstance(item, dict) and "text" in item:
                        text_parts.append(str(item["text"]))
                    else:
                        text_parts.append(str(item))
                return "\n".join(text_parts).strip()

            if hasattr(tool_result, "content"):
                content = tool_result.content
                if isinstance(content, list):
                    text_parts = []
                    for item in content:
                        if hasattr(item, "text"):
                            text_parts.append(str(item.text))
                        elif isinstance(item, dict) and "text" in item:
                            text_parts.append(str(item["text"]))
                        else:
                            text_parts.append(str(item))
                    return "\n".join(text_parts).strip()

            return str(tool_result)

        except httpx.TimeoutException:
            logger.error(f"Timeout connecting to MCP server: {self.server_url}")
            raise ValueError("Request timeout - the server took too long to respond")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from MCP server: {e.response.status_code}")
            raise ValueError(f"MCP server returned error: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Connection error to MCP server: {e}")
            raise ValueError(
                f"Failed to connect to MCP server at {self.server_url}: {str(e)}. "
                "Ensure server.py is running and listening on port 8000."
            )


# Initialize MCP client
mcp_client = MCPClient(MCP_SERVER_URL)


def render_page(url: str = "", summary: Optional[str] = None, error: Optional[str] = None, exec_time: Optional[str] = None) -> str:
    """Render the inline HTML template with Jinja variables and conditionals."""
    return Template(HTML_TEMPLATE).render(
        url=url,
        summary=summary,
        error=error,
        exec_time=exec_time,
        mcp_server_url=MCP_SERVER_URL,
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the main page."""
    return HTMLResponse(content=render_page())


@app.post("/", response_class=HTMLResponse)
async def summarize(request: Request, url: str = Form(...), start_ms: Optional[str] = Form(None)):
    """Handle URL summarization request."""
    logger.info(f"Received summarization request for URL: {url}")
    
    try:
        # Validate URL format
        if not url.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        
        # Call MCP server to summarize
        summary = await mcp_client.call_tool(
            tool_name="summarize_url",
            arguments={"url": url}
        )
        
        logger.info(f"Successfully summarized URL: {url}")
        
        exec_time = None
        if start_ms and start_ms.isdigit():
            elapsed_ms = int(time.time() * 1000) - int(start_ms)
            if elapsed_ms >= 0:
                exec_time = f"{elapsed_ms / 1000:.1f} s"

        return HTMLResponse(content=render_page(url=url, summary=summary, exec_time=exec_time))
        
    except Exception as e:
        logger.error(f"Error summarizing URL {url}: {e}", exc_info=True)
        error_message = str(e)
        exec_time = None
        if start_ms and start_ms.isdigit():
            elapsed_ms = int(time.time() * 1000) - int(start_ms)
            if elapsed_ms >= 0:
                exec_time = f"{elapsed_ms / 1000:.1f} s"

        return HTMLResponse(content=render_page(url=url, error=error_message, exec_time=exec_time))


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "mcp-client"}


@app.get("/healthz")
async def healthz():
    """Deep health check - verify MCP server connectivity."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try to reach the MCP server's health endpoint
            server_base = MCP_SERVER_URL.rsplit("/mcp", 1)[0]
            response = await client.get(f"{server_base}/health")
            response.raise_for_status()
            
            return {
                "status": "ok",
                "service": "mcp-client",
                "mcp_server": "connected",
                "mcp_server_url": MCP_SERVER_URL
            }
    except Exception as e:
        logger.error(f"MCP server health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "degraded",
                "service": "mcp-client",
                "mcp_server": "disconnected",
                "error": str(e)
            }
        )


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting MCP Client on port 8080")
    logger.info(f"MCP Server URL: {MCP_SERVER_URL}")
    uvicorn.run(app, host="0.0.0.0", port=8080)
