@echo off
setlocal
cd /d "%~dp0"

call ensure_python.bat
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean MiniScreenShot_v1.1.10.spec
if errorlevel 1 exit /b 1
copy /y LICENSE.txt dist\MiniScreenShot_v1.1.10\LICENSE.txt >nul
if errorlevel 1 exit /b 1
powershell -NoProfile -Command "Compress-Archive -LiteralPath 'dist\MiniScreenShot_v1.1.10' -DestinationPath 'dist\MiniScreenShot_v1.1.10_windows.zip' -Force"
if errorlevel 1 exit /b 1
powershell -NoProfile -Command "'{0}  {1}' -f (Get-FileHash -LiteralPath 'dist\MiniScreenShot_v1.1.10_windows.zip' -Algorithm SHA256).Hash.ToLowerInvariant(), 'MiniScreenShot_v1.1.10_windows.zip' | Set-Content -LiteralPath 'dist\MiniScreenShot_v1.1.10_SHA256SUMS.txt' -Encoding ascii"
if errorlevel 1 exit /b 1

echo.
echo Gotowy program i paczka ZIP znajduja sie w katalogu dist
echo.
if exist "dist\MiniScreenShot_v1.1.10\MiniScreenShot_v1.1.10.exe" (
    echo Znalazlem: dist\MiniScreenShot_v1.1.10\MiniScreenShot_v1.1.10.exe
) else (
    echo Nie znaleziono pliku EXE. Sprawdz kompilacje.
)
echo.
pause
