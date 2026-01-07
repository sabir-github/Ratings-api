# Quick Fix: MongoDB MCP Server Node.js Version Issue

## Problem Identified

- **Your System:** Node.js v22.20.0 ✅ (installed and compatible)
- **Cursor is Using:** Node.js v17.9.1 ❌ (old version from different location)
- **Error:** `SyntaxError: Unexpected token 'with'`

**Root Cause:** Cursor is finding an old Node.js installation (v17.9.1) instead of your newer one (v22.20.0).

## Solution Applied

I've updated `cursor-mcp-config-with-mongodb.json` to use the **full path** to the correct Node.js installation.

### Updated Configuration

The MongoDB MCP Server now uses:
```json
"command": "C:\\Program Files\\nodejs\\npx.cmd"
```

This forces Cursor to use Node.js v22.20.0 instead of the old v17.9.1.

## Next Steps

### 1. Copy Configuration to Cursor

Copy the contents of `cursor-mcp-config-with-mongodb.json` to your Cursor MCP settings:

**Location:** `%APPDATA%\Cursor\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`

Or manually update just the MongoDB server section:

```json
{
  "mcpServers": {
    "ratings-api": {
      // ... your existing ratings-api config ...
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

### 2. Restart Cursor

1. **Close Cursor completely** (not just the window)
2. **Reopen Cursor**
3. **Test MongoDB MCP Server** - the error should be gone

### 3. Verify It Works

After restarting Cursor, try using MongoDB MCP tools. The `SyntaxError: Unexpected token 'with'` should no longer appear.

## Alternative: Remove Old Node.js

If you want to prevent this issue in the future:

1. **Find old Node.js installation:**
   - Check: `C:\Users\jaffa\AppData\Roaming\npm\` (this might have the old version)
   - Or check Control Panel → Programs for Node.js v17.9.1

2. **Uninstall old version:**
   - Control Panel → Programs → Uninstall a program
   - Remove Node.js v17.9.1
   - Keep Node.js v22.20.0

3. **Restart computer** to refresh PATH

## Files Updated

- ✅ `cursor-mcp-config-with-mongodb.json` - Updated to use full path
- ✅ `FIX_CURSOR_NODE_VERSION.md` - Detailed troubleshooting guide
- ✅ `QUICK_FIX_MONGODB_MCP.md` - This file

## Summary

**The fix:** Use full path `C:\\Program Files\\nodejs\\npx.cmd` in Cursor config instead of just `npx`.

This ensures Cursor uses Node.js v22.20.0 (compatible) instead of v17.9.1 (too old).

After updating Cursor settings and restarting, the MongoDB MCP Server should work! 🎉



