@echo off
cd /d "%~dp0"
title Omnexa E-Signing Agent (port 5002)
echo Omnexa USB signing agent — keep this window open while signing in ERP.
echo Health: http://127.0.0.1:5002/health
echo.
if not exist "chilkat_config.json" (
  echo Tip: copy chilkat_config.json.example to chilkat_config.json and set unlock_code.
  echo Or set Chilkat key in ERP Branch -^> Chilkat Unlock Code.
  echo.
)
OmnexaESigningAgent.exe
pause
