"""Shared project paths for the book-bounding pipeline."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "models" / "book_spine_detector.pt"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
CROP_DIR = OUTPUT_DIR / "crops"
CAPTURE_DIR = PROJECT_ROOT / "data" / "captures"
LATEST_CAPTURE_FILE = OUTPUT_DIR / "latest_capture.txt"


def ensure_runtime_directories():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CROP_DIR.mkdir(parents=True, exist_ok=True)
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
