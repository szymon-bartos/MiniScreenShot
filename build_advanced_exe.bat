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
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
python -m PyInstaller --noconfirm --clean MiniScreenShot_v1.1.8.spec
if errorlevel 1 exit /b 1
copy /y LICENSE.txt dist\MiniScreenShot_v1.1.8\LICENSE.txt >nul
if errorlevel 1 exit /b 1
powershell -NoProfile -Command "Compress-Archive -LiteralPath 'dist\MiniScreenShot_v1.1.8' -DestinationPath 'dist\MiniScreenShot_v1.1.8_windows.zip' -Force"
if errorlevel 1 exit /b 1
powershell -NoProfile -Command "'{0}  {1}' -f (Get-FileHash -LiteralPath 'dist\MiniScreenShot_v1.1.8_windows.zip' -Algorithm SHA256).Hash.ToLowerInvariant(), 'MiniScreenShot_v1.1.8_windows.zip' | Set-Content -LiteralPath 'dist\MiniScreenShot_v1.1.8_SHA256SUMS.txt' -Encoding ascii"
if errorlevel 1 exit /b 1

echo.
echo Gotowy program i paczka ZIP znajduja sie w katalogu dist
echo.
if exist "dist\MiniScreenShot_v1.1.8\MiniScreenShot_v1.1.8.exe" (
    echo Znalazlem: dist\MiniScreenShot_v1.1.8\MiniScreenShot_v1.1.8.exe
) else (
    echo Nie znaleziono pliku EXE. Sprawdz kompilacje.
)
echo.
pause
