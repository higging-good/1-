#!/usr/bin/env python3
import json
import re
from pathlib import Path

from settings import OUTPUT_DIR, ensure_runtime_directories

BASE = OUTPUT_DIR
ensure_runtime_directories()

target_info_path = BASE / "target_info.json"
target_depth_path = BASE / "target_depth.txt"
final_result_path = BASE / "final_result.txt"
out_path = BASE / "book_target_output.json"

def read_text(path):
    if path.exists():
        return path.read_text(encoding="utf-8", errors="ignore")
    return ""

def parse_float(pattern, text, default=None):
    m = re.search(pattern, text)
    if not m:
        return default
    try:
        return float(m.group(1))
    except Exception:
        return default

def parse_pixel(pattern, text, default=None):
    m = re.search(pattern, text)
    if not m:
        return default
    return [int(m.group(1)), int(m.group(2))]

def find_first_key(obj, keys):
    if isinstance(obj, dict):
        for k in keys:
            if k in obj:
                return obj[k]
        for v in obj.values():
            found = find_first_key(v, keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = find_first_key(v, keys)
            if found is not None:
                return found
    return None

target_info = {}
if target_info_path.exists():
    try:
        target_info = json.loads(target_info_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] target_info.json 읽기 실패: {e}")

depth_text = read_text(target_depth_path)
final_text = read_text(final_result_path)

title = None
m = re.search(r"책제목:\s*(.+)", final_text)
if m:
    title = m.group(1).strip()

ocr_result = None
m = re.search(r"검출결과:\s*(.+)", final_text)
if m:
    ocr_result = m.group(1).strip()

distance_m = parse_float(r"final_distance_m:\s*([0-9.]+)", depth_text)
if distance_m is None:
    distance_m = parse_float(r"거리:\s*([0-9.]+)", final_text)

angle_deg = parse_float(r"각도:\s*([-+0-9.]+)", final_text)

center_px = parse_pixel(r"center_rgb_pixel:\s*\((\d+),\s*(\d+)\)", depth_text)

distance_status = None
m = re.search(r"distance_status:\s*(\S+)", depth_text)
if m:
    distance_status = m.group(1).strip()

valid_depth_count = parse_float(r"valid_depth_count:\s*([0-9.]+)", depth_text, 0)

# target_info.json 안에서 가능한 좌표/박스 정보 자동 탐색
obb_points = find_first_key(target_info, [
    "obb_points",
    "points",
    "polygon",
    "pts",
    "corners",
    "box_points"
])

yolo_confidence = find_first_key(target_info, [
    "yolo_confidence",
    "yolo_conf",
    "confidence",
    "conf"
])

match_score = find_first_key(target_info, [
    "match_score",
    "score"
])

min_match_score = 0.75

try:
    match_score_value = float(match_score) if match_score is not None else 0.0
except Exception:
    match_score_value = 0.0

target_found = bool(
    title and
    distance_m is not None and
    distance_status == "success" and
    match_score_value >= min_match_score
)

quality = "OK"
warnings = []

if not target_found:
    quality = "BAD"
    warnings.append("target_found 조건 불만족")

if match_score is None:
    quality = "BAD"
    warnings.append("match_score 없음")
else:
    try:
        if float(match_score) < min_match_score:
            quality = "BAD"
            warnings.append(f"match_score 낮음: {float(match_score):.3f} < {min_match_score}")
    except Exception:
        quality = "BAD"
        warnings.append("match_score 변환 실패")

if distance_m is None:
    quality = "BAD"
    warnings.append("거리값 없음")

if distance_status != "success":
    quality = "BAD"
    warnings.append("거리 계산 실패")

if valid_depth_count is not None and valid_depth_count < 500:
    quality = "CHECK"
    warnings.append("유효 depth 픽셀 수가 적음")

if center_px is None:
    quality = "CHECK"
    warnings.append("중심 픽셀 없음")

if angle_deg is None:
    quality = "CHECK"
    warnings.append("각도값 없음")

output = {
    "target_found": target_found,
    "quality": quality,
    "warnings": warnings,

    "title": title,
    "ocr_result": ocr_result,

    "distance_m": distance_m,
    "distance_status": distance_status,
    "valid_depth_count": int(valid_depth_count) if valid_depth_count is not None else None,

    "center_px": center_px,
    "angle_deg": angle_deg,

    "obb_points": obb_points,
    "yolo_confidence": yolo_confidence,
    "match_score": match_score,
    "min_match_score": 0.75,

    "source_files": {
        "target_info": str(target_info_path),
        "target_depth": str(target_depth_path),
        "final_result": str(final_result_path)
    }
}

out_path.write_text(
    json.dumps(output, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print("[SAVE]", out_path)
print(json.dumps(output, ensure_ascii=False, indent=2))
