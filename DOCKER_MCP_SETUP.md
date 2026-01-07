# Docker-based MCP Server Setup for Cursor

This guide explains how to connect Cursor IDE to the MCP server running in the Docker container.

## Overview

The MCP server is **integrated with the FastAPI server** and runs on the same port (8000). There is no separate `mcp-server` container. The MCP server is accessible via:
- **HTTP endpoints:** `/api/v1/mcp/*` (for external agents)
- **Stdio:** via `run_mcp_server.py` (for Cursor IDE)

## Prerequisites

1. **Docker and Docker Compose** must be installed and running
2. **Docker containers** must be built and running:
   ```bash
   docker-compose up -d
   ```

## Setup Steps

### Step 1: Start the Docker Containers

Ensure all containers are running:

```bash
docker-compose up -d
```

This will start:
- `api` - FastAPI server with integrated MCP server (port 8000)
- `mongodb` - MongoDB database (port 37017)

**Note:** There is no separate `mcp-server` container. The MCP server runs as part of the `api` service.

### Step 2: Verify Container is Running

Check that the API container is running:

```bash
docker ps --format "{{.Names}}"
```

You should see `ratings-api-api-1` (or similar, depending on your Docker Compose project name).

Verify the container name:
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### Step 3: Configure Cursor

#### Option A: Using cursor-mcp-config.json (Recommended)

The `cursor-mcp-config.json` file is already configured. Copy its contents to your Cursor MCP settings:

**Location:** `%APPDATA%\Cursor\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json` (Windows)

Or: `c:\Users\<username>\.cursor\mcp.json`

**Current Configuration:**
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
- The `-i` flag is required for interactive stdio communication
- `PYTHONPATH` ensures Python can find the app modules

#### Option B: Using Cursor UI

1. Open Cursor Settings (File → Preferences → Settings)
2. Search for "MCP" or navigate to Features → MCP
3. Add new MCP server:
   - **Name:** `ratings-api`
   - **Command:** `docker`
   - **Arguments:** `["exec", "-i", "ratings-api-api-1", "python", "/app/run_mcp_server.py"]`
   - **Environment Variables:**
     - `API_URL=http://localhost:8000`
     - `MONGODB_URL=mongodb://admin:password@localhost:37017/?authSource=admin`
     - `MONGODB_DB_NAME=ratings_db`
     - `PYTHONPATH=/app`

#### Option C: Use Local Python (Alternative)

If you prefer not to use Docker exec, you can run the MCP server locally:

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

**Prerequisites for local Python:**
- Python 3.11+ installed
- `fastmcp` package installed: `pip install fastmcp`
- FastAPI server running on port 8000

### Step 4: Restart Cursor

After configuring, **completely restart Cursor** for the changes to take effect.

## Testing

### Test 1: Verify Container Access

```bash
docker exec -i ratings-api-api-1 python -c "import sys; print('Python works')"
```

### Test 2: Test MCP Server

```bash
docker exec -i ratings-api-api-1 python /app/run_mcp_server.py --list-tools
```

This should list all available MCP tools.

### Test 3: Test in Cursor

1. Open Cursor chat
2. Try: "List all companies"
3. The MCP server should respond using the Docker container

### Test 4: Verify HTTP Endpoints

The MCP server is also accessible via HTTP:

```bash
# Check MCP status
curl http://localhost:8000/api/v1/mcp/status

# List tools
curl http://localhost:8000/api/v1/mcp/tools

# Get protocol info
curl http://localhost:8000/api/v1/mcp/protocol/info
```

## Troubleshooting

### Container Not Found

**Error:** `No such container: ratings-api-mcp-server` or `No such container: ratings-api-api-1`

**Solution:**
1. **Check container name:**
   ```bash
   docker ps --format "{{.Names}}"
   ```

2. **Update Cursor config** with the correct container name

3. **Start containers if not running:**
   ```bash
   docker-compose up -d
   ```

### "Not Connected" Error in Cursor

**Error:** `Error listing tools: Not connected`

**Solution:**
1. **Verify container is running:**
   ```bash
   docker ps | grep ratings-api-api
   ```

2. **Test MCP server manually:**
   ```bash
   docker exec -i ratings-api-api-1 python /app/run_mcp_server.py --list-tools
   ```

3. **Check configuration:**
   - Ensure `-i` flag is in docker exec args
   - Verify full path `/app/run_mcp_server.py`
   - Check `PYTHONPATH` is set to `/app`

4. **Restart Cursor** completely

