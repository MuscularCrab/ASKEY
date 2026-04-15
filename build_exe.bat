@echo off
REM Build script for ASCII Video Filter - creates a standalone Windows .exe
REM Requires PyInstaller: pip install pyinstaller

echo ====================================
echo Building ASCII Video Filter .exe
echo ====================================
echo.

REM Check PyInstaller
pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

REM Clean previous builds
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist AsciiVideo.spec del AsciiVideo.spec

echo Building...
echo.

pyinstaller ^
    --onefile ^
    --windowed ^
    --name AsciiVideo ^
    --collect-all cupy ^
    --collect-all cv2 ^
    --collect-all PIL ^
    --hidden-import ascii_video ^
    ascii_video_gui.py

echo.
if exist dist\AsciiVideo.exe (
    echo ====================================
    echo SUCCESS! Built: dist\AsciiVideo.exe
    echo ====================================
    echo.
    echo Note: The .exe is large ^(~500MB-1GB^) because it bundles
    echo CuPy and CUDA runtime. End users will still need:
    echo   - NVIDIA GPU with CUDA support
    echo   - CUDA Toolkit installed on their system
    echo   - FFmpeg ^(optional, for audio muxing^)
) else (
    echo ====================================
    echo BUILD FAILED
    echo ====================================
    echo Check the output above for errors.
)

pause
