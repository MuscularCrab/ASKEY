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
        self.root.geometry("720x640")
        self.root.minsize(600, 560)

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
        progress_frame = tk.Frame(main, bg=BG)
        progress_frame.pack(fill="x", pady=(16, 0))

        self.status_var = tk.StringVar(value="Ready.")
        status_label = tk.Label(
            progress_frame, textvariable=self.status_var,
            bg=BG, fg=TEXT_DIM, font=_font(mono=True), anchor="w"
        )
        status_label.pack(fill="x", pady=(0, 4))

        # Custom progress bar (tkinter's default is hard to style)
        self.progress_canvas = tk.Canvas(
            progress_frame, height=6, bg=BG_INPUT,
            highlightthickness=0, borderwidth=0
        )
        self.progress_canvas.pack(fill="x")
        self.progress_bar = self.progress_canvas.create_rectangle(
            0, 0, 0, 6, fill=PINK, outline=""
        )

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
            self.status_var.set("Ready. Add some video files to get started.")
        else:
            self.status_var.set(f"{len(self.files)} file(s) queued.")

    # --- Preview ---

    def launch_preview(self):
        if not self.files:
            self.status_var.set("Add at least one file first.")
            return
        if not ascii_video.GPU_AVAILABLE:
            self.status_var.set("ERROR: CuPy not installed. Run: pip install cupy-cuda12x")
            return

        # Preview runs in a thread to avoid blocking the GUI
        def run_preview():
            self.status_var.set("Opening preview... (see OpenCV window)")
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
                    self.status_var.set(
                        f"Preview settings applied: {settings['fontsize']}px, "
                        f"{settings['color_mode']}"
                    )
                else:
                    self.status_var.set("Preview cancelled.")
            except Exception as e:
                self.status_var.set(f"Preview error: {e}")

        threading.Thread(target=run_preview, daemon=True).start()

    # --- Render ---

    def start_render(self):
        if not self.files:
            self.status_var.set("Add at least one file first.")
            return
        if not ascii_video.GPU_AVAILABLE:
            self.status_var.set("ERROR: CuPy not installed. Run: pip install cupy-cuda12x")
            return
        if self.render_thread and self.render_thread.is_alive():
            return

        # Lock UI
        self.render_btn.pack_forget()
        self.cancel_btn.pack(side="left", ipadx=12, ipady=4)
        self.preview_btn.config(state="disabled")
        self.cancel_flag.clear()

        font_size = self.fontsize_var.get()
        color_mode = self.color_var.get()
        output_dir = self.output_var.get()
        if output_dir == "(same folder as source)" or not output_dir:
            output_dir = None

        files = list(self.files)

        def render_all():
            total = len(files)
            done = 0
            for i, input_path in enumerate(files, 1):
                if self.cancel_flag.is_set():
                    break

                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                    base = os.path.splitext(os.path.basename(input_path))[0]
                    output_path = os.path.join(output_dir, base + "_ascii.mp4")
                else:
                    base, _ = os.path.splitext(input_path)
                    output_path = base + "_ascii.mp4"

                basename = os.path.basename(input_path)

                def on_progress(cur, tot, fps_p, fn=basename, idx=i):
                    pct = (cur / tot) * 100 if tot else 0
                    eta = (tot - cur) / fps_p if fps_p > 0 else 0
                    msg = (f"[{idx}/{total}] {fn} — "
                           f"{cur}/{tot} ({pct:.1f}%) — "
                           f"{fps_p:.1f} fps — ETA: {eta:.0f}s")
                    self.progress_queue.put(("status", msg))
                    self.progress_queue.put(("progress", pct))

                try:
                    ok = ascii_video.render_file(
                        input_path, output_path,
                        font_size, color_mode,
                        progress_callback=on_progress,
                        cancel_flag=self.cancel_flag
                    )
                    if ok:
                        done += 1
                except Exception as e:
                    self.progress_queue.put(
                        ("status", f"Error on {basename}: {e}")
                    )

            if self.cancel_flag.is_set():
                self.progress_queue.put(("status", f"Cancelled. {done}/{total} completed."))
            else:
                self.progress_queue.put(
                    ("status", f"Done! {done}/{total} files rendered.")
                )
            self.progress_queue.put(("progress", 100))
            self.progress_queue.put(("done", None))

        self.render_thread = threading.Thread(target=render_all, daemon=True)
        self.render_thread.start()

    def cancel_render(self):
        self.cancel_flag.set()
        self.status_var.set("Cancelling...")

    def _poll_progress(self):
        try:
            while True:
                kind, data = self.progress_queue.get_nowait()
                if kind == "status":
                    self.status_var.set(data)
                elif kind == "progress":
                    w = self.progress_canvas.winfo_width()
                    fill_w = int(w * (data / 100))
                    self.progress_canvas.coords(self.progress_bar, 0, 0, fill_w, 6)
                elif kind == "done":
                    self.cancel_btn.pack_forget()
                    self.render_btn.pack(side="left", ipadx=18, ipady=4)
                    self.preview_btn.config(state="normal")
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
