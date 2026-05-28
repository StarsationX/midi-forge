"""Download BS-Rofo-SW-Fixed model + FFmpeg shared DLLs into the repo folder.
Run by install.bat after Python deps are installed."""
import io
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MODEL_DIR = ROOT / "models" / "bs_rofo_sw"
CKPT_URL = "https://huggingface.co/jarredou/BS-ROFO-SW-Fixed/resolve/main/BS-Rofo-SW-Fixed.ckpt"
YAML_URL = "https://huggingface.co/jarredou/BS-ROFO-SW-Fixed/resolve/main/BS-Rofo-SW-Fixed.yaml"

FFMPEG_DIR = ROOT / "ffmpeg"
FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-lgpl-shared.zip"


def _download(url: str, dest: Path, label: str) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  [skip] {label} already present ({dest.stat().st_size // (1024*1024)} MB)")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  [get ] {label}")
    print(f"         {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length", "0"))
        read = 0
        block = 1024 * 256
        last_pct = -5
        while True:
            chunk = r.read(block)
            if not chunk:
                break
            f.write(chunk)
            read += len(chunk)
            if total > 0:
                pct = int(read * 100 / total)
                if pct - last_pct >= 5:
                    print(f"         {pct:3d}%  ({read // (1024*1024)} / {total // (1024*1024)} MB)")
                    last_pct = pct
    tmp.replace(dest)
    print(f"         done ({dest.stat().st_size // (1024*1024)} MB)")


def fetch_model() -> None:
    print("Model: BS-Rofo-SW-Fixed (SOTA 6-stem piano separator)")
    _download(CKPT_URL, MODEL_DIR / "BS-Rofo-SW-Fixed.ckpt", "BS-Rofo-SW-Fixed.ckpt")
    _download(YAML_URL, MODEL_DIR / "BS-Rofo-SW-Fixed.yaml", "BS-Rofo-SW-Fixed.yaml")


def fetch_ffmpeg() -> None:
    print("\nFFmpeg shared DLLs (BtbN build):")
    target = FFMPEG_DIR / "ffmpeg-master-latest-win64-lgpl-shared"
    if (target / "bin" / "ffmpeg.exe").exists():
        print(f"  [skip] FFmpeg already extracted")
        return
    zip_path = FFMPEG_DIR / "ffmpeg.zip"
    _download(FFMPEG_URL, zip_path, "ffmpeg-master-latest-win64-lgpl-shared.zip")
    print(f"  [unzip] -> {FFMPEG_DIR}")
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(FFMPEG_DIR)
    zip_path.unlink()
    print(f"  done")


def main() -> int:
    try:
        fetch_model()
        fetch_ffmpeg()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        return 1
    print("\nAll assets ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