### Permission Issues

**Error:** Permission denied or access errors

**Solution:**
1. **Check Docker is running:**
   ```bash
   docker ps
   ```

2. **Check container logs:**
   ```bash
   docker logs ratings-api-api-1
   ```

3. **Verify file permissions:**
   ```bash
   docker exec ratings-api-api-1 ls -la /app/run_mcp_server.py
   ```

### Connection Issues

**Error:** Cursor can't connect to MCP server

**Solution:**
1. **Verify the container is accessible:**
   ```bash
   docker exec -i ratings-api-api-1 python -c "import sys; print(sys.version)"
   ```

2. **Check MCP server can run:**
   ```bash
   docker exec -i ratings-api-api-1 python /app/run_mcp_server.py --list-tools
   ```

3. **Check Cursor logs:**
   - Open Developer Tools (Help → Toggle Developer Tools)
   - Look for MCP-related errors in the console

4. **Verify FastAPI is running:**
   ```bash
   curl http://localhost:8000/health
   ```

### Module Import Errors

**Error:** `ModuleNotFoundError` or import errors

**Solution:**
1. **Add PYTHONPATH to environment:**
   ```json
   "env": {
     "PYTHONPATH": "/app",
     ...
   }
   ```

2. **Verify modules are accessible:**
   ```bash
   docker exec ratings-api-api-1 python -c "from app.mcp_server import mcp; print('OK')"
   ```

## Current Architecture

```
┌─────────────────────────────────────────┐
│         Docker Container: api            │
│  ┌───────────────────────────────────┐  │
│  │   FastAPI Server (port 8000)      │  │
│  │   - REST API endpoints            │  │
│  │   - MCP HTTP endpoints            │  │
│  │     (/api/v1/mcp/*)               │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │   MCP Server (stdio)              │  │
│  │   - run_mcp_server.py             │  │
│  │   - Accessible via docker exec    │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
         │
         │ docker exec -i
         │
    ┌────▼────┐
    │ Cursor  │
    │   IDE   │
    └─────────┘
```

## Advantages of Current Setup

1. **Integrated Architecture:** MCP server runs alongside FastAPI in the same container
2. **Single Port:** Both services use port 8000
3. **Resource Efficient:** No separate container needed
4. **Easy Access:** HTTP endpoints available at `/api/v1/mcp/*`
5. **Flexible:** Can use Docker exec for stdio or HTTP for external agents

## Maintenance

### Rebuilding Containers

If you update dependencies:

```bash
docker-compose build api
docker-compose up -d api
```

### Viewing Logs

```bash
# View API/MCP server logs
docker logs -f ratings-api-api-1

# View only recent logs
docker logs --tail 100 ratings-api-api-1
```

### Stopping Containers

```bash
# Stop all services
docker-compose stop

# Stop only API service
docker-compose stop api
```

### Restarting Services

```bash
# Restart API service (includes MCP server)
docker-compose restart api

# Restart all services
docker-compose restart
```

### Removing Containers

```bash
# Stop and remove containers
docker-compose down

# Remove containers and volumes
docker-compose down -v
```

## MCP Endpoints

The MCP server is accessible via HTTP on the same port:

- `GET /api/v1/mcp/tools` - List all MCP tools
- `POST /api/v1/mcp/tools/{tool_name}/call` - Call a tool
- `GET /api/v1/mcp/status` - Server status
- `POST /api/v1/mcp/protocol` - MCP protocol (JSON-RPC)
- `GET /api/v1/mcp/protocol/info` - Server information
- `GET /api/v1/mcp/protocol/sse` - Server-Sent Events

## Migration Notes

If you were using the old separate `mcp-server` container:

1. ✅ **Already done:** Removed `mcp-server` service from `docker-compose.yml`
2. ✅ **Already done:** MCP server integrated with FastAPI
3. **Update Cursor config:** Change container name from `ratings-api-mcp-server` to `ratings-api-api-1`
4. **Update paths:** Use `/app/run_mcp_server.py` (full path in container)
5. **Add PYTHONPATH:** Set to `/app` in environment variables

## Summary

- **Container:** `ratings-api-api-1` (check with `docker ps`)
- **MCP Script:** `/app/run_mcp_server.py` (inside container)
- **HTTP Access:** `http://localhost:8000/api/v1/mcp/*`
- **Stdio Access:** Via `docker exec -i ratings-api-api-1 python /app/run_mcp_server.py`
- **Environment:** `PYTHONPATH=/app` required
