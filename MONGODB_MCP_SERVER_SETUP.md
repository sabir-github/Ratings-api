# MongoDB MCP Server Setup Guide

This guide explains how to set up the official MongoDB MCP Server to work alongside your existing Ratings API MCP server.

## Overview

The MongoDB MCP Server (`@mongodb-js/mongodb-mcp-server`) is an official MongoDB package that provides MCP tools for directly interacting with MongoDB databases. This is separate from your custom Ratings API MCP server.

## Prerequisites

1. **Node.js 20.10.0+ or 21+** - **CRITICAL**: Required for import attributes support
   - The MongoDB MCP Server uses `import ... with { type: "json" }` syntax
   - This feature requires Node.js 20.10.0+ or any Node.js 21.x version
   - Check your version: `node --version`
   - Download latest: https://nodejs.org/
2. **MongoDB Connection** - Your MongoDB instance (local or Atlas)

## Installation Steps

### Step 1: Install/Upgrade Node.js (if not already installed)

**IMPORTANT**: MongoDB MCP Server requires Node.js 20.10.0+ or 21+

Download and install Node.js 20.10.0+ or 21+ from: https://nodejs.org/

Verify installation:
```bash
node --version
npm --version
```

**Check if your version is compatible:**
- ✅ Node.js 20.10.0 or higher
- ✅ Node.js 21.x or higher
- ❌ Node.js 20.0.0 - 20.9.x (will show "Unexpected token 'with'" error)
- ❌ Node.js 18.x or lower

If you see an error like `SyntaxError: Unexpected token 'with'`, you need to upgrade Node.js.

### Step 2: Install MongoDB MCP Server

Install globally:
```bash
npm install -g @mongodb-js/mongodb-mcp-server
```

Or install locally in your project:
```bash
npm init -y
npm install @mongodb-js/mongodb-mcp-server
```

### Step 3: Configure Connection

You have two options for connecting to MongoDB:

#### Option A: Connection String (Recommended for Local MongoDB)

Set environment variable:
```bash
# Windows Command Prompt
set MDB_MCP_CONNECTION_STRING=mongodb://admin:password@localhost:37017/ratings_db?authSource=admin

# Windows PowerShell
$env:MDB_MCP_CONNECTION_STRING="mongodb://admin:password@localhost:37017/ratings_db?authSource=admin"

# Linux/Mac
export MDB_MCP_CONNECTION_STRING="mongodb://admin:password@localhost:37017/ratings_db?authSource=admin"
```

#### Option B: MongoDB Atlas API Credentials

If using MongoDB Atlas:
```bash
# Windows Command Prompt
set MDB_MCP_API_CLIENT_ID=your-client-id
set MDB_MCP_API_CLIENT_SECRET=your-client-secret

# Windows PowerShell
$env:MDB_MCP_API_CLIENT_ID="your-client-id"
$env:MDB_MCP_API_CLIENT_SECRET="your-client-secret"

# Linux/Mac
export MDB_MCP_API_CLIENT_ID="your-client-id"
export MDB_MCP_API_CLIENT_SECRET="your-client-secret"
```

### Step 4: Test the MCP Server

Run the server to test:
```bash
npx -y @mongodb-js/mongodb-mcp-server
```

If it starts successfully, you'll see it running and ready to accept connections.

## Cursor IDE Configuration

### Step 1: Locate Cursor MCP Settings

**Windows:**
```
%APPDATA%\Cursor\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json
```

**macOS:**
```
~/Library/Application Support/Cursor/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json
```

**Linux:**
```
~/.config/Cursor/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json
```

### Step 2: Add MongoDB MCP Server Configuration

