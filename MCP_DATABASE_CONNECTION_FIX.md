# MCP Database Connection Fix

## Problem

The MCP server was reporting database connection errors when called via Cursor IDE, even though:
- The FastAPI server was running and connected to MongoDB
- HTTP endpoints were working correctly
- The database was accessible

## Root Cause

When the MCP server runs as a **standalone process via stdio** (for Cursor IDE), it's a separate process from the FastAPI server. The database connection (`connect_to_mongo()`) is only called in the FastAPI startup event, so the standalone MCP server process didn't have an initialized database connection.

## Solution

Updated `run_mcp_server.py` to initialize the database connection when the MCP server starts:

1. **Added database initialization** before the MCP server starts
2. **Added cleanup** on shutdown to properly close connections
3. **Made initialization happen** for both `--list-tools` and normal operation

## Changes Made

### File: `run_mcp_server.py`

**Added imports:**
```python
from app.core.database import connect_to_mongo, close_mongo_connection
```

**Added initialization function:**
```python
async def initialize_database():
    """Initialize database connection for standalone MCP server"""
    try:
        await connect_to_mongo()
        logger.info("Database connection initialized for MCP server")
    except Exception as e:
        logger.error(f"Failed to initialize database connection: {e}")
        # Don't exit - allow MCP server to start but tools will fail with connection error
```

**Added initialization before server starts:**
```python
# Initialize database connection before starting MCP server
try:
    asyncio.run(initialize_database())
except Exception as e:
    logger.warning(f"Database initialization warning: {e}")
    logger.warning("MCP server will start but database operations may fail")
```

**Added cleanup on shutdown:**
```python
except KeyboardInterrupt:
    logger.info("MCP server stopped by user")
    # Cleanup database connection on shutdown
    try:
        asyncio.run(close_mongo_connection())
    except Exception:
        pass
    sys.exit(0)
```

## Testing

### Test 1: Verify Database Initialization

```bash
# Check if database connection is initialized
docker exec -i ratings-api-api-1 python /app/run_mcp_server.py --list-tools
```

### Test 2: Test via HTTP Endpoint (Fallback)

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
  }'
```

### Test 3: Test in Cursor IDE

1. Restart Cursor IDE to reload MCP server configuration
2. Try using MCP tools in Cursor:
   - "Get all companies"
   - "List all states"
   - "Check API health"

## Expected Behavior

### Before Fix
- ❌ MCP tools reported: "Database not connected. Please ensure MongoDB is running and the connection was established."
- ✅ HTTP endpoints worked correctly
- ✅ FastAPI server was connected to database

### After Fix
- ✅ MCP tools work correctly via stdio (Cursor IDE)
- ✅ HTTP endpoints continue to work
- ✅ Database connection is initialized when MCP server starts
- ✅ Proper cleanup on shutdown

## Configuration

The fix works with both Docker and local configurations:

### Docker Configuration (mcp.json)
```json
{
  "mcpServers": {
    "ratings-api": {
      "command": "docker",
      "args": ["exec", "-i", "ratings-api-api-1", "python", "/app/run_mcp_server.py"],
      "env": {
        "MONGODB_URL": "mongodb://admin:password@localhost:37017/?authSource=admin",
        "MONGODB_DB_NAME": "ratings_db"
      }
    }
  }
}
```

### Local Configuration (mcp.json.local)
```json
{
  "mcpServers": {
    "ratings-api": {
      "command": "python",
      "args": ["run_mcp_server.py"],
      "env": {
        "MONGODB_URL": "mongodb://admin:password@localhost:37017/?authSource=admin",
        "MONGODB_DB_NAME": "ratings_db"
      }
    }
  }
}
```

## Troubleshooting

### Issue: Still getting database connection errors

1. **Check MongoDB is running:**
   ```bash
   docker ps | grep mongodb
   ```

2. **Verify connection string:**
   ```bash
   # Check environment variables in container
   docker exec ratings-api-api-1 env | grep MONGODB
   ```

3. **Check database connection directly:**
   ```bash
   docker exec ratings-api-api-1 python -c "from app.core.database import connect_to_mongo; import asyncio; asyncio.run(connect_to_mongo())"
   ```

4. **Check MCP server logs:**
   - Look for database initialization messages in stderr
   - Check for connection errors

### Issue: MCP server doesn't start

1. **Check FastMCP is installed:**
   ```bash
   docker exec ratings-api-api-1 pip list | grep fastmcp
   ```

2. **Check Python path:**
   ```bash
   docker exec ratings-api-api-1 python -c "import app.mcp_server; print('OK')"
   ```

### Issue: Tools work via HTTP but not via stdio

- This is expected if FastMCP's stdio implementation has issues
- HTTP endpoints will continue to work as a fallback
- Check Cursor IDE MCP configuration and logs

## Notes

- The database connection is initialized **once** when the MCP server starts
- If the database becomes unavailable, the MCP server will continue running but tools will fail
- The connection is properly cleaned up on shutdown
- This fix ensures the MCP server has the same database access as the FastAPI server

## Related Files

- `run_mcp_server.py` - MCP server entry point (updated)
- `app/core/database.py` - Database connection logic
- `app/mcp_server.py` - MCP tool implementations
- `mcp.json` - Docker configuration
- `mcp.json.local` - Local configuration



