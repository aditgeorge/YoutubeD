#!/usr/bin/env python3
"""
YouTube Downloader
==================
A simple GUI app to download YouTube videos using yt-dlp.

Requirements (auto-installed on first run):
    pip install yt-dlp

Optional — needed for merging high-quality video + audio streams:
    Install ffmpeg and add it to PATH:
      Windows : https://www.gyan.dev/ffmpeg/builds/  (add bin/ to PATH)
      macOS   : brew install ffmpeg
      Linux   : sudo apt install ffmpeg

Run:
    python youtube_downloader.py

Build a standalone executable (no Python needed on target machine):
    pip install pyinstaller
    pyinstaller --onefile --windowed --name "YouTube Downloader" youtube_downloader.py
    # Output is in the dist/ folder
"""

import os
import re
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.parse import parse_qs, urlparse


# ---------------------------------------------------------------------------
# Auto-install yt-dlp if missing
# ---------------------------------------------------------------------------

def _ensure_ytdlp():
    try:
        import yt_dlp
        return yt_dlp
    except ImportError:
        import subprocess
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", "yt-dlp"],
            stdout=subprocess.DEVNULL,
        )
        import yt_dlp
        return yt_dlp


yt_dlp = _ensure_ytdlp()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VIDEO_ID_RE = re.compile(r"^[\w\-]{11}$", re.IGNORECASE)

QUALITY_OPTIONS = {
    "Best Quality":       "bestvideo+bestaudio/best",
    "1080p":              "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p":               "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p":               "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360p (no ffmpeg)":   "best[height<=360]",
    "Audio Only (MP3)":   "bestaudio/best",
}

DEFAULT_QUALITY = "Best Quality"


