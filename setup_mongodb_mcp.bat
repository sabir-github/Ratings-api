@echo off
REM Setup script for MongoDB MCP Server on Windows

echo ========================================
echo MongoDB MCP Server Setup
echo ========================================
echo.

REM Check if Node.js is installed
echo Checking Node.js installation...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js 20.10.0+ from https://nodejs.org/
    pause
    exit /b 1
)

echo Node.js found:
for /f "tokens=*" %%i in ('node --version') do set NODE_VERSION=%%i
echo %NODE_VERSION%

REM Check version compatibility (requires 20.10.0+ or 21+)
echo Checking version compatibility...
for /f "tokens=1 delims=." %%a in ("%NODE_VERSION:v=%") do set MAJOR=%%a
for /f "tokens=2 delims=." %%b in ("%NODE_VERSION:v=%") do set MINOR=%%b

if %MAJOR% LSS 20 (
    echo ERROR: Node.js version %NODE_VERSION% is too old
    echo MongoDB MCP Server requires Node.js 20.10.0+ or 21+
    echo Please upgrade from https://nodejs.org/
    pause
    exit /b 1
)

if %MAJOR% EQU 20 (
    if %MINOR% LSS 10 (
        echo ERROR: Node.js version %NODE_VERSION% is too old
        echo MongoDB MCP Server requires Node.js 20.10.0+ (you have %NODE_VERSION%)
        echo Please upgrade from https://nodejs.org/
        pause
        exit /b 1
    )
)

echo Version check passed! Node.js %NODE_VERSION% is compatible.
echo.

REM Check if npm is installed
echo Checking npm installation...
npm --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: npm is not installed or not in PATH
    pause
    exit /b 1
)

echo npm found:
npm --version
echo.

REM Install MongoDB MCP Server
echo Installing MongoDB MCP Server...
echo.
npm install -g @mongodb-js/mongodb-mcp-server

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Failed to install MongoDB MCP Server
    pause
    exit /b 1
)

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Configure connection string in Cursor MCP settings
echo 2. See MONGODB_MCP_SERVER_SETUP.md for details
echo.
echo Test the installation:
echo   npx -y @mongodb-js/mongodb-mcp-server
echo.
pause


