@echo off
echo ========================================
echo Finding All Node.js Installations
echo ========================================
echo.

echo Checking common Node.js locations...
echo.

echo [1] Program Files:
if exist "C:\Program Files\nodejs\node.exe" (
    echo   Found: C:\Program Files\nodejs\node.exe
    "C:\Program Files\nodejs\node.exe" --version 2>nul | findstr /V "^$" && echo     Version: OK || echo     Version: Could not determine
) else (
    echo   Not found
)
echo.

echo [2] Program Files (x86):
if exist "C:\Program Files (x86)\nodejs\node.exe" (
    echo   Found: C:\Program Files (x86)\nodejs\node.exe
    "C:\Program Files (x86)\nodejs\node.exe" --version 2>nul | findstr /V "^$" && echo     Version: OK || echo     Version: Could not determine
) else (
    echo   Not found
)
echo.

echo [3] User Local Programs:
if exist "%LOCALAPPDATA%\Programs\nodejs\node.exe" (
    echo   Found: %LOCALAPPDATA%\Programs\nodejs\node.exe
    "%LOCALAPPDATA%\Programs\nodejs\node.exe" --version 2>nul | findstr /V "^$" && echo     Version: OK || echo     Version: Could not determine
) else (
    echo   Not found
)
echo.

echo [4] User Roaming npm:
if exist "%APPDATA%\npm\node.exe" (
    echo   Found: %APPDATA%\npm\node.exe
    "%APPDATA%\npm\node.exe" --version 2>nul | findstr /V "^$" && echo     Version: OK || echo     Version: Could not determine
) else (
    echo   Not found
)
echo.

echo [5] Checking PATH:
echo   Current PATH entries containing 'nodejs' or 'npm':
echo %PATH% | findstr /i "nodejs npm" || echo   No nodejs/npm found in PATH
echo.

echo [6] Which node command finds:
where node 2>nul || echo   'where node' command not available
echo.

echo [7] Testing the node that Cursor might use:
echo   Testing: C:\Program Files\nodejs\node.exe
"C:\Program Files\nodejs\node.exe" --version 2>nul
if %errorlevel% equ 0 (
    echo   SUCCESS: This Node.js works!
) else (
    echo   ERROR: This Node.js does not work
)
echo.

echo ========================================
echo Summary
echo ========================================
echo.
echo If you see multiple Node.js installations, you may need to:
echo 1. Uninstall old versions from Control Panel
echo 2. Update PATH to prioritize C:\Program Files\nodejs
echo 3. Restart your computer
echo.
pause