def _normalize_youtube_url(raw_url):
    url = raw_url.strip()
    if not url:
        return None

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        url = f"https://{url.lstrip('/')}"

    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    video_id = None
    path_parts = [part for part in parsed.path.split("/") if part]

    if host == "youtu.be" and path_parts:
        video_id = path_parts[0]
    elif host.endswith("youtube.com"):
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        elif len(path_parts) >= 2 and path_parts[0] in {"shorts", "embed", "live"}:
            video_id = path_parts[1]

    if not video_id or not _VIDEO_ID_RE.fullmatch(video_id):
        return None

    return f"https://www.youtube.com/watch?v={video_id}"


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class App(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("YouTube Downloader")
        self.resizable(False, False)
        self._video_info = None
        self._build_ui()
        self._center()

    # ── Layout ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = {"padx": 14, "pady": 6}

        # --- URL section ---------------------------------------------------
        url_box = ttk.LabelFrame(self, text="YouTube URL", padding=10)
        url_box.grid(row=0, column=0, sticky="ew", **outer)

        self.url_var = tk.StringVar()
        url_entry = ttk.Entry(url_box, textvariable=self.url_var, width=52)
        url_entry.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        url_entry.bind("<Return>", lambda _e: self._start_validate())

        ttk.Button(url_box, text="Validate", width=9,
                   command=self._start_validate).grid(row=0, column=1)
        ttk.Button(url_box, text="Clear", width=7,
                   command=self._clear).grid(row=0, column=2, padx=(4, 0))

        self._url_status = ttk.Label(url_box, text="Paste a URL and press Validate.",
                                     foreground="gray")
        self._url_status.grid(row=1, column=0, columnspan=3,
                               sticky="w", pady=(5, 0))

        # --- Video info section --------------------------------------------
        info_box = ttk.LabelFrame(self, text="Video Info", padding=10)
        info_box.grid(row=1, column=0, sticky="ew", **outer)

        self._title_lbl = ttk.Label(info_box, text="—", wraplength=490,
                                    font=("", 10, "bold"))
        self._title_lbl.grid(row=0, column=0, sticky="w")

        self._meta_lbl = ttk.Label(info_box, text="", foreground="gray")
        self._meta_lbl.grid(row=1, column=0, sticky="w", pady=(2, 0))

        # --- Options section -----------------------------------------------
        opt_box = ttk.LabelFrame(self, text="Options", padding=10)
        opt_box.grid(row=2, column=0, sticky="ew", **outer)

        ttk.Label(opt_box, text="Quality:").grid(row=0, column=0, sticky="w")
        self._quality_var = tk.StringVar(value=DEFAULT_QUALITY)
        ttk.Combobox(
            opt_box, textvariable=self._quality_var,
            values=list(QUALITY_OPTIONS.keys()), state="readonly", width=22,
        ).grid(row=0, column=1, padx=(6, 24))

        ttk.Label(opt_box, text="Save to:").grid(row=0, column=2, sticky="w")
        self._folder_var = tk.StringVar(value=os.path.expanduser("~/Downloads"))
        ttk.Entry(opt_box, textvariable=self._folder_var, width=22).grid(
            row=0, column=3, padx=(6, 4))
        ttk.Button(opt_box, text="Browse…",
                   command=self._browse).grid(row=0, column=4)

        # --- Progress section ----------------------------------------------
        prog_box = ttk.LabelFrame(self, text="Progress", padding=10)
        prog_box.grid(row=3, column=0, sticky="ew", **outer)

        self._progress = ttk.Progressbar(prog_box, length=490, mode="determinate")
        self._progress.grid(row=0, column=0, sticky="ew")

        self._status_var = tk.StringVar(value="Ready.")
        ttk.Label(prog_box, textvariable=self._status_var,
                  foreground="gray").grid(row=1, column=0, sticky="w", pady=(4, 0))

        # --- Download button -----------------------------------------------
        self._dl_btn = ttk.Button(
            self, text="Download", width=18,
            command=self._start_download, state="disabled",
        )
        self._dl_btn.grid(row=4, column=0, pady=(8, 16))

        self.columnconfigure(0, weight=1)

    def _center(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _set_url_status(self, text, color="gray"):
        self._url_status.config(text=text, foreground=color)

    def _set_status(self, text):
        self._status_var.set(text)

    def _browse(self):
        folder = filedialog.askdirectory(initialdir=self._folder_var.get())
        if folder:
            self._folder_var.set(folder)

    def _clear(self):
        self.url_var.set("")
        self._video_info = None
        self._title_lbl.config(text="—")
        self._meta_lbl.config(text="")
        self._progress["value"] = 0
        self._set_url_status("Paste a URL and press Validate.", "gray")
        self._set_status("Ready.")
        self._dl_btn.config(state="disabled")

    # ── Validation ──────────────────────────────────────────────────────────

    def _start_validate(self):
        url = self.url_var.get().strip()
        if not url:
            self._set_url_status("Please enter a URL.", "red")
            return

        normalized_url = _normalize_youtube_url(url)
        if not normalized_url:
            self._set_url_status(
                "Not a recognised YouTube video URL (youtube.com or youtu.be).", "red")
            self._dl_btn.config(state="disabled")
            return

        self.url_var.set(normalized_url)
        self._set_url_status("Contacting YouTube…", "gray")
        self._dl_btn.config(state="disabled")
        threading.Thread(target=self._fetch_info, args=(normalized_url,), daemon=True).start()

    def _fetch_info(self, url):
        try:
            opts = {"quiet": True, "no_warnings": True, "skip_download": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            self.after(0, self._on_info_ok, info)
        except Exception as exc:
            self.after(0, self._on_info_fail, str(exc))

    def _on_info_ok(self, info):
        self._video_info = info
        title    = info.get("title", "Unknown title")
        duration = int(info.get("duration") or 0)
        uploader = info.get("uploader") or info.get("channel", "Unknown")
        views    = info.get("view_count")

        mins, secs = divmod(duration, 60)
        hrs, mins  = divmod(mins, 60)
        dur_str = f"{hrs}:{mins:02d}:{secs:02d}" if hrs else f"{mins}:{secs:02d}"
        view_str = f"  ·  {views:,} views" if views else ""

        self._title_lbl.config(text=title)
        self._meta_lbl.config(text=f"{uploader}  ·  {dur_str}{view_str}")
        self._set_url_status("Video confirmed and ready to download.", "green")
        self._dl_btn.config(state="normal")

    def _on_info_fail(self, msg):
        self._video_info = None
        self._title_lbl.config(text="—")
        self._meta_lbl.config(text="")
        short = msg[:120] + "…" if len(msg) > 120 else msg
        self._set_url_status(f"Could not retrieve video: {short}", "red")
        self._dl_btn.config(state="disabled")

    # ── Download ────────────────────────────────────────────────────────────

    def _start_download(self):
        folder = self._folder_var.get().strip()
        if not os.path.isdir(folder):
            messagebox.showerror("Folder not found",
                                 f"The download folder does not exist:\n{folder}")
            return

        url = self.url_var.get().strip()
        normalized_url = _normalize_youtube_url(url)
        if not normalized_url:
            messagebox.showerror(
                "Invalid URL",
                "Please enter a valid YouTube video URL and validate it first.",
            )
            self._dl_btn.config(state="disabled")
            return

        self._dl_btn.config(state="disabled")
        self._progress["value"] = 0
        self._set_status("Starting…")
        self.url_var.set(normalized_url)
        threading.Thread(target=self._download, args=(normalized_url, folder),
                         daemon=True).start()

    def _download(self, url, folder):
        quality_key = self._quality_var.get()
        fmt = QUALITY_OPTIONS[quality_key]
        is_audio = quality_key == "Audio Only (MP3)"

        postprocessors = []
        if is_audio:
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            })

        opts = {
            "format": fmt,
            "outtmpl": os.path.join(folder, "%(title)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [self._progress_hook],
            "postprocessors": postprocessors,
        }

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            self.after(0, self._on_download_done, folder)
        except Exception as exc:
            self.after(0, self._on_download_error, str(exc))

    def _progress_hook(self, d):
        if d["status"] == "downloading":
            total      = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            speed      = d.get("speed") or 0
            eta        = d.get("eta")
            pct        = (downloaded / total * 100) if total else 0
            speed_str  = f"{speed / 1_048_576:.1f} MB/s" if speed else ""
            eta_str    = f"  ETA {eta}s" if eta is not None else ""
            msg = f"Downloading… {pct:.1f}%  {speed_str}{eta_str}".strip()
            self.after(0, self._update_progress, min(pct, 99.9), msg)
        elif d["status"] == "finished":
            self.after(0, self._update_progress, 99.9, "Post-processing…")

    def _update_progress(self, pct, msg):
        self._progress["value"] = pct
        self._set_status(msg)

    def _on_download_done(self, folder):
        self._progress["value"] = 100
        self._set_status("Download complete!")
        self._dl_btn.config(state="normal")
        if messagebox.askyesno("Done", f"Download complete!\n\nOpen the folder?"):
            _open_folder(folder)

    def _on_download_error(self, msg):
        self._progress["value"] = 0
        self._set_status("Download failed.")
        self._dl_btn.config(state="normal")
        short = msg[:300] + "…" if len(msg) > 300 else msg
        messagebox.showerror("Download Error", short)


# ---------------------------------------------------------------------------
# Cross-platform folder open
# ---------------------------------------------------------------------------

def _open_folder(path):
    import subprocess
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = App()
    app.mainloop()
