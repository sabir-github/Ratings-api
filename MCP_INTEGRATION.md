# MCP Server Integration with FastAPI

The MCP server is now fully integrated with the FastAPI server and runs on the same port (8000).

## Integration Details

### How It Works

1. **Single Process**: The MCP server runs in the same process as FastAPI
2. **Same Port**: Both services share port 8000
3. **HTTP Access**: MCP server is accessible via HTTP endpoints
4. **No Separate Container**: No need for a separate `mcp-server` Docker service

### Available Endpoints

The MCP server is accessible at the following endpoints:

- **`GET /api/v1/mcp/tools`** - List all available MCP tools
- **`POST /api/v1/mcp/tools/{tool_name}/call`** - Call a specific MCP tool
- **`GET /api/v1/mcp/status`** - Get MCP server status
- **`POST /api/v1/mcp/protocol`** - MCP protocol endpoint (JSON-RPC)
- **`GET /api/v1/mcp/protocol/info`** - Get MCP server information
- **`GET /api/v1/mcp/protocol/sse`** - Server-Sent Events endpoint

### Benefits

1. **Simplified Deployment**: Only one service to manage
2. **Resource Efficiency**: Single process, shared resources
3. **Easy Access**: All endpoints on the same port
4. **No Port Conflicts**: No need to manage multiple ports

### Usage Examples

#### List All Tools
```bash
curl http://localhost:8000/api/v1/mcp/tools
```

#### Check MCP Status
```bash
curl http://localhost:8000/api/v1/mcp/status
```

#### Call MCP Protocol
```bash
curl -X POST http://localhost:8000/api/v1/mcp/protocol \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 1
  }'
```

### Docker Configuration

The `docker-compose.yml` no longer includes a separate `mcp-server` service. The MCP server runs as part of the `api` service.

### For Cursor IDE

If you need stdio-based MCP for Cursor IDE, you can:

**Option 1: Use Docker exec (Recommended)**
```json
{
  "mcpServers": {
    "ratings-api": {
      "command": "docker",
      "args": ["exec", "-i", "ratings-api-api-1", "python", "/app/run_mcp_server.py"],
      "env": {
        "API_URL": "http://localhost:8000",
        "PYTHONPATH": "/app"
      }
    }
  }
}
```

**Option 2: Run locally**
- Run `run_mcp_server.py` locally for stdio access
- Requires Python 3.11+ and `fastmcp` installed

### Migration Notes

If you were using the separate `mcp-server` Docker service:
1. ✅ **Already done:** Removed `mcp-server` service from `docker-compose.yml`
2. **Update Cursor config:** Change container name from `ratings-api-mcp-server` to `ratings-api-api-1`
3. **Update paths:** Use `/app/run_mcp_server.py` (full path in container)
4. **Add PYTHONPATH:** Set to `/app` in environment variables
5. All MCP functionality is now available via HTTP on port 8000

