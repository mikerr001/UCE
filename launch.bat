@echo off
title NexForge UCE
cd /d "%~dp0"
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)
pip install -q -r requirements.txt
python sce.py
