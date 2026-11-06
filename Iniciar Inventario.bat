@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Inventario de Enfermeria - FAENUS
if not exist ".venv\Scripts\pythonw.exe" (
    echo Preparando la aplicacion por primera vez, espera un momento...
    where py >nul 2>nul && (py -3 -m venv .venv) || (python -m venv .venv)
    if errorlevel 1 (
        echo.
        echo No se encontro Python. Instala Python 3.10 o superior desde https://www.python.org/downloads/
        echo y marca la casilla "Add python.exe to PATH" durante la instalacion.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 ( echo Error instalando dependencias. & pause & exit /b 1 )
)
start "" ".venv\Scripts\pythonw.exe" inventario.py
