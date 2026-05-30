"""midi-forge self-installing launcher.

Frozen with PyInstaller into MidiForge.exe. On first run it builds a full,
self-contained environment in %LOCALAPPDATA%\\midi-forge (embeddable Python +
all deps + BS-Rofo model + FFmpeg) while showing a tkinter setup window, then
launches the real PySide6 GUI. Later runs skip setup and open the app directly.

No Python / git required on the target machine.
"""
import os
import queue
import shutil
import subprocess
import sys
import threading
import urllib.request
import zipfile
from pathlib import Path

import tkinter as tk
from tkinter import ttk

APP_VERSION = "1.2.1"
# Bump ENV_VERSION only when the dependency set changes enough to need a full
# reinstall. App-only fixes bump APP_VERSION and just re-extract the scripts.
ENV_VERSION = "1"
PYVER = "3.13.5"

INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "midi-forge"
READY_MARKER = INSTALL_DIR / ".ready"

PYEMBED_URL = f"https://www.python.org/ftp/python/{PYVER}/python-{PYVER}-embed-amd64.zip"
GETPIP_URL = "https://bootstrap.pypa.io/get-pip.py"
MSST_ZIP_URL = "https://github.com/ZFTurbo/Music-Source-Separation-Training/archive/refs/heads/main.zip"
TORCH_INDEX = "https://download.pytorch.org/whl/cu128"

# Files the launcher carries inside the exe and unpacks into INSTALL_DIR.
PAYLOAD_FILES = [
    "app.py", "song_to_midi.py", "transcribe.py", "stem_to_midi.py",
    "audio_utils.py", "analyze.py", "yt_download.py", "download_assets.py",
    "verify_install.py", "requirements.txt", "README.md", "LICENSE",
    "PianoExtractor.bat", "SongToMidi.bat", "SongToMidiMax.bat",
    "Transcribe.bat", "StemToMidi.bat",
]
PAYLOAD_DIRS = ["wheelhouse"]


