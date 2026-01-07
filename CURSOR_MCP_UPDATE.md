# Cursor MCP Configuration Update

## Issue
The `ratings-api-mcp-server` container no longer exists because the MCP server is now integrated with the FastAPI server.

## Solution

Since MCP is integrated with FastAPI, you have two options:

### Option 1: Use the API Container (Recommended)

Update your Cursor MCP configuration to use the `api` container:

**Location:** `%APPDATA%\Cursor\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`

```json
{
  "mcpServers": {
    "ratings-api": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "ratings-api-api-1",
        "python",
        "/app/run_mcp_server.py"
      ],
      "env": {
        "API_URL": "http://localhost:8000",
        "MONGODB_URL": "mongodb://admin:password@localhost:37017/?authSource=admin",
        "MONGODB_DB_NAME": "ratings_db",
        "PYTHONPATH": "/app"
      }
    }
  }
}
```

**Important:**
- Replace `ratings-api-api-1` with your actual container name (check with `docker ps`)
- Use full path `/app/run_mcp_server.py` inside the container
- `PYTHONPATH=/app` is required for Python to find modules

### Option 2: Use Local Python (Alternative)

If you prefer not to use Docker exec, run the MCP server locally:

```json
{
  "mcpServers": {
    "ratings-api": {
      "command": "python",
      "args": ["run_mcp_server.py"],
      "cwd": "C:\\sabir\\Ratings-api",
      "env": {
        "API_URL": "http://localhost:8000",
        "MONGODB_URL": "mongodb://admin:password@localhost:37017/?authSource=admin",
        "MONGODB_DB_NAME": "ratings_db"
      }
    }
  }
}
```

## Verify Container Name

To find the correct container name:
```bash
docker ps --format "{{.Names}}"
```

Look for the container that starts with `ratings-api-api-` (the exact name depends on your Docker Compose project name).

## After Updating

1. **Update the configuration** in Cursor settings
2. **Restart Cursor** completely for changes to take effect
3. **Test** by asking Cursor to "List all companies"

## Why This Changed

The MCP server is now integrated with FastAPI and runs on the same port (8000). There's no need for a separate `mcp-server` container. The MCP server is accessible via:
- HTTP endpoints: `/api/v1/mcp/*`
- Stdio: via `run_mcp_server.py` (for Cursor)

