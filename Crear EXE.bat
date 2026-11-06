@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Primero ejecuta "Iniciar Inventario.bat" una vez.
    pause & exit /b 1
)
".venv\Scripts\python.exe" -m pip install pyinstaller
".venv\Scripts\python.exe" herramientas\compilar.py
if errorlevel 1 ( pause & exit /b 1 )
echo.
echo Listo. El programa quedo en: dist\InventarioEnfermeria.exe
pause
