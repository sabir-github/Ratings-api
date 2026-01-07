#!/bin/bash
# Helper script to run MCP server in Docker container
# MCP server is now integrated with FastAPI (api container)
# This script runs the MCP server via stdio from the api container

# Check if api container exists and is running
if ! docker ps --format "{{.Names}}" | grep -q "ratings-api-api"; then
    echo "Starting Docker containers..."
    docker-compose up -d api
    sleep 3
fi

# Execute MCP server in the api container (MCP is integrated with FastAPI)
# Note: Container name may vary - check with: docker ps --format "{{.Names}}"
docker exec -i ratings-api-api-1 python /app/run_mcp_server.py


