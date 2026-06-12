@echo off
echo.
echo  ============================================
echo   AssistFlow -- Service Status Check
echo  ============================================
echo.

:: ── Flask (port 5000) ──────────────────────────────────────
echo  [1] Flask App  (port 5000)
netstat -ano | findstr ":5000" | findstr "LISTENING" >nul 2>&1
if %errorlevel% == 0 (
    echo      STATUS : RUNNING
) else (
    echo      STATUS : NOT RUNNING
    echo      FIX    : python app.py
)
echo.

:: ── ngrok process ──────────────────────────────────────────
echo  [2] ngrok Tunnel
tasklist /FI "IMAGENAME eq ngrok.exe" 2>nul | findstr /I "ngrok.exe" >nul
if %errorlevel% == 0 (
    echo      STATUS : RUNNING
    echo      Fetching public URL from ngrok API...
    for /f "delims=" %%U in ('powershell -NoProfile -Command ^
        "try { (Invoke-RestMethod http://localhost:4040/api/tunnels).tunnels | Where-Object { $_.proto -eq 'https' } | Select-Object -ExpandProperty public_url } catch { 'Could not reach ngrok API (http://localhost:4040)' }"^
    ') do echo      PUBLIC URL : %%U
) else (
    echo      STATUS : NOT RUNNING
    echo      FIX    : .\ngrok.exe http 5000
)

echo.
echo  ============================================
echo.
pause