Add the MongoDB MCP Server to your existing Cursor MCP configuration:

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
      "command": "npx",
      "args": [
        "-y",
        "@mongodb-js/mongodb-mcp-server"
      ],
      "env": {
        "MDB_MCP_CONNECTION_STRING": "mongodb://admin:password@localhost:37017/ratings_db?authSource=admin"
      }
    }
  }
}
```

### Step 3: Restart Cursor

After updating the configuration, completely restart Cursor IDE for the changes to take effect.

## Available MongoDB MCP Tools

Once configured, the MongoDB MCP Server provides tools for:

- **Querying Collections** - Run MongoDB queries directly
- **Listing Collections** - View all collections in the database
- **Database Operations** - Get database information
- **Aggregation Pipelines** - Run complex aggregations
- **Document Operations** - Insert, update, delete documents (if not read-only)

## Security Considerations

### Read-Only Mode (Default)

By default, the MongoDB MCP Server runs in **read-only mode** to prevent accidental data modifications.

To enable write operations:
```bash
# Set environment variable
set MDB_MCP_READ_ONLY=false
```

Or in Cursor config:
```json
{
  "mcpServers": {
    "mongodb": {
      "command": "npx",
      "args": [
        "-y",
        "@mongodb-js/mongodb-mcp-server"
      ],
      "env": {
        "MDB_MCP_CONNECTION_STRING": "mongodb://admin:password@localhost:37017/ratings_db?authSource=admin",
        "MDB_MCP_READ_ONLY": "false"
      }
    }
  }
}
```

### Service Account (Recommended for Production)

When using MongoDB Atlas, create a dedicated service account with minimal required permissions.

## Troubleshooting

### Issue: "SyntaxError: Unexpected token 'with'"
**Error Message:**
```
SyntaxError: Unexpected token 'with'
    at ESMLoader.moduleStrategy (node:internal/modules/esm/translators:117:18)
```

**Cause:** Your Node.js version is too old. The MongoDB MCP Server requires Node.js 20.10.0+ or 21+.

**Solution:**
1. Check your Node.js version: `node --version`
2. If version is below 20.10.0, upgrade Node.js:
   - Download from: https://nodejs.org/
   - Install Node.js 20.10.0+ (LTS) or 21+ (Current)
   - Restart your terminal/command prompt
   - Verify: `node --version`
3. Reinstall MongoDB MCP Server:
   ```bash
   npm install -g @mongodb-js/mongodb-mcp-server
   ```

### Issue: "npx command not found"
**Solution:** Ensure Node.js and npm are installed and in your PATH.

### Issue: Connection refused
**Solution:** 
- Verify MongoDB is running: `docker ps` (if using Docker)
- Check connection string format
- Ensure MongoDB port is accessible (37017 for local Docker setup)

### Issue: Authentication failed
**Solution:**
- Verify username and password in connection string
- Check `authSource` parameter matches your MongoDB configuration
- Ensure user has appropriate permissions

### Issue: MCP Server not appearing in Cursor
**Solution:**
- Verify configuration file location and syntax
- Check for JSON syntax errors
- Restart Cursor completely (not just reload window)
- Check Cursor logs for errors
- Verify Node.js version meets requirements (20.10.0+)

## Using Both MCP Servers

You can use both MCP servers simultaneously:

1. **Ratings API MCP Server** - For Ratings API-specific operations (companies, LOBs, rating tables, etc.)
2. **MongoDB MCP Server** - For direct MongoDB database operations and queries

This gives you flexibility to:
- Use high-level API operations via Ratings API MCP
- Perform direct database queries via MongoDB MCP
- Access raw MongoDB data when needed

## Example Usage

Once configured, you can use MongoDB MCP tools in Cursor:

- "List all collections in the ratings_db database"
- "Query the companies collection for active companies"
- "Show me the structure of the ratingtables collection"
- "Run an aggregation pipeline on the states collection"

## Additional Resources

- [MongoDB MCP Server Documentation](https://www.mongodb.com/docs/mcp-server/)
- [MCP Server Configuration Guide](https://www.mongodb.com/docs/mcp-server/configuration/)
- [Security Best Practices](https://www.mongodb.com/docs/mcp-server/security/best-practices/)


