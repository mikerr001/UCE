@echo off
title Build NexForge UCE .exe
echo ============================================
echo  NexForge UCE -- PyInstaller Build Script
echo ============================================
echo.

pip install pyinstaller

pyinstaller ^
  --onefile ^
  --windowed ^
  --name "NexForge_UCE" ^
  --add-data "engine;engine" ^
  --add-data "extractors;extractors" ^
  --add-data "ui;ui" ^
  --hidden-import=PIL ^
  --hidden-import=PIL.Image ^
  --hidden-import=numpy ^
  --hidden-import=zstd ^
  --hidden-import=tkinter ^
  --hidden-import=tkinterdnd2 ^
  --hidden-import=cv2 ^
  --hidden-import=wave ^
  sce.py

echo.
echo Build complete. Find NexForge_UCE.exe in the dist\ folder.
echo Copy the entire dist\NexForge_UCE\ folder (or the .exe) to your flash drive.
pause
