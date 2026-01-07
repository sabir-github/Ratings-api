# External Agents Setup Guide

This guide explains how to connect external AI agents (like Google Gemini, OpenAI, etc.) to the Ratings API MCP server via HTTP.

## Overview

The MCP server is accessible via HTTP endpoints that follow the MCP (Model Context Protocol) specification. This allows external agents to interact with the Ratings API without requiring stdio-based connections.

## Available Endpoints

### 1. MCP Protocol Endpoint (JSON-RPC)
**URL:** `POST /api/v1/mcp/protocol`

This is the main endpoint for MCP protocol communication. It handles JSON-RPC requests following the MCP specification.

### 2. Server Information
**URL:** `GET /api/v1/mcp/protocol/info`

Returns server capabilities, available tools, and endpoint information.

### 3. Server-Sent Events (SSE)
**URL:** `GET /api/v1/mcp/protocol/sse`

Provides streaming MCP protocol support for real-time communication.

### 4. REST API Endpoints
- `GET /api/v1/mcp/tools` - List all available tools
- `POST /api/v1/mcp/tools/{tool_name}/call` - Call a specific tool
- `GET /api/v1/mcp/status` - Server status

## Connecting with Google Gemini

### Step 1: Get Server Information

```bash
curl http://localhost:8000/api/v1/mcp/protocol/info
```

Response:
```json
{
  "protocolVersion": "2024-11-05",
  "capabilities": {
    "tools": {
      "listChanged": true
    }
  },
  "serverInfo": {
    "name": "Ratings API MCP Server",
    "version": "1.0.0"
  },
  "tools": {
    "count": 50,
    "list": [...]
  }
}
```

### Step 2: Initialize Connection

```bash
curl -X POST http://localhost:8000/api/v1/mcp/protocol \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {
        "name": "gemini-client",
        "version": "1.0.0"
      }
    },
    "id": 1
  }'
```

### Step 3: List Available Tools

```bash
curl -X POST http://localhost:8000/api/v1/mcp/protocol \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 2
  }'
```

### Step 4: Call a Tool

```bash
curl -X POST http://localhost:8000/api/v1/mcp/protocol \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_companies",
      "arguments": {
        "skip": 0,
        "limit": 10,
        "active": true
      }
    },
    "id": 3
  }'
```

## Python Client Example

```python
import httpx
import json

class MCPClient:
    def __init__(self, base_url: str = "http://localhost:8000/api/v1/mcp"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
        self.request_id = 0
    
    async def _request(self, method: str, params: dict = None):
        """Make a JSON-RPC request"""
        self.request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self.request_id
        }
        if params:
            payload["params"] = params
        
        response = await self.client.post(
            f"{self.base_url}/protocol",
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    async def initialize(self):
        """Initialize MCP connection"""
        return await self._request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "python-client",
                "version": "1.0.0"
            }
        })
    
    async def list_tools(self):
        """List all available tools"""
        result = await self._request("tools/list")
        return result.get("result", {}).get("tools", [])
    
    async def call_tool(self, tool_name: str, **kwargs):
        """Call an MCP tool"""
        result = await self._request("tools/call", {
            "name": tool_name,
            "arguments": kwargs
        })
        return result.get("result", {})
    
    async def close(self):
        """Close the client"""
        await self.client.aclose()

# Usage example
async def main():
    client = MCPClient()
    
    # Initialize
    await client.initialize()
    
    # List tools
    tools = await client.list_tools()
    print(f"Available tools: {len(tools)}")
    
    # Call a tool
    result = await client.call_tool("get_companies", skip=0, limit=5)
    print(f"Companies: {result}")
    
    await client.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## JavaScript/TypeScript Client Example

```typescript
class MCPClient {
  private baseUrl: string;
  private requestId: number = 0;

  constructor(baseUrl: string = "http://localhost:8000/api/v1/mcp") {
    this.baseUrl = baseUrl;
  }

