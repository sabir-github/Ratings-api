# Fix Cursor MCP "Not Connected" Error

## Problem
Cursor shows "Not connected" errors when trying to access the MCP server:
```
Error listing tools: Not connected
Error listing prompts: Not connected
Error listing resources: Not connected
```

## Solution

### Step 1: Verify Container is Running

```bash
docker ps --format "{{.Names}}"
```

You should see `ratings-api-api-1` (or similar).

### Step 2: Update Cursor Configuration

**Location:** `c:\Users\jaffa\.cursor\mcp.json`

Update to use the correct container name:

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
- The `-i` flag is required for interactive stdio communication
- `PYTHONPATH=/app` ensures Python can find the app modules

### Step 3: Alternative - Use Local Python

If Docker exec doesn't work, use local Python:

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

**Prerequisites for local Python:**
- Python 3.11+ installed
- `fastmcp` package installed: `pip install fastmcp`
- FastAPI server running on port 8000

### Step 4: Test MCP Server Manually

Test if the MCP server works:

```bash
# In Docker (use full path)
docker exec -i ratings-api-api-1 python /app/run_mcp_server.py --list-tools

# Or locally
python run_mcp_server.py --list-tools
```

### Step 5: Restart Cursor

**Completely close and restart Cursor** after updating the configuration.

### Step 6: Verify Connection

1. Open Cursor
2. Check MCP status in Developer Tools (Help → Toggle Developer Tools)
3. Try: "List all companies" in Cursor chat

## Troubleshooting

### Issue: "No such container"
- **Fix:** Check container name with `docker ps`
- Update the container name in Cursor config

### Issue: "Not connected"
- **Fix:** Ensure `-i` flag is in docker exec args
- Verify MCP server can run: `docker exec -i ratings-api-api-1 python run_mcp_server.py --list-tools`
- Check Cursor logs for detailed errors

### Issue: "fastmcp not available"
- **Fix:** Install in container: `docker exec ratings-api-api-1 pip install fastmcp`
- Or use local Python with fastmcp installed

### Issue: Connection timeout
- **Fix:** Ensure FastAPI server is running: `curl http://localhost:8000/health`
- Check API_URL environment variable is correct

## Current Setup

- **MCP Server:** Integrated with FastAPI (port 8000)
- **HTTP Endpoints:** `/api/v1/mcp/*`
- **Stdio Access:** Via `run_mcp_server.py` (for Cursor)
- **Container:** `ratings-api-api-1` (or check with `docker ps`)

