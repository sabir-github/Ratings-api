#!/bin/bash
# Setup script for MongoDB MCP Server on Linux/Mac

echo "========================================"
echo "MongoDB MCP Server Setup"
echo "========================================"
echo ""

# Check if Node.js is installed
echo "Checking Node.js installation..."
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js is not installed or not in PATH"
    echo "Please install Node.js 20+ from https://nodejs.org/"
    exit 1
fi

echo "Node.js found:"
node --version
echo ""

# Check if npm is installed
echo "Checking npm installation..."
if ! command -v npm &> /dev/null; then
    echo "ERROR: npm is not installed or not in PATH"
    exit 1
fi

echo "npm found:"
npm --version
echo ""

# Install MongoDB MCP Server
echo "Installing MongoDB MCP Server..."
echo ""
npm install -g @mongodb-js/mongodb-mcp-server

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Failed to install MongoDB MCP Server"
    exit 1
fi

echo ""
echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Configure connection string in Cursor MCP settings"
echo "2. See MONGODB_MCP_SERVER_SETUP.md for details"
echo ""
echo "Test the installation:"
echo "  npx -y @mongodb-js/mongodb-mcp-server"
echo ""





