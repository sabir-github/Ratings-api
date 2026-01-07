@echo off
REM Quick script to check if Node.js version is compatible with MongoDB MCP Server

echo Checking Node.js version compatibility...
echo.

node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH
    echo.
    echo Please install Node.js 20.10.0+ from: https://nodejs.org/
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('node --version') do set NODE_VERSION=%%i
echo Current Node.js version: %NODE_VERSION%
echo.

REM Parse version
for /f "tokens=1 delims=." %%a in ("%NODE_VERSION:v=%") do set MAJOR=%%a
for /f "tokens=2 delims=." %%b in ("%NODE_VERSION:v=%") do set MINOR=%%b

if %MAJOR% LSS 20 (
    echo [ERROR] Node.js version is too old!
    echo.
    echo Required: Node.js 20.10.0+ or 21+
    echo Current:   %NODE_VERSION%
    echo.
    echo Please upgrade from: https://nodejs.org/
    pause
    exit /b 1
)

if %MAJOR% EQU 20 (
    if %MINOR% LSS 10 (
        echo [ERROR] Node.js version is too old!
        echo.
        echo Required: Node.js 20.10.0+ (for import attributes support)
        echo Current:   %NODE_VERSION%
        echo.
        echo Please upgrade from: https://nodejs.org/
        pause
        exit /b 1
    )
    echo [OK] Node.js %NODE_VERSION% is compatible!
    echo.
    echo MongoDB MCP Server should work with this version.
    pause
    exit /b 0
)

if %MAJOR% GEQ 21 (
    echo [OK] Node.js %NODE_VERSION% is compatible!
    echo.
    echo MongoDB MCP Server should work with this version.
    pause
    exit /b 0
)

echo [OK] Node.js %NODE_VERSION% appears compatible.
pause




