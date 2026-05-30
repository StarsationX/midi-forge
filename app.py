import os
import re
import shutil
import subprocess
import sys
import threading
import urllib.request
import zipfile
import json
from pathlib import Path


def safe_name(name: str) -> str:
    # Must match song_to_midi.safe_name so the GUI finds the stems folder it writes.
    cleaned = re.sub(r'[\[\]()*?{}<>:"|!&#%$]', "_", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ._")
    return cleaned or "audio"

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, QUrl, QSize, QRectF, QObject, Signal
from PySide6.QtGui import (
    QDesktopServices, QDragEnterEvent, QDropEvent, QFont, QPalette, QColor,
    QPainter, QPen, QBrush, QFontMetrics,
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QProgressBar, QPushButton,
    QSpinBox, QDoubleSpinBox, QTextEdit, QVBoxLayout, QWidget, QButtonGroup,
    QSizePolicy, QStackedWidget,
)

APP_VERSION = "1.3.1"
FROZEN = getattr(sys, "frozen", False)

# In a frozen all-in-one build the GUI runs from PyInstaller's bundled Python,
# but the heavy pipeline (torch/model) lives in a separate env we build into
# %LOCALAPPDATA%\midi-forge. In dev / wizard / portable installs everything is
# already next to this file.
if FROZEN:
    ENV_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "midi-forge"
    SCRIPTS_DIR = ENV_DIR
    PY = ENV_DIR / "python" / "python.exe"
    PAYLOAD_DIR = Path(getattr(sys, "_MEIPASS", ".")) / "payload"
else:
    ENV_DIR = Path(__file__).resolve().parent
    SCRIPTS_DIR = ENV_DIR
    _exe = Path(sys.executable)
    PY = _exe.with_name("python.exe") if _exe.name.lower() == "pythonw.exe" else _exe
    PAYLOAD_DIR = None

ROOT = SCRIPTS_DIR
SONG_SCRIPT = SCRIPTS_DIR / "song_to_midi.py"
STEM_SCRIPT_PIANO = SCRIPTS_DIR / "transcribe.py"
STEM_SCRIPT_GENERAL = SCRIPTS_DIR / "stem_to_midi.py"
YT_SCRIPT = SCRIPTS_DIR / "yt_download.py"
DOWNLOADS_DIR = ENV_DIR / "downloads"

GITHUB_REPO = "StarsationX/midi-forge"
LATEST_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# ---- first-run install (frozen all-in-one only) -------------------------
PYVER = "3.13.5"
PYEMBED_URL = f"https://www.python.org/ftp/python/{PYVER}/python-{PYVER}-embed-amd64.zip"
GETPIP_URL = "https://bootstrap.pypa.io/get-pip.py"
MSST_ZIP_URL = "https://github.com/ZFTurbo/Music-Source-Separation-Training/archive/refs/heads/main.zip"
TORCH_INDEX = "https://download.pytorch.org/whl/cu128"
READY_MARKER = ENV_DIR / ".ready"

PAYLOAD_FILES = [
    "app.py", "song_to_midi.py", "transcribe.py", "stem_to_midi.py",
    "audio_utils.py", "analyze.py", "yt_download.py", "download_assets.py",
    "verify_install.py", "requirements.txt", "README.md", "LICENSE",
]
PAYLOAD_DIRS = ["wheelhouse"]
_NOWINDOW = 0x08000000  # CREATE_NO_WINDOW


def env_ready() -> bool:
    """True when the heavy pipeline env is physically installed."""
    return ((ENV_DIR / "python" / "python.exe").exists()
            and (ENV_DIR / "python" / "Lib" / "site-packages" / "torch").exists())


def extract_payload():
    """Copy the bundled scripts/wheels next to the env (frozen mode only)."""
    if not (FROZEN and PAYLOAD_DIR and PAYLOAD_DIR.exists()):
        return
    ENV_DIR.mkdir(parents=True, exist_ok=True)
    for name in PAYLOAD_FILES:
        s = PAYLOAD_DIR / name
        if s.exists():
            shutil.copy2(s, ENV_DIR / name)
    for d in PAYLOAD_DIRS:
        s = PAYLOAD_DIR / d
        if s.exists():
            shutil.copytree(s, ENV_DIR / d, dirs_exist_ok=True)


class Installer(QObject):
    """Builds the heavy env in a background thread, reporting to the UI."""
    log = Signal(str)
    status = Signal(str)
    finished = Signal(bool, str)   # ok, error-message

    def __init__(self):
        super().__init__()
        self.py = ENV_DIR / "python" / "python.exe"

    def _run(self, args):
        self.log.emit("$ " + " ".join(str(a) for a in args))
        proc = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", cwd=str(ENV_DIR), creationflags=_NOWINDOW,
        )
        for line in proc.stdout:
            self.log.emit(line.rstrip())
        if proc.wait() != 0:
            raise RuntimeError(f"step failed: {args[0]}")

    def _pip(self, *args):
        self._run([str(self.py), "-m", "pip", "install", "--retries", "5",
                   "--timeout", "60", "--disable-pip-version-check",
                   "--no-warn-script-location",
                   "--find-links", str(ENV_DIR / "wheelhouse"), *args])

    def _download(self, url, dest):
        self.log.emit(f"download {url}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "midi-forge"})
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            total = int(r.headers.get("Content-Length", "0")); read = 0; last = -5
            while True:
                chunk = r.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk); read += len(chunk)
                if total:
                    pct = int(read * 100 / total)
                    if pct - last >= 5:
                        self.status.emit(f"{Path(url).name}  {pct}%"); last = pct

    def _ensure_python(self):
        if self.py.exists():
            return
        self.status.emit("Downloading Python…")
        zp = ENV_DIR / "python-embed.zip"
        self._download(PYEMBED_URL, zp)
        pdir = ENV_DIR / "python"; pdir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zp) as z:
            z.extractall(pdir)
        zp.unlink()
        for pth in pdir.glob("python*._pth"):
            pth.write_text(pth.read_text().replace("#import site", "import site"))
        self.status.emit("Bootstrapping pip…")
        gp = pdir / "get-pip.py"
        self._download(GETPIP_URL, gp)
        self._run([str(self.py), str(gp), "--no-warn-script-location"])
        gp.unlink(missing_ok=True)

    def _fetch_msst(self):
        if (ENV_DIR / "msst" / "inference.py").exists():
            return
        self.status.emit("Downloading MSST…")
        zp = ENV_DIR / "msst.zip"
        self._download(MSST_ZIP_URL, zp)
        with zipfile.ZipFile(zp) as z:
            z.extractall(ENV_DIR)
        zp.unlink()
        ex = ENV_DIR / "Music-Source-Separation-Training-main"
        if ex.exists():
            if (ENV_DIR / "msst").exists():
                shutil.rmtree(ENV_DIR / "msst", ignore_errors=True)
            ex.rename(ENV_DIR / "msst")

    def run(self):
        try:
            extract_payload()
            self._ensure_python()
            self.status.emit("Installing PyTorch + CUDA (~3 GB)…")
            self._pip("--index-url", TORCH_INDEX, "torch==2.11.0", "torchaudio==2.11.0", "torchvision==0.26.0")
            self._pip("torchcodec==0.11.1")
            self.status.emit("Installing packages…")
            self._pip("-r", str(ENV_DIR / "requirements.txt"))
            self._pip("--no-deps", "basic-pitch==0.4.0")
            self._pip("onnxruntime")
            self._fetch_msst()
            self.status.emit("Downloading model + FFmpeg (~900 MB)…")
            self._run([str(self.py), str(ENV_DIR / "download_assets.py")])
            self.status.emit("Verifying…")
            self._run([str(self.py), str(ENV_DIR / "verify_install.py")])
            READY_MARKER.write_text(APP_VERSION)
            self.finished.emit(True, "")
        except Exception as e:
            self.log.emit(f"\n[ERROR] {type(e).__name__}: {e}")
            self.finished.emit(False, str(e))


