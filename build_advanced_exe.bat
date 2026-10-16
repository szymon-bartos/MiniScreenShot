@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Python nie jest zainstalowany lub nie jest dodany do PATH.
    echo Zainstaluj Python 3.11+ i zaznacz opcje: "Add Python to PATH".
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install pillow pyinstaller pyautogui pygetwindow pywin32
python -m PyInstaller --noconfirm MiniScreenShot_v1.1.3.spec
if errorlevel 1 exit /b 1
copy /y LICENSE.txt dist\LICENSE.txt >nul
if errorlevel 1 exit /b 1

echo.
echo Gotowy plik EXE znajduje sie w katalogu dist
echo.
if exist "dist\MiniScreenShot_v1.1.3.exe" (
    echo Znalazlem: dist\MiniScreenShot_v1.1.3.exe
) else (
    echo Nie znaleziono pliku EXE. Sprawdz kompilacje.
)
echo.
pause
