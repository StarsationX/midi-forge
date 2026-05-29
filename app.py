import os
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent, QFont, QPalette, QColor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QMainWindow, QProgressBar, QPushButton,
    QSpinBox, QDoubleSpinBox, QTextEdit, QVBoxLayout, QWidget,
)

ROOT = Path(__file__).resolve().parent
# sys.executable here is pythonw.exe; flip to python.exe so subprocess stdout is captured.
_exe = Path(sys.executable)
PY = _exe.with_name("python.exe") if _exe.name.lower() == "pythonw.exe" else _exe
SONG_SCRIPT = ROOT / "song_to_midi.py"
STEM_SCRIPT_PIANO = ROOT / "transcribe.py"
STEM_SCRIPT_GENERAL = ROOT / "stem_to_midi.py"

AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac", ".wma", ".aiff"}

PRESETS = {
    "Fast": {"USE_TTA": "0", "BIGSHIFTS": "1"},
    "Balanced": {"USE_TTA": "0", "BIGSHIFTS": "1", "SEGMENT_HOP": "5"},
    "Max": {"USE_TTA": "1", "BIGSHIFTS": "3", "SEGMENT_HOP": "2"},
}


class DropZone(QLabel):
    def __init__(self, on_file):
        super().__init__()
        self.on_file = on_file
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(140)
        self.setText("Drop a song here\n(or click to choose)")
        self.setFont(QFont("Segoe UI", 12))
        self._update_style(idle=True)

    def _update_style(self, idle: bool, accept: bool | None = None):
        if accept is True:
            border, bg = "#7cd1ff", "#1a2a3a"
        elif accept is False:
            border, bg = "#ff6b6b", "#3a1a1a"
        else:
            border, bg = "#454854", "#252830"
        self.setStyleSheet(
            f"border: 2px dashed {border}; border-radius: 12px;"
            f"background-color: {bg}; color: #d6d8de; padding: 18px;"
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
            self._update_style(idle=False, accept=True)
            e.acceptProposedAction()
        else:
            self._update_style(idle=False, accept=False)
            e.ignore()

    def dragLeaveEvent(self, _):
        self._update_style(idle=True)

    def dropEvent(self, e: QDropEvent):
        for u in e.mimeData().urls():
            p = Path(u.toLocalFile())
            if p.suffix.lower() in AUDIO_EXTS:
                self._update_style(idle=True)
                self.on_file(p)
                return
        self._update_style(idle=True)


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Piano Extractor")
        self.resize(820, 720)
        self.audio_path: Path | None = None
        self.midi_path: Path | None = None
        self.proc: QProcess | None = None
        self._build_ui()
        self._apply_dark_theme()

    def _apply_dark_theme(self):
        app = QApplication.instance()
        pal = QPalette()
        pal.setColor(QPalette.Window, QColor(30, 32, 38))
        pal.setColor(QPalette.WindowText, QColor(220, 222, 228))
        pal.setColor(QPalette.Base, QColor(40, 42, 50))
        pal.setColor(QPalette.AlternateBase, QColor(50, 52, 60))
        pal.setColor(QPalette.Text, QColor(220, 222, 228))
        pal.setColor(QPalette.Button, QColor(50, 52, 60))
        pal.setColor(QPalette.ButtonText, QColor(220, 222, 228))
        pal.setColor(QPalette.Highlight, QColor(70, 140, 220))
        pal.setColor(QPalette.HighlightedText, Qt.white)
        app.setPalette(pal)
        self.setStyleSheet("""
            QPushButton { padding: 8px 14px; border-radius: 6px; background: #3a3d48; }
            QPushButton:hover { background: #494d5a; }
            QPushButton:disabled { color: #777; background: #2c2e36; }
            QPushButton#primary { background: #2c7be0; color: white; font-weight: 600; }
            QPushButton#primary:hover { background: #3b8df2; }
            QPushButton#primary:disabled { background: #2c2e36; color: #777; }
            QComboBox, QSpinBox, QDoubleSpinBox { padding: 4px 8px; }
            QTextEdit { background: #1a1c22; border: 1px solid #2c2e36; border-radius: 6px;
                        font-family: Consolas, monospace; font-size: 11px; color: #c5c8d0; }
            QProgressBar { border: 1px solid #3a3d48; border-radius: 4px; background: #1a1c22;
                           text-align: center; color: #c5c8d0; }
            QProgressBar::chunk { background: #2c7be0; border-radius: 3px; }
            QLabel#stage { font-size: 13px; color: #9aa0ac; }
            QFrame#card { background: #282a32; border-radius: 10px; }
        """)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        title = QLabel("Piano Extractor")
        title.setFont(QFont("Segoe UI", 18, QFont.DemiBold))
        root.addWidget(title)
        subtitle = QLabel("Song → isolated piano stem → MIDI. Powered by BS-Rofo-SW + Transkun V2.")
        subtitle.setStyleSheet("color: #888c99;")
        root.addWidget(subtitle)

        self.drop = DropZone(self._on_file)
        root.addWidget(self.drop)
        self.file_label = QLabel("No file selected.")
        self.file_label.setStyleSheet("color: #aab0bc;")
        root.addWidget(self.file_label)

        # Settings card
        card = QFrame(); card.setObjectName("card")
        card_l = QVBoxLayout(card); card_l.setContentsMargins(16, 12, 16, 12)
        row = QHBoxLayout()
        row.addWidget(QLabel("Quality preset:"))
        self.preset = QComboBox(); self.preset.addItems(list(PRESETS.keys()))
        self.preset.setCurrentText("Balanced")
        row.addWidget(self.preset)
        row.addStretch()
        self.skip_sep = QCheckBox("Skip separation (input is already a stem)")
        row.addWidget(self.skip_sep)
        card_l.addLayout(row)

        trans_row = QHBoxLayout()
        trans_row.addWidget(QLabel("Transcriber:"))
        self.transcriber = QComboBox()
        self.transcriber.addItem("Piano  (Transkun V2 - SOTA, piano-only)", "piano")
        self.transcriber.addItem("General  (basic-pitch - vocals/guitar/synth/etc)", "general")
        trans_row.addWidget(self.transcriber)
        trans_row.addStretch()
        card_l.addLayout(trans_row)
        self.skip_sep.toggled.connect(lambda v: self.transcriber.setEnabled(v))
        self.transcriber.setEnabled(False)

        adv_btn = QPushButton("Advanced ▾"); adv_btn.setCheckable(True)
        adv_btn.setStyleSheet("text-align: left; background: transparent;")
        card_l.addWidget(adv_btn)
        self.adv = QWidget(); adv_l = QFormLayout(self.adv); adv_l.setContentsMargins(0, 4, 0, 0)
        self.min_vel = QSpinBox(); self.min_vel.setRange(0, 127); self.min_vel.setValue(20)
        self.min_note = QDoubleSpinBox(); self.min_note.setRange(0.0, 1.0); self.min_note.setSingleStep(0.01); self.min_note.setDecimals(3); self.min_note.setValue(0.05)
        self.pitch_lo = QSpinBox(); self.pitch_lo.setRange(0, 127); self.pitch_lo.setValue(21)
        self.pitch_hi = QSpinBox(); self.pitch_hi.setRange(0, 127); self.pitch_hi.setValue(108)
        self.velocity_gamma = QDoubleSpinBox(); self.velocity_gamma.setRange(0.5, 1.5); self.velocity_gamma.setSingleStep(0.05); self.velocity_gamma.setDecimals(2); self.velocity_gamma.setValue(0.85)
        self.target_rms = QDoubleSpinBox(); self.target_rms.setRange(-40.0, 0.0); self.target_rms.setSingleStep(1.0); self.target_rms.setDecimals(1); self.target_rms.setValue(-20.0)
        self.loudness_norm = QCheckBox("normalize loudness before Transkun"); self.loudness_norm.setChecked(True)
        adv_l.addRow("MIN_VELOCITY (drop quieter notes)", self.min_vel)
        adv_l.addRow("MIN_NOTE_SEC (drop shorter notes)", self.min_note)
        adv_l.addRow("PIANO_MIN_PITCH (lowest kept pitch)", self.pitch_lo)
        adv_l.addRow("PIANO_MAX_PITCH (highest kept pitch)", self.pitch_hi)
        adv_l.addRow("VELOCITY_GAMMA (<1 expands dynamics)", self.velocity_gamma)
        adv_l.addRow("TARGET_RMS_DB (normalize target)", self.target_rms)
        adv_l.addRow("LOUDNESS_NORM", self.loudness_norm)
        self.adv.setVisible(False)
        card_l.addWidget(self.adv)
        adv_btn.toggled.connect(lambda v: (self.adv.setVisible(v), adv_btn.setText("Advanced ▴" if v else "Advanced ▾")))
        root.addWidget(card)

        # Run controls
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Start"); self.start_btn.setObjectName("primary")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._start)
        self.cancel_btn = QPushButton("Cancel"); self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel)
        btn_row.addWidget(self.start_btn); btn_row.addWidget(self.cancel_btn); btn_row.addStretch()
        root.addLayout(btn_row)

        # Progress
        self.stage = QLabel("Idle."); self.stage.setObjectName("stage")
        root.addWidget(self.stage)
        self.bar = QProgressBar(); self.bar.setRange(0, 0); self.bar.setVisible(False)
        root.addWidget(self.bar)

        # Log
        root.addWidget(QLabel("Log"))
        self.log = QTextEdit(); self.log.setReadOnly(True)
        root.addWidget(self.log, 1)

        # Result row
        self.result_row = QHBoxLayout()
        self.open_folder_btn = QPushButton("Open folder"); self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.clicked.connect(self._open_folder)
        self.open_stems_btn = QPushButton("Open stems folder"); self.open_stems_btn.setEnabled(False)
        self.open_stems_btn.clicked.connect(self._open_stems)
        self.open_midi_btn = QPushButton("Open MIDI"); self.open_midi_btn.setEnabled(False)
        self.open_midi_btn.clicked.connect(self._open_midi)
        self.result_row.addWidget(self.open_folder_btn); self.result_row.addWidget(self.open_stems_btn); self.result_row.addWidget(self.open_midi_btn); self.result_row.addStretch()
        root.addLayout(self.result_row)

    def _on_file(self, p: Path):
        self.audio_path = p
        self.file_label.setText(f"Selected:  {p.name}    ({p.parent})")
        self.start_btn.setEnabled(True)
        self.open_folder_btn.setEnabled(False); self.open_stems_btn.setEnabled(False); self.open_midi_btn.setEnabled(False)
        self.midi_path = None
        name = p.stem.lower()
        stem_hints = ("piano", "vocals", "guitar", "drums", "bass", "other", "stem")
        if any(h in name for h in stem_hints):
            self.skip_sep.setChecked(True)
            self.transcriber.setCurrentIndex(0 if "piano" in name else 1)

    def _build_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.update(PRESETS[self.preset.currentText()])
        env["MIN_VELOCITY"] = str(self.min_vel.value())
        env["MIN_NOTE_SEC"] = str(self.min_note.value())
        env["PIANO_MIN_PITCH"] = str(self.pitch_lo.value())
        env["PIANO_MAX_PITCH"] = str(self.pitch_hi.value())
        env["VELOCITY_GAMMA"] = str(self.velocity_gamma.value())
        env["TARGET_RMS_DB"] = str(self.target_rms.value())
        env["LOUDNESS_NORM"] = "1" if self.loudness_norm.isChecked() else "0"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        # Stop the subprocess from inheriting a user-site basic_pitch (or
        # anything else) that may have been globally pip-installed and is
        # masking the venv's working copy.
        env["PYTHONNOUSERSITE"] = "1"
        return env

    def _start(self):
        if not self.audio_path:
            return
        self.log.clear()
        self.start_btn.setEnabled(False); self.cancel_btn.setEnabled(True)
        self.open_folder_btn.setEnabled(False); self.open_stems_btn.setEnabled(False); self.open_midi_btn.setEnabled(False)
        self.bar.setVisible(True); self.bar.setRange(0, 0)
        self.stage.setText("Starting…")

        if self.skip_sep.isChecked():
            script = STEM_SCRIPT_PIANO if self.transcriber.currentData() == "piano" else STEM_SCRIPT_GENERAL
        else:
            script = SONG_SCRIPT
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        qenv = QProcessEnvironment()
        for k, v in self._build_env().items():
            qenv.insert(k, v)
        self.proc.setProcessEnvironment(qenv)
        self.proc.readyReadStandardOutput.connect(self._on_output)
        self.proc.finished.connect(self._on_finished)
        self.proc.errorOccurred.connect(self._on_error)
        self.proc.start(str(PY), [str(script), str(self.audio_path)])

    def _on_output(self):
        if not self.proc:
            return
        data = bytes(self.proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            self.log.append(line)
            low = line.lower()
            if "[1/3]" in line or "separating" in low:
                self.stage.setText("Separating piano stem (BS-Rofo-SW)…")
            elif "normalizing" in low:
                self.stage.setText("Normalizing loudness…")
            elif "[2/3]" in line or "transcribing" in low:
                self.stage.setText("Transcribing to MIDI (Transkun)…")
            elif "[3/3]" in line or "cleaning" in low:
                self.stage.setText("Cleaning MIDI…")
            elif line.startswith("DONE"):
                self.stage.setText("Done.")

    def _on_finished(self, code: int, _status):
        self.bar.setVisible(False)
        self.cancel_btn.setEnabled(False); self.start_btn.setEnabled(True)
        if code != 0:
            self.stage.setText(f"Failed (exit {code}).")
            return
        # The new MIDI is at <input>.mid (same dir, .mid suffix)
        if self.audio_path:
            self.midi_path = self.audio_path.with_suffix(".mid")
            if self.midi_path.exists():
                self.open_folder_btn.setEnabled(True)
                self.open_midi_btn.setEnabled(True)
                # Stems folder only exists when separation ran (song_to_midi.py path)
                stems = self.audio_path.parent / "stems" / self.audio_path.stem
                if stems.exists():
                    self.open_stems_btn.setEnabled(True)
                self.stage.setText(f"Done: {self.midi_path.name}")

    def _on_error(self, _):
        self.log.append(f"[process error] {self.proc.errorString() if self.proc else ''}")

    def _cancel(self):
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self.proc.kill()
            self.stage.setText("Cancelled.")
            self.bar.setVisible(False)
            self.cancel_btn.setEnabled(False); self.start_btn.setEnabled(True)

    def _open_folder(self):
        if self.midi_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.midi_path.parent)))

    def _open_stems(self):
        if self.audio_path:
            stems = self.audio_path.parent / "stems" / self.audio_path.stem
            if stems.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(stems)))

    def _open_midi(self):
        if self.midi_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.midi_path)))


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = App()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
