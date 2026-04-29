"""
ASCII Video Filter - GUI
Black and hot pink themed interface for the ASCII video converter.

Run: python ascii_video_gui.py
"""

import tkinter as tk
from tkinter import filedialog, ttk, font as tkfont
import threading
import queue
import os
import sys
import time
import platform

import ascii_video

# --- Theme ---
BG = "#0a0a0a"           # near-black background
BG_ALT = "#151515"       # slightly lighter panel
BG_INPUT = "#1a1a1a"     # input field background
PINK = "#FF1493"         # hot pink accent
PINK_DIM = "#C01070"     # dimmer pink (hover/border)
TEXT = "#F0F0F0"         # primary text
TEXT_DIM = "#888888"     # secondary text


def _pick_font(candidates, default):
    """Return the first available font family from candidates, or default."""
    try:
        available = set(tkfont.families())
        for name in candidates:
            if name in available:
                return name
    except Exception:
        pass
    return default


def _init_fonts():
    """Choose cross-platform fonts (Tk must be initialized first)."""
    system = platform.system()
    if system == "Windows":
        ui_candidates = ["Segoe UI", "Tahoma", "Arial"]
        mono_candidates = ["Consolas", "Courier New"]
    elif system == "Darwin":
        ui_candidates = ["SF Pro Text", "Helvetica Neue", "Helvetica"]
        mono_candidates = ["Menlo", "Monaco", "Courier"]
    else:  # Linux
        ui_candidates = ["Inter", "Cantarell", "Noto Sans", "DejaVu Sans",
                         "Liberation Sans"]
        mono_candidates = ["JetBrains Mono", "Fira Code", "Source Code Pro",
                           "DejaVu Sans Mono", "Liberation Mono", "Monospace"]

    ui = _pick_font(ui_candidates, "TkDefaultFont")
    mono = _pick_font(mono_candidates, "TkFixedFont")
    return ui, mono


# Defaults — replaced after Tk init
FONT_UI = "TkDefaultFont"
FONT_MONO_FAMILY = "TkFixedFont"


def _font(weight="normal", size=10, mono=False):
    family = FONT_MONO_FAMILY if mono else FONT_UI
    if weight == "bold":
        return (family, size, "bold")
    return (family, size)


class AsciiGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ASCII Video Filter")
        self.root.configure(bg=BG)
        self.root.geometry("760x820")
        self.root.minsize(640, 720)

        self.files = []
        self.render_thread = None
        self.cancel_flag = threading.Event()
        self.progress_queue = queue.Queue()

        self._build_ui()
        self._poll_progress()

    # --- UI construction ---

    def _build_ui(self):
        # Header
        header = tk.Label(
            self.root, text="ASCII VIDEO FILTER",
            bg=BG, fg=PINK, font=_font("bold", 18)
        )
        header.pack(pady=(20, 4))

        subheader = tk.Label(
            self.root, text="GPU-accelerated video to ASCII art converter",
            bg=BG, fg=TEXT_DIM, font=_font()
        )
        subheader.pack(pady=(0, 16))

        # Main content frame
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        # --- File list section ---
        self._section_label(main, "INPUT FILES")

        file_frame = tk.Frame(main, bg=BG_ALT, highlightbackground=PINK_DIM,
                              highlightthickness=1)
        file_frame.pack(fill="x", pady=(4, 12))

        # Scrollable listbox
        list_wrap = tk.Frame(file_frame, bg=BG_ALT)
        list_wrap.pack(fill="x", padx=8, pady=8)

        self.file_listbox = tk.Listbox(
            list_wrap, bg=BG_INPUT, fg=TEXT,
            selectbackground=PINK, selectforeground="#000000",
            font=_font(mono=True), height=5, borderwidth=0, highlightthickness=0,
            activestyle="none"
        )
        self.file_listbox.pack(side="left", fill="x", expand=True)

        scroll = tk.Scrollbar(list_wrap, command=self.file_listbox.yview,
                              bg=BG_ALT, troughcolor=BG_INPUT,
                              activebackground=PINK, borderwidth=0)
        scroll.pack(side="right", fill="y")
        self.file_listbox.config(yscrollcommand=scroll.set)

        btn_frame = tk.Frame(file_frame, bg=BG_ALT)
        btn_frame.pack(fill="x", padx=8, pady=(0, 8))

        self._button(btn_frame, "+ Add Files", self.add_files).pack(side="left", padx=(0, 6))
        self._button(btn_frame, "- Remove", self.remove_selected).pack(side="left", padx=6)
        self._button(btn_frame, "Clear All", self.clear_files).pack(side="left", padx=6)

        # --- Settings section ---
        self._section_label(main, "SETTINGS")

        settings = tk.Frame(main, bg=BG_ALT, highlightbackground=PINK_DIM,
                            highlightthickness=1)
        settings.pack(fill="x", pady=(4, 12))

        settings_inner = tk.Frame(settings, bg=BG_ALT)
        settings_inner.pack(fill="x", padx=12, pady=12)

        # Font size slider
        tk.Label(settings_inner, text="Font Size:", bg=BG_ALT, fg=TEXT,
                 font=_font()).grid(row=0, column=0, sticky="w", pady=4)

        self.fontsize_var = tk.IntVar(value=12)
        self.fontsize_label = tk.Label(settings_inner, text="12 px",
                                        bg=BG_ALT, fg=PINK,
                                        font=_font("bold"), width=6, anchor="e")
        self.fontsize_label.grid(row=0, column=2, sticky="e", padx=(8, 0))

        slider = tk.Scale(
            settings_inner, from_=4, to=32, orient="horizontal",
            variable=self.fontsize_var, bg=BG_ALT, fg=TEXT,
            troughcolor=BG_INPUT, activebackground=PINK,
            highlightthickness=0, borderwidth=0, showvalue=0,
            command=lambda v: self.fontsize_label.config(text=f"{int(float(v))} px")
        )
        slider.grid(row=0, column=1, sticky="ew", padx=12)
        settings_inner.grid_columnconfigure(1, weight=1)

        # Color mode
        tk.Label(settings_inner, text="Color Mode:", bg=BG_ALT, fg=TEXT,
                 font=_font()).grid(row=1, column=0, sticky="w", pady=(12, 4))

        self.color_var = tk.StringVar(value="green")
        mode_frame = tk.Frame(settings_inner, bg=BG_ALT)
        mode_frame.grid(row=1, column=1, columnspan=2, sticky="w", padx=12, pady=(12, 4))

        for mode in ["green", "white", "pink", "color"]:
            rb = tk.Radiobutton(
                mode_frame, text=mode.capitalize(), variable=self.color_var,
                value=mode, bg=BG_ALT, fg=TEXT, selectcolor=BG_INPUT,
                activebackground=BG_ALT, activeforeground=PINK,
                font=_font(), borderwidth=0, highlightthickness=0
            )
            rb.pack(side="left", padx=(0, 14))

        # Output directory
        tk.Label(settings_inner, text="Output Dir:", bg=BG_ALT, fg=TEXT,
                 font=_font()).grid(row=2, column=0, sticky="w", pady=(12, 4))

        out_frame = tk.Frame(settings_inner, bg=BG_ALT)
        out_frame.grid(row=2, column=1, columnspan=2, sticky="ew", padx=12, pady=(12, 4))

        self.output_var = tk.StringVar(value="(same folder as source)")
        self.output_entry = tk.Entry(
            out_frame, textvariable=self.output_var,
            bg=BG_INPUT, fg=TEXT_DIM, font=_font(mono=True),
            borderwidth=0, highlightthickness=1,
            highlightbackground=BG_INPUT, highlightcolor=PINK,
            insertbackground=PINK
        )
        self.output_entry.pack(side="left", fill="x", expand=True, ipady=4)

        self._button(out_frame, "Browse", self.choose_output_dir).pack(side="left", padx=(6, 0))

        # --- Actions section ---
        action_frame = tk.Frame(main, bg=BG)
        action_frame.pack(fill="x", pady=(4, 4))

        self.preview_btn = self._button(
            action_frame, "PREVIEW (first file)",
            self.launch_preview, primary=False
        )
        self.preview_btn.pack(side="left", padx=(0, 8), ipadx=12, ipady=4)

        self.render_btn = self._button(
            action_frame, "RENDER ALL",
            self.start_render, primary=True
        )
        self.render_btn.pack(side="left", ipadx=18, ipady=4)

        self.cancel_btn = self._button(
            action_frame, "Cancel", self.cancel_render, primary=False
        )
        # hidden until render starts

        # --- Progress section ---
        self._section_label(main, "PROGRESS")

        progress_frame = tk.Frame(main, bg=BG_ALT, highlightbackground=PINK_DIM,
                                  highlightthickness=1)
        progress_frame.pack(fill="both", expand=True, pady=(4, 0))

        progress_inner = tk.Frame(progress_frame, bg=BG_ALT)
        progress_inner.pack(fill="both", expand=True, padx=12, pady=10)

        # Top line: current file / batch position
        self.current_file_var = tk.StringVar(value="Idle")
        current_file_label = tk.Label(
            progress_inner, textvariable=self.current_file_var,
            bg=BG_ALT, fg=PINK, font=_font("bold"),
            anchor="w", justify="left"
        )
        current_file_label.pack(fill="x")

        # Stage / status line
        self.stage_var = tk.StringVar(value="Add files and click RENDER ALL.")
        stage_label = tk.Label(
            progress_inner, textvariable=self.stage_var,
            bg=BG_ALT, fg=TEXT, font=_font(mono=True),
            anchor="w", justify="left"
        )
        stage_label.pack(fill="x", pady=(2, 8))

        # Per-file progress bar
        self.file_progress_canvas = tk.Canvas(
            progress_inner, height=6, bg=BG_INPUT,
            highlightthickness=0, borderwidth=0
        )
        self.file_progress_canvas.pack(fill="x", pady=(0, 4))
        self.file_progress_bar = self.file_progress_canvas.create_rectangle(
            0, 0, 0, 6, fill=PINK, outline=""
        )

        # Per-file stats grid
        stats_frame = tk.Frame(progress_inner, bg=BG_ALT)
        stats_frame.pack(fill="x", pady=(2, 8))

        self.frame_count_var = tk.StringVar(value="—")
        self.fps_var = tk.StringVar(value="—")
        self.eta_var = tk.StringVar(value="—")
        self.percent_var = tk.StringVar(value="0%")

        self._stat_widget(stats_frame, "Frame", self.frame_count_var, 0)
        self._stat_widget(stats_frame, "Speed", self.fps_var, 1)
        self._stat_widget(stats_frame, "ETA", self.eta_var, 2)
        self._stat_widget(stats_frame, "Done", self.percent_var, 3)

        # Overall batch progress
        self.batch_label_var = tk.StringVar(value="Batch: 0 / 0")
        batch_label = tk.Label(
            progress_inner, textvariable=self.batch_label_var,
            bg=BG_ALT, fg=TEXT_DIM, font=_font(mono=True, size=9),
            anchor="w"
        )
        batch_label.pack(fill="x", pady=(8, 2))

        self.batch_progress_canvas = tk.Canvas(
            progress_inner, height=4, bg=BG_INPUT,
            highlightthickness=0, borderwidth=0
        )
        self.batch_progress_canvas.pack(fill="x")
        self.batch_progress_bar = self.batch_progress_canvas.create_rectangle(
            0, 0, 0, 4, fill=PINK_DIM, outline=""
        )

        # Log area for messages and errors
        log_frame = tk.Frame(progress_inner, bg=BG_ALT)
        log_frame.pack(fill="both", expand=True, pady=(10, 0))

        log_label = tk.Label(
            log_frame, text="LOG", bg=BG_ALT, fg=PINK_DIM,
            font=_font("bold", 8), anchor="w"
        )
        log_label.pack(fill="x")

        log_inner = tk.Frame(log_frame, bg=BG_INPUT)
        log_inner.pack(fill="both", expand=True, pady=(2, 0))

        self.log_text = tk.Text(
            log_inner, bg=BG_INPUT, fg=TEXT,
            font=_font(mono=True, size=9),
            borderwidth=0, highlightthickness=0,
            wrap="word", height=4, state="disabled",
            padx=8, pady=6
        )
        self.log_text.pack(side="left", fill="both", expand=True)

        log_scroll = tk.Scrollbar(
            log_inner, command=self.log_text.yview,
            bg=BG_ALT, troughcolor=BG_INPUT,
            activebackground=PINK, borderwidth=0
        )
        log_scroll.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=log_scroll.set)

        # Configure log tags for color-coded messages
        self.log_text.tag_configure("info", foreground=TEXT)
        self.log_text.tag_configure("success", foreground="#00FF88")
        self.log_text.tag_configure("error", foreground="#FF5577")
        self.log_text.tag_configure("warn", foreground="#FFCC44")
        self.log_text.tag_configure("dim", foreground=TEXT_DIM)

    def _stat_widget(self, parent, label, var, col):
        cell = tk.Frame(parent, bg=BG_ALT)
        cell.grid(row=0, column=col, sticky="ew", padx=(0, 12) if col < 3 else 0)
        parent.grid_columnconfigure(col, weight=1)
        tk.Label(cell, text=label, bg=BG_ALT, fg=TEXT_DIM,
                 font=_font(size=8)).pack(anchor="w")
        tk.Label(cell, textvariable=var, bg=BG_ALT, fg=TEXT,
                 font=_font("bold", 11)).pack(anchor="w")

    def _log(self, message, level="info"):
        """Append a line to the log area."""
        self.log_text.config(state="normal")
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] ", "dim")
        self.log_text.insert("end", message + "\n", level)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _section_label(self, parent, text):
        lbl = tk.Label(
            parent, text=text, bg=BG, fg=PINK,
            font=_font("bold", 9)
        )
        lbl.pack(anchor="w", pady=(4, 0))

    def _button(self, parent, text, command, primary=False):
        if primary:
            fg = "#000000"
            bg_c = PINK
            hover_bg = "#FF4FA8"
        else:
            fg = PINK
            bg_c = BG_ALT
            hover_bg = "#202020"

        btn = tk.Button(
            parent, text=text, command=command,
            bg=bg_c, fg=fg, font=_font("bold"),
            activebackground=hover_bg, activeforeground=fg,
            borderwidth=0, highlightthickness=1,
            highlightbackground=PINK_DIM,
            cursor="hand2", padx=14, pady=6
        )

        def on_enter(e):
            btn.config(bg=hover_bg)

        def on_leave(e):
            btn.config(bg=bg_c)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    # --- File list actions ---

    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="Select video files",
            filetypes=[
                ("Video files", "*.mp4 *.mov *.avi *.mkv *.webm *.m4v"),
                ("All files", "*.*")
            ]
        )
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                self.file_listbox.insert("end", os.path.basename(p))
        self._update_status()

    def remove_selected(self):
        sel = list(self.file_listbox.curselection())
        for idx in reversed(sel):
            self.files.pop(idx)
            self.file_listbox.delete(idx)
        self._update_status()

    def clear_files(self):
        self.files.clear()
        self.file_listbox.delete(0, "end")
        self._update_status()

    def choose_output_dir(self):
        d = filedialog.askdirectory(title="Select output directory")
        if d:
            self.output_var.set(d)
            self.output_entry.config(fg=TEXT)

    def _update_status(self):
        if not self.files:
            self.stage_var.set("Add files and click RENDER ALL.")
            self.batch_label_var.set("Batch: 0 / 0")
        else:
            self.stage_var.set(f"{len(self.files)} file(s) queued. Ready to render.")
            self.batch_label_var.set(f"Batch: 0 / {len(self.files)}")

    # --- Preview ---

    def launch_preview(self):
        if not self.files:
            self._log("Add at least one file first.", "warn")
            return
        if not ascii_video.GPU_AVAILABLE:
            self._log("CuPy not installed. Run: pip install cupy-cuda12x", "error")
            return

        # Preview runs in a thread to avoid blocking the GUI
        def run_preview():
            self.stage_var.set("Opening preview window...")
            self._log("Launching preview...", "info")
            try:
                settings = ascii_video.preview_mode(
                    self.files[0],
                    initial_fontsize=self.fontsize_var.get(),
                    initial_color=self.color_var.get()
                )
                if settings:
                    self.fontsize_var.set(settings["fontsize"])
                    self.fontsize_label.config(text=f"{settings['fontsize']} px")
                    self.color_var.set(settings["color_mode"])
                    self.stage_var.set(
                        f"Preview settings applied: {settings['fontsize']}px, "
                        f"{settings['color_mode']}"
                    )
                    self._log(
                        f"Settings applied from preview: {settings['fontsize']}px, "
                        f"{settings['color_mode']}", "success"
                    )
                else:
                    self.stage_var.set("Preview cancelled.")
                    self._log("Preview cancelled.", "dim")
            except Exception as e:
                import traceback
                self.stage_var.set(f"Preview error: {e}")
                self._log(f"Preview error: {e}", "error")
                self._log(traceback.format_exc(), "error")

        threading.Thread(target=run_preview, daemon=True).start()

    # --- Render ---

    def start_render(self):
        if not self.files:
            self._log("Add at least one file first.", "warn")
            return
        if not ascii_video.GPU_AVAILABLE:
            self._log("CuPy not installed. Run: pip install cupy-cuda12x", "error")
            return
        if self.render_thread and self.render_thread.is_alive():
            return

        # Lock UI
        self.render_btn.pack_forget()
        self.cancel_btn.pack(side="left", ipadx=12, ipady=4)
        self.preview_btn.config(state="disabled")
        self.cancel_flag.clear()

        # Reset progress display
        self._reset_progress()

        font_size = self.fontsize_var.get()
        color_mode = self.color_var.get()
        output_dir = self.output_var.get()
        if output_dir == "(same folder as source)" or not output_dir:
            output_dir = None

        files = list(self.files)

        # Initial log entries
        self._log(f"Starting batch of {len(files)} file(s)", "info")
        self._log(f"Settings: {font_size}px, {color_mode} mode, "
                  f"output to {output_dir or 'source folder'}", "dim")

        def render_all():
            total = len(files)
            done = 0
            failed = 0
            batch_start = time.time()

            for i, input_path in enumerate(files, 1):
                if self.cancel_flag.is_set():
                    break

                if output_dir:
                    try:
                        os.makedirs(output_dir, exist_ok=True)
                    except Exception as e:
                        self.progress_queue.put(
                            ("log", (f"Cannot create output dir: {e}", "error"))
                        )
                        failed += 1
                        continue
                    base = os.path.splitext(os.path.basename(input_path))[0]
                    output_path = os.path.join(output_dir, base + "_ascii.mp4")
                else:
                    base, _ = os.path.splitext(input_path)
                    output_path = base + "_ascii.mp4"

                basename = os.path.basename(input_path)

                # Update batch position
                self.progress_queue.put(("batch", (i, total)))
                self.progress_queue.put(
                    ("current_file", f"[{i}/{total}] {basename}")
                )
                self.progress_queue.put(
                    ("log", (f"Starting: {basename}", "info"))
                )

                # Verify file exists
                if not os.path.exists(input_path):
                    self.progress_queue.put(
                        ("log", (f"File not found: {input_path}", "error"))
                    )
                    failed += 1
                    continue

                # Check file size
                try:
                    size_mb = os.path.getsize(input_path) / (1024 * 1024)
                    self.progress_queue.put(
                        ("log", (f"  Source size: {size_mb:.1f} MB", "dim"))
                    )
                except Exception:
                    pass

                def on_progress(cur, tot, fps_p):
                    pct = (cur / tot) * 100 if tot else 0
                    eta = (tot - cur) / fps_p if fps_p > 0 else 0
                    self.progress_queue.put(("frame", (cur, tot)))
                    self.progress_queue.put(("fps", fps_p))
                    self.progress_queue.put(("eta", eta))
                    self.progress_queue.put(("file_progress", pct))

                def on_stage(stage_name):
                    self.progress_queue.put(("stage", stage_name))
                    self.progress_queue.put(
                        ("log", (f"  {stage_name}...", "dim"))
                    )

                file_start = time.time()
                try:
                    ok = ascii_video.render_file(
                        input_path, output_path,
                        font_size, color_mode,
                        progress_callback=on_progress,
                        cancel_flag=self.cancel_flag,
                        stage_callback=on_stage
                    )
                    elapsed = time.time() - file_start
                    if ok:
                        done += 1
                        self.progress_queue.put(
                            ("log",
                             (f"  ✓ Saved: {output_path} ({elapsed:.1f}s)",
                              "success"))
                        )
                    else:
                        # Cancelled
                        self.progress_queue.put(
                            ("log", (f"  Cancelled mid-render", "warn"))
                        )
                except Exception as e:
                    import traceback
                    failed += 1
                    self.progress_queue.put(
                        ("log", (f"  ✗ FAILED: {basename}", "error"))
                    )
                    # Multi-line error message
                    for line in str(e).split("\n"):
                        if line.strip():
                            self.progress_queue.put(
                                ("log", (f"    {line}", "error"))
                            )
                    # Full traceback for debugging
                    tb = traceback.format_exc()
                    self.progress_queue.put(
                        ("log", (f"    [traceback below]", "dim"))
                    )
                    for line in tb.split("\n")[-6:-1]:  # last few lines
                        if line.strip():
                            self.progress_queue.put(
                                ("log", (f"    {line}", "dim"))
                            )

            # Final summary
            batch_elapsed = time.time() - batch_start
            if self.cancel_flag.is_set():
                msg = f"Cancelled. Completed {done}/{total}."
                level = "warn"
            elif failed > 0:
                msg = (f"Finished with errors: {done} succeeded, "
                       f"{failed} failed in {batch_elapsed:.1f}s")
                level = "error"
            else:
                msg = (f"All {total} file(s) rendered successfully "
                       f"in {batch_elapsed:.1f}s")
                level = "success"

            self.progress_queue.put(("stage", msg))
            self.progress_queue.put(("log", (msg, level)))
            self.progress_queue.put(("file_progress", 100))
            self.progress_queue.put(("batch", (total, total)))
            self.progress_queue.put(("done", None))

        self.render_thread = threading.Thread(target=render_all, daemon=True)
        self.render_thread.start()

    def _reset_progress(self):
        self.current_file_var.set("Starting...")
        self.stage_var.set("Initializing...")
        self.frame_count_var.set("—")
        self.fps_var.set("—")
        self.eta_var.set("—")
        self.percent_var.set("0%")
        self.batch_label_var.set(f"Batch: 0 / {len(self.files)}")
        self.file_progress_canvas.coords(self.file_progress_bar, 0, 0, 0, 6)
        self.batch_progress_canvas.coords(self.batch_progress_bar, 0, 0, 0, 4)

    def cancel_render(self):
        self.cancel_flag.set()
        self.stage_var.set("Cancelling — finishing current frame...")
        self._log("Cancellation requested.", "warn")

    def _poll_progress(self):
        try:
            while True:
                kind, data = self.progress_queue.get_nowait()

                if kind == "current_file":
                    self.current_file_var.set(data)

                elif kind == "stage":
                    self.stage_var.set(data)

                elif kind == "frame":
                    cur, tot = data
                    self.frame_count_var.set(f"{cur:,} / {tot:,}")

                elif kind == "fps":
                    self.fps_var.set(f"{data:.1f} fps")

                elif kind == "eta":
                    eta = data
                    if eta > 60:
                        self.eta_var.set(f"{int(eta // 60)}m {int(eta % 60)}s")
                    else:
                        self.eta_var.set(f"{eta:.0f}s")

                elif kind == "file_progress":
                    self.percent_var.set(f"{data:.0f}%")
                    w = self.file_progress_canvas.winfo_width()
                    fill_w = int(w * (data / 100))
                    self.file_progress_canvas.coords(
                        self.file_progress_bar, 0, 0, fill_w, 6
                    )

                elif kind == "batch":
                    cur_idx, total = data
                    self.batch_label_var.set(f"Batch: {cur_idx} / {total}")
                    if total > 0:
                        w = self.batch_progress_canvas.winfo_width()
                        fill_w = int(w * (cur_idx / total))
                        self.batch_progress_canvas.coords(
                            self.batch_progress_bar, 0, 0, fill_w, 4
                        )

                elif kind == "log":
                    msg, level = data
                    self._log(msg, level)

                elif kind == "done":
                    self.cancel_btn.pack_forget()
                    self.render_btn.pack(side="left", ipadx=18, ipady=4)
                    self.preview_btn.config(state="normal")
                    self.current_file_var.set("Idle")

        except queue.Empty:
            pass
        self.root.after(50, self._poll_progress)


def main():
    root = tk.Tk()

    # Initialize fonts (must happen after Tk root is created)
    global FONT_UI, FONT_MONO_FAMILY
    FONT_UI, FONT_MONO_FAMILY = _init_fonts()

    # Set app icon if available — .png on Linux, .ico on Windows
    base_dir = os.path.dirname(os.path.abspath(__file__))
    png_icon = os.path.join(base_dir, "icon.png")
    ico_icon = os.path.join(base_dir, "icon.ico")
    try:
        if os.path.exists(png_icon):
            img = tk.PhotoImage(file=png_icon)
            root.iconphoto(True, img)
        elif os.path.exists(ico_icon) and platform.system() == "Windows":
            root.iconbitmap(ico_icon)
    except Exception:
        pass

    app = AsciiGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
