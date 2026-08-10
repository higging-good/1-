#!/usr/bin/env python3
import csv
import json
from pathlib import Path
from datetime import datetime

from settings import OUTPUT_DIR, ensure_runtime_directories

ensure_runtime_directories()
src = OUTPUT_DIR / "book_target_output.json"
out = OUTPUT_DIR / "target_test_log.csv"

if not src.exists():
    raise SystemExit("[ERROR] book_target_output.json 없음")

data = json.loads(src.read_text(encoding="utf-8"))

center = data.get("center_px") or [None, None]

row = {
    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "target_found": data.get("target_found"),
    "quality": data.get("quality"),
    "title": data.get("title"),
    "ocr_result": data.get("ocr_result"),
    "distance_m": data.get("distance_m"),
    "angle_deg": data.get("angle_deg"),
    "center_x": center[0],
    "center_y": center[1],
    "yolo_confidence": data.get("yolo_confidence"),
    "match_score": data.get("match_score"),
    "valid_depth_count": data.get("valid_depth_count"),
}

write_header = not out.exists()

with out.open("a", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=row.keys())
    if write_header:
        writer.writeheader()
    writer.writerow(row)

print("[LOG SAVE]", out)
print(row)
