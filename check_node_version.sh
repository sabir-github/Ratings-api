#!/bin/bash
# Quick script to check if Node.js version is compatible with MongoDB MCP Server

echo "Checking Node.js version compatibility..."
echo ""

if ! command -v node &> /dev/null; then
    echo "[ERROR] Node.js is not installed or not in PATH"
    echo ""
    echo "Please install Node.js 20.10.0+ from: https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node --version)
echo "Current Node.js version: $NODE_VERSION"
echo ""

# Parse version (remove 'v' prefix)
VERSION_NUM=${NODE_VERSION#v}
MAJOR=$(echo $VERSION_NUM | cut -d. -f1)
MINOR=$(echo $VERSION_NUM | cut -d. -f2)

if [ "$MAJOR" -lt 20 ]; then
    echo "[ERROR] Node.js version is too old!"
    echo ""
    echo "Required: Node.js 20.10.0+ or 21+"
    echo "Current:   $NODE_VERSION"
    echo ""
    echo "Please upgrade from: https://nodejs.org/"
    exit 1
fi

if [ "$MAJOR" -eq 20 ]; then
    if [ "$MINOR" -lt 10 ]; then
        echo "[ERROR] Node.js version is too old!"
        echo ""
        echo "Required: Node.js 20.10.0+ (for import attributes support)"
        echo "Current:   $NODE_VERSION"
        echo ""
        echo "Please upgrade from: https://nodejs.org/"
        exit 1
    fi
    echo "[OK] Node.js $NODE_VERSION is compatible!"
    echo ""
    echo "MongoDB MCP Server should work with this version."
    exit 0
fi

if [ "$MAJOR" -ge 21 ]; then
    echo "[OK] Node.js $NODE_VERSION is compatible!"
    echo ""
    echo "MongoDB MCP Server should work with this version."
    exit 0
fi

echo "[OK] Node.js $NODE_VERSION appears compatible."




