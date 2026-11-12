@echo off
setlocal
cd /d "%~dp0"

call ensure_python.bat
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe app_launcher.py
exit /b %errorlevel%
