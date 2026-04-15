# ASCII Video Filter

GPU-accelerated video-to-ASCII-art converter. Takes any video file and renders it as ASCII characters at full 1080p resolution, with audio preserved.

Built originally as a workflow for DJ mix videos since Kdenlive doesn't have a native ASCII filter — but works on any video.

![screenshot placeholder](docs/screenshot.png)

## Features

- **GPU-accelerated** — uses CuPy (CUDA) for fast processing. ~100+ fps on an RTX 4070.
- **Four color modes** — green-on-black (terminal), white-on-black, hot pink, or full color.
- **Live preview** — tune font size and color interactively before committing to a render.
- **Batch processing** — queue up multiple files and render them all in one go.
- **Audio preserved** — automatically muxes the original audio back into the output.
- **iPhone rotation handling** — auto-detects and corrects portrait-stored landscape video.
- **Simple GUI** — black and hot pink themed tkinter interface.
- **CLI** — scriptable from the command line for automation.

## Requirements

- **NVIDIA GPU** with CUDA support (tested on RTX 4070)
- **Windows** (Linux should also work; Mac has no CUDA)
- **Python 3.10+**
- **CUDA Toolkit 12.x** — [download from NVIDIA](https://developer.nvidia.com/cuda-downloads)
- **FFmpeg** (optional, required for audio muxing) — [download here](https://ffmpeg.org/download.html)

## Installation

### 1. Install the CUDA Toolkit

Download and install from [developer.nvidia.com/cuda-downloads](https://developer.nvidia.com/cuda-downloads). Pick your OS and version, use the "exe (local)" installer on Windows.

### 2. Install Python dependencies

```bash
git clone https://github.com/YOUR_USERNAME/ascii-video-filter.git
cd ascii-video-filter
pip install -r requirements.txt
```

### 3. Install FFmpeg (optional but recommended)

Download from [ffmpeg.org](https://ffmpeg.org/download.html) and either add it to PATH or drop it in your Downloads folder — the script auto-detects it.

## Usage

### GUI

Double-click `run_gui.bat` (Windows) or run:

```bash
python ascii_video_gui.py
```

Add files, pick a color mode, set font size with the slider, hit **PREVIEW** to tune, then **RENDER ALL**.

### Command line

**Single file with color:**
```bash
python ascii_video.py input.mov --color
```

**Batch mode with pink text:**
```bash
python ascii_video.py clip1.mov clip2.mov clip3.mov --pink --fontsize 8
```

**Wildcard batch:**
```bash
python ascii_video.py "*.MOV" --color --output-dir ./output
```

**Interactive preview before rendering:**
```bash
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
--preview-each      Preview each file separately in batch mode
```

## Building a standalone .exe

A prebuilt `.exe` isn't included because it bundles CUDA and ends up ~500MB-1GB. You can build one yourself:

```bash
pip install pyinstaller
build_exe.bat
```

This produces `dist/AsciiVideo.exe`. Note that end users will still need:
- An NVIDIA GPU
- CUDA Toolkit installed
- FFmpeg (optional)

## How it works

1. **Read** a frame from the video with OpenCV
2. **Downscale** to a small grid (e.g. 160×90) on CPU
3. **Upload** to GPU via CuPy
4. **Map** each cell's brightness to an ASCII character index
5. **Gather** pre-rendered character tiles from a CUDA array
6. **Composite** into a 1920×1080 output frame entirely on GPU
7. **Optionally** tint with color from the original frame
8. **Download** finished frame back to CPU and write via OpenCV
9. **Mux** audio from the original using FFmpeg

Reading, processing, and writing run in three parallel threads so the GPU never idles.

## Troubleshooting

**`cuda.pathfinder._dynamic_libs.load_dl_common.DynamicLibNotFoundError: Failure finding "nvrtc*.dll"`**
The CUDA Toolkit isn't installed. Download it from NVIDIA's site (see Requirements above).

**Video comes out rotated/portrait**
The script auto-detects iPhone rotation metadata using `ffprobe`. Make sure FFmpeg is installed or findable.

**Audio is missing from the output**
FFmpeg wasn't found. Install it and make sure it's on PATH or in `~/Downloads/ffmpeg-*/bin/`.

**GPU usage is low and fps is slow**
You're likely bottlenecked on disk I/O (reading/writing video). Try copying the source file to a local SSD first.

**`ImportError: cupy` or GPU not found**
Run `pip install cupy-cuda12x` again and verify with: `python -c "import cupy; print(cupy.cuda.runtime.getDeviceProperties(0))"`

## License

MIT — see [LICENSE](LICENSE).