# ---- updater ------------------------------------------------------------
def _ver_tuple(v: str):
    v = v.lstrip("vV")
    parts = []
    for p in v.split("."):
        num = "".join(c for c in p if c.isdigit())
        parts.append(int(num) if num else 0)
    return tuple(parts)


def check_update():
    """Return (version, exe_url) if a newer release exists, else None."""
    try:
        req = urllib.request.Request(LATEST_API, headers={
            "User-Agent": "midi-forge", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read().decode("utf-8"))
        tag = data.get("tag_name", "")
        if _ver_tuple(tag) <= _ver_tuple(APP_VERSION):
            return None
        for a in data.get("assets", []):
            if a.get("name", "").lower() == "midiforge.exe":
                return tag, a.get("browser_download_url")
        return None
    except Exception:
        return None


def apply_update(exe_url: str) -> bool:
    """Download the new exe next to the current one and swap on exit."""
    if not FROZEN:
        return False
    cur = Path(sys.executable)
    new = cur.with_name("MidiForge.new.exe")
    try:
        req = urllib.request.Request(exe_url, headers={"User-Agent": "midi-forge"})
        with urllib.request.urlopen(req, timeout=120) as r, open(new, "wb") as f:
            shutil.copyfileobj(r, f)
    except Exception:
        return False
    bat = cur.with_name("_update.bat")
    bat.write_text(
        "@echo off\r\n"
        "ping 127.0.0.1 -n 3 >nul\r\n"
        f'del "{cur.name}"\r\n'
        f'move "{new.name}" "{cur.name}" >nul\r\n'
        f'start "" "{cur.name}"\r\n'
        'del "%~f0"\r\n',
        encoding="ascii",
    )
    subprocess.Popen(["cmd", "/c", str(bat)], cwd=str(cur.parent), creationflags=_NOWINDOW)
    return True

AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac", ".wma", ".aiff"}

PRESETS = {
    "Fast": {"USE_TTA": "0", "BIGSHIFTS": "1"},
    "Balanced": {"USE_TTA": "0", "BIGSHIFTS": "1", "SEGMENT_HOP": "5"},
    "Max": {"USE_TTA": "1", "BIGSHIFTS": "3", "SEGMENT_HOP": "2"},
}
PRESET_HINT = {
    "Fast": "Quickest. Good for a fast preview.",
    "Balanced": "Recommended. Clean result, reasonable time.",
    "Max": "Best quality. TTA + fine hop, ~6× slower.",
}

# ---- palette -------------------------------------------------------------
BG        = "#0e1014"
SURFACE   = "#171a21"
SURFACE2  = "#1e222b"
BORDER    = "#2a2f3a"
TEXT      = "#e6e9ef"
MUTED     = "#8b93a3"
ACCENT    = "#7c5cff"
ACCENT_HI = "#8f72ff"
SUCCESS   = "#34d399"
DANGER    = "#f87171"


class StepIndicator(QWidget):
    """Horizontal pipeline: Input → Separate → Transcribe → Done."""

    def __init__(self, steps: list[str]):
        super().__init__()
        self.steps = steps
        self.current = -1   # -1 = idle, index = active step, len = all done
        self.setFixedHeight(64)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_current(self, i: int):
        self.current = i
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        n = len(self.steps)
        if n == 0:
            return
        w = self.width()
        r = 11
        margin = 46
        usable = w - 2 * margin
        ys = 24
        xs = [int(margin + usable * i / (n - 1)) for i in range(n)] if n > 1 else [w // 2]

        fm = QFontMetrics(self.font())
        for i in range(n - 1):
            done = i < self.current
            pen = QPen(QColor(ACCENT if done else BORDER), 3)
            p.setPen(pen)
            p.drawLine(xs[i] + r, ys, xs[i + 1] - r, ys)

        for i, label in enumerate(self.steps):
            active = i == self.current
            done = i < self.current
            if done or active:
                p.setBrush(QBrush(QColor(ACCENT)))
                p.setPen(QPen(QColor(ACCENT_HI), 2))
            else:
                p.setBrush(QBrush(QColor(SURFACE2)))
                p.setPen(QPen(QColor(BORDER), 2))
            p.drawEllipse(QRectF(xs[i] - r, ys - r, 2 * r, 2 * r))

            # check or number
            p.setPen(QPen(QColor("#ffffff" if (done or active) else MUTED)))
            f = QFont(self.font()); f.setPointSize(9); f.setBold(True)
            p.setFont(f)
            glyph = "✓" if done else str(i + 1)
            p.drawText(QRectF(xs[i] - r, ys - r, 2 * r, 2 * r), Qt.AlignCenter, glyph)

            # label
            p.setPen(QPen(QColor(TEXT if (active or done) else MUTED)))
            lf = QFont(self.font()); lf.setPointSize(9); lf.setBold(active)
            p.setFont(lf)
            tw = fm.horizontalAdvance(label)
            p.drawText(int(xs[i] - tw / 2), ys + r + 18, label)
        p.end()


class SegmentedControl(QWidget):
    """Row of mutually-exclusive pill buttons; .value() returns selected key."""

    def __init__(self, options: list[str], default: str, on_change=None):
        super().__init__()
        self.on_change = on_change
        self._value = default
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        for opt in options:
            b = QPushButton(opt)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setProperty("seg", True)
            b.setChecked(opt == default)
            b.clicked.connect(lambda _=False, o=opt: self._pick(o))
            self.group.addButton(b)
            self._buttons[opt] = b
            lay.addWidget(b)
        lay.addStretch()

    def _pick(self, opt: str):
        self._value = opt
        if self.on_change:
            self.on_change(opt)

    def value(self) -> str:
        return self._value


class DropZone(QFrame):
    def __init__(self, on_file):
        super().__init__()
        self.on_file = on_file
        self.setAcceptDrops(True)
        self.setObjectName("drop")
        self.setMinimumHeight(150)
        self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        self.icon = QLabel("♪")
        self.icon.setAlignment(Qt.AlignCenter)
        self.icon.setStyleSheet(f"font-size: 34px; color: {ACCENT};")
        self.text = QLabel("Drop an audio file here")
        self.text.setAlignment(Qt.AlignCenter)
        self.text.setStyleSheet(f"font-size: 15px; color: {TEXT}; font-weight: 600;")
        self.sub = QLabel("or click to browse  ·  mp3, wav, flac, m4a…")
        self.sub.setAlignment(Qt.AlignCenter)
        self.sub.setStyleSheet(f"font-size: 11px; color: {MUTED};")
        lay.addWidget(self.icon); lay.addWidget(self.text); lay.addWidget(self.sub)
        self._set_state("idle")

    def _set_state(self, state: str):
        colors = {
            "idle":   (BORDER, SURFACE),
            "accept": (ACCENT, "#1a1730"),
            "reject": (DANGER, "#2a1717"),
        }[state]
        self.setStyleSheet(
            f"#drop {{ border: 2px dashed {colors[0]}; border-radius: 14px;"
            f" background-color: {colors[1]}; }}"
        )

    def mousePressEvent(self, _):
        f, _ = QFileDialog.getOpenFileName(
            self, "Select an audio file", "",
            "Audio (*.mp3 *.wav *.flac *.m4a *.ogg *.aac *.wma *.aiff);;All files (*)",
        )
        if f:
            self.on_file(Path(f))

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls() and any(Path(u.toLocalFile()).suffix.lower() in AUDIO_EXTS for u in e.mimeData().urls()):
            self._set_state("accept"); e.acceptProposedAction()
        else:
            self._set_state("reject"); e.ignore()

    def dragLeaveEvent(self, _):
        self._set_state("idle")

    def dropEvent(self, e: QDropEvent):
        for u in e.mimeData().urls():
            p = Path(u.toLocalFile())
            if p.suffix.lower() in AUDIO_EXTS:
                self._set_state("idle"); self.on_file(p); return
        self._set_state("idle")


def _card(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame(); card.setObjectName("card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(18, 16, 18, 16)
    lay.setSpacing(12)
    if title:
        t = QLabel(title)
        t.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {MUTED}; letter-spacing: 1px;")
        lay.addWidget(t)
    return card, lay


class App(QMainWindow):
    STEPS = ["Input", "Separate", "Transcribe", "Done"]
    update_found = Signal(str, str)   # version, exe_url

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"midi-forge  v{APP_VERSION}")
        self.resize(900, 860)
        self.setMinimumWidth(720)
        self.audio_path: Path | None = None
        self.midi_path: Path | None = None
        self.proc: QProcess | None = None
        self.mode: str = "transcribe"
        self._downloaded: Path | None = None
        self._update_url: str | None = None
        self._apply_theme()
        self._build_ui()
        self.update_found.connect(self._on_update_found)
        threading.Thread(target=self._check_update, daemon=True).start()

    def _check_update(self):
        res = check_update()
        if res:
            self.update_found.emit(res[0], res[1])

    def _on_update_found(self, version: str, url: str):
        self._update_url = url
        self.update_btn.setText(f"⟳  Update to {version}")
        self.update_btn.setVisible(True)

    def _do_update(self):
        if not self._update_url:
            return
        self.update_btn.setEnabled(False)
        self.update_btn.setText("Downloading update…")
        def work():
            ok = apply_update(self._update_url)
            if ok:
                QApplication.quit()
        threading.Thread(target=work, daemon=True).start()

    # ---------------------------------------------------------------- theme
    def _apply_theme(self):
        app = QApplication.instance()
        pal = QPalette()
        pal.setColor(QPalette.Window, QColor(BG))
        pal.setColor(QPalette.WindowText, QColor(TEXT))
        pal.setColor(QPalette.Base, QColor(SURFACE2))
        pal.setColor(QPalette.AlternateBase, QColor(SURFACE))
        pal.setColor(QPalette.Text, QColor(TEXT))
        pal.setColor(QPalette.Button, QColor(SURFACE2))
        pal.setColor(QPalette.ButtonText, QColor(TEXT))
        pal.setColor(QPalette.Highlight, QColor(ACCENT))
        pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        pal.setColor(QPalette.PlaceholderText, QColor(MUTED))
        app.setPalette(pal)
        self.setStyleSheet(f"""
            QMainWindow {{ background: {BG}; }}
            QWidget {{ color: {TEXT}; font-family: 'Segoe UI', sans-serif; }}
            QLabel {{ background: transparent; }}

            QFrame#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px; }}

            QPushButton {{ padding: 8px 16px; border-radius: 8px; background: {SURFACE2};
                           border: 1px solid {BORDER}; color: {TEXT}; }}
            QPushButton:hover {{ background: #262b35; border-color: #39404d; }}
            QPushButton:disabled {{ color: #5a606c; background: #161922; border-color: #222732; }}

            QPushButton#primary {{ background: {ACCENT}; border: none; color: white;
                                   font-weight: 700; font-size: 14px; padding: 12px 22px; }}
            QPushButton#primary:hover {{ background: {ACCENT_HI}; }}
            QPushButton#primary:disabled {{ background: #2b2740; color: #6b6790; }}

            QPushButton#ghost {{ background: transparent; border: 1px solid {BORDER}; }}
            QPushButton#ghost:hover {{ background: {SURFACE2}; }}

            QPushButton#update {{ background: {SUCCESS}; border: none; color: #06281c;
                                  font-weight: 700; padding: 7px 14px; }}
            QPushButton#update:hover {{ background: #4ade9f; }}
            QPushButton#update:disabled {{ background: #25513f; color: #7fd6b3; }}

            QPushButton[seg="true"] {{ padding: 7px 16px; border-radius: 8px;
                background: {SURFACE2}; border: 1px solid {BORDER}; color: {MUTED}; font-weight: 600; }}
            QPushButton[seg="true"]:hover {{ color: {TEXT}; }}
            QPushButton[seg="true"]:checked {{ background: {ACCENT}; border-color: {ACCENT};
                color: white; }}

            QLineEdit {{ background: {SURFACE2}; border: 1px solid {BORDER}; border-radius: 8px;
                         padding: 9px 12px; color: {TEXT}; selection-background-color: {ACCENT}; }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}

            QComboBox {{ background: {SURFACE2}; border: 1px solid {BORDER}; border-radius: 8px;
                         padding: 7px 12px; color: {TEXT}; }}
            QComboBox:hover {{ border-color: #39404d; }}
            QComboBox QAbstractItemView {{ background: {SURFACE2}; border: 1px solid {BORDER};
                         selection-background-color: {ACCENT}; outline: none; }}

            QSpinBox, QDoubleSpinBox {{ background: {SURFACE2}; border: 1px solid {BORDER};
                         border-radius: 8px; padding: 6px 8px; color: {TEXT}; }}

            QCheckBox {{ spacing: 8px; color: {TEXT}; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px;
                         border: 1px solid {BORDER}; background: {SURFACE2}; }}
            QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT};
                         image: none; }}

            QTextEdit {{ background: #0b0d11; border: 1px solid {BORDER}; border-radius: 10px;
                         font-family: 'Cascadia Code', Consolas, monospace; font-size: 11px;
                         color: #b9c0cc; padding: 8px; }}

            QProgressBar {{ border: none; border-radius: 5px; background: {SURFACE2};
                            height: 8px; text-align: center; color: transparent; }}
            QProgressBar::chunk {{ background: {ACCENT}; border-radius: 5px; }}

            QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
            QScrollBar::handle:vertical {{ background: #2f3540; border-radius: 5px; min-height: 24px; }}
            QScrollBar::handle:vertical:hover {{ background: #3b4250; }}
            QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

            QLabel#stage {{ font-size: 13px; color: {MUTED}; }}
            QLabel#h1 {{ font-size: 22px; font-weight: 800; color: {TEXT}; }}
            QLabel#sub {{ font-size: 12px; color: {MUTED}; }}
            QLabel#hint {{ font-size: 11px; color: {MUTED}; }}
            QLabel#file {{ font-size: 12px; color: {TEXT}; }}
        """)

    # ------------------------------------------------------------------- UI
    def _build_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(26, 22, 26, 22)
        outer.setSpacing(16)

        # Header
        head = QHBoxLayout()
        logo = QLabel("⬣")
        logo.setStyleSheet(f"font-size: 30px; color: {ACCENT};")
        head.addWidget(logo)
        htext = QVBoxLayout(); htext.setSpacing(0)
        h1 = QLabel("midi-forge"); h1.setObjectName("h1")
        sub = QLabel("Song → isolated piano → MIDI   ·   BS-Rofo-SW + Transkun V2"); sub.setObjectName("sub")
        htext.addWidget(h1); htext.addWidget(sub)
        head.addLayout(htext); head.addStretch()
        self.update_btn = QPushButton("⟳  Update")
        self.update_btn.setObjectName("update")
        self.update_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn.setVisible(False)
        self.update_btn.clicked.connect(self._do_update)
        head.addWidget(self.update_btn, 0, Qt.AlignTop)
        outer.addLayout(head)

        # Stepper
        self.stepper = StepIndicator(self.STEPS)
        outer.addWidget(self.stepper)

        # Input card
        in_card, in_l = _card("INPUT")
        self.drop = DropZone(self._on_file)
        in_l.addWidget(self.drop)

        url_row = QHBoxLayout(); url_row.setSpacing(8)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Paste a YouTube link to download its audio…")
        self.url_edit.returnPressed.connect(self._download_url)
        url_row.addWidget(self.url_edit, 1)
        self.download_btn = QPushButton("Download")
        self.download_btn.setObjectName("ghost")
        self.download_btn.setCursor(Qt.PointingHandCursor)
        self.download_btn.clicked.connect(self._download_url)
        url_row.addWidget(self.download_btn)
        in_l.addLayout(url_row)

        self.file_label = QLabel("No file selected."); self.file_label.setObjectName("file")
        in_l.addWidget(self.file_label)
        outer.addWidget(in_card)

        # Options card
        opt_card, opt_l = _card("OPTIONS")
        # preset
        prow = QHBoxLayout()
        plab = QLabel("Quality"); plab.setFixedWidth(70)
        prow.addWidget(plab)
        self.preset = SegmentedControl(list(PRESETS.keys()), "Balanced", on_change=self._on_preset)
        prow.addWidget(self.preset); prow.addStretch()
        opt_l.addLayout(prow)
        self.preset_hint = QLabel(PRESET_HINT["Balanced"]); self.preset_hint.setObjectName("hint")
        self.preset_hint.setContentsMargins(78, 0, 0, 0)
        opt_l.addWidget(self.preset_hint)

        # skip + transcriber
        trow = QHBoxLayout()
        tlab = QLabel("Source"); tlab.setFixedWidth(70)
        trow.addWidget(tlab)
        self.skip_sep = QCheckBox("Already a stem (skip separation)")
        trow.addWidget(self.skip_sep)
        trow.addStretch()
        self.transcriber = QComboBox()
        self.transcriber.addItem("Piano · Transkun V2", "piano")
        self.transcriber.addItem("General · basic-pitch", "general")
        self.transcriber.setEnabled(False)
        self.transcriber.setFixedWidth(200)
        trow.addWidget(self.transcriber)
        opt_l.addLayout(trow)
        self.skip_sep.toggled.connect(lambda v: self.transcriber.setEnabled(v))

        # advanced toggle
        self.adv_btn = QPushButton("⚙  Advanced settings")
        self.adv_btn.setObjectName("ghost"); self.adv_btn.setCheckable(True)
        self.adv_btn.setCursor(Qt.PointingHandCursor)
        self.adv_btn.setStyleSheet("text-align: left;")
        opt_l.addWidget(self.adv_btn)

        self.adv = QWidget(); adv_l = QFormLayout(self.adv)
        adv_l.setContentsMargins(4, 4, 4, 0); adv_l.setSpacing(8)
        self.min_vel = QSpinBox(); self.min_vel.setRange(0, 127); self.min_vel.setValue(20)
        self.min_note = QDoubleSpinBox(); self.min_note.setRange(0.0, 1.0); self.min_note.setSingleStep(0.01); self.min_note.setDecimals(3); self.min_note.setValue(0.05)
        self.pitch_lo = QSpinBox(); self.pitch_lo.setRange(0, 127); self.pitch_lo.setValue(21)
        self.pitch_hi = QSpinBox(); self.pitch_hi.setRange(0, 127); self.pitch_hi.setValue(108)
        self.velocity_gamma = QDoubleSpinBox(); self.velocity_gamma.setRange(0.5, 1.5); self.velocity_gamma.setSingleStep(0.05); self.velocity_gamma.setDecimals(2); self.velocity_gamma.setValue(0.85)
        self.target_rms = QDoubleSpinBox(); self.target_rms.setRange(-40.0, 0.0); self.target_rms.setSingleStep(1.0); self.target_rms.setDecimals(1); self.target_rms.setValue(-20.0)
        self.loudness_norm = QCheckBox("normalize loudness before Transkun"); self.loudness_norm.setChecked(True)
        adv_l.addRow("Min velocity", self.min_vel)
        adv_l.addRow("Min note (s)", self.min_note)
        adv_l.addRow("Min pitch", self.pitch_lo)
        adv_l.addRow("Max pitch", self.pitch_hi)
        adv_l.addRow("Velocity gamma", self.velocity_gamma)
        adv_l.addRow("Target RMS (dB)", self.target_rms)
        adv_l.addRow("", self.loudness_norm)
        self.adv.setVisible(False)
        opt_l.addWidget(self.adv)
        self.adv_btn.toggled.connect(lambda v: (self.adv.setVisible(v),
            self.adv_btn.setText(("⚙  Advanced settings  ▲") if v else "⚙  Advanced settings")))
        outer.addWidget(opt_card)

        # Action row
        act = QHBoxLayout(); act.setSpacing(10)
        self.start_btn = QPushButton("Start  →"); self.start_btn.setObjectName("primary")
        self.start_btn.setEnabled(False); self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self._start)
        self.cancel_btn = QPushButton("Cancel"); self.cancel_btn.setObjectName("ghost")
        self.cancel_btn.setEnabled(False); self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._cancel)
        act.addWidget(self.start_btn); act.addWidget(self.cancel_btn); act.addStretch()
        # result buttons live on the right of the action row
        self.open_midi_btn = QPushButton("▶  Open MIDI"); self.open_midi_btn.setEnabled(False)
        self.open_midi_btn.setCursor(Qt.PointingHandCursor); self.open_midi_btn.clicked.connect(self._open_midi)
        self.open_folder_btn = QPushButton("Folder"); self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.setCursor(Qt.PointingHandCursor); self.open_folder_btn.clicked.connect(self._open_folder)
        self.open_stems_btn = QPushButton("Stems"); self.open_stems_btn.setEnabled(False)
        self.open_stems_btn.setCursor(Qt.PointingHandCursor); self.open_stems_btn.clicked.connect(self._open_stems)
        act.addWidget(self.open_stems_btn); act.addWidget(self.open_folder_btn); act.addWidget(self.open_midi_btn)
        outer.addLayout(act)

        # Progress
        self.stage = QLabel("Ready."); self.stage.setObjectName("stage")
        outer.addWidget(self.stage)
        self.bar = QProgressBar(); self.bar.setRange(0, 0); self.bar.setVisible(False)
        self.bar.setTextVisible(False)
        outer.addWidget(self.bar)

        # Log
        self.log = QTextEdit(); self.log.setReadOnly(True); self.log.setMinimumHeight(150)
        outer.addWidget(self.log, 1)

    # --------------------------------------------------------------- helpers
    def _on_preset(self, name: str):
        self.preset_hint.setText(PRESET_HINT.get(name, ""))

    def _set_step(self, i: int):
        self.stepper.set_current(i)

    def _on_file(self, p: Path):
        self.audio_path = p
        self.file_label.setText(f"✓  {p.name}")
        self.file_label.setStyleSheet(f"font-size: 12px; color: {SUCCESS};")
        self.start_btn.setEnabled(True)
        self.open_folder_btn.setEnabled(False); self.open_stems_btn.setEnabled(False); self.open_midi_btn.setEnabled(False)
        self.midi_path = None
        self._set_step(0)
        name = p.stem.lower()
        stem_hints = ("piano", "vocals", "guitar", "drums", "bass", "other", "stem")
        if any(h in name for h in stem_hints):
            self.skip_sep.setChecked(True)
            self.transcriber.setCurrentIndex(0 if "piano" in name else 1)

    def _build_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.update(PRESETS[self.preset.value()])
        env["MIN_VELOCITY"] = str(self.min_vel.value())
        env["MIN_NOTE_SEC"] = str(self.min_note.value())
        env["PIANO_MIN_PITCH"] = str(self.pitch_lo.value())
        env["PIANO_MAX_PITCH"] = str(self.pitch_hi.value())
        env["VELOCITY_GAMMA"] = str(self.velocity_gamma.value())
        env["TARGET_RMS_DB"] = str(self.target_rms.value())
        env["LOUDNESS_NORM"] = "1" if self.loudness_norm.isChecked() else "0"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONNOUSERSITE"] = "1"
        return env

    def _make_proc(self) -> QProcess:
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.MergedChannels)
        qenv = QProcessEnvironment()
        for k, v in self._build_env().items():
            qenv.insert(k, v)
        proc.setProcessEnvironment(qenv)
        proc.readyReadStandardOutput.connect(self._on_output)
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_error)
        return proc

    # --------------------------------------------------------------- actions
    def _download_url(self):
        url = self.url_edit.text().strip()
        if not url:
            return
        if self.proc and self.proc.state() != QProcess.NotRunning:
            return
        self.log.clear()
        self.mode = "download"; self._downloaded = None
        self.download_btn.setEnabled(False); self.url_edit.setEnabled(False)
        self.start_btn.setEnabled(False); self.cancel_btn.setEnabled(True)
        self.open_folder_btn.setEnabled(False); self.open_stems_btn.setEnabled(False); self.open_midi_btn.setEnabled(False)
        self.bar.setVisible(True); self.bar.setRange(0, 0)
        self.stage.setText("Downloading audio…")
        self._set_step(0)
        self.proc = self._make_proc()
        self.proc.start(str(PY), [str(YT_SCRIPT), url, str(DOWNLOADS_DIR)])

    def _start(self):
        if not self.audio_path:
            return
        self.log.clear()
        self.mode = "transcribe"
        self.start_btn.setEnabled(False); self.cancel_btn.setEnabled(True)
        self.open_folder_btn.setEnabled(False); self.open_stems_btn.setEnabled(False); self.open_midi_btn.setEnabled(False)
        self.bar.setVisible(True); self.bar.setRange(0, 0)
        self.stage.setText("Starting…")
        self._set_step(1 if not self.skip_sep.isChecked() else 2)

        if self.skip_sep.isChecked():
            script = STEM_SCRIPT_PIANO if self.transcriber.currentData() == "piano" else STEM_SCRIPT_GENERAL
        else:
            script = SONG_SCRIPT
        self.proc = self._make_proc()
        self.proc.start(str(PY), [str(script), str(self.audio_path)])

    def _on_output(self):
        if not self.proc:
            return
        data = bytes(self.proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            self.log.append(line)
            low = line.lower()
            if line.startswith("DOWNLOADED:"):
                self._downloaded = Path(line.split("DOWNLOADED:", 1)[1].strip())
            elif self.mode == "download" and "[download]" in low:
                self.stage.setText(f"Downloading… {line.split(']', 1)[-1].strip()[:60]}")
            elif "[1/3]" in line or "separating" in low:
                self.stage.setText("Separating piano stem (BS-Rofo-SW)…"); self._set_step(1)
            elif "normalizing" in low:
                self.stage.setText("Normalizing loudness…"); self._set_step(2)
            elif "[2/3]" in line or "transcribing" in low:
                self.stage.setText("Transcribing to MIDI (Transkun)…"); self._set_step(2)
            elif "[3/3]" in line or "cleaning" in low:
                self.stage.setText("Cleaning MIDI…"); self._set_step(2)
            elif line.startswith("DONE"):
                self.stage.setText("Done.")
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def _on_finished(self, code: int, _status):
        self.bar.setVisible(False)
        self.cancel_btn.setEnabled(False)

        if self.mode == "download":
            self.download_btn.setEnabled(True); self.url_edit.setEnabled(True)
            self.start_btn.setEnabled(self.audio_path is not None)
            if code != 0:
                self.stage.setText("Download failed — see log.")
                self.stage.setStyleSheet(f"font-size: 13px; color: {DANGER};")
                return
            if self._downloaded and self._downloaded.exists():
                self.url_edit.clear()
                self._on_file(self._downloaded)
                self.stage.setText(f"Downloaded — ready to transcribe.")
                self.stage.setStyleSheet(f"font-size: 13px; color: {SUCCESS};")
            else:
                self.stage.setText("Download finished but MP3 not found — see log.")
            return

        self.start_btn.setEnabled(True)
        if code != 0:
            self.stage.setText(f"Failed (exit {code}) — see log.")
            self.stage.setStyleSheet(f"font-size: 13px; color: {DANGER};")
            self._set_step(-1)
            return
        if self.audio_path:
            self.midi_path = self.audio_path.with_suffix(".mid")
            if self.midi_path.exists():
                self._set_step(len(self.STEPS))  # all done
                self.open_folder_btn.setEnabled(True)
                self.open_midi_btn.setEnabled(True)
                stems = self.audio_path.parent / "stems" / safe_name(self.audio_path.stem)
                if stems.exists():
                    self.open_stems_btn.setEnabled(True)
                self.stage.setText(f"✓  Done — {self.midi_path.name}")
                self.stage.setStyleSheet(f"font-size: 13px; color: {SUCCESS};")

    def _on_error(self, _):
        self.log.append(f"[process error] {self.proc.errorString() if self.proc else ''}")

    def _cancel(self):
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self.proc.kill()
            self.stage.setText("Cancelled.")
            self.stage.setStyleSheet(f"font-size: 13px; color: {MUTED};")
            self.bar.setVisible(False)
            self.cancel_btn.setEnabled(False)
            self.start_btn.setEnabled(self.audio_path is not None)
            self.download_btn.setEnabled(True); self.url_edit.setEnabled(True)
            self._set_step(-1)

    def _open_folder(self):
        if self.midi_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.midi_path.parent)))

    def _open_stems(self):
        if self.audio_path:
            stems = self.audio_path.parent / "stems" / safe_name(self.audio_path.stem)
            if stems.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(stems)))

    def _open_midi(self):
        if self.midi_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.midi_path)))


