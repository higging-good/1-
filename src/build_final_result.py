import json
import re
import numpy as np
from pathlib import Path

from settings import OUTPUT_DIR, ensure_runtime_directories

BASE = OUTPUT_DIR
ensure_runtime_directories()
target_txt = BASE / "target_result.txt"
depth_txt = BASE / "target_depth.txt"
info_json = BASE / "target_info.json"
final_txt = BASE / "final_result.txt"

def read_text(path):
    if path.exists():
        return path.read_text(encoding="utf-8", errors="ignore")
    return ""

def find_line_value(text, key):
    for line in text.splitlines():
        if line.startswith(key):
            return line.split(":", 1)[1].strip()
    return "N/A"

def find_float_value(text, key):
    m = re.search(rf"{re.escape(key)}:\s*([-+]?\d+(?:\.\d+)?)", text)
    if m:
        return float(m.group(1))
    return None

def find_obb_points(obj):
    if isinstance(obj, dict):
        if "obb_points" in obj:
            return obj["obb_points"]
        for v in obj.values():
            found = find_obb_points(v)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = find_obb_points(v)
            if found is not None:
                return found
    return None


ANGLE_SCALE = 1.0
ANGLE_OFFSET_DEG = 0.0

def calibrate_angle_deg(raw_angle):
    corrected = raw_angle * ANGLE_SCALE + ANGLE_OFFSET_DEG

    if corrected > 90.0:
        corrected = 90.0
    if corrected < -90.0:
        corrected = -90.0

    return corrected

def compute_angle_deg(pts):
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)

    c = np.mean(pts, axis=0)
    angles = np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0])
    pts = pts[np.argsort(angles)]

    edges = []
    for i in range(4):
        p1 = pts[i]
        p2 = pts[(i + 1) % 4]
        v = p2 - p1
        length = float(np.linalg.norm(v))
        if length > 1e-6:
            v = v / length
            edges.append((length, v))

    edges = sorted(edges, key=lambda x: x[0], reverse=True)[:2]

    if len(edges) == 0:
        return 0.0

    base = edges[0][1]
    vectors = []

    for _, v in edges:
        if float(np.dot(base, v)) < 0:
            v = -v
        vectors.append(v)

    mean_v = np.mean(np.asarray(vectors), axis=0)
    norm = float(np.linalg.norm(mean_v))

    if norm < 1e-6:
        mean_v = base
    else:
        mean_v = mean_v / norm

    angle_from_x = float(np.degrees(np.arctan2(mean_v[1], mean_v[0])))
    angle_from_vertical = angle_from_x - 90.0

    while angle_from_vertical <= -90.0:
        angle_from_vertical += 180.0
    while angle_from_vertical > 90.0:
        angle_from_vertical -= 180.0

    return calibrate_angle_deg(angle_from_vertical)


target_text = read_text(target_txt)
depth_text = read_text(depth_txt)

input_title = find_line_value(target_text, "입력 제목")
ocr_result = find_line_value(target_text, "OCR 결과")
judgement = find_line_value(target_text, "판정")

distance = (
    find_float_value(depth_text, "final_distance_m")
    or find_float_value(depth_text, "corrected_distance_m")
    or find_float_value(depth_text, "raw_distance_m")
)

angle = find_float_value(target_text, "TARGET angle")

if angle is None and info_json.exists():
    try:
        data = json.loads(info_json.read_text(encoding="utf-8"))
        pts = find_obb_points(data)
        if pts is not None:
            angle = compute_angle_deg(pts)
    except Exception:
        angle = None

distance_str = f"{distance:.3f} m" if distance is not None else "N/A"
angle_str = f"{angle:.2f} deg" if angle is not None else "N/A"

out = []
out.append(f"책제목: {input_title}")
out.append(f"검출결과: {ocr_result} / {judgement}")
out.append(f"거리: {distance_str}")
out.append(f"각도: {angle_str}")

final_txt.write_text("\n".join(out) + "\n", encoding="utf-8")

print("\n".join(out))
