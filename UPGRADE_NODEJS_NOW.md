# URGENT: Upgrade Node.js to Fix MongoDB MCP Server

## Your Current Situation

- **Current Node.js Version:** v17.9.1 ❌
- **Required Version:** v20.10.0+ or v21+ ✅
- **Status:** Your version is too old and incompatible

## Why It's Failing

Node.js v17.9.1 doesn't support the `import ... with { type: "json" }` syntax that MongoDB MCP Server uses. This feature was added in Node.js 20.10.0.

## Quick Fix: Upgrade Node.js

### Step 1: Download Node.js

1. **Visit:** https://nodejs.org/
2. **Download:** 
   - **Recommended:** Node.js 20.x LTS (Long Term Support) - most stable
   - **Alternative:** Node.js 21.x Current - latest features
3. **Choose:** Windows Installer (.msi) for your system (64-bit recommended)

### Step 2: Install Node.js

1. **Run the installer** you just downloaded
2. **Follow the installation wizard:**
   - Accept the license
   - Choose installation location (default is fine)
   - **Important:** Make sure "Add to PATH" is checked ✅
   - Click "Install"
3. **Wait for installation to complete**

### Step 3: Verify Installation

1. **Close ALL terminal/command prompt windows**
2. **Open a NEW terminal/command prompt**
3. **Check version:**
   ```bash
   node --version
   ```
   You should see `v20.10.0` or higher, or `v21.x.x`

4. **Check npm:**
   ```bash
   npm --version
   ```

### Step 4: Reinstall MongoDB MCP Server

```bash
npm install -g @mongodb-js/mongodb-mcp-server
```

### Step 5: Test It Works

```bash
npx -y @mongodb-js/mongodb-mcp-server
```

If it starts without the "Unexpected token 'with'" error, you're good!

## After Upgrading

1. **Restart Cursor completely** (close and reopen)
2. **The MongoDB MCP Server should now work** in Cursor

## Version Comparison

| Version | Status | Notes |
|---------|--------|-------|
| v17.9.1 (yours) | ❌ Too old | Released 2022, missing modern features |
| v18.x | ❌ Too old | Missing import attributes |
| v20.0.0 - 20.9.x | ❌ Too old | Missing import attributes |
| v20.10.0+ | ✅ Compatible | LTS, recommended |
| v21.x | ✅ Compatible | Current, works great |

## Troubleshooting

### "node --version" still shows v17.9.1 after installing

**Solution:**
1. Close ALL terminal windows
2. Restart your computer (to refresh PATH)
3. Open a new terminal
4. Check again: `node --version`

If still showing old version:
1. Check where Node.js is installed: `where node` (Windows)
2. Make sure the new installation directory is in your PATH
3. You may need to manually update PATH environment variable

### Multiple Node.js versions installed

If you have multiple versions:
1. Uninstall old Node.js versions from Control Panel → Programs
2. Keep only the newest version (20.10.0+)
3. Restart terminal

### Using Node Version Manager (NVM)

If you're using nvm-windows:
```bash
nvm install 20.10.0
nvm use 20.10.0
nvm alias default 20.10.0
```

## Need Help?

- **Node.js Download:** https://nodejs.org/
- **Node.js Installation Guide:** https://nodejs.org/en/download/package-manager/
- **Check your version:** Run `check_node_version.bat` after upgrading

## Summary

**You need to upgrade from Node.js v17.9.1 to v20.10.0+ or v21+**

This is a required upgrade - there's no workaround. The MongoDB MCP Server simply won't work with Node.js 17.



