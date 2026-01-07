# Fix: Cursor Using Wrong Node.js Version

## Problem

- **System Node.js:** v22.20.0 ✅ (compatible)
- **Cursor's Node.js:** v17.9.1 ❌ (too old)
- **Error:** `SyntaxError: Unexpected token 'with'`

Cursor is using an old Node.js version (v17.9.1) even though you have v22.20.0 installed.

## Solution: Specify Full Node.js Path in Cursor Config

### Step 1: Find Your Node.js Installation Path

Run this command to find where Node.js is installed:

```bash
where node
```

You'll see something like:
```
C:\Program Files\nodejs\node.exe
```

### Step 2: Update Cursor MCP Configuration

Instead of using `npx`, use the full path to Node.js and npx.

**Location:** `%APPDATA%\Cursor\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`

**Update the MongoDB MCP Server configuration:**

#### Option A: Use Full Path to npx (Recommended)

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
    },
    "mongodb": {
      "command": "C:\\Program Files\\nodejs\\npx.cmd",
      "args": [
        "-y",
        "@mongodb-js/mongodb-mcp-server"
      ],
      "env": {
        "MDB_MCP_CONNECTION_STRING": "mongodb://admin:password@localhost:37017/ratings_db?authSource=admin",
        "MDB_MCP_READ_ONLY": "true",
        "PATH": "C:\\Program Files\\nodejs;%PATH%"
      }
    }
  }
}
```

**Important:** Replace `C:\\Program Files\\nodejs\\npx.cmd` with the actual path from `where npx`.

#### Option B: Use Full Path to Node.js

```json
{
  "mcpServers": {
    "mongodb": {
      "command": "C:\\Program Files\\nodejs\\node.exe",
      "args": [
        "C:\\Program Files\\nodejs\\node_modules\\npm\\bin\\npx-cli.js",
        "-y",
        "@mongodb-js/mongodb-mcp-server"
      ],
      "env": {
        "MDB_MCP_CONNECTION_STRING": "mongodb://admin:password@localhost:37017/ratings_db?authSource=admin",
        "MDB_MCP_READ_ONLY": "true",
        "PATH": "C:\\Program Files\\nodejs;%PATH%"
      }
    }
  }
}
```

### Step 3: Alternative - Use Node.js Directly

If npx is causing issues, install MongoDB MCP Server globally and use node directly:

```bash
npm install -g @mongodb-js/mongodb-mcp-server
```

Then in Cursor config:

```json
{
  "mcpServers": {
    "mongodb": {
      "command": "C:\\Program Files\\nodejs\\node.exe",
      "args": [
        "C:\\Users\\%USERNAME%\\AppData\\Roaming\\npm\\node_modules\\@mongodb-js\\mongodb-mcp-server\\dist\\index.js"
      ],
      "env": {
        "MDB_MCP_CONNECTION_STRING": "mongodb://admin:password@localhost:37017/ratings_db?authSource=admin",
        "MDB_MCP_READ_ONLY": "true"
      }
    }
  }
}
```

### Step 4: Restart Cursor

1. **Close Cursor completely**
2. **Reopen Cursor**
3. **Check if the error is gone**

## Finding the Correct Paths

### Find Node.js Path:
```bash
where node
```

### Find npx Path:
```bash
where npx
```

### Find Global npm Modules:
```bash
npm root -g
```

This shows where globally installed packages are located.

## Verify Node.js Version in Cursor

After updating, check Cursor logs to see which Node.js version it's using. The error message should change or disappear.

## Alternative: Uninstall Old Node.js

If you have multiple Node.js installations:

1. **Open Control Panel → Programs → Uninstall a program**
2. **Find all Node.js installations**
3. **Uninstall Node.js v17.9.1** (keep v22.20.0)
4. **Restart computer**
5. **Restart Cursor**

## Quick Test

After updating Cursor config, test if it works:

1. Open Cursor
2. Try using MongoDB MCP tools
3. If you still see the error, check Cursor logs for the Node.js path being used

## Summary

The issue is that Cursor is finding Node.js v17.9.1 instead of v22.20.0. By specifying the full path to the correct Node.js/npx in the Cursor configuration, you force Cursor to use the right version.



