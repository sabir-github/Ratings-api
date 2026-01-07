# Cursor MCP Server Configuration Guide

This guide will help you configure the Ratings API MCP server in Cursor IDE.

## Prerequisites

1. **Python 3.11+** installed and accessible in PATH
2. **fastmcp** package installed: `pip install fastmcp`
3. **FastAPI server running** on `http://localhost:8000` (or update API_URL)

## Configuration Steps

### Step 1: Locate Cursor Settings

Cursor stores MCP server configurations in its settings. The location depends on your OS:

- **Windows**: `%APPDATA%\Cursor\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`
- **macOS**: `~/Library/Application Support/Cursor/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`
- **Linux**: `~/.config/Cursor/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

### Step 2: Add MCP Server Configuration

Open the Cursor settings file and add the following configuration:

```json
{
  "mcpServers": {
    "ratings-api": {
      "command": "python",
      "args": [
        "run_mcp_server.py"
      ],
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

**Important:** Update the `cwd` path to match your actual project directory path.

### Step 3: Alternative - Using Cursor Settings UI

1. Open Cursor Settings:
   - Press `Ctrl+,` (Windows/Linux) or `Cmd+,` (macOS)
   - Or go to File → Preferences → Settings

2. Search for "MCP" or "Model Context Protocol"

3. Click "Edit in settings.json" or find the MCP settings section

4. Add the configuration above

### Step 4: Verify Python Path

Make sure `python` command works. If you need to use `python3` instead:

```json
{
  "mcpServers": {
    "ratings-api": {
      "command": "python3",
      "args": ["run_mcp_server.py"],
      ...
    }
  }
}
```

### Step 5: Restart Cursor

After adding the configuration, **restart Cursor completely** for the changes to take effect.

## Testing the Configuration

1. **Check MCP Server Status:**
   - Open Cursor's developer console (Help → Toggle Developer Tools)
   - Look for MCP-related messages

2. **Test in Cursor Chat:**
   - Open Cursor's chat/composer
   - Try prompts like:
     - "List all companies"
     - "Get company with ID 100000001"
     - "Check the API health status"
   - Cursor should use the MCP tools automatically

3. **Verify Tools are Available:**
   ```bash
   # Check via HTTP API
   curl http://localhost:8000/api/v1/mcp/tools
   
   # Check status
   curl http://localhost:8000/api/v1/mcp/status
   ```

## Configuration Options

### Environment Variables

You can customize the following environment variables:

- **API_URL**: Base URL for the FastAPI server
  - Default: `http://localhost:8000`
  - Docker: `http://api:8000`

- **MONGODB_URL**: MongoDB connection string
  - Default: `mongodb://admin:password@localhost:37017/?authSource=admin`

- **MONGODB_DB_NAME**: Database name
  - Default: `ratings_db`

### Example: Docker Setup

If running in Docker, use:

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
- MCP server is integrated with FastAPI - no separate `mcp-server` container

## Troubleshooting

### MCP Server Not Connecting

1. **Check Python Installation:**
   ```bash
   python --version
   python -c "import fastmcp; print('fastmcp installed')"
   ```

2. **Test MCP Server Manually:**
   ```bash
   cd C:\sabir\Ratings-api
   python run_mcp_server.py
   ```
   The server should start and wait for input (this is normal for stdio mode)

3. **Check Cursor Logs:**
   - Open Developer Tools (Help → Toggle Developer Tools)
   - Check Console for MCP-related errors
   - Look for connection issues or path problems

### Tools Not Available

1. **Verify FastAPI Server is Running:**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Check MCP Server Status:**
   ```bash
   curl http://localhost:8000/api/v1/mcp/status
   ```

3. **Verify fastmcp is Installed:**
   ```bash
   pip show fastmcp
   ```

### Path Issues

If you get "command not found" errors:

1. Use full path to Python:
   ```json
   "command": "C:\\Python311\\python.exe"
   ```

2. Use full path to script:
   ```json
   "args": ["C:\\sabir\\Ratings-api\\run_mcp_server.py"]
   ```

3. Set working directory:
   ```json
   "cwd": "C:\\sabir\\Ratings-api"
   ```

## Using MCP Tools in Cursor

Once configured, you can use natural language prompts in Cursor:

### Example Prompts:

- **"Get all companies"** → Uses `get_companies` tool
- **"Create a new company named Acme Corp"** → Uses `create_company` tool
- **"List all rating tables for company 100000001"** → Uses `get_ratingtables` with filters
- **"Get algorithm with ID 100000001"** → Uses `get_algorithm` tool
- **"Check if the API is healthy"** → Uses `health_check` tool
- **"Find rating manuals with effective_date 2024-01-01"** → Uses `get_ratingmanuals` with date filter

Cursor will automatically:
1. Parse your request
2. Select the appropriate MCP tool
3. Call the tool with correct parameters
4. Return the results

## Advanced Configuration

### Multiple MCP Servers

You can configure multiple MCP servers:

```json
{
  "mcpServers": {
    "ratings-api": {
      "command": "python",
      "args": ["run_mcp_server.py"],
      "cwd": "C:\\sabir\\Ratings-api"
    },
    "another-server": {
      "command": "python",
      "args": ["another_mcp_server.py"]
    }
  }
}
```

### Custom Logging

To see MCP server logs, check Cursor's developer console or configure logging in `run_mcp_server.py`.

## Next Steps

1. ✅ Configure MCP server in Cursor settings
2. ✅ Restart Cursor
3. ✅ Test with simple prompts
4. ✅ Explore all 46 available tools
5. ✅ Use natural language to interact with your API

For a complete list of tools, see `MCP_TOOLS_LIST.md`.







