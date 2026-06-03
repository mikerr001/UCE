@echo off
title NexForge UCE (Portable)
cd /d "%~dp0"
set PYTHON_PATH=%~dp0python\python.exe
if exist "%PYTHON_PATH%" (
    "%PYTHON_PATH%" -m pip install -q -r requirements.txt
    "%PYTHON_PATH%" sce.py
) else (
    echo Portable Python not found at .\python\python.exe
    echo Falling back to system Python...
    python sce.py
)