def resource_root() -> Path:
    """Where the bundled payload lives (PyInstaller temp dir when frozen)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "payload"
    return Path(__file__).resolve().parent


class Setup:
    def __init__(self, log, set_status):
        self.log = log
        self.set_status = set_status
        self.py = INSTALL_DIR / "python" / "python.exe"

    # -- small helpers -----------------------------------------------------
    def _run(self, args, **kw):
        self.log(f"$ {' '.join(str(a) for a in args)}")
        creationflags = 0x08000000  # CREATE_NO_WINDOW
        proc = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            cwd=str(INSTALL_DIR), creationflags=creationflags, **kw,
        )
        for line in proc.stdout:
            self.log(line.rstrip())
        rc = proc.wait()
        if rc != 0:
            raise RuntimeError(f"command failed (exit {rc}): {args[0]}")

    def _pip(self, *args):
        self._run([str(self.py), "-m", "pip", "install",
                   "--retries", "5", "--timeout", "60",
                   "--disable-pip-version-check", "--no-warn-script-location",
                   "--find-links", str(INSTALL_DIR / "wheelhouse"), *args])

    def _download(self, url: str, dest: Path):
        self.log(f"download {url}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "midi-forge-launcher"})
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            total = int(r.headers.get("Content-Length", "0"))
            read = 0; last = -5
            while True:
                chunk = r.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk); read += len(chunk)
                if total:
                    pct = int(read * 100 / total)
                    if pct - last >= 5:
                        self.set_status(f"{Path(url).name}  {pct}%")
                        last = pct

    # -- steps -------------------------------------------------------------
    def unpack_payload(self):
        self.set_status("Unpacking…")
        src = resource_root()
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        for name in PAYLOAD_FILES:
            s = src / name
            if s.exists():
                shutil.copy2(s, INSTALL_DIR / name)
        for d in PAYLOAD_DIRS:
            s = src / d
            if s.exists():
                shutil.copytree(s, INSTALL_DIR / d, dirs_exist_ok=True)
        self.log("payload unpacked")

    def ensure_python(self):
        if self.py.exists():
            self.log("embedded Python present")
            return
        self.set_status("Downloading Python…")
        zip_path = INSTALL_DIR / "python-embed.zip"
        self._download(PYEMBED_URL, zip_path)
        pdir = INSTALL_DIR / "python"; pdir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(pdir)
        zip_path.unlink()
        # enable site-packages in the ._pth file
        for pth in pdir.glob("python*._pth"):
            txt = pth.read_text().replace("#import site", "import site")
            pth.write_text(txt)
        self.set_status("Bootstrapping pip…")
        getpip = pdir / "get-pip.py"
        self._download(GETPIP_URL, getpip)
        self._run([str(self.py), str(getpip), "--no-warn-script-location"])
        getpip.unlink(missing_ok=True)

    def install_torch(self):
        self.set_status("Installing PyTorch + CUDA (~3 GB)…")
        self._pip("--index-url", TORCH_INDEX,
                  "torch==2.11.0", "torchaudio==2.11.0", "torchvision==0.26.0")
        self._pip("torchcodec==0.11.1")

    def install_deps(self):
        self.set_status("Installing Python packages…")
        self._pip("-r", str(INSTALL_DIR / "requirements.txt"))
        self._pip("--no-deps", "basic-pitch==0.4.0")
        self._pip("onnxruntime")

    def fetch_msst(self):
        if (INSTALL_DIR / "msst" / "inference.py").exists():
            self.log("MSST present")
            return
        self.set_status("Downloading MSST…")
        zip_path = INSTALL_DIR / "msst.zip"
        self._download(MSST_ZIP_URL, zip_path)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(INSTALL_DIR)
        zip_path.unlink()
        extracted = INSTALL_DIR / "Music-Source-Separation-Training-main"
        if extracted.exists():
            if (INSTALL_DIR / "msst").exists():
                shutil.rmtree(INSTALL_DIR / "msst", ignore_errors=True)
            extracted.rename(INSTALL_DIR / "msst")

    def fetch_assets(self):
        self.set_status("Downloading model + FFmpeg (~900 MB)…")
        self._run([str(self.py), str(INSTALL_DIR / "download_assets.py")])

    def verify(self):
        self.set_status("Verifying…")
        self._run([str(self.py), str(INSTALL_DIR / "verify_install.py")])

    def run(self):
        self.unpack_payload()
        self.ensure_python()
        self.install_torch()
        self.install_deps()
        self.fetch_msst()
        self.fetch_assets()
        self.verify()
        READY_MARKER.write_text(ENV_VERSION)


def launch_app():
    pyw = INSTALL_DIR / "python" / "pythonw.exe"
    app = INSTALL_DIR / "app.py"
    env = dict(os.environ); env["PYTHONNOUSERSITE"] = "1"
    subprocess.Popen([str(pyw), str(app)], cwd=str(INSTALL_DIR), env=env,
                     creationflags=0x08000000)


def is_ready() -> bool:
    # Ready = the heavy environment is physically present. Checked by file
    # existence (not marker string) so an already-installed user is never
    # forced into a reinstall by an app-version bump. Scripts refresh each launch.
    pyw = INSTALL_DIR / "python" / "pythonw.exe"
    torch = INSTALL_DIR / "python" / "Lib" / "site-packages" / "torch"
    return pyw.exists() and torch.exists()


class SetupWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("midi-forge — first-time setup")
        self.root.configure(bg="#0e1014")
        self.root.geometry("680x460")
        self.q: queue.Queue = queue.Queue()
        self.done = False
        self.error: str | None = None

        head = tk.Frame(self.root, bg="#0e1014"); head.pack(fill="x", padx=22, pady=(20, 8))
        tk.Label(head, text="⬣  midi-forge", fg="#7c5cff", bg="#0e1014",
                 font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(head, text="Setting up for the first time. This downloads ~4 GB and runs once.",
                 fg="#8b93a3", bg="#0e1014", font=("Segoe UI", 10)).pack(anchor="w")

        self.status = tk.Label(self.root, text="Starting…", fg="#e6e9ef", bg="#0e1014",
                               font=("Segoe UI", 11, "bold"))
        self.status.pack(anchor="w", padx=22, pady=(6, 4))

        self.bar = ttk.Progressbar(self.root, mode="indeterminate")
        self.bar.pack(fill="x", padx=22); self.bar.start(12)

        frame = tk.Frame(self.root, bg="#0b0d11"); frame.pack(fill="both", expand=True, padx=22, pady=14)
        self.text = tk.Text(frame, bg="#0b0d11", fg="#b9c0cc", insertbackground="#b9c0cc",
                            font=("Cascadia Code", 9), relief="flat", wrap="word")
        sb = tk.Scrollbar(frame, command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); self.text.pack(side="left", fill="both", expand=True)

        self.root.after(80, self._drain)

    def log(self, msg: str):
        self.q.put(("log", msg))

    def set_status(self, msg: str):
        self.q.put(("status", msg))

    def _drain(self):
        try:
            while True:
                kind, msg = self.q.get_nowait()
                if kind == "log":
                    self.text.insert("end", msg + "\n"); self.text.see("end")
                elif kind == "status":
                    self.status.config(text=msg)
                elif kind == "done":
                    self.done = True
                elif kind == "error":
                    self.error = msg
        except queue.Empty:
            pass
        if self.done:
            self._finish_ok()
            return
        if self.error:
            self._finish_err()
            return
        self.root.after(80, self._drain)

    def _finish_ok(self):
        self.bar.stop()
        self.status.config(text="Done — launching midi-forge…", fg="#34d399")
        self.root.after(700, self.root.destroy)

    def _finish_err(self):
        self.bar.stop()
        self.status.config(text="Setup failed — see log. Close and reopen to retry.", fg="#f87171")
        btn = tk.Button(self.root, text="Close", command=self.root.destroy,
                        bg="#1e222b", fg="#e6e9ef", relief="flat", padx=16, pady=6)
        btn.pack(pady=(0, 14))

    def start(self):
        def worker():
            try:
                Setup(self.log, self.set_status).run()
                self.q.put(("done", ""))
            except Exception as e:
                self.log(f"\n[ERROR] {type(e).__name__}: {e}")
                self.q.put(("error", str(e)))
        threading.Thread(target=worker, daemon=True).start()
        self.root.mainloop()


def main() -> int:
    if is_ready():
        # Always refresh the lightweight scripts so app updates ship with the exe.
        try:
            Setup(lambda *_: None, lambda *_: None).unpack_payload()
        except Exception:
            pass
        launch_app()
        return 0
    win = SetupWindow()
    win.start()
    if is_ready():
        launch_app()
    return 0


if __name__ == "__main__":
    sys.exit(main())
