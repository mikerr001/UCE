@echo off
title Build NexForge UCE .exe
echo ============================================
echo  NexForge UCE -- PyInstaller Build Script
echo ============================================
echo.

echo [1/3] Installing PyInstaller...
pip install pyinstaller
if %ERRORLEVEL% neq 0 (
    echo ERROR: pip install failed. Is Python in your PATH?
    pause
    exit /b 1
)

echo.
echo [2/3] Checking for optional OpenCV...
python -c "import cv2" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo OpenCV found -- including it.
    set CV2_FLAG=--hidden-import=cv2
) else (
    echo OpenCV not found -- skipping ^(video compression will use fallback^).
    set CV2_FLAG=
)

echo.
echo [3/3] Building NexForge_UCE.exe ...
echo.

pyinstaller ^
  --onefile ^
  --windowed ^
  --name "NexForge_UCE" ^
  --add-data "engine;engine" ^
  --add-data "extractors;extractors" ^
  --add-data "ui;ui" ^
  --hidden-import=PIL ^
  --hidden-import=PIL.Image ^
  --hidden-import=PIL.PngImagePlugin ^
  --hidden-import=PIL.JpegImagePlugin ^
  --hidden-import=numpy ^
  --hidden-import=zstd ^
  --hidden-import=tkinter ^
  --hidden-import=tkinter.ttk ^
  --hidden-import=tkinterdnd2 ^
  --hidden-import=sqlite3 ^
  --hidden-import=wave ^
  --hidden-import=struct ^
  --hidden-import=zlib ^
  %CV2_FLAG% ^
  --collect-all tkinterdnd2 ^
  --noconfirm ^
  sce.py

echo.
if exist dist\NexForge_UCE.exe (
    echo ============================================
    echo  SUCCESS!
    echo  Your exe is at:  dist\NexForge_UCE.exe
    echo.
    echo  Copy these to your flash drive root:
    echo    dist\NexForge_UCE.exe
    echo    autorun.inf
    echo    launch.bat
    echo    launch_portable.bat
    echo    engine\
    echo    extractors\
    echo ============================================
) else (
    echo ============================================
    echo  BUILD FAILED -- no exe was produced.
    echo  Scroll up to find the error message.
    echo  Common fixes:
    echo    - Run:  pip install pyinstaller pillow numpy zstd tkinterdnd2
    echo    - Make sure you are in the NexForge_UCE folder
    echo ============================================
)

pause
