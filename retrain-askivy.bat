@echo off
REM ============================================================
REM  AskIvy - retrain the Rasa model, then restart the two Rasa
REM  processes that need it.
REM
REM  Touches ONLY:
REM    Rasa server   :5005  - loads the model once at boot, so a new model
REM                           does nothing until it restarts
REM    Action server :5055  - loads actions.py once at boot, no auto-reload
REM
REM  Leaves alone:
REM    Flask    :5000  - auto-reloads .py on save
REM    Frontend :5173  - unaffected by a retrain
REM
REM  Trains FIRST, restarts second: a failed train leaves your running
REM  servers untouched rather than killing them for nothing.
REM
REM  Not part of run-askivy.bat on purpose - a train takes about a minute
REM  and makes an Anthropic API call, so it should not run on every launch.
REM ============================================================

set "ROOT=%~dp0"

echo.
echo  ================================
echo   Retrain + restart Rasa
echo  ================================
echo.

if not exist "%ROOT%rasa\.venv\Scripts\python.exe" goto :no_venv
if not exist "%ROOT%rasa\.env" goto :no_env

REM ------------------------------------------------------------
REM  1. Train
REM ------------------------------------------------------------

pushd "%ROOT%rasa"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-Content .env | ForEach-Object { if ($_ -match '^([^#][^=]*)=(.*)$') { [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2]) } }; $env:PYTHONUTF8='1'; .\.venv\Scripts\python.exe -m rasa train"
if errorlevel 1 goto :fail

echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$m = Get-ChildItem models\*.tar.gz | Sort-Object LastWriteTime -Descending | Select-Object -First 1; Write-Host ('  Newest model: ' + $m.Name) -ForegroundColor Green"
popd

REM ------------------------------------------------------------
REM  2. Show what is currently holding :5005 and :5055
REM ------------------------------------------------------------

echo.
echo Checking for running Rasa processes...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$found = $false; foreach ($p in 5005,5055) { foreach ($conn in (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)) { $found = $true; $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue; $cmd = (Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $conn.OwningProcess) -ErrorAction SilentlyContinue).CommandLine; $name = if ($proc) { $proc.ProcessName } else { 'unknown' }; $age = if ($proc -and $proc.StartTime) { 'started ' + [string][Math]::Round(((Get-Date) - $proc.StartTime).TotalMinutes) + ' min ago' } else { 'start time unavailable' }; $label = if ($p -eq 5005) { 'Rasa server  ' } else { 'Action server' }; Write-Host ''; Write-Host ('   ' + $label + '  port ' + $p + '  |  PID ' + $conn.OwningProcess + '  |  ' + $name + '  |  ' + $age) -ForegroundColor Yellow; Write-Host ('     ' + $cmd) -ForegroundColor DarkGray } }; if ($found) { exit 1 }; exit 0"
if errorlevel 1 goto :running

echo   Neither is running - starting them fresh.
goto :launch

:running
echo.
echo   ------------------------------------------------------------
echo   These are serving the OLD model / OLD actions.py until they
echo   are restarted.
echo   ------------------------------------------------------------
echo.
choice /M "  Stop and restart them now"
if errorlevel 2 goto :skipped

echo   Stopping...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "foreach ($p in 5005,5055) { Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"
timeout /t 2 /nobreak >nul

REM ------------------------------------------------------------
REM  3. Relaunch both, action server first
REM ------------------------------------------------------------

:launch
start "AskIvy - Rasa Actions :5055" powershell -NoExit -ExecutionPolicy Bypass -Command ^
  "cd '%ROOT%rasa'; Write-Host 'RASA ACTION SERVER :5055' -ForegroundColor Cyan; Get-Content .env | ForEach-Object { if ($_ -match '^([^#][^=]*)=(.*)$') { [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2]) } }; $env:PYTHONUTF8='1'; .\.venv\Scripts\python.exe -m rasa run actions"

timeout /t 3 /nobreak >nul

start "AskIvy - Rasa Server :5005" powershell -NoExit -ExecutionPolicy Bypass -Command ^
  "cd '%ROOT%rasa'; Write-Host 'RASA SERVER :5005' -ForegroundColor Cyan; Get-Content .env | ForEach-Object { if ($_ -match '^([^#][^=]*)=(.*)$') { [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2]) } }; $env:PYTHONUTF8='1'; .\.venv\Scripts\python.exe -m rasa run --enable-api --cors '*'"

echo.
echo  ================================
echo   Done
echo  ================================
echo.
echo   The Rasa server takes ~30s to load the model. Confirm the model it
echo   actually picked up matches the one printed above:
echo.
echo     http://localhost:5000/api/askivy/rasa/health
echo.
pause
exit /b 0

:skipped
echo.
echo   Left running. They are still serving the previous model and the
echo   previous actions.py - the retrain has no effect until they restart.
echo.
pause
exit /b 0

:no_venv
echo   rasa\.venv not found. Run setup-askivy.bat first.
echo.
pause
exit /b 1

:no_env
echo   rasa\.env not found - the train needs ANTHROPIC_API_KEY and RASA_LICENSE.
echo.
pause
exit /b 1

:fail
popd
echo.
echo  ================================
echo   Training failed - nothing restarted
echo  ================================
echo.
echo   Your running servers were left untouched. Common causes:
echo     - a YAML syntax error in domain.yml or data\flows.yml
echo     - a `rejections:` predicate using `in` / list syntax (pypred has neither)
echo     - RASA_LICENSE missing or expired
echo   The error above says which. See Troubleshooting in quickstart.md.
echo.
pause
exit /b 1
