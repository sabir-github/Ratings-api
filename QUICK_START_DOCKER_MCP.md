# Quick Start: Docker-based MCP Server for Cursor

## 🚀 Quick Setup (3 Steps)

### Step 1: Start Docker Containers

```bash
docker-compose up -d
```

This starts:
- ✅ API server with integrated MCP (port 8000)
- ✅ MongoDB (port 37017)

**Note:** MCP server is integrated with FastAPI - no separate container needed!

### Step 2: Copy Configuration to Cursor

**Windows Location:**
```
%APPDATA%\Cursor\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json
```

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
- Use full path `/app/run_mcp_server.py` inside container
- `PYTHONPATH=/app` ensures Python can find modules

### Step 3: Restart Cursor

**Completely close and restart Cursor** for changes to take effect.

## ✅ Verify Setup

1. **Check container is running:**
   ```bash
   docker ps --format "{{.Names}}"
   ```
   Should show `ratings-api-api-1` (or similar)

2. **Test MCP server:**
   ```bash
   docker exec -i ratings-api-api-1 python /app/run_mcp_server.py --list-tools
   ```

3. **Test HTTP endpoints:**
   ```bash
   curl http://localhost:8000/api/v1/mcp/status
   ```

4. **Test in Cursor:**
   - Open Cursor chat
   - Type: "List all companies"
   - Should work! 🎉

## 🔧 Troubleshooting

### Container Not Found?
```bash
# Check container name
docker ps --format "{{.Names}}"

# Update Cursor config with correct name
```

### Can't Connect?
1. Check Docker is running: `docker ps`
2. Check container logs: `docker logs ratings-api-api-1`
3. Verify config uses `/app/run_mcp_server.py` and `PYTHONPATH=/app`
4. Test manually: `docker exec -i ratings-api-api-1 python /app/run_mcp_server.py --list-tools`

### Need to Rebuild?
```bash
docker-compose build api
docker-compose up -d api
```

## 📝 Notes

- **MCP is integrated** with FastAPI - runs on same port (8000)
- **No separate container** - MCP runs in the `api` container
- **HTTP access:** `/api/v1/mcp/*` endpoints available
- **Stdio access:** Via `docker exec` for Cursor IDE
- Environment variables use `localhost` (from host perspective)


