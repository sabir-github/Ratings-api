# Fix: MongoDB MCP Server "Unexpected token 'with'" Error

## Problem

You're seeing this error when trying to use the MongoDB MCP Server:

```
SyntaxError: Unexpected token 'with'
    at ESMLoader.moduleStrategy (node:internal/modules/esm/translators:117:18)
```

## Root Cause

The MongoDB MCP Server uses JavaScript import attributes (`import ... with { type: "json" }`), which requires:
- **Node.js 20.10.0 or higher**, OR
- **Node.js 21.x or higher**

If you have Node.js 20.0.0 through 20.9.x, or any version below 20, you'll see this error.

## Solution: Upgrade Node.js

### Step 1: Check Current Version

```bash
node --version
```

### Step 2: Download and Install Node.js

1. **Visit:** https://nodejs.org/
2. **Download:** Node.js 20.10.0+ (LTS) or 21+ (Current)
3. **Install:** Run the installer
4. **Restart:** Close and reopen your terminal/command prompt

### Step 3: Verify Installation

```bash
node --version
npm --version
```

You should see:
- `v20.10.0` or higher, OR
- `v21.x.x` or higher

### Step 4: Reinstall MongoDB MCP Server

```bash
npm install -g @mongodb-js/mongodb-mcp-server
```

### Step 5: Test Installation

```bash
npx -y @mongodb-js/mongodb-mcp-server
```

If it starts without errors, the installation is successful!

## Alternative: Use Node Version Manager (NVM)

If you need to manage multiple Node.js versions:

### Windows (nvm-windows)

1. **Download:** https://github.com/coreybutler/nvm-windows/releases
2. **Install nvm-windows**
3. **Install Node.js 20.10.0+**:
   ```bash
   nvm install 20.10.0
   nvm use 20.10.0
   ```

### macOS/Linux (nvm)

1. **Install nvm:**
   ```bash
   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
   ```

2. **Install Node.js 20.10.0+**:
   ```bash
   nvm install 20.10.0
   nvm use 20.10.0
   ```

## Verify Fix in Cursor

After upgrading Node.js:

1. **Update Cursor MCP Configuration** (if needed)
2. **Restart Cursor completely**
3. **Check Cursor logs** - the error should be gone

## Still Having Issues?

1. **Clear npm cache:**
   ```bash
   npm cache clean --force
   ```

2. **Uninstall and reinstall:**
   ```bash
   npm uninstall -g @mongodb-js/mongodb-mcp-server
   npm install -g @mongodb-js/mongodb-mcp-server
   ```

3. **Check PATH environment variable** includes Node.js installation directory

4. **Verify which Node.js is being used:**
   ```bash
   where node    # Windows
   which node    # macOS/Linux
   ```

## Version Compatibility Reference

| Node.js Version | Compatible? | Notes |
|----------------|-------------|-------|
| 18.x | ❌ No | Too old |
| 20.0.0 - 20.9.x | ❌ No | Missing import attributes |
| 20.10.0+ | ✅ Yes | LTS, recommended |
| 21.x | ✅ Yes | Current, works |
| 22.x | ✅ Yes | Latest, works |

## Need Help?

- Check MongoDB MCP Server docs: https://www.mongodb.com/docs/mcp-server/
- Node.js download: https://nodejs.org/
- Node.js release notes: https://nodejs.org/en/blog/release/




