# Cursor MCP Server Configuration - Quick Start

## Step-by-Step Instructions

### Step 1: Open Cursor Settings

1. Open Cursor IDE
2. Press `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (macOS) to open Command Palette
3. Type "Preferences: Open Settings (JSON)" and select it
4. Or go to: **File → Preferences → Settings** → Click the `{}` icon (Open Settings JSON)

### Step 2: Add MCP Server Configuration

Add this configuration to your Cursor settings JSON file:

**Option 1: Using Docker (Recommended if using Docker Compose)**
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

**Option 2: Using Local Python**
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

**Important:** 
- For Docker: Replace `ratings-api-api-1` with your actual container name (check with `docker ps`)
- For Local: Replace `C:\\sabir\\Ratings-api` with your actual project path
- Ensure the FastAPI server is running on `http://localhost:8000`

### Step 3: Alternative - Using Cursor UI

1. Go to **Cursor Settings** → **Features** → **MCP**
2. Click **"+ Add New MCP Server"**
3. Fill in:
   - **Name**: `ratings-api`
   - **Type**: `stdio`
   - **Command**: `python`
   - **Arguments**: `run_mcp_server.py`
   - **Working Directory**: `C:\sabir\Ratings-api`
   - **Environment Variables**:
     - `API_URL=http://localhost:8000`
     - `MONGODB_URL=mongodb://admin:password@localhost:37017/?authSource=admin`
     - `MONGODB_DB_NAME=ratings_db`

### Step 4: Verify Configuration

1. **Test the MCP server manually:**
   ```bash
   cd C:\sabir\Ratings-api
   python run_mcp_server.py
   ```
   (It should start and wait - this is normal for stdio mode. Press Ctrl+C to stop)

2. **Check Python and fastmcp:**
   ```bash
   python --version
   python -c "import fastmcp; print('fastmcp OK')"
   ```

### Step 5: Restart Cursor

**IMPORTANT:** Completely quit and restart Cursor for the MCP configuration to take effect.

### Step 6: Test in Cursor

1. Open Cursor's chat/composer
2. Try these prompts:
   - "List all available MCP tools"
   - "Get all companies"
   - "Check the API health status"
   - "List rating tables for company 100000001"

## Configuration File Location

Cursor stores MCP settings in:
- **Windows**: `%APPDATA%\Cursor\User\settings.json` or MCP-specific settings file
- **macOS**: `~/Library/Application Support/Cursor/User/settings.json`
- **Linux**: `~/.config/Cursor/User/settings.json`

## Troubleshooting

### Issue: MCP Server Not Connecting

**Solution:**
1. Check if Python is in PATH: `python --version`
2. Verify fastmcp is installed: `pip show fastmcp`
3. Test the script: `python run_mcp_server.py` (should start without errors)
4. Check Cursor Developer Console (Help → Toggle Developer Tools) for errors

### Issue: "Command not found"

**Solution:**
Use full path to Python:
```json
"command": "C:\\Python311\\python.exe"
```

Or use full path to script:
```json
"args": ["C:\\sabir\\Ratings-api\\run_mcp_server.py"]
```

### Issue: Tools Not Available

**Solution:**
1. Ensure FastAPI server is running: `curl http://localhost:8000/health`
2. Check MCP status: `curl http://localhost:8000/api/v1/mcp/status`
3. Verify fastmcp is installed in the same Python environment Cursor uses

## Example Usage in Cursor

Once configured, you can use natural language:

```
"Get all companies with active=true"
"Create a new company with name 'Test Corp' and company_code 'TEST001'"
"List all rating tables"
"Get algorithm with ID 100000001"
"Find rating manuals for company 100000001"
"Check if the database is connected"
```

Cursor will automatically use the appropriate MCP tools to fulfill these requests!







