@echo off
REM ============================================================
REM  AskIvy - one-time setup for a fresh machine or fresh clone
REM
REM  Installs prerequisites, creates both virtual environments,
REM  installs all dependencies, creates the .env files, and
REM  trains the Rasa model.
REM
REM  Safe to re-run: everything here is idempotent. Existing
REM  venvs and .env files are kept, never overwritten.
REM
REM  When this finishes, use run-askivy.bat to start the app.
REM ============================================================

set "ROOT=%~dp0"

echo.
echo  ================================
echo   AskIvy setup
echo  ================================
echo.

REM ============================================================
REM  1. Prerequisites
REM ============================================================

echo [1/7] Checking prerequisites...

where uv >nul 2>&1
if not errorlevel 1 goto :have_uv
echo.
echo   uv is not installed. It is used to create the virtual
echo   environments and to install Python 3.12.
choice /M "  Install uv now via winget"
if errorlevel 2 goto :no_uv
winget install --id=astral-sh.uv -e --accept-package-agreements --accept-source-agreements
echo.
echo   uv was just installed. Windows needs a new terminal to see it.
echo   Please close this window and run setup-askivy.bat again.
echo.
pause
exit /b 0
:no_uv
echo.
echo   Cannot continue without uv. Install it from https://docs.astral.sh/uv/
echo.
pause
exit /b 1
:have_uv
echo   - uv found

where node >nul 2>&1
if not errorlevel 1 goto :have_node
echo.
echo   Node.js is not installed. It is needed for the frontend.
choice /M "  Install Node.js LTS now via winget"
if errorlevel 2 goto :no_node
winget install --id=OpenJS.NodeJS.LTS -e --accept-package-agreements --accept-source-agreements
echo.
echo   Node.js was just installed. Windows needs a new terminal to see it.
echo   Please close this window and run setup-askivy.bat again.
echo.
pause
exit /b 0
:no_node
echo.
echo   Cannot continue without Node.js. Install it from https://nodejs.org/
echo.
pause
exit /b 1
:have_node
echo   - Node.js found

REM ============================================================
REM  2. Python 3.12
REM     rasa-pro requires >=3.10,<3.14. The system Python is often
REM     newer than that, so we pin 3.12 explicitly via uv.
REM ============================================================

echo.
echo [2/7] Ensuring Python 3.12 is available...
uv python install 3.12
if errorlevel 1 goto :fail

REM ============================================================
REM  3. Backend virtual environment
REM ============================================================

echo.
echo [3/7] Backend environment...
if not exist "%ROOT%backend\.venv\Scripts\python.exe" goto :backend_venv_create
"%ROOT%backend\.venv\Scripts\python.exe" -c "" >nul 2>&1
if not errorlevel 1 (
  echo   - backend\.venv already exists and works, keeping it
  goto :backend_venv_done
)
echo   - backend\.venv exists but is broken ^(venvs don't survive being copied
echo     between machines - pyvenv.cfg hardcodes the original machine's Python
echo     path^), recreating it
rmdir /s /q "%ROOT%backend\.venv"
:backend_venv_create
uv venv --python 3.12 "%ROOT%backend\.venv"
if errorlevel 1 goto :fail
:backend_venv_done
echo   - installing backend dependencies
uv pip install -p "%ROOT%backend\.venv\Scripts\python.exe" -r "%ROOT%backend\requirements.txt"
if errorlevel 1 goto :fail

REM ============================================================
REM  4. Rasa virtual environment
REM     Kept separate on purpose - rasa-pro's pinned dependencies
REM     conflict with the Flask backend's.
REM ============================================================

