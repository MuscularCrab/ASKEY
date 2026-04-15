# ASCII Video Filter

> **⚠️ Generated with AI**
> This project was built collaboratively with the help of an AI assistant (Claude). The code has been tested and works, but review it before using in production or critical workflows.

GPU-accelerated video-to-ASCII-art converter. Renders any video as ASCII characters at full 1080p, with audio preserved.

Originally built as a workflow for DJ mix videos since Kdenlive doesn't have a native ASCII filter — works on any video file.

## Features

- **GPU-accelerated** with CuPy/CUDA — ~100+ fps on an RTX 4070
- **Four color modes** — green, white, hot pink, or full color
- **Live preview** — tune font size and colors interactively before rendering
- **Batch processing** — queue multiple files
- **Audio preserved** — auto-muxed from the original via FFmpeg
- **iPhone rotation handling** — auto-detects and corrects portrait-stored landscape video
- **GUI** — black and hot pink themed, cross-platform (Tk)
- **CLI** — fully scriptable

## Requirements

- **NVIDIA GPU** with CUDA support
- **Python 3.10+**
- **CUDA Toolkit 12.x** — [download from NVIDIA](https://developer.nvidia.com/cuda-downloads)
- **FFmpeg** (optional, required for audio in the output)

Works on Windows and Linux. macOS isn't supported (no CUDA).

## Installation

### Windows

1. **Install the CUDA Toolkit** from [developer.nvidia.com/cuda-downloads](https://developer.nvidia.com/cuda-downloads). Pick Windows → x86_64 → exe (local).

2. **Clone and install dependencies:**
   ```powershell
   git clone https://github.com/MuscularCrab/ascii-video-filter.git
   cd ascii-video-filter
   pip install -r requirements.txt
   ```

3. **Install FFmpeg** (optional but recommended) from [ffmpeg.org](https://ffmpeg.org/download.html). Either add it to PATH or drop it in your Downloads folder — the script will auto-detect it.

### Linux (CachyOS / Arch)

1. **Install CUDA + FFmpeg + Tk** via pacman:
   ```bash
   sudo pacman -S cuda ffmpeg tk python-pip
   ```
   On CachyOS the NVIDIA driver should already be set up. If not: `sudo pacman -S nvidia nvidia-utils` then reboot.

2. **Clone and install dependencies:**
   ```bash
   git clone https://github.com/MuscularCrab/ascii-video-filter.git
   cd ascii-video-filter
   pip install -r requirements.txt --break-system-packages
   ```
   (Use `--break-system-packages` because Arch protects the system Python — or set up a virtualenv if you prefer.)

3. **Verify the GPU is visible:**
   ```bash
   python -c "import cupy; print(cupy.cuda.runtime.getDeviceProperties(0)['name'].decode())"
   ```
   Should print your GPU model.

### Linux (Ubuntu/Debian)

```bash
sudo apt install nvidia-cuda-toolkit ffmpeg python3-tk python3-pip
git clone https://github.com/MuscularCrab/ascii-video-filter.git
cd ascii-video-filter
pip install -r requirements.txt
```

If `nvidia-cuda-toolkit` from apt is too old, install the latest from [NVIDIA's site](https://developer.nvidia.com/cuda-downloads).

## Usage

### GUI

**Windows:** double-click `run_gui.bat`

**Linux:** run `./run_gui.sh` (or `python3 ascii_video_gui.py`)

Add files, pick a color mode, set font size with the slider, hit **PREVIEW** to tune, then **RENDER ALL**.

To install as a desktop app on Linux (so it appears in your application menu):
```bash
cp ascii-video-filter.desktop ~/.local/share/applications/
```
Edit the `Exec=` line to point at your install path.

### Command line

```bash
# Single file with color
python ascii_video.py input.mov --color

# Batch with hot pink
python ascii_video.py clip1.mov clip2.mov clip3.mov --pink --fontsize 8

# Wildcard batch + custom output dir
python ascii_video.py "*.MOV" --color --output-dir ./output

# Interactive preview before rendering
python ascii_video.py input.mov --preview
```

### Preview controls

| Key | Action |
|-----|--------|
| `+` / `-` | Increase/decrease font size |
| `c` | Cycle color modes |
| `[` / `]` | Seek back/forward 1 second |
| `SPACE` | Play/pause |
| `r` | Commit settings and start render |
| `q` / `ESC` | Quit without rendering |

### CLI options

```
--cols N            Character columns (0 = auto-fill)
--color             Use original video colors
--green             Green on black (default)
--white             White on black
--pink              Hot pink on black
--fontsize N        Font size in pixels (default 12)
--output PATH       Output file (single input)
--output-dir PATH   Output directory (batch)
--width W           Output width (default 1920)
--height H          Output height (default 1080)
--preview           Open preview window before rendering
--preview-each      Preview each file separately in batch
```

## Building a standalone executable

A prebuilt binary isn't included — bundling CuPy + CUDA produces a 500MB-1GB file, and end users still need the CUDA Toolkit installed regardless. You can build your own:

### Windows

```powershell
pip install pyinstaller
build_exe.bat
```

Produces `dist/AsciiVideo.exe`.

### Linux

```bash
pip install pyinstaller --break-system-packages
./build_exe.sh
```

Produces `dist/AsciiVideo` (no extension on Linux).

End users will still need:
- An NVIDIA GPU
- CUDA Toolkit installed
- FFmpeg (optional, for audio)

## How it works

1. Read a frame from the video with OpenCV
2. Downscale to a small character grid on CPU
3. Upload to GPU via CuPy
4. Map each cell's brightness to an ASCII character index
5. Gather pre-rendered character tiles from a CUDA array
6. Composite into a full-resolution output frame on GPU
7. Optionally tint per-cell with color from the original frame
8. Download the finished frame back to CPU and write via OpenCV
9. Mux audio from the original using FFmpeg

Reading, processing, and writing run in three parallel threads so the GPU stays fed.

## Troubleshooting

**`DynamicLibNotFoundError: Failure finding "nvrtc*.dll"` (Windows)**
The CUDA Toolkit isn't installed. Download it from NVIDIA's site (see Requirements above).

**`libnvrtc.so` not found (Linux)**
Install the CUDA Toolkit via your package manager, or add `/opt/cuda/lib64` to `LD_LIBRARY_PATH`:
```bash
echo 'export LD_LIBRARY_PATH=/opt/cuda/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
```

**Video comes out rotated/portrait**
Auto-detection uses `ffprobe`. Make sure FFmpeg is installed and on PATH.

**Audio is missing from the output**
FFmpeg wasn't found. Install it (`sudo pacman -S ffmpeg` / `sudo apt install ffmpeg`).

**GPU usage is low and fps is mediocre**
The bottleneck is disk I/O reading/writing video. Try copying the source file to a local SSD first, especially if it's on a network drive.

**Tk error on launch (Linux)**
Tkinter isn't installed. On Arch: `sudo pacman -S tk`. On Debian: `sudo apt install python3-tk`.

**Fonts look ugly in the GUI**
The GUI auto-picks the best available system font. To get nicer typography on Linux, install one of these:
```bash
sudo pacman -S inter-font ttf-jetbrains-mono   # Arch
sudo apt install fonts-inter fonts-jetbrains-mono   # Debian
```

## License

MIT — see [LICENSE](LICENSE).
