# Quick Fix: Cursor MCP "Not Connected" Error

## Immediate Fix

The error "Not connected" means Cursor can't connect to the MCP server. Here's how to fix it:

### Option 1: Update Cursor Config (Recommended)

1. **Open Cursor MCP settings:**
   - File: `c:\Users\jaffa\.cursor\mcp.json`

2. **Update the configuration:**
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

**Key changes:**
- Container name: `ratings-api-api-1` (check with `docker ps`)
- Full path: `/app/run_mcp_server.py` (inside container)
- Added `PYTHONPATH`: `/app` (so Python can find modules)

3. **Restart Cursor completely**

### Option 2: Use Local Python (If Docker doesn't work)

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
        "MONGODB_DB_NAME": "ratings_db",
        "PYTHONPATH": "C:\\sabir\\Ratings-api"
      }
    }
  }
}
```

**Prerequisites:**
- Python 3.11+ installed
- `pip install fastmcp`
- FastAPI server running

### Verify Container Name

```bash
docker ps --format "{{.Names}}"
```

Use the exact container name in your config.

### Test Connection

After updating, test in Cursor:
1. Restart Cursor
2. Open chat
3. Type: "List all companies"
4. Should work!

## Common Issues

### Wrong Container Name
- **Error:** "No such container"
- **Fix:** Check with `docker ps` and update config

### Path Issues
- **Error:** "File not found"
- **Fix:** Use full path `/app/run_mcp_server.py` in Docker

### Module Import Errors
- **Error:** "Module not found"
- **Fix:** Add `PYTHONPATH` environment variable

### Still Not Working?
- Check Cursor Developer Tools (Help → Toggle Developer Tools)
- Look for detailed error messages
- Verify FastAPI is running: `curl http://localhost:8000/health`

