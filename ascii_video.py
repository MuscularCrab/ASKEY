"""
ASCII Video Filter - Core Engine
GPU-accelerated ASCII art video conversion using CuPy (CUDA).

Can be used as a CLI tool or imported as a module.
"""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os
import sys
import argparse
import subprocess
import time
import json
import threading
import glob
from collections import deque

# Try to import CuPy, fall back gracefully if unavailable
try:
    import cupy as cp
    GPU_AVAILABLE = True
except ImportError:
    cp = None
    GPU_AVAILABLE = False

ASCII_CHARS = " .,:;i1tfLCG08@"
NUM_CHARS = len(ASCII_CHARS)


def get_monospace_font(size):
    font_paths = [
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/cour.ttf",
        "C:/Windows/Fonts/lucon.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
        "/System/Library/Fonts/Menlo.ttc",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()


def find_ffprobe():
    try:
        subprocess.run(["ffprobe", "-version"], capture_output=True, check=True)
        return "ffprobe"
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    home = os.path.expanduser("~")
    downloads = os.path.join(home, "Downloads")
    if os.path.exists(downloads):
        for item in os.listdir(downloads):
            path = os.path.join(downloads, item, "bin", "ffprobe.exe")
            if os.path.exists(path):
                return path
    return None


def find_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return "ffmpeg"
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    home = os.path.expanduser("~")
    downloads = os.path.join(home, "Downloads")
    if os.path.exists(downloads):
        for item in os.listdir(downloads):
            path = os.path.join(downloads, item, "bin", "ffmpeg.exe")
            if os.path.exists(path):
                return path
    return None


def get_rotation(video_path):
    ffprobe = find_ffprobe()
    if not ffprobe:
        return 0
    try:
        cmd = [ffprobe, "-v", "quiet", "-print_format", "json",
               "-show_streams", "-show_format", video_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        data = json.loads(result.stdout)
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                tags = stream.get("tags", {})
                if "rotate" in tags:
                    return int(tags["rotate"])
                for sd in stream.get("side_data_list", []):
                    if "rotation" in sd:
                        return abs(int(sd["rotation"]))
    except Exception:
        pass
    try:
        cap = cv2.VideoCapture(video_path)
        if cap.isOpened():
            orientation = int(cap.get(cv2.CAP_PROP_ORIENTATION_META))
            cap.release()
            if orientation in (90, 180, 270):
                return orientation
    except Exception:
        pass
    return 0


def rotate_frame(frame, rotation):
    if rotation == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    elif rotation == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    elif rotation == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    return frame


def measure_char(font):
    img = Image.new("RGB", (200, 200))
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), "@", font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def pre_render_tiles(font, char_w, char_h):
    tiles = []
    for ch in ASCII_CHARS:
        img = Image.new("L", (char_w, char_h), 0)
        draw = ImageDraw.Draw(img)
        draw.text((0, 0), ch, fill=255, font=font)
        tiles.append(np.array(img, dtype=np.float32) / 255.0)
    return np.stack(tiles, axis=0)


class AsciiRenderer:
    """GPU-accelerated ASCII renderer. Reusable across frames."""

    def __init__(self, src_w, src_h, out_w, out_h, font_size, cols_override=0):
        if not GPU_AVAILABLE:
            raise RuntimeError(
                "CuPy not installed. Run: pip install cupy-cuda12x"
            )
        self.src_w = src_w
        self.src_h = src_h
        self.out_w = out_w
        self.out_h = out_h
        self.font_size = font_size
        self.cols_override = cols_override
        self._build()

    def _build(self):
        video_aspect = self.src_w / self.src_h
        self.font = get_monospace_font(self.font_size)
        self.char_w, self.char_h = measure_char(self.font)

        if self.cols_override > 0:
            cols = self.cols_override
        else:
            cols = self.out_w // self.char_w

        rows = int((cols * self.char_w) / (video_aspect * self.char_h))

        if cols * self.char_w > self.out_w:
            cols = self.out_w // self.char_w
            rows = int((cols * self.char_w) / (video_aspect * self.char_h))
        if rows * self.char_h > self.out_h:
            rows = self.out_h // self.char_h
            cols = int((rows * self.char_h * video_aspect) / self.char_w)

        self.cols = cols
        self.rows = rows
        self.ttw = cols * self.char_w
        self.tth = rows * self.char_h
        self.off_x = (self.out_w - self.ttw) // 2
        self.off_y = (self.out_h - self.tth) // 2

        self.py1 = max(self.off_y, 0)
        self.py2 = min(self.off_y + self.tth, self.out_h)
        self.px1 = max(self.off_x, 0)
        self.px2 = min(self.off_x + self.ttw, self.out_w)
        self.sy1 = self.py1 - self.off_y
        self.sy2 = self.py2 - self.off_y
        self.sx1 = self.px1 - self.off_x
        self.sx2 = self.px2 - self.off_x

        tile_stack_np = pre_render_tiles(self.font, self.char_w, self.char_h)
        self.tile_stack_gpu = cp.asarray(tile_stack_np)
        self.output_gpu = cp.zeros((self.out_h, self.out_w, 3), dtype=cp.uint8)
        self.output_pinned = np.empty((self.out_h, self.out_w, 3), dtype=np.uint8)

        self.green_bgr = cp.array([70, 255, 0], dtype=cp.float32)
        self.white_bgr = cp.array([255, 255, 255], dtype=cp.float32)
        self.pink_bgr = cp.array([147, 20, 255], dtype=cp.float32)  # hot pink

    def render(self, frame_bgr, color_mode):
        """Process a BGR frame, return ASCII BGR uint8 array."""
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray_small = cv2.resize(gray, (self.cols, self.rows),
                                interpolation=cv2.INTER_AREA)
        gray_small_gpu = cp.asarray(gray_small)

        indices = (gray_small_gpu.astype(cp.float32) *
                   (NUM_CHARS / 256.0)).astype(cp.int32)
        cp.clip(indices, 0, NUM_CHARS - 1, out=indices)

        all_tiles = self.tile_stack_gpu[indices]
        text_image = all_tiles.transpose(0, 2, 1, 3).reshape(self.tth, self.ttw)

        self.output_gpu[:] = 0

        if color_mode == "color":
            color_small = cv2.resize(frame_bgr, (self.cols, self.rows),
                                     interpolation=cv2.INTER_AREA).astype(np.float32)
            color_small_gpu = cp.asarray(color_small)
            color_expanded = color_small_gpu[:, cp.newaxis, :, cp.newaxis, :]
            color_expanded = cp.broadcast_to(
                color_expanded,
                (self.rows, self.char_h, self.cols, self.char_w, 3)
            ).reshape(self.tth, self.ttw, 3)
            text_bgr = (color_expanded * text_image[:, :, cp.newaxis]).astype(cp.uint8)
            self.output_gpu[self.py1:self.py2, self.px1:self.px2] = \
                text_bgr[self.sy1:self.sy2, self.sx1:self.sx2]
        else:
            if color_mode == "green":
                color = self.green_bgr
            elif color_mode == "pink":
                color = self.pink_bgr
            else:
                color = self.white_bgr
            text_bgr = (text_image[:, :, cp.newaxis] *
                        color[cp.newaxis, cp.newaxis, :]).astype(cp.uint8)
            self.output_gpu[self.py1:self.py2, self.px1:self.px2] = \
                text_bgr[self.sy1:self.sy2, self.sx1:self.sx2]

        cp.asnumpy(self.output_gpu, out=self.output_pinned)
        return self.output_pinned.copy()


def render_file(input_path, output_path, font_size, color_mode,
                out_w=1920, out_h=1080, progress_callback=None,
                cancel_flag=None):
    """Render a single video file.

    Args:
        input_path: source video path
        output_path: where to save the result
        font_size: character font size in pixels
        color_mode: 'green' | 'white' | 'pink' | 'color'
        out_w, out_h: output resolution
        progress_callback: optional fn(current, total, fps) for progress updates
        cancel_flag: optional threading.Event() - set to cancel mid-render

    Returns:
        True on success, False on failure/cancellation
    """
    temp_output = output_path + ".temp.mp4"
    rotation = get_rotation(input_path)

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        return False

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    ret, first_frame = cap.read()
    if not ret:
        cap.release()
        return False
    if rotation:
        first_frame = rotate_frame(first_frame, rotation)
    src_h, src_w = first_frame.shape[:2]
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    renderer = AsciiRenderer(src_w, src_h, out_w, out_h, font_size)

    # Clean up old output files
    for f in [temp_output, output_path]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(temp_output, fourcc, fps, (out_w, out_h))
    if not writer.isOpened():
        cap.release()
        return False

    # Threaded I/O pipeline
    read_queue = deque()
    write_queue = deque()
    stop_event = threading.Event()

    def reader():
        while not stop_event.is_set():
            r, f = cap.read()
            if not r:
                read_queue.append(None)
                break
            if rotation:
                f = rotate_frame(f, rotation)
            read_queue.append(f)
            while len(read_queue) > 64 and not stop_event.is_set():
                time.sleep(0.001)

    def writer_fn():
        written = 0
        while written < total_frames and not stop_event.is_set():
            if write_queue:
                fr = write_queue.popleft()
                if fr is None:
                    break
                writer.write(fr)
                written += 1
            else:
                time.sleep(0.001)

    reader_t = threading.Thread(target=reader, daemon=True)
    writer_t = threading.Thread(target=writer_fn, daemon=True)
    reader_t.start()
    writer_t.start()

    frame_num = 0
    start_time = time.time()
    cancelled = False

    while True:
        if cancel_flag is not None and cancel_flag.is_set():
            cancelled = True
            stop_event.set()
            break

        while not read_queue:
            if cancel_flag is not None and cancel_flag.is_set():
                cancelled = True
                stop_event.set()
                break
            time.sleep(0.0005)

        if cancelled:
            break

        frame = read_queue.popleft()
        if frame is None:
            break
        frame_num += 1
        output = renderer.render(frame, color_mode)
        write_queue.append(output)

        if progress_callback and (frame_num % 10 == 0 or frame_num == total_frames):
            elapsed = time.time() - start_time
            fps_proc = frame_num / elapsed if elapsed > 0 else 0
            try:
                progress_callback(frame_num, total_frames, fps_proc)
            except Exception:
                pass

    stop_event.set()
    reader_t.join(timeout=5)
    writer_t.join(timeout=30)
    writer.release()
    cap.release()

    if cancelled:
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except Exception:
                pass
        return False

    # Mux audio
    ffmpeg_path = find_ffmpeg()
    if ffmpeg_path:
        try:
            cmd = [ffmpeg_path, "-y",
                   "-i", temp_output, "-i", input_path,
                   "-c:v", "copy", "-c:a", "aac",
                   "-map", "0:v:0", "-map", "1:a:0?",
                   "-shortest", output_path]
            subprocess.run(cmd, capture_output=True, check=True)
            os.remove(temp_output)
        except subprocess.CalledProcessError:
            if os.path.exists(output_path):
                os.remove(output_path)
            os.rename(temp_output, output_path)
    else:
        os.rename(temp_output, output_path)

    return True


def preview_mode(input_path, initial_fontsize=12, initial_color="green"):
    """Interactive OpenCV preview window. Returns settings dict if user commits, else None."""
    rotation = get_rotation(input_path)
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        return None

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    ret, first_frame = cap.read()
    if not ret:
        return None
    if rotation:
        first_frame = rotate_frame(first_frame, rotation)
    src_h, src_w = first_frame.shape[:2]
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    font_size = initial_fontsize
    color_mode = initial_color
    preview_w, preview_h = 1280, 720
    renderer = AsciiRenderer(src_w, src_h, preview_w, preview_h, font_size)

    window_name = f"Preview: {os.path.basename(input_path)}"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, preview_w, preview_h)

    playing = True
    current_pos = 0
    frame_time = 1.0 / fps
    last_frame_time = time.time()
    current_output = None
    should_render = False

    def draw_overlay(frame):
        text_lines = [
            f"Font: {font_size}px ({renderer.cols}x{renderer.rows})",
            f"Mode: {color_mode}",
            f"Frame: {current_pos}/{total_frames}",
            "+/- size | c color | [ ] seek | SPC pause | r render | q quit"
        ]
        y = 30
        for line in text_lines:
            cv2.putText(frame, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(frame, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (255, 255, 255), 1, cv2.LINE_AA)
            y += 22
        return frame

    def rerender_current():
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, current_pos - 1))
        r, f = cap.read()
        if r:
            if rotation:
                f = rotate_frame(f, rotation)
            return renderer.render(f, color_mode)
        return None

    while True:
        now = time.time()
        if playing and (now - last_frame_time) >= frame_time:
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                current_pos = 0
                continue
            current_pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            if rotation:
                frame = rotate_frame(frame, rotation)
            current_output = renderer.render(frame, color_mode)
            last_frame_time = now

        if current_output is not None:
            display = current_output.copy()
            draw_overlay(display)
            cv2.imshow(window_name, display)

        key = cv2.waitKey(1) & 0xFF

        if key == ord('q') or key == 27:
            should_render = False
            break
        elif key == ord('r'):
            should_render = True
            break
        elif key == ord(' '):
            playing = not playing
        elif key == ord('+') or key == ord('='):
            font_size = min(font_size + 1, 48)
            renderer = AsciiRenderer(src_w, src_h, preview_w, preview_h, font_size)
            current_output = rerender_current()
        elif key == ord('-') or key == ord('_'):
            font_size = max(font_size - 1, 4)
            renderer = AsciiRenderer(src_w, src_h, preview_w, preview_h, font_size)
            current_output = rerender_current()
        elif key == ord('c'):
            modes = ["green", "white", "pink", "color"]
            color_mode = modes[(modes.index(color_mode) + 1) % len(modes)]
            current_output = rerender_current()
        elif key == ord('['):
            new_pos = max(0, current_pos - int(fps))
            cap.set(cv2.CAP_PROP_POS_FRAMES, new_pos)
            current_pos = new_pos
        elif key == ord(']'):
            new_pos = min(total_frames - 1, current_pos + int(fps))
            cap.set(cv2.CAP_PROP_POS_FRAMES, new_pos)
            current_pos = new_pos

    cap.release()
    cv2.destroyAllWindows()

    if should_render:
        return {"fontsize": font_size, "color_mode": color_mode}
    return None


