"""
Audio to MP3 Converter - GUI Tool
Requirements: Python 3.8+, ffmpeg (auto-detected or configurable)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import subprocess
import os
import re
import json
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

AUDIO_EXTS = {".m4a", ".aac", ".flac", ".wav", ".ogg", ".wma", ".opus", ".mp3"}
CONFIG_FILE = Path(__file__).parent / "mp3converter_config.json"
FFMPEG_SEARCH_PATHS = [
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"D:\ffmpeg\bin\ffmpeg.exe",
    str(Path(__file__).parent / "ffmpeg" / "bin" / "ffmpeg.exe"),
]
CHECK_ON  = "☑"
CHECK_OFF = "☐"

# ── Config ────────────────────────────────────────────────────────────────────

def load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

# ── FFmpeg ────────────────────────────────────────────────────────────────────

def find_ffmpeg():
    found = shutil.which("ffmpeg")
    if found:
        return found
    for p in FFMPEG_SEARCH_PATHS:
        if os.path.exists(p):
            return p
    return ""

def parse_duration(text: str) -> float:
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", text)
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))

def parse_time(line: str) -> float:
    m = re.search(r"time=(\d+):(\d+):(\d+\.?\d*)", line)
    if not m:
        return -1.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))

def convert_file(ffmpeg, src, dst, bitrate, progress_cb=None, cancel_event=None):
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-i", str(src), "-vn", "-ar", "44100", "-ac", "2",
           "-b:a", bitrate, "-y", str(dst)]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace")
    buf = []
    duration = 0.0
    for line in proc.stderr:
        if cancel_event and cancel_event.is_set():
            proc.kill()
            return False, "cancelled"
        buf.append(line)
        if duration == 0.0:
            duration = parse_duration("".join(buf))
        if duration > 0 and progress_cb:
            t = parse_time(line)
            if t >= 0:
                progress_cb(min(int(t / duration * 100), 99))
    proc.wait()
    if proc.returncode == 0:
        if progress_cb:
            progress_cb(100)
        return True, "ok"
    return False, "".join(buf[-5:])

# ── GUI ───────────────────────────────────────────────────────────────────────

class ConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Audio → MP3 Converter")
        self.resizable(True, True)
        self.minsize(780, 580)

        self._cancel_event = threading.Event()
        self._running      = False
        self._file_rows    = {}   # Path -> iid
        self._checked      = {}   # iid  -> bool

        cfg = load_config()
        self.var_src    = tk.StringVar(value=cfg.get("src", str(Path(__file__).parent)))
        self.var_dst    = tk.StringVar(value=cfg.get("dst", ""))
        self.var_ffmpeg = tk.StringVar(value=cfg.get("ffmpeg", find_ffmpeg()))
        self.var_br     = tk.StringVar(value=cfg.get("bitrate", "192k"))
        self.var_jobs   = tk.IntVar(value=cfg.get("jobs", 4))

        self._build_ui()
        self._scan_source()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        if not self.var_ffmpeg.get():
            self.after(300, self._ffmpeg_setup_guide)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        P = 8

        # Paths
        fp = ttk.LabelFrame(self, text="Paths", padding=P)
        fp.pack(fill="x", padx=P, pady=(P, 0))
        fp.columnconfigure(1, weight=1)
        for row, (lbl, var, cmd) in enumerate([
            ("Source dir:", self.var_src,    self._browse_src),
            ("Dest dir:",   self.var_dst,    self._browse_dst),
            ("ffmpeg:",     self.var_ffmpeg, self._browse_ffmpeg),
        ]):
            ttk.Label(fp, text=lbl, anchor="e").grid(row=row, column=0, sticky="e", padx=(0,4), pady=2)
            ttk.Entry(fp, textvariable=var).grid(row=row, column=1, sticky="ew", pady=2)
            ttk.Button(fp, text="Browse…", width=8, command=cmd).grid(row=row, column=2, padx=(4,0), pady=2)
        self.var_src.trace_add("write", lambda *_: self.after(600, self._scan_source))

        # Settings
        fs = ttk.LabelFrame(self, text="Settings", padding=P)
        fs.pack(fill="x", padx=P, pady=(6, 0))
        ttk.Label(fs, text="Bitrate:").grid(row=0, column=0, sticky="e", padx=(0,4))
        ttk.Combobox(fs, textvariable=self.var_br, width=8,
                     values=["96k","128k","160k","192k","256k","320k"],
                     state="readonly").grid(row=0, column=1, sticky="w")
        ttk.Label(fs, text="  Parallel jobs:").grid(row=0, column=2, sticky="e", padx=(16,4))
        ttk.Spinbox(fs, textvariable=self.var_jobs, from_=1, to=16, width=5).grid(row=0, column=3, sticky="w")
        ttk.Label(fs, text="  (more = faster, more CPU)").grid(row=0, column=4, sticky="w", padx=(8,0))

        # File list
        fl = ttk.LabelFrame(self, text="Files  (click row to toggle)", padding=P)
        fl.pack(fill="both", expand=True, padx=P, pady=(6, 0))
        fl.rowconfigure(0, weight=1)
        fl.columnconfigure(0, weight=1)

        cols = ("check", "file", "size", "status", "progress")
        self.tree = ttk.Treeview(fl, columns=cols, show="headings", selectmode="none")
        self.tree.heading("check",    text="✓")
        self.tree.heading("file",     text="Filename")
        self.tree.heading("size",     text="Size")
        self.tree.heading("status",   text="Status")
        self.tree.heading("progress", text="Progress")
        self.tree.column("check",    width=32,  anchor="center", stretch=False)
        self.tree.column("file",     width=370, stretch=True)
        self.tree.column("size",     width=70,  anchor="e",      stretch=False)
        self.tree.column("status",   width=90,  anchor="center", stretch=False)
        self.tree.column("progress", width=80,  anchor="center", stretch=False)

        vsb = ttk.Scrollbar(fl, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        self.tree.tag_configure("checked",   background="#e8f4e8")
        self.tree.tag_configure("done",      foreground="#2a9d2a")
        self.tree.tag_configure("failed",    foreground="#cc2222")
        self.tree.tag_configure("running",   foreground="#1a6bb5")

        self.tree.bind("<ButtonRelease-1>", self._on_row_click)

        # Overall progress
        fp2 = ttk.Frame(self)
        fp2.pack(fill="x", padx=P, pady=(4, 0))
        self.lbl_overall = ttk.Label(fp2, text="Ready")
        self.lbl_overall.pack(side="left")
        self.prog_overall = ttk.Progressbar(fp2, length=220, mode="determinate")
        self.prog_overall.pack(side="right")

        # Buttons
        fb = ttk.Frame(self)
        fb.pack(fill="x", padx=P, pady=P)
        self.btn_start  = ttk.Button(fb, text="▶  Start",     width=12, command=self._start)
        self.btn_cancel = ttk.Button(fb, text="■  Stop",      width=10, command=self._cancel, state="disabled")
        btn_all         = ttk.Button(fb, text="☑ All",        width=8,  command=self._check_all)
        btn_none        = ttk.Button(fb, text="☐ None",       width=8,  command=self._check_none)
        btn_rescan      = ttk.Button(fb, text="⟳ Rescan",     width=9,  command=self._scan_source)
        btn_save        = ttk.Button(fb, text="⚙ Save cfg",   width=10, command=self._save_cfg)
        self.lbl_sel    = ttk.Label(fb, text="")

        self.btn_start.pack(side="left")
        self.btn_cancel.pack(side="left", padx=(6, 0))
        btn_all.pack(side="left", padx=(12, 0))
        btn_none.pack(side="left", padx=(4, 0))
        btn_rescan.pack(side="left", padx=(12, 0))
        self.lbl_sel.pack(side="left", padx=(10, 0))
        btn_save.pack(side="right")

        # Log
        flog = ttk.LabelFrame(self, text="Log", padding=4)
        flog.pack(fill="x", padx=P, pady=(0, P))
        self.log_text = tk.Text(flog, height=5, state="disabled", wrap="word",
                                font=("Consolas", 9))
        self.log_text.pack(fill="x")

    # ── Browsing ──────────────────────────────────────────────────────────────

    def _browse_src(self):
        d = filedialog.askdirectory(initialdir=self.var_src.get() or ".")
        if d:
            self.var_src.set(d)
            self._scan_source()

    def _browse_dst(self):
        d = filedialog.askdirectory(initialdir=self.var_dst.get() or self.var_src.get() or ".")
        if d:
            self.var_dst.set(d)

    def _browse_ffmpeg(self):
        cur = self.var_ffmpeg.get()
        f = filedialog.askopenfilename(
            title="Select ffmpeg.exe",
            filetypes=[("ffmpeg", "ffmpeg.exe"), ("All", "*.*")],
            initialdir=str(Path(cur).parent) if cur else "C:\\",
        )
        if f:
            self.var_ffmpeg.set(f)

    # ── File scanning ─────────────────────────────────────────────────────────

    def _scan_source(self):
        src = Path(self.var_src.get())
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._file_rows.clear()
        self._checked.clear()

        if not src.is_dir():
            return

        files = sorted(f for f in src.iterdir() if f.suffix.lower() in AUDIO_EXTS)
        for f in files:
            size_mb = f"{f.stat().st_size / 1_048_576:.1f} MB"
            iid = self.tree.insert("", "end",
                                   values=(CHECK_OFF, f.name, size_mb, "Pending", "—"))
            self._file_rows[f] = iid
            self._checked[iid] = False

        self._update_sel_label()
        self._log(f"Found {len(files)} audio files in {src}")

    # ── Checkbox logic ────────────────────────────────────────────────────────

    def _on_row_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid or iid not in self._checked:
            return
        self._toggle(iid)

    def _toggle(self, iid):
        new_state = not self._checked[iid]
        self._checked[iid] = new_state
        vals = list(self.tree.item(iid)["values"])
        vals[0] = CHECK_ON if new_state else CHECK_OFF
        tags = self.tree.item(iid)["tags"]
        # preserve existing status tags, add/remove "checked" background
        status_tags = [t for t in tags if t != "checked"]
        if new_state:
            status_tags = ["checked"] + status_tags
        self.tree.item(iid, values=vals, tags=status_tags)
        self._update_sel_label()

    def _check_all(self):
        for iid in self._checked:
            if not self._checked[iid]:
                self._toggle(iid)

    def _check_none(self):
        for iid in list(self._checked):
            if self._checked[iid]:
                self._toggle(iid)

    def _update_sel_label(self):
        n_checked = sum(1 for v in self._checked.values() if v)
        n_total   = len(self._checked)
        if n_checked == 0:
            self.lbl_sel.config(text=f"{n_total} files · none checked → converts all")
        else:
            self.lbl_sel.config(text=f"{n_checked} / {n_total} checked")

    # ── Conversion ────────────────────────────────────────────────────────────

    def _start(self):
        ffmpeg = self.var_ffmpeg.get().strip()
        if not ffmpeg or not os.path.exists(ffmpeg):
            messagebox.showerror("ffmpeg not found",
                                 f"Cannot find ffmpeg at:\n{ffmpeg}")
            return

        dst_str = self.var_dst.get().strip()
        if not dst_str:
            messagebox.showerror("No destination", "Please set a destination directory.")
            return
        dst = Path(dst_str)

        checked_iids = {iid for iid, v in self._checked.items() if v}
        if checked_iids:
            files = [f for f, iid in self._file_rows.items() if iid in checked_iids]
        else:
            files = list(self._file_rows.keys())

        if not files:
            messagebox.showinfo("No files", "No audio files found.")
            return

        self._cancel_event.clear()
        self._running = True
        self.btn_start.config(state="disabled")
        self.btn_cancel.config(state="normal")
        self.prog_overall["value"]   = 0
        self.prog_overall["maximum"] = len(files)

        # Reset status column for targeted files only
        for f in files:
            iid  = self._file_rows[f]
            vals = list(self.tree.item(iid)["values"])
            vals[3] = "Pending"
            vals[4] = "—"
            tags = [t for t in self.tree.item(iid)["tags"] if t == "checked"]
            self.tree.item(iid, values=vals, tags=tags)

        threading.Thread(
            target=self._run_batch,
            args=(ffmpeg, files, dst, self.var_br.get(), self.var_jobs.get()),
            daemon=True,
        ).start()

    def _run_batch(self, ffmpeg, files, dst, bitrate, jobs):
        done_count = 0

        def do_one(src_path: Path):
            iid  = self._file_rows[src_path]
            out  = dst / (src_path.stem + ".mp3")
            self._set_status(iid, "Converting", "—", "running")

            if src_path.suffix.lower() == ".mp3":
                try:
                    dst.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_path, out)
                    self._set_status(iid, "Copied", "100%", "done")
                    return True
                except Exception as e:
                    self._set_status(iid, "Failed", "—", "failed")
                    self._log(f"FAIL {src_path.name}: {e}")
                    return False

            ok, msg = convert_file(
                ffmpeg, src_path, out, bitrate,
                progress_cb=lambda pct: self._set_progress(iid, pct),
                cancel_event=self._cancel_event,
            )
            if ok:
                self._set_status(iid, "Done", "100%", "done")
                self._log(f"OK   {src_path.name}")
            elif msg == "cancelled":
                self._set_status(iid, "Cancelled", "—", "")
            else:
                self._set_status(iid, "Failed", "—", "failed")
                self._log(f"FAIL {src_path.name}")
            return ok

        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = {pool.submit(do_one, f): f for f in files}
            for _ in as_completed(futures):
                if self._cancel_event.is_set():
                    break
                done_count += 1
                self.after(0, lambda n=done_count: self._tick_overall(n, len(files)))

        self.after(0, self._on_batch_done)

    def _tick_overall(self, done, total):
        self.prog_overall["value"] = done
        self.lbl_overall.config(text=f"{done} / {total} files")

    def _on_batch_done(self):
        self._running = False
        self.btn_start.config(state="normal")
        self.btn_cancel.config(state="disabled")
        msg = "Stopped" if self._cancel_event.is_set() else "All done!"
        self.lbl_overall.config(text=msg)
        self._log(f"=== {msg} ===")

    def _cancel(self):
        self._cancel_event.set()
        self.btn_cancel.config(state="disabled")
        self._log("Stopping…")

    # ── Row helpers ───────────────────────────────────────────────────────────

    def _set_status(self, iid, status, progress, tag):
        def _do():
            vals = list(self.tree.item(iid)["values"])
            vals[3] = status
            vals[4] = progress
            base_tags = ["checked"] if self._checked.get(iid) else []
            if tag:
                base_tags.append(tag)
            self.tree.item(iid, values=vals, tags=base_tags)
        self.after(0, _do)

    def _set_progress(self, iid, pct):
        def _do():
            vals = list(self.tree.item(iid)["values"])
            vals[4] = f"{pct}%"
            self.tree.item(iid, values=vals)
        self.after(0, _do)

    def _log(self, msg: str):
        def _do():
            self.log_text.config(state="normal")
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        self.after(0, _do)

    # ── Config / close ────────────────────────────────────────────────────────

    def _ffmpeg_setup_guide(self):
        msg = (
            "未检测到 ffmpeg，转换功能无法使用。\n\n"
            "请选择安装方式：\n\n"
            "  • 是  → 打开 ffmpeg 官网下载页\n"
            "  • 否  → 手动指定已有的 ffmpeg.exe 路径\n\n"
            "安装后在顶部 ffmpeg 栏填入路径，或点 Browse 选择。\n"
            "也可将 ffmpeg 解压到程序同目录的 ffmpeg/bin/ 下，下次自动识别。"
        )
        go_web = messagebox.askyesno("ffmpeg 未找到", msg, icon="warning")
        if go_web:
            import webbrowser
            webbrowser.open("https://ffmpeg.org/download.html#build-windows")
        else:
            self._browse_ffmpeg()

    def _save_cfg(self):
        save_config({
            "src":     self.var_src.get(),
            "dst":     self.var_dst.get(),
            "ffmpeg":  self.var_ffmpeg.get(),
            "bitrate": self.var_br.get(),
            "jobs":    self.var_jobs.get(),
        })
        self._log("Settings saved.")

    def _on_close(self):
        if self._running:
            if not messagebox.askyesno("Quit", "Conversion is running. Stop and quit?"):
                return
            self._cancel_event.set()
        self.destroy()


if __name__ == "__main__":
    app = ConverterApp()
    app.mainloop()
