# HTTP Streaming with Model Context Protocol (MCP)

This example demonstrates a classic HTTP streaming server and client, as well as the MCP streaming server and client using Python.

## Table of Contents
- [Transport Mechanisms](#transport-mechanisms)
- [Understanding Streaming](#understanding-streaming)
- [Streaming in MCP](#streaming-in-mcp)
- [Notifications in MCP](#notifications-in-mcp)
- [Running the Examples](#running-the-examples)
- [Security Best Practices](#security-best-practices)
- [Migration from SSE](#migration-from-sse-to-streamable-http)

## Transport Mechanisms

A transport mechanism defines how data is exchanged between the client and server. MCP supports multiple transport mechanisms:

| Transport         | Real-time Updates | Streaming | Scalability | Use Case                |
|-------------------|-------------------|-----------|-------------|-------------------------|
| stdio             | No                | No        | Low         | Local CLI tools         |
| SSE               | Yes               | Yes       | Medium      | Web, real-time updates  |
| Streamable HTTP   | Yes               | Yes       | High        | Cloud, multi-client     |

Streaming is a technique in network programming that allows data to be sent and received in small, manageable chunks or as a sequence of events, rather than waiting for an entire response to be ready. This is especially useful for:

- Large files or datasets
- Real-time updates (e.g., chat, progress bars)
- Long-running computations where you want to keep the user informed

### Why Streaming Matters

Streaming enables:
- **Progressive delivery**: Data is delivered progressively, not all at once
- **Real-time processing**: The client can process data as it arrives
- **Reduced latency**: Users get feedback immediately, not just at the end
- **Responsive UIs**: Enables real-time applications with immediate user feedback
- **Efficient resource usage**: More efficient use of network and compute resources

### Classic HTTP Streaming Example

A server sending a series of messages to the client as they become available, rather than waiting for all messages to be ready.

**How it works:**
- The server yields each message as it is ready
- The client receives and prints each chunk as it arrives

**Requirements:**
- The server must use a streaming response (e.g., `StreamingResponse` in FastAPI)
- The client must process the response as a stream (`stream=True` in requests)
- Content-Type is usually `text/event-stream` or `application/octet-stream`

**Example Server (FastAPI with StreamingResponse):**
```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import time

app = FastAPI()

async def event_stream():
    for i in range(1, 6):
        yield f"data: Message {i}\n\n"
        time.sleep(1)

@app.get("/stream")
def stream():
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

**Example Client (using requests):**
```python
import requests

with requests.get("http://localhost:8000/stream", stream=True) as r:
    for line in r.iter_lines():
        if line:
            print(line.decode())
```

## Comparison: Classic Streaming vs MCP Streaming

The key differences between classic HTTP streaming and MCP streaming:

| Feature                | Classic HTTP Streaming         | MCP Streaming (Notifications)      |
|------------------------|-------------------------------|-------------------------------------|
| Main response          | Chunked across stream          | Single, at end                      |
| Progress updates       | Sent as data chunks            | Sent as notifications               |
| Communication pattern  | Simple chunked transfer encoding | Structured JSON-RPC protocol        |
| Message format         | Plain text chunks with newlines | Structured LoggingMessageNotification objects |
| Client requirements    | Must process stream            | Must implement message handler      |
| Use case               | Large files, AI token streams  | Progress, logs, real-time feedback  |

### When to Use Each Approach

- **For simple streaming needs:** Classic HTTP streaming is simpler to implement and sufficient for basic streaming requirements
- **For complex, interactive applications:** MCP streaming provides a more structured approach with richer metadata and separation between notifications and final results
- **For AI applications:** MCP's notification system is particularly useful for long-running AI tasks where you want to keep users informed of progress

## Streaming in MCP

Ok, so you've seen some recommendations and comparisons so far on the difference between classical streaming and streaming in MCP. Let's get into detail exactly how you can leverage streaming in MCP.

Understanding how streaming works within the MCP framework is essential for building responsive applications that provide real-time feedback to users during long-running operations.

In MCP, streaming is not about sending the main response in chunks, but about sending **notifications** to the client while a tool is processing a request. These notifications can include progress updates, logs, or other events.

### How it works

The main result is still sent as a single response. However, notifications can be sent as separate messages during processing and thereby update the client in real time. The client must be able to handle and display these notifications.

## Notifications in MCP

A notification is a message sent from the server to the client to inform the client about progress, status, or other events during a long-running operation. Notifications improve transparency and user experience.

For example, a client should send a notification once the initial handshake with the server has been made.

### Notification Structure

A notification looks like the following JSON message:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/message",
  "params": {
    "level": "info",
    "data": "Processing file 1/3..."
  }
}
```

### Notification Levels

Notifications in MCP belong to the ["Logging"](https://modelcontextprotocol.io/specification/draft/server/utilities/logging) topic and support the following levels:

| Level     | Description                    | Example Use Case                |
|-----------|-------------------------------|---------------------------------|
| debug     | Detailed debugging information | Function entry/exit points      |
| info      | General informational messages | Operation progress updates      |
| notice    | Normal but significant events  | Configuration changes           |
| warning   | Warning conditions             | Deprecated feature usage        |
| error     | Error conditions               | Operation failures              |
| critical  | Critical conditions            | System component failures       |
| alert     | Action must be taken immediately | Data corruption detected      |
| emergency | System is unusable             | Complete system failure         |

### Enabling Logging in MCP

To enable logging as a server capability, configure it like so:

```json
{
  "capabilities": {
    "logging": {}
  }
}
```

> [!NOTE]
> Depending on the SDK used, logging might be enabled by default, or you might need to explicitly enable it in your server configuration.

### Implementing Notifications

#### Server-side: Sending Notifications

In MCP, you define tools that can send notifications while processing requests. The server uses the context object (usually `ctx`) to send messages to the client.

```python
@mcp.tool(description="A tool that sends progress notifications")
async def process_files(message: str, ctx: Context) -> TextContent:
    await ctx.info("Processing file 1/3...")
    await ctx.info("Processing file 2/3...")
    await ctx.info("Processing file 3/3...")
    return TextContent(type="text", text=f"Done: {message}")
```

Additionally, ensure your server uses a streaming transport like `streamable-http`:

```python
mcp.run(transport="streamable-http")
```

#### Client-side: Receiving Notifications

Implement a message handler that listens for and displays notifications as they arrive:

```python
async def message_handler(message):
    if isinstance(message, types.ServerNotification):
        print("NOTIFICATION:", message)
    else:
        print("SERVER MESSAGE:", message)
```

## Progress Notifications

Progress notifications are real-time messages sent from the server to the client during long-running operations. Instead of waiting for the entire process to finish, the server keeps the client updated about the current status.

**Example:**
```
Processing document 1/10
Processing document 2/10
...
Processing complete!
```

### Why Use Progress Notifications?

- **Better user experience:** Users see updates as work progresses, not just at the end
- **Real-time feedback:** Clients can display progress bars or logs, making the app feel responsive
- **Easier debugging and monitoring:** Developers and users can see where a process might be slow or stuck

### Implementation Example

**Server:**
```python
@mcp.tool(description="A tool that sends progress notifications")
async def process_files(message: str, ctx: Context) -> TextContent:
    for i in range(1, 11):
        await ctx.info(f"Processing document {i}/10")
    await ctx.info("Processing complete!")
    return TextContent(type="text", text=f"Done: {message}")
```

**Client:**
```python
async def message_handler(message):
    if isinstance(message, types.ServerNotification):
        print("NOTIFICATION:", message)
    else:
        print("SERVER MESSAGE:", message)
```

## Security Best Practices

When implementing MCP servers with HTTP-based transports, security becomes a paramount concern that requires careful attention to multiple attack vectors and protection mechanisms.

### Key Security Considerations

- **Origin Header Validation:** Always validate the `Origin` header to prevent DNS rebinding attacks
- **Localhost Binding:** For local development, bind servers to `localhost` to avoid exposing them to the public internet
- **Authentication:** Implement authentication (e.g., API keys, OAuth) for production deployments
- **CORS:** Configure Cross-Origin Resource Sharing (CORS) policies to restrict access
- **HTTPS:** Use HTTPS in production to encrypt traffic

### Best Practices

- Never trust incoming requests without validation
- Log and monitor all access and errors
- Regularly update dependencies to patch security vulnerabilities

## Running the Examples

### Classic HTTP Streaming

Open two terminals in the Python virtual environment:

**Terminal 1 - Start the server:**
```bash
python server.py
```

Output:
```console
Starting FastAPI server for classic HTTP streaming...
INFO:     Will watch for changes in these directories: ['C:\mcp-http-streaming']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [35576] using StatReload
INFO:     Started server process [18940]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Terminal 2 - Run the client:**
```bash
python client.py
```

Output:
```console
2026-02-28 20:30:23 - mcp_client - INFO - Running classic HTTP streaming client...
2026-02-28 20:30:23 - mcp_client - INFO - Connecting to http://localhost:8000/stream with message: hello
2026-02-28 20:30:23 - mcp_client - INFO - --- Streaming Progress ---
Processing file 1/3...
Processing file 2/3...
Processing file 3/3...
Here's the file content: hello
2026-02-28 20:30:26 - mcp_client - INFO - --- Stream Ended ---
```

### MCP Streaming with Streamable HTTP

Open two terminals in the Python virtual environment:

**Terminal 1 - Start the MCP server:**
```bash
python server.py mcp
```

Output:
```console
Starting MCP server with streamable-http transport...
INFO:     Started server process [37052]
INFO:     Waiting for application startup.
[02/28/26 20:32:26] INFO     StreamableHTTP session       streamable_http_manager.py:116
                             manager started                                            
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

**Terminal 2 - Run the MCP client:**
```bash
python client.py mcp
```

Output (truncated):
```console
2026-02-28 20:33:18 - mcp_client - INFO - Running MCP client...
2026-02-28 20:33:18 - mcp_client - INFO - Starting client...
2026-02-28 20:33:19 - httpx - INFO - HTTP Request: POST http://localhost:8000/mcp "HTTP/1.1 200 OK"
2026-02-28 20:33:19 - mcp_client - INFO - Session initialized, ready to call tools.
2026-02-28 20:33:19 - mcp_client - INFO - NOTIFICATION: Processing file_1.txt (1/3)...
2026-02-28 20:33:19 - mcp_client - INFO - NOTIFICATION: Processing file_2.txt (2/3)...
2026-02-28 20:33:20 - mcp_client - INFO - NOTIFICATION: Processing file_3.txt (3/3)...
2026-02-28 20:33:21 - mcp_client - INFO - NOTIFICATION: All files processed!
2026-02-28 20:33:23 - mcp_client - INFO - Tool result: Processed files: file_1.txt, file_2.txt, file_3.txt | Message: hello from client
```

### Key Implementation Steps

1. Create the MCP server using FastMCP
2. Define a tool that processes a list and sends notifications using `ctx.info()` or `ctx.log()`
3. Run the server with `transport="streamable-http"`
4. Implement a client with a message handler to display notifications as they arrive

## Migration from SSE to Streamable HTTP

For applications currently using Server-Sent Events (SSE), migrating to Streamable HTTP provides enhanced capabilities and better long-term sustainability for your MCP implementations.

### Why Upgrade?

There are two compelling reasons to upgrade from SSE to Streamable HTTP:

- **Better scalability:** Streamable HTTP offers better scalability and compatibility
- **Richer notifications:** Enhanced support for structured notifications
- **Recommended approach:** It is the recommended transport for new MCP applications

### Migration Steps

Here's how to migrate from SSE to Streamable HTTP in your MCP applications:

1. **Update server code** to use `transport="streamable-http"` in `mcp.run()`
2. **Update client code** to use `streamablehttp_client` instead of SSE client
3. **Implement a message handler** in the client to process notifications
4. **Test for compatibility** with existing tools and workflows

### Maintaining Compatibility

It's recommended to maintain compatibility with existing SSE clients during the migration process:

- Support both SSE and Streamable HTTP by running both transports on different endpoints
- Gradually migrate clients to the new transport
- Test for differences in notification delivery

## Reference

- [mcp-for-beginners](https://github.com/microsoft/mcp-for-beginners/tree/main)
- [MCP Specification - Logging](https://modelcontextprotocol.io/specification/draft/server/utilities/logging)