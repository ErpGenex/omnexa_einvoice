@echo off
REM Build standalone Omnexa USB signing agent (Windows + Python 3.13 only).
setlocal
cd /d "%~dp0"

set PY313=%LocalAppData%\Programs\Python\Python313\python.exe
if not exist "%PY313%" set "PY313=C:\Users\Micros\AppData\Local\Programs\Python\Python313\python.exe"
if not exist "%PY313%" (
  echo ERROR: Install Python 3.13 from python.org — Chilkat v10 does not support 3.14 on pip.
  pause
  exit /b 1
)

echo Using: %PY313%
"%PY313%" --version

echo.
echo [1/4] Install build dependencies...
"%PY313%" -m pip install --upgrade pip pyinstaller
"%PY313%" -m pip install -r requirements-agent.txt

echo.
echo [2/4] PyInstaller (one-folder portable EXE)...
"%PY313%" -m PyInstaller --noconfirm --clean Omnexa_ESigning_Agent.spec
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)

echo.
echo [3/4] Copy launcher + config example...
set DIST=dist\OmnexaESigningAgent
copy /Y "Start_Omnexa_ESigning_Agent.bat" "%DIST%\"
copy /Y "chilkat_config.json.example" "%DIST%\"
copy /Y "README_AGENT_AR.txt" "%DIST%\"

echo.
echo [4/4] Create ZIP for ERP download...
"%PY313%" package_release.py
if errorlevel 1 (
  echo package_release.py failed.
  pause
  exit /b 1
)

echo.
echo Done.
echo   Run agent: dist\OmnexaESigningAgent\Start_Omnexa_ESigning_Agent.bat
echo   ERP zip:   ..\public\downloads\OmnexaESigningAgent-win64.zip
echo.
pause