  private async request(method: string, params?: any): Promise<any> {
    this.requestId++;
    const payload = {
      jsonrpc: "2.0",
      method,
      id: this.requestId,
      ...(params && { params })
    };

    const response = await fetch(`${this.baseUrl}/protocol`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  async initialize() {
    return await this.request("initialize", {
      protocolVersion: "2024-11-05",
      capabilities: {},
      clientInfo: {
        name: "javascript-client",
        version: "1.0.0"
      }
    });
  }

  async listTools() {
    const result = await this.request("tools/list");
    return result.result?.tools || [];
  }

  async callTool(toolName: string, args: any = {}) {
    const result = await this.request("tools/call", {
      name: toolName,
      arguments: args
    });
    return result.result;
  }
}

// Usage
async function main() {
  const client = new MCPClient();
  
  await client.initialize();
  
  const tools = await client.listTools();
  console.log(`Available tools: ${tools.length}`);
  
  const companies = await client.callTool("get_companies", {
    skip: 0,
    limit: 5
  });
  console.log("Companies:", companies);
}
```

## Available Tools

The MCP server exposes all Ratings API endpoints as tools:

### Companies
- `get_companies` - List companies with filtering
- `get_company` - Get company by ID
- `create_company` - Create new company
- `update_company` - Update company
- `delete_company` - Delete company

### Lines of Business (LOBs)
- `get_lobs` - List LOBs
- `get_lob` - Get LOB by ID
- `create_lob` - Create new LOB
- `update_lob` - Update LOB
- `delete_lob` - Delete LOB

### Products
- `get_products` - List products
- `get_product` - Get product by ID
- `create_product` - Create new product
- `update_product` - Update product
- `delete_product` - Delete product

### States
- `get_states` - List states
- `get_state` - Get state by ID
- `create_state` - Create new state
- `update_state` - Update state
- `delete_state` - Delete state

### Contexts
- `get_contexts` - List contexts
- `get_context` - Get context by ID
- `create_context` - Create new context
- `update_context` - Update context
- `delete_context` - Delete context

### Rating Tables
- `get_ratingtables` - List rating tables
- `get_ratingtable` - Get rating table by ID
- `create_ratingtable` - Create new rating table
- `update_ratingtable` - Update rating table
- `delete_ratingtable` - Delete rating table

### Algorithms
- `get_algorithms` - List algorithms
- `get_algorithm` - Get algorithm by ID
- `create_algorithm` - Create new algorithm
- `update_algorithm` - Update algorithm
- `delete_algorithm` - Delete algorithm

### Rating Manuals
- `get_ratingmanuals` - List rating manuals
- `get_ratingmanual` - Get rating manual by ID
- `create_ratingmanual` - Create new rating manual
- `update_ratingmanual` - Update rating manual
- `delete_ratingmanual` - Delete rating manual

### Rating Plans
- `get_ratingplans` - List rating plans
- `get_ratingplan` - Get rating plan by ID
- `create_ratingplan` - Create new rating plan
- `update_ratingplan` - Update rating plan
- `delete_ratingplan` - Delete rating plan

### System
- `health_check` - Check API and database health

## Error Handling

The MCP protocol uses standard JSON-RPC error codes:

- `-32700` - Parse error
- `-32600` - Invalid Request
- `-32601` - Method not found
- `-32602` - Invalid params
- `-32603` - Internal error
- `-32000` - Server error

Example error response:
```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32601,
    "message": "Method not found",
    "data": "Tool 'unknown_tool' not found"
  },
  "id": 1
}
```

## Authentication

Currently, authentication is disabled for MCP endpoints for easier testing. In production, you should:

1. Enable authentication on MCP endpoints
2. Use API keys or OAuth tokens
3. Implement rate limiting
4. Use HTTPS for secure communication

## CORS Configuration

The API is configured to allow CORS requests. For production:

1. Restrict CORS origins to specific domains
2. Configure proper CORS headers
3. Use credentials only when necessary

## Testing

### Test Server Status
```bash
curl http://localhost:8000/api/v1/mcp/status
```

### Test Tool Listing
```bash
curl http://localhost:8000/api/v1/mcp/tools
```

### Test Protocol Endpoint
```bash
curl -X POST http://localhost:8000/api/v1/mcp/protocol \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"ping","id":1}'
```

## Production Deployment

For production use:

1. **Use HTTPS**: Always use HTTPS in production
2. **Enable Authentication**: Add API key or OAuth authentication
3. **Rate Limiting**: Implement rate limiting to prevent abuse
4. **Monitoring**: Add logging and monitoring
5. **Error Handling**: Implement proper error handling and retries
6. **Documentation**: Keep API documentation up to date

## Support

For issues or questions:
- Check the API documentation at `/docs`
- Review server logs
- Test endpoints using the examples above

