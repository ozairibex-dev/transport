@echo off
REM One-command start for Windows. Double-click it, or run from Command Prompt:
REM   start.bat          first run: sets everything up, then starts the app
REM   start.bat demo     same, plus demo site/vendor/vehicles/drivers/employee
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.10+ is required. Install it from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" during installation.
  pause
  exit /b 1
)

if not exist .venv (
  echo Creating virtual environment ^(.venv^)...
  python -m venv .venv || goto :fail
)
call .venv\Scripts\activate.bat || goto :fail

echo Installing / checking libraries...
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt || goto :fail
if "%HTTPS%"=="1" python -m pip install -q cryptography

if /i "%1"=="demo" (
  python -m flask --app app seed --demo || goto :fail
) else (
  python -m flask --app app seed || goto :fail
)

echo.
echo   App:           http://localhost:5000
echo   Same Wi-Fi:    http://YOUR-PC-IP:5000   (find it with: ipconfig)
echo   Public HTTPS:  run "cloudflared tunnel --url http://localhost:5000" in another window
echo   Stop:          Ctrl+C
echo   If Windows Firewall asks, allow Python on Private networks.
echo.
python app.py
pause
exit /b 0

:fail
echo.
echo Something went wrong above. Copy the error message and share it.
pause
exit /b 1
