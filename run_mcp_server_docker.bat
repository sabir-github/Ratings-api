@echo off
REM Helper script to run MCP server in Docker container
REM MCP server is now integrated with FastAPI (api container)
REM This script runs the MCP server via stdio from the api container

REM Check if api container exists and is running
docker ps --filter "name=ratings-api-api" --format "{{.Names}}" | findstr /C:"ratings-api-api" >nul
if %errorlevel% neq 0 (
    echo Starting Docker containers...
    docker-compose up -d api
    timeout /t 3 /nobreak >nul
)

REM Execute MCP server in the api container (MCP is integrated with FastAPI)
docker exec -i ratings-api-api-1 python /app/run_mcp_server.py