echo.
echo [4/7] Rasa environment (this one is large, please be patient)...
if not exist "%ROOT%rasa\.venv\Scripts\python.exe" goto :rasa_venv_create
"%ROOT%rasa\.venv\Scripts\python.exe" -c "" >nul 2>&1
if not errorlevel 1 (
  echo   - rasa\.venv already exists and works, keeping it
  goto :rasa_venv_done
)
echo   - rasa\.venv exists but is broken ^(venvs don't survive being copied
echo     between machines - pyvenv.cfg hardcodes the original machine's Python
echo     path^), recreating it
rmdir /s /q "%ROOT%rasa\.venv"
:rasa_venv_create
uv venv --python 3.12 "%ROOT%rasa\.venv"
if errorlevel 1 goto :fail
:rasa_venv_done
echo   - installing Rasa dependencies
uv pip install -p "%ROOT%rasa\.venv\Scripts\python.exe" -r "%ROOT%rasa\requirements.txt"
if errorlevel 1 goto :fail

REM ============================================================
REM  5. Frontend dependencies
REM ============================================================

echo.
echo [5/7] Frontend dependencies...
pushd "%ROOT%frontend"
call npm install
if errorlevel 1 (popd & goto :fail)
popd

REM ============================================================
REM  6. Config files
REM     These are gitignored, so a fresh clone never has them.
REM ============================================================

echo.
echo [6/7] Config files...

if exist "%ROOT%rasa\.env" (
  echo   - rasa\.env already exists, keeping it
) else (
  copy "%ROOT%rasa\.env.example" "%ROOT%rasa\.env" >nul
  echo   - created rasa\.env from the example
)

if exist "%ROOT%backend\.env" (
  echo   - backend\.env already exists, keeping it
) else (
  copy "%ROOT%backend\.env.example" "%ROOT%backend\.env" >nul
  echo   - created backend\.env from the example
)

if exist "%ROOT%frontend\.env.local" (
  echo   - frontend\.env.local already exists, keeping it
) else (
  (echo VITE_ASKIVY_ENGINE=rasa)>"%ROOT%frontend\.env.local"
  echo   - created frontend\.env.local ^(engine set to rasa^)
)

REM ============================================================
REM  7. Train the model - only once the API keys are real
REM ============================================================

echo.
echo [7/7] Rasa model...

REM findstr's $ anchor does not match reliably against CRLF line endings,
REM so the "is this key still a placeholder" test is done in PowerShell.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$e = Get-Content '%ROOT%rasa\.env' -Raw; if ($e -match 'ANTHROPIC_API_KEY\s*=\s*(sk-ant-\.\.\.)?\s*(\r?\n|$)' -or $e -match 'RASA_LICENSE\s*=\s*(\r?\n|$)') { exit 1 } else { exit 0 }"
if errorlevel 1 goto :need_keys

echo   - training (takes a moment, calls the Anthropic API)
pushd "%ROOT%rasa"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-Content .env | ForEach-Object { if ($_ -match '^([^#][^=]*)=(.*)$') { [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2]) } }; $env:PYTHONUTF8='1'; .\.venv\Scripts\python.exe -m rasa train"
if errorlevel 1 (popd & goto :fail)
popd

echo.
echo  ================================
echo   Setup complete
echo  ================================
echo.
echo   Now run:  run-askivy.bat
echo.
pause
exit /b 0

:need_keys
echo.
echo  ================================
echo   Almost done - two keys needed
echo  ================================
echo.
echo   Open this file in a text editor:
echo.
echo     %ROOT%rasa\.env
echo.
echo   Fill in both values:
echo.
echo     ANTHROPIC_API_KEY=   your Anthropic API key
echo     RASA_LICENSE=        your Rasa Pro licence key
echo                          (free tier: rasa.com/rasa-pro-developer-edition/)
echo.
echo   Then run setup-askivy.bat again to train the model.
echo   Everything else is already installed.
echo.
pause
exit /b 0

:fail
echo.
echo  ================================
echo   Setup failed
echo  ================================
echo.
echo   The step above reported an error. Fix it and re-run this
echo   script - completed steps are skipped automatically.
echo.
pause
exit /b 1
