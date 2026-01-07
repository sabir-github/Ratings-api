# Quick Start: External Agents (Gemini, etc.)

## 🚀 Connect External Agents in 3 Steps

### Step 1: Check Server Status

```bash
curl http://localhost:8000/api/v1/mcp/status
```

### Step 2: Get Server Info

```bash
curl http://localhost:8000/api/v1/mcp/protocol/info
```

### Step 3: Call a Tool

```bash
curl -X POST http://localhost:8000/api/v1/mcp/protocol \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_companies",
      "arguments": {"skip": 0, "limit": 5}
    },
    "id": 1
  }'
```

## 📝 Python Example

```python
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        # Call a tool
        response = await client.post(
            "http://localhost:8000/api/v1/mcp/protocol",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "get_companies",
                    "arguments": {"skip": 0, "limit": 5}
                },
                "id": 1
            }
        )
        print(response.json())

import asyncio
asyncio.run(main())
```

## 🔗 Available Endpoints

- **Protocol:** `POST /api/v1/mcp/protocol` - Main MCP endpoint
- **Info:** `GET /api/v1/mcp/protocol/info` - Server capabilities
- **SSE:** `GET /api/v1/mcp/protocol/sse` - Server-Sent Events
- **Tools:** `GET /api/v1/mcp/tools` - List all tools
- **Status:** `GET /api/v1/mcp/status` - Server status

## 📚 Full Documentation

See `EXTERNAL_AGENTS_SETUP.md` for complete examples and integration guides.

