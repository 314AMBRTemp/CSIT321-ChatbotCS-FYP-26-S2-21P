@echo off
REM ============================================================
REM  AskIvy - start all four local services in their own windows
REM
REM  Just double-click this file. It opens:
REM    1. Flask backend        :5000
REM    2. Rasa action server   :5055
REM    3. Rasa server          :5005
REM    4. Frontend (Vite)      :5173
REM
REM  Each window uses -ExecutionPolicy Bypass, so the PowerShell
REM  "running scripts is disabled on this system" error can't bite.
REM  Close a window to stop that service.
REM ============================================================

set "ROOT=%~dp0"

echo Starting AskIvy...
echo.

REM ------------------------------------------------------------
REM  Stale-process guard.
REM
REM  A leftover server silently wins the port: the new one dies
REM  with "Errno 10048 ... only one usage of each socket address"
REM  while the OLD process keeps serving. That is especially nasty
REM  for the Rasa server, which loads its model once at boot -- so
REM  a stale one serves an out-of-date model and your latest
REM  `rasa train` appears to have done nothing.
REM ------------------------------------------------------------

echo Checking ports 5000, 5005, 5055, 5173...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$found = $false; foreach ($p in 5000,5005,5055,5173) { foreach ($conn in (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)) { $found = $true; $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue; $cmd = (Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $conn.OwningProcess) -ErrorAction SilentlyContinue).CommandLine; $name = if ($proc) { $proc.ProcessName } else { 'unknown' }; $age = if ($proc -and $proc.StartTime) { 'started ' + [string][Math]::Round(((Get-Date) - $proc.StartTime).TotalMinutes) + ' min ago' } else { 'start time unavailable' }; Write-Host ''; Write-Host ('   port ' + $p + '  |  PID ' + $conn.OwningProcess + '  |  ' + $name + '  |  ' + $age) -ForegroundColor Yellow; Write-Host ('     ' + $cmd) -ForegroundColor DarkGray } }; if ($found) { exit 1 }; exit 0"
if errorlevel 1 goto :ports_busy
echo   All four ports are free.
goto :launch

:ports_busy
echo.
echo   ------------------------------------------------------------
echo   The processes listed above are already using AskIvy's ports.
echo   They are almost always servers left over from a previous run.
echo.
echo   Check the ages above. Anything more than a few minutes old is
echo   stale and safe to stop.
echo   ------------------------------------------------------------
echo.
choice /M "  Stop these processes and start fresh"
if errorlevel 2 goto :keep_running
echo   Stopping...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "foreach ($p in 5000,5005,5055,5173) { Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"
timeout /t 2 /nobreak >nul
goto :launch

:keep_running
echo.
echo   Leaving them alone. Note the new windows will fail to bind,
echo   and the old servers - including any stale Rasa model - keep
echo   serving. Close this and re-run if that is not what you want.
echo.
pause

:launch

REM --- 1. Flask backend (seeds the DB on first boot) -----------
start "AskIvy - Backend :5000" powershell -NoExit -ExecutionPolicy Bypass -Command ^
  "cd '%ROOT%backend'; Write-Host 'FLASK BACKEND :5000' -ForegroundColor Cyan; .\.venv\Scripts\python.exe app.py"

REM Give Flask a moment to create/seed the database first.
timeout /t 3 /nobreak >nul

REM --- 2. Rasa action server -----------------------------------
REM Loads rasa\.env so ANTHROPIC_API_KEY / RASA_LICENSE are set.
start "AskIvy - Rasa Actions :5055" powershell -NoExit -ExecutionPolicy Bypass -Command ^
  "cd '%ROOT%rasa'; Write-Host 'RASA ACTION SERVER :5055' -ForegroundColor Cyan; Get-Content .env | ForEach-Object { if ($_ -match '^([^#][^=]*)=(.*)$') { [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2]) } }; $env:PYTHONUTF8='1'; .\.venv\Scripts\python.exe -m rasa run actions"

timeout /t 3 /nobreak >nul

REM --- 3. Rasa server (slowest to boot - loads the model) ------
start "AskIvy - Rasa Server :5005" powershell -NoExit -ExecutionPolicy Bypass -Command ^
  "cd '%ROOT%rasa'; Write-Host 'RASA SERVER :5005' -ForegroundColor Cyan; Get-Content .env | ForEach-Object { if ($_ -match '^([^#][^=]*)=(.*)$') { [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2]) } }; $env:PYTHONUTF8='1'; .\.venv\Scripts\python.exe -m rasa run --enable-api --cors '*'"

REM --- 4. Frontend ---------------------------------------------
start "AskIvy - Frontend :5173" powershell -NoExit -ExecutionPolicy Bypass -Command ^
  "cd '%ROOT%frontend'; Write-Host 'FRONTEND :5173' -ForegroundColor Cyan; npm run dev"

echo.
echo All four windows launched.
echo.
echo   App          http://localhost:5173
echo   API health   http://localhost:5000/api/health
echo   Rasa wiring  http://localhost:5000/api/askivy/rasa/health
echo.
echo The Rasa server takes ~30s to load its model - the wiring check
echo will say "unreachable" until it finishes. That is normal.
echo.
pause
