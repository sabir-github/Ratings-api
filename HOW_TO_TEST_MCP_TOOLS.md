# How to Test MCP Tools

This guide explains various ways to test MCP (Model Context Protocol) tools in the Ratings API.

## Prerequisites

1. **API Server Running**: Ensure the FastAPI server is running
   ```bash
   # Check if server is running
   curl http://localhost:8000/health
   ```

2. **Dependencies**: Install required packages
   ```bash
   pip install httpx requests  # For HTTP testing
   ```

## Method 1: Automated Test Suite (Recommended)

Run the comprehensive automated test suite:

```bash
python test_mcp_auto.py
```

This script tests:
- Server info endpoint
- List tools (HTTP endpoint)
- List tools (JSON-RPC)
- Call `get_companies` tool
- Call `get_states` tool
- Call `get_ratingtables` tool
- Call `health_check` tool

## Method 2: List All Available Tools

List all MCP tools programmatically:

```bash
python list_mcp_tools.py
```

This shows:
- Total number of tools
- Tools grouped by category (Companies, LOBs, Products, etc.)
- Tool names and descriptions
- JSON format output

## Method 3: HTTP Endpoints (Direct API Calls)

### 3.1 List All Tools

```bash
# Get list of all tools
curl http://localhost:8000/api/v1/mcp/tools

# Pretty print JSON
curl -s http://localhost:8000/api/v1/mcp/tools | python -m json.tool
```

### 3.2 Get Server Info

```bash
curl http://localhost:8000/api/v1/mcp/protocol/info
```

### 3.3 Call a Tool via JSON-RPC

```bash
# Example: Call get_companies
curl -X POST http://localhost:8000/api/v1/mcp/protocol \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_companies",
      "arguments": {
        "limit": 10
      }
    },
    "id": 1
  }'
```

## Method 4: Python Script Testing

### 4.1 Simple Test Script

```bash
python test_mcp_simple.py
```

### 4.2 External Agent Test

```bash
python test_external_agent.py
```

## Method 5: Manual Tool Testing via curl

### Test get_companies

```bash
curl -X POST http://localhost:8000/api/v1/mcp/protocol \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_companies",
      "arguments": {"limit": 5}
    },
    "id": 1
  }' | python -m json.tool
```

### Test get_states

```bash
curl -X POST http://localhost:8000/api/v1/mcp/protocol \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_states",
      "arguments": {"limit": 10}
    },
    "id": 2
  }' | python -m json.tool
```

### Test health_check

```bash
curl -X POST http://localhost:8000/api/v1/mcp/protocol \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "health_check"
    },
    "id": 3
  }' | python -m json.tool
```

## Method 6: Using Python Interactive Shell

```python
import httpx
import json

# Base URL
base_url = "http://localhost:8000/api/v1/mcp"

# List tools
response = httpx.get(f"{base_url}/tools")
tools = response.json()
print(f"Found {len(tools.get('tools', []))} tools")

# Call a tool
payload = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "get_companies",
        "arguments": {"limit": 5}
    },
    "id": 1
}
response = httpx.post(f"{base_url}/protocol", json=payload)
result = response.json()
print(json.dumps(result, indent=2))
```

## Method 7: Test via MCP Direct Endpoints

Some tools have direct HTTP endpoints:

```bash
# Get companies via direct endpoint
curl http://localhost:8000/api/v1/mcp/api/companies?limit=10

# Get health status
curl http://localhost:8000/api/v1/mcp/status
```

## Common Tool Names

Here are some commonly used MCP tools:

- `get_companies` - List insurance companies
- `get_lobs` - List lines of business
- `get_products` - List products
- `get_states` - List US states
- `get_contexts` - List rating contexts
- `get_ratingtables` - List rating tables
- `get_algorithms` - List rating algorithms
- `get_ratingmanuals` - List rating manuals
- `get_ratingplans` - List rating plans
- `health_check` - Check system health

## Troubleshooting

### Server Not Running

```bash
# Check if server is running
curl http://localhost:8000/health

# If not running, start it
docker-compose up -d
# or
uvicorn app.main:app --reload
```

### Connection Errors

- Ensure MongoDB is running: `docker ps | grep mongodb`
- Check API logs: `docker logs ratings-api-api-1`
- Verify MONGODB_URL in `.env` file

### Tool Not Found

- List all tools: `curl http://localhost:8000/api/v1/mcp/tools`
- Check tool name spelling (case-sensitive)
- Verify tool is registered in `app/mcp_server.py`

## Example: Complete Test Workflow

```bash
# 1. Check server health
curl http://localhost:8000/health

# 2. List all MCP tools
curl -s http://localhost:8000/api/v1/mcp/tools | python -m json.tool | head -20

# 3. Test get_companies
curl -X POST http://localhost:8000/api/v1/mcp/protocol \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_companies","arguments":{"limit":3}},"id":1}' \
  | python -m json.tool

# 4. Run automated tests
python test_mcp_auto.py
```

## Additional Resources

- `test_mcp_auto.py` - Comprehensive automated test suite
- `list_mcp_tools.py` - List all available tools
- `test_mcp_simple.py` - Simple test script
- `test_external_agent.py` - External agent testing
- `app/mcp_server.py` - MCP server implementation
- `app/api/v1/endpoints/mcp.py` - MCP HTTP endpoints



