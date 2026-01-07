# Fix: Cursor Cannot Run MCP Server from Project Root

## Problem
Cursor is unable to run `run_mcp_server.py` from the project root directory.

## Solution

Update your Cursor MCP configuration with the following:

### Option 1: Using Docker (Recommended)

1. **Use Docker exec** to run MCP server in the container
2. **Full path inside container**: `/app/run_mcp_server.py`
3. **Added PYTHONPATH**: `/app` ensures Python can find modules
4. **Container name**: Use `ratings-api-api-1` (check with `docker ps`)

## Updated Configuration

### Option 1: Docker Exec (Recommended)

Your `c:\Users\jaffa\.cursor\mcp.json` should have:

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

### Option 2: Local Python

If using local Python:

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

## Alternative: Use Python Module Syntax

If the absolute path still doesn't work, try using Python's `-m` flag:

```json
{
  "mcpServers": {
    "ratings-api": {
      "command": "python",
      "args": [
        "-m",
        "run_mcp_server"
      ],
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

## Testing

1. **Test the script manually:**
   ```bash
   cd C:\sabir\Ratings-api
   python run_mcp_server.py --list-tools
   ```

2. **Verify Python can find the app module:**
   ```bash
   cd C:\sabir\Ratings-api
   python -c "from app.mcp_server import mcp, MCP_AVAILABLE; print('OK' if MCP_AVAILABLE else 'FAIL')"
   ```

3. **Restart Cursor** after updating the configuration

## Troubleshooting

### If Python command doesn't work:
- Try `python3` instead of `python`
- Use full path: `"command": "C:\\Python311\\python.exe"`

### If module import fails:
- Ensure `PYTHONPATH` is set correctly
- Verify you're in the project root directory
- Check that `app/__init__.py` exists

### If Cursor still can't connect:
- Check Cursor's Developer Console (Help → Toggle Developer Tools)
- Look for MCP-related errors
- Verify the script runs without errors when executed manually







