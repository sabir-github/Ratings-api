# Final Fix: MongoDB MCP Server Node.js Version Issue

## Problem

Even after updating the Cursor config to use the full path to `npx.cmd`, Cursor is still using Node.js v17.9.1 instead of v22.20.0.

## Root Cause

When `npx.cmd` runs, it may still be finding the old Node.js v17.9.1 from a different location in the system PATH, even though we're pointing to the correct npx.

## Solution: Use Node.js Directly

Instead of using `npx.cmd`, we'll use `node.exe` directly with the `npx-cli.js` script. This ensures we're using the correct Node.js version.

### Updated Configuration

I've updated your Cursor config file (`c:/Users/jaffa/.cursor/mcp.json`) to use:

```json
{
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
      "PATH": "C:\\Program Files\\nodejs;C:\\Program Files\\nodejs\\node_modules\\npm\\bin;%PATH%",
      "NODE_PATH": "C:\\Program Files\\nodejs"
    }
  }
}
```

## Next Steps

### 1. Verify the Configuration

The file `c:/Users/jaffa/.cursor/mcp.json` has been updated. Make sure it matches the configuration above.

### 2. Restart Cursor

**CRITICAL:** You must completely close and restart Cursor for the changes to take effect.

1. **Close Cursor completely** (not just the window - quit the application)
2. **Wait a few seconds**
3. **Reopen Cursor**

### 3. Test

After restarting, try using MongoDB MCP tools. The error should be gone.

## Alternative: Find and Remove Old Node.js

If the issue persists, there's likely an old Node.js v17.9.1 installation somewhere that's interfering.

### Find Old Node.js Installation

1. **Check Control Panel:**
   - Open Control Panel → Programs → Uninstall a program
   - Look for "Node.js" entries
   - If you see Node.js v17.9.1, uninstall it

2. **Check Common Locations:**
   - `C:\Program Files\nodejs\` (should be v22.20.0)
   - `C:\Program Files (x86)\nodejs\` (might have old version)
   - `C:\Users\jaffa\AppData\Local\Programs\nodejs\` (might have old version)
   - `C:\Users\jaffa\AppData\Roaming\npm\` (check for old node.exe)

3. **Check PATH Environment Variable:**
   - Press `Win + R`, type `sysdm.cpl`, press Enter
   - Go to "Advanced" tab → "Environment Variables"
   - Check "Path" in both "User variables" and "System variables"
   - Make sure `C:\Program Files\nodejs` is listed FIRST (before any other Node.js paths)
   - Remove any paths pointing to old Node.js installations

### After Removing Old Node.js

1. **Restart your computer** (to refresh PATH)
2. **Restart Cursor**
3. **Test again**

## Why This Should Work

By using `node.exe` directly with the full path, we bypass any PATH issues. The `npx-cli.js` script will use the same Node.js executable that we're calling, ensuring version consistency.

## Still Having Issues?

If you're still seeing the error after:
1. ✅ Updating the config file
2. ✅ Completely restarting Cursor
3. ✅ Verifying Node.js v22.20.0 is installed

Then try this diagnostic:

1. **Open Command Prompt as Administrator**
2. **Run:**
   ```cmd
   "C:\Program Files\nodejs\node.exe" --version
   ```
   Should show: `v22.20.0`

3. **Run:**
   ```cmd
   "C:\Program Files\nodejs\node.exe" "C:\Program Files\nodejs\node_modules\npm\bin\npx-cli.js" -y @mongodb-js/mongodb-mcp-server
   ```
   This should start the MongoDB MCP Server without errors.

If this works in Command Prompt but not in Cursor, there may be a Cursor-specific PATH issue. In that case, we may need to create a wrapper batch script.

## Summary

- ✅ Config file updated to use `node.exe` directly
- ⏳ **You need to restart Cursor completely**
- ⏳ **Test after restart**

The configuration change should fix the issue once Cursor is restarted.


