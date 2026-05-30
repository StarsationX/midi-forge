# midi-forge

Drop a song in, get a MIDI out. Piano-focused, but works on other lead instruments too.

The pipeline isolates the piano from a full mix with **BS-Rofo-SW-Fixed** (SOTA 6-stem separator), then transcribes the stem to MIDI with **Transkun V2** (SOTA piano transcription, F1 92.64 on MAESTRO V3). For non-piano stems (vocals, guitar, synth lead) it falls back to **basic-pitch** (Spotify's general-purpose transcriber).

![GUI dropzone](docs/screenshot.png) <!-- optional, remove if no screenshot -->

## What you need

- **Windows 10/11**
- **Python 3.10, 3.11, 3.12, or 3.13** &mdash; install from [python.org](https://www.python.org/downloads/), tick "Add Python to PATH". 3.12 is the safest pick.
- **Git** &mdash; install from [git-scm.com](https://git-scm.com/)
- **NVIDIA GPU** &mdash; any RTX 20/30/40/50-series with up-to-date drivers (CPU works but is ~30x slower)
- ~10 GB free disk (mostly PyTorch + CUDA runtime)

## Install

**Option 1 &mdash; `MidiForge.exe` launcher** (easiest &mdash; no Python, no git needed) ⭐
Download `MidiForge.exe` (~12 MB) from [Releases](https://github.com/StarsationX/midi-forge/releases) and run it. On first launch it shows a setup window and builds everything it needs (Python, PyTorch + CUDA, the BS-Rofo model, FFmpeg) into `%LOCALAPPDATA%\midi-forge` &mdash; ~4 GB download, runs once. When it finishes it opens the app, and every launch after that goes straight in. Nothing to install beforehand.

**Option 2 &mdash; Setup wizard**
Grab `midi-forge-setup-X.Y.Z.exe` from [Releases](https://github.com/StarsationX/midi-forge/releases). Double-click, follow the wizard, and on the final page tick "Run midi-forge installer". Needs Python 3.10&ndash;3.13 installed. Files go to `%LOCALAPPDATA%\midi-forge`, no admin needed.

**Option 3 &mdash; Portable bundle** (offline, nothing fetched at runtime)
Grab `midi-forge-portable-X.Y.Z.7z.001`, `.002`, ... from [Releases](https://github.com/StarsationX/midi-forge/releases). Select all parts, right-click &rarr; 7-Zip &rarr; Extract. Self-contained folder &mdash; just run `PianoExtractor.bat`. Bigger download (~3 GB), no internet needed at runtime.

**Option 4 &mdash; From source** (for developers / customizing the pipeline)
```cmd
git clone https://github.com/StarsationX/midi-forge.git
cd midi-forge
install.bat
```
The installer creates a local `venv/`, installs PyTorch 2.11 + CUDA 12.8, downloads the BS-Rofo model from HuggingFace, clones MSST, and pulls FFmpeg shared DLLs. First run is ~10 minutes.

## Use

| Way to launch | What it does |
|---|---|
| **`PianoExtractor.bat`** | Drag-drop GUI &mdash; pick a song, hit Start |
| Drag a song onto **`SongToMidi.bat`** | Default-quality piano MIDI |
| Drag a song onto **`SongToMidiMax.bat`** | TTA + bigshifts=3 + fine segment hop. ~6&times; slower, cleaner |
| Drag a piano stem onto **`Transcribe.bat`** | Skip separation, go straight to Transkun |
| Drag any stem onto **`StemToMidi.bat`** | General-purpose transcription via basic-pitch (vocals, guitar, etc.) |

### From a YouTube link

In the GUI, paste a YouTube (or other site) URL into the **"…or paste a link"** box and hit **Download**. The audio is saved as an MP3 in the `downloads/` folder and auto-loaded as the input &mdash; then just hit **Start** to transcribe it. Powered by [yt-dlp](https://github.com/yt-dlp/yt-dlp) + the bundled FFmpeg.

> Some videos (age-restricted, or certain newer uploads) need a JavaScript runtime for YouTube extraction. If a download fails with a JS/format hint, install [Deno](https://deno.com) and reopen midi-forge.

Output goes next to the input file:
```
mysong.mp3        <- input
mysong.mid        <- transcribed MIDI
stems/mysong/     <- intermediate piano.wav + other separated stems
```

## Tuning

All knobs are environment variables (set them in a `.bat` or shell before running). The GUI exposes the most common ones in the Advanced panel.

| Variable | Default | What it does |
|---|---|---|
| `USE_TTA` | `0` | Test-time augmentation during separation. Cleaner, 2&times; slower |
| `BIGSHIFTS` | `1` | Number of phase shifts in separation. Higher = cleaner, slower |
| `SEGMENT_HOP` | (off) | Transkun overlap in seconds. Smaller = catches fast passages, slower |
| `SEGMENT_SIZE` | `16` | Transkun window size when `SEGMENT_HOP` is set. Leave at 16 |
| `LOUDNESS_NORM` | `1` | Normalize the piano stem to MAESTRO levels before transcription |
| `TARGET_RMS_DB` | `-20.0` | Target RMS for loudness normalization |
| `PEAK_CEILING_DB` | `-1.0` | Peak ceiling so normalization doesn't clip |
| `VELOCITY_GAMMA` | `0.85` | Power-curve velocity expansion. <1 expands dynamics, 1 disables |
| `MIN_NOTE_SEC` | `0.05` | Drop notes shorter than this in cleanup |
| `MIN_VELOCITY` | `20` | Drop notes quieter than this in cleanup |
| `PIANO_MIN_PITCH` | `21` (A0) | Drop notes below this pitch |
| `PIANO_MAX_PITCH` | `108` (C8) | Drop notes above this pitch |

## Making the MIDI sound like a real piano

MIDI is just notes &mdash; how it sounds depends on your synth. Windows Media Player uses Microsoft GS Wavetable Synth, which sounds tinny. Two ways to fix:

1. Install [CoolSoft VirtualMIDISynth](https://coolsoft.altervista.org/en/virtualmidisynth) + a piano soundfont (e.g. [Salamander Grand Piano](https://freepats.zenvoid.org/Piano/acoustic-grand-piano.html)). All MIDI playback on Windows then uses your soundfont. Once-and-done.
2. Open the `.mid` in a DAW (Reaper / FL / Ableton) with a piano VST.

## Troubleshooting

If anything breaks after install:

```cmd
venv\Scripts\python.exe verify_install.py
```

That runs the same smoke test the installer uses at the end &mdash; reports any missing packages, missing assets, or CUDA not detected.

If something downloaded incomplete or is corrupt, just re-run `install.bat` &mdash; it resumes interrupted downloads and skips work that's already done.

## Credits

- **[BS-Rofo-SW-Fixed](https://huggingface.co/jarredou/BS-ROFO-SW-Fixed)** by jarredou &mdash; the 6-stem separator
- **[MSST](https://github.com/ZFTurbo/Music-Source-Separation-Training)** by ZFTurbo &mdash; the inference framework
- **[Transkun](https://github.com/Yujia-Yan/Transkun)** &mdash; piano transcription (ISMIR 2024)
- **[basic-pitch](https://github.com/spotify/basic-pitch)** by Spotify &mdash; general-purpose transcription
- **[FFmpeg](https://www.ffmpeg.org/)** shared builds by [BtbN](https://github.com/BtbN/FFmpeg-Builds)

## License

MIT for the glue code in this repo. Third-party components retain their own licenses &mdash; see [LICENSE](LICENSE).