class SetupWindow(QMainWindow):
    """First-run setup page (frozen all-in-one only). Builds the heavy env
    in a worker thread and shows live progress, then opens the main app."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"midi-forge  v{APP_VERSION}  —  setup")
        self.resize(720, 540)
        self.app_window: App | None = None
        self.setStyleSheet(f"""
            QMainWindow {{ background: {BG}; }}
            QLabel {{ color: {TEXT}; background: transparent; }}
            QPushButton {{ padding: 8px 16px; border-radius: 8px; background: {SURFACE2};
                           border: 1px solid {BORDER}; color: {TEXT}; }}
            QPushButton:hover {{ background: #262b35; }}
            QProgressBar {{ border: none; border-radius: 5px; background: {SURFACE2}; height: 8px; }}
            QProgressBar::chunk {{ background: {ACCENT}; border-radius: 5px; }}
            QTextEdit {{ background: #0b0d11; border: 1px solid {BORDER}; border-radius: 10px;
                         font-family: 'Cascadia Code', Consolas, monospace; font-size: 11px;
                         color: #b9c0cc; padding: 8px; }}
        """)
        c = QWidget(); self.setCentralWidget(c)
        v = QVBoxLayout(c); v.setContentsMargins(26, 22, 26, 22); v.setSpacing(12)

        title = QLabel("⬣  Welcome to midi-forge")
        title.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {ACCENT};")
        v.addWidget(title)
        sub = QLabel("First-time setup. This downloads ~4 GB (Python, PyTorch + CUDA, the\n"
                     "separation model) and runs once. It opens automatically when done.")
        sub.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        v.addWidget(sub)

        self.status = QLabel("Starting…")
        self.status.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {TEXT};")
        v.addWidget(self.status)
        self.bar = QProgressBar(); self.bar.setRange(0, 0); self.bar.setTextVisible(False)
        v.addWidget(self.bar)
        self.logbox = QTextEdit(); self.logbox.setReadOnly(True)
        v.addWidget(self.logbox, 1)
        self.retry = QPushButton("Retry"); self.retry.setVisible(False)
        self.retry.clicked.connect(self._start)
        v.addWidget(self.retry, 0, Qt.AlignLeft)

        self._thread: threading.Thread | None = None
        self._start()

    def _start(self):
        self.retry.setVisible(False)
        self.bar.setRange(0, 0)
        extract_payload()
        self.installer = Installer()
        self.installer.log.connect(self._log)
        self.installer.status.connect(self.status.setText)
        self.installer.finished.connect(self._done)
        self._thread = threading.Thread(target=self.installer.run, daemon=True)
        self._thread.start()

    def _log(self, msg: str):
        self.logbox.append(msg)
        self.logbox.verticalScrollBar().setValue(self.logbox.verticalScrollBar().maximum())

    def _done(self, ok: bool, err: str):
        self.bar.setRange(0, 1); self.bar.setValue(1)
        if ok:
            self.status.setText("Done — opening midi-forge…")
            self.status.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {SUCCESS};")
            self.app_window = App(); self.app_window.show()
            self.close()
        else:
            self.status.setText("Setup failed — see log. You can retry.")
            self.status.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {DANGER};")
            self.retry.setVisible(True)


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    # Refresh bundled scripts each launch (frozen) so app fixes ship with the exe.
    extract_payload()
    if FROZEN and not env_ready():
        w = SetupWindow()
    else:
        w = App()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
