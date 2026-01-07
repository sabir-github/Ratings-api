# Cursor MCP Server Integration Guide

This guide explains how to integrate the Ratings API MCP server with Cursor IDE.

## Prerequisites

1. **Install fastmcp** (if not already installed):
   ```bash
   pip install fastmcp
   ```

2. **Ensure the FastAPI server is running**:
   ```bash
   # Local development
   uvicorn app.main:app --reload

   # Or using Docker
   docker-compose up api
   ```

## Configuration Steps

### Option 1: Using Cursor Settings (Recommended)

1. Open Cursor Settings (File → Preferences → Settings)
2. Search for "MCP" or "Model Context Protocol"
3. Add a new MCP server configuration:

   **Server Name:** `ratings-api`
   
   **Command:** `python`
   
   **Arguments:** `["run_mcp_server.py"]`
   
   **Working Directory:** (path to your Ratings-api project)
   
   **Environment Variables:**
   ```
   API_URL=http://localhost:8000
   MONGODB_URL=mongodb://admin:password@localhost:37017/?authSource=admin
   MONGODB_DB_NAME=ratings_db
   ```

### Option 2: Using Configuration File

1. Locate Cursor's MCP configuration file (typically in Cursor settings directory)
2. Add the configuration from `cursor-mcp-config.json` to your Cursor MCP settings
3. Restart Cursor

### Option 3: Manual Configuration

Add this to your Cursor settings JSON:

```json
{
  "mcpServers": {
    "ratings-api": {
      "command": "python",
      "args": ["run_mcp_server.py"],
      "cwd": "/path/to/Ratings-api",
      "env": {
        "API_URL": "http://localhost:8000",
        "MONGODB_URL": "mongodb://admin:password@localhost:37017/?authSource=admin",
        "MONGODB_DB_NAME": "ratings_db"
      }
    }
  }
}
```

## Available MCP Tools

Once configured, Cursor will have access to all Ratings API endpoints as tools:

### Companies
- `get_companies` - List companies with filtering
- `get_company` - Get company by ID
- `create_company` - Create new company
- `update_company` - Update company
- `delete_company` - Delete company

### LOBs (Lines of Business)
- `get_lobs` - List LOBs
- `get_lob` - Get LOB by ID
- `create_lob` - Create new LOB
- `update_lob` - Update LOB
- `delete_lob` - Delete LOB

### Products
- `get_products` - List products
- `get_product` - Get product by ID
- `create_product` - Create new product
- `update_product` - Update product
- `delete_product` - Delete product

### States
- `get_states` - List states
- `get_state` - Get state by ID
- `create_state` - Create new state
- `update_state` - Update state
- `delete_state` - Delete state

### Contexts
- `get_contexts` - List contexts
- `get_context` - Get context by ID
- `create_context` - Create new context
- `update_context` - Update context
- `delete_context` - Delete context

### Rating Tables
- `get_ratingtables` - List rating tables with filtering
- `get_ratingtable` - Get rating table by ID
- `create_ratingtable` - Create new rating table
- `update_ratingtable` - Update rating table
- `delete_ratingtable` - Delete rating table

### Algorithms
- `get_algorithms` - List algorithms with filtering
- `get_algorithm` - Get algorithm by ID
- `create_algorithm` - Create new algorithm
- `update_algorithm` - Update algorithm
- `delete_algorithm` - Delete algorithm

### Rating Manuals
- `get_ratingmanuals` - List rating manuals with filtering
- `get_ratingmanual` - Get rating manual by ID
- `create_ratingmanual` - Create new rating manual
- `update_ratingmanual` - Update rating manual
- `delete_ratingmanual` - Delete rating manual

### Rating Plans
- `get_ratingplans` - List rating plans with filtering
- `get_ratingplan` - Get rating plan by ID
- `create_ratingplan` - Create new rating plan
- `update_ratingplan` - Update rating plan
- `delete_ratingplan` - Delete rating plan

### Health Check
- `health_check` - Check API and database health

## Testing the Integration

1. **Check MCP Server Status:**
   ```bash
   curl http://localhost:8000/api/v1/mcp/status
   ```

2. **List Available Tools:**
   ```bash
   curl http://localhost:8000/api/v1/mcp/tools
   ```

3. **In Cursor:**
   - Open the chat/composer
   - Try prompts like:
     - "Get all companies"
     - "Create a new rating table"
     - "List all active algorithms"
   - Cursor should automatically use the MCP tools to interact with your API

## Troubleshooting

### MCP Server Not Connecting

1. **Check if fastmcp is installed:**
   ```bash
   pip show fastmcp
   ```

2. **Test the MCP server manually:**
   ```bash
   python run_mcp_server.py
   ```
   (This should start and wait for stdio input)

3. **Check Cursor logs:**
   - Look for MCP-related errors in Cursor's developer console
   - Verify the command path is correct

### Tools Not Available

1. **Verify the API server is running:**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Check MCP server status:**
   ```bash
   curl http://localhost:8000/api/v1/mcp/status
   ```

3. **Restart Cursor** after configuration changes

## Environment Variables

The MCP server uses these environment variables:

- `API_URL` - Base URL for the FastAPI server (default: `http://localhost:8000`)
- `MONGODB_URL` - MongoDB connection string
- `MONGODB_DB_NAME` - Database name

Adjust these in your Cursor MCP configuration if your setup differs.

## Docker Setup

### Option 1: Using Docker Exec (Recommended)

If running in Docker, use Docker exec to run the MCP server:

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
    }
  }
}
```

**Important:**
- Replace `ratings-api-api-1` with your actual container name (check with `docker ps`)
- Use full path `/app/run_mcp_server.py` inside the container
- `PYTHONPATH=/app` ensures Python can find the app modules
- The `-i` flag is required for interactive stdio communication

### Option 2: Local Python with Docker API

If you prefer local Python but API is in Docker:

```json
{
  "mcpServers": {
    "ratings-api": {
      "command": "python",
      "args": ["run_mcp_server.py"],
      "cwd": "C:\\sabir\\Ratings-api",
      "env": {
        "API_URL": "http://localhost:8000",
        "MONGODB_URL": "mongodb://admin:password@localhost:37017/?authSource=admin",
        "MONGODB_DB_NAME": "ratings_db"
      }
    }
  }
}
```

**Note:** MCP server is integrated with FastAPI and runs on the same port (8000). No separate `mcp-server` container is needed.







