#!/usr/bin/env bash
# Build script for Linux - creates a standalone binary with PyInstaller
set -e

cd "$(dirname "$0")"

echo "===================================="
echo "Building ASCII Video Filter binary"
echo "===================================="

if ! command -v pyinstaller >/dev/null 2>&1; then
    echo "PyInstaller not found. Installing..."
    pip install pyinstaller --break-system-packages 2>/dev/null || pip install pyinstaller
fi

# Clean previous builds
rm -rf build dist AsciiVideo.spec

echo "Building..."

pyinstaller \
    --onefile \
    --windowed \
    --name AsciiVideo \
    --collect-all cupy \
    --collect-all cv2 \
    --collect-all PIL \
    --hidden-import ascii_video \
    ascii_video_gui.py

if [ -f dist/AsciiVideo ]; then
    echo
    echo "===================================="
    echo "SUCCESS! Built: dist/AsciiVideo"
    echo "===================================="
    echo
    echo "Note: The binary is large (~500MB-1GB) because it bundles"
    echo "CuPy and CUDA runtime. End users will still need:"
    echo "  - NVIDIA GPU with CUDA support"
    echo "  - CUDA Toolkit installed on their system"
    echo "  - FFmpeg (optional, for audio muxing)"
else
    echo
    echo "===================================="
    echo "BUILD FAILED"
    echo "===================================="
    exit 1
fi
