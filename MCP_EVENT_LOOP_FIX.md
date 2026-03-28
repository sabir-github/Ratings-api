# MCP Event Loop Issue Fix

## Problem

The MCP tool was reporting "Event loop is closed" errors when called via Cursor IDE. This occurred because:

1. **Event Loop Conflict**: `asyncio.run(initialize_database())` creates and closes an event loop
2. **FastMCP's Own Loop**: FastMCP's `mcp.run()` creates its own event loop
3. **Database Connection**: The database connection was initialized in a closed event loop, making it inaccessible to FastMCP's tools

## Root Cause

```python
# This creates and closes an event loop
asyncio.run(initialize_database())

# Then FastMCP creates its own event loop
mcp.run()  # Tools can't access the database connection from the closed loop
```

## Solution: Lazy Initialization

Instead of initializing the database before FastMCP starts, we now initialize it **lazily** when first needed. This ensures:

1. Database connection is initialized within FastMCP's event loop
2. No event loop conflicts
3. Connection is available when tools are called

### Changes Made

#### 1. Updated `app/core/database.py` - `get_database()`

Added lazy initialization to automatically connect if not already connected:

```python
async def get_database() -> AsyncIOMotorClient:
    """Get database instance, raising error if not connected. Auto-initializes if needed."""
    # Lazy initialization: if not connected, try to connect
    if not mongodb.connected or mongodb.database is None:
        try:
            # Check if client exists but not connected
            if mongodb.client is None:
                await connect_to_mongo()
            else:
                # Client exists, verify connection
                await verify_connection()
        except Exception as e:
            raise ConnectionFailure(
                f"Database not connected. Please ensure MongoDB is running and the connection was established. Error: {e}"
            )
    return mongodb.database
```

#### 2. Updated `run_mcp_server.py`

Removed pre-initialization to avoid event loop conflicts:

```python
# Note: Database connection will be initialized lazily when first needed
# This avoids event loop conflicts with FastMCP's internal event loop
logger.info("MCP server starting. Database will be initialized on first use.")
```

## How It Works

1. **MCP Server Starts**: FastMCP creates its event loop
2. **Tool Called**: When a tool like `get_companies` is called
3. **Lazy Init**: `get_database()` checks if connected
4. **Auto-Connect**: If not connected, it initializes within FastMCP's event loop
5. **Tool Executes**: Database operations proceed normally

## Benefits

- ✅ No event loop conflicts
- ✅ Database initialized in correct event loop context
- ✅ Works with FastMCP's stdio communication
- ✅ Automatic connection management
- ✅ Graceful error handling

## Testing

### Test 1: Verify Lazy Initialization Works

```bash
# Start MCP server (database not pre-initialized)
docker exec -i ratings-api-api-1 python /app/run_mcp_server.py

# Call a tool (should auto-initialize database)
# Via HTTP endpoint:
curl -X POST http://localhost:8000/api/v1/mcp/protocol \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_companies",
      "arguments": {"limit": 3}
    },
    "id": 1
  }'
```

### Test 2: Verify in Cursor IDE

1. Restart Cursor IDE
2. Use MCP tools:
   - "Get all companies"
   - "List all states"
   - "Check API health"

## Troubleshooting

### Issue: Still getting "Event loop is closed"

1. **Check FastMCP version**: Ensure you're using a compatible version
   ```bash
   docker exec ratings-api-api-1 pip show fastmcp
   ```

2. **Verify lazy initialization**: Check logs for database initialization messages
   ```bash
   docker logs ratings-api-api-1 | grep -i "database\|mongo"
   ```

3. **Test HTTP endpoint**: If HTTP works but stdio doesn't, it's an event loop issue
   ```bash
   curl http://localhost:8000/api/v1/mcp/tools
   ```

### Issue: Database connection fails on first tool call

1. **Check MongoDB is running**:
   ```bash
   docker ps | grep mongodb
   ```

2. **Verify connection string**:
   ```bash
   docker exec ratings-api-api-1 env | grep MONGODB
   ```

3. **Test direct connection**:
   ```bash
   docker exec ratings-api-api-1 python -c "from app.core.database import connect_to_mongo; import asyncio; asyncio.run(connect_to_mongo())"
   ```

## Related Files

- `app/core/database.py` - Database connection with lazy initialization (updated)
- `run_mcp_server.py` - MCP server entry point (updated)
- `app/mcp_server.py` - MCP tool implementations
- `MCP_DATABASE_CONNECTION_FIX.md` - Previous fix documentation

## Notes

- Lazy initialization happens automatically - no manual intervention needed
- First tool call may be slightly slower due to connection initialization
- Subsequent calls use the existing connection
- Connection is properly managed within FastMCP's event loop context