def cli_main():
    parser = argparse.ArgumentParser(description="ASCII Video Filter (GPU)")
    parser.add_argument("inputs", nargs="+", help="Input video file(s)")
    parser.add_argument("--cols", type=int, default=0)
    parser.add_argument("--color", action="store_true")
    parser.add_argument("--green", action="store_true")
    parser.add_argument("--white", action="store_true")
    parser.add_argument("--pink", action="store_true")
    parser.add_argument("--output", type=str, default="")
    parser.add_argument("--output-dir", type=str, default="")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--fontsize", type=int, default=0)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--preview-each", action="store_true")
    args = parser.parse_args()

    all_inputs = []
    for inp in args.inputs:
        if "*" in inp or "?" in inp:
            all_inputs.extend(glob.glob(inp))
        elif os.path.exists(inp):
            all_inputs.append(inp)
        else:
            print(f"Not found: {inp}")

    if not all_inputs:
        print("No valid inputs.")
        sys.exit(1)

    if not GPU_AVAILABLE:
        print("ERROR: CuPy not installed. Run: pip install cupy-cuda12x")
        sys.exit(1)

    print(f"GPU: {cp.cuda.runtime.getDeviceProperties(0)['name'].decode()}")
    print(f"Files: {len(all_inputs)}")

    color_mode = "green"
    if args.color:
        color_mode = "color"
    elif args.white:
        color_mode = "white"
    elif args.pink:
        color_mode = "pink"

    font_size = args.fontsize if args.fontsize > 0 else 12

    if args.preview:
        settings = preview_mode(all_inputs[0], font_size, color_mode)
        if settings is None:
            print("Cancelled.")
            return
        font_size = settings["fontsize"]
        color_mode = settings["color_mode"]

    def progress(current, total, fps_proc):
        pct = (current / total) * 100
        eta = (total - current) / fps_proc if fps_proc > 0 else 0
        print(f"  {current}/{total} ({pct:.1f}%) - {fps_proc:.1f} fps - ETA: {eta:.0f}s",
              end="\r")

    success = 0
    for i, input_path in enumerate(all_inputs, 1):
        print(f"\n[{i}/{len(all_inputs)}] {input_path}")

        if args.preview_each and not args.preview:
            settings = preview_mode(input_path, font_size, color_mode)
            if settings is None:
                print("Skipped.")
                continue
            fs = settings["fontsize"]
            cm = settings["color_mode"]
        else:
            fs = font_size
            cm = color_mode

        if args.output and len(all_inputs) == 1:
            output_path = args.output
        elif args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)
            base = os.path.splitext(os.path.basename(input_path))[0]
            output_path = os.path.join(args.output_dir, base + "_ascii.mp4")
        else:
            base, _ = os.path.splitext(input_path)
            output_path = base + "_ascii.mp4"

        if render_file(input_path, output_path, fs, cm,
                       args.width, args.height, progress_callback=progress):
            success += 1
            print(f"\n  Saved: {output_path}")
        else:
            print("\n  Failed.")

    print(f"\nDone: {success}/{len(all_inputs)} succeeded.")


if __name__ == "__main__":
    cli_main()
