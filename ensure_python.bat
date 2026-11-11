@echo off
rem Validate the interpreter, including virtual environments moved from another PC.
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -c "import sys, tkinter, venv; sys.exit(sys.version_info < (3, 11))" >nul 2>nul
    if not errorlevel 1 exit /b 0
)

py -3 -c "import sys, venv; sys.exit(sys.version_info < (3, 11))" >nul 2>nul
if not errorlevel 1 (
    py -3 -m venv .venv
    if errorlevel 1 exit /b 1
    goto verify
)
python -c "import sys, venv; sys.exit(sys.version_info < (3, 11))" >nul 2>nul
if not errorlevel 1 (
    python -m venv .venv
    if errorlevel 1 exit /b 1
    goto verify
)
echo Nie znaleziono dzialajacego Pythona 3.11+.
echo Zainstaluj Python z Tkinterem i opcja Add Python to PATH, a nastepnie ponow uruchomienie.
exit /b 1

:verify
.venv\Scripts\python.exe -c "import sys, tkinter, venv; sys.exit(sys.version_info < (3, 11))"
exit /b %errorlevel%
