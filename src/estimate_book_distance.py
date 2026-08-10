import sys
import json
import cv2
import numpy as np
from pathlib import Path

from settings import OUTPUT_DIR, ensure_runtime_directories

DISTANCE_SCALE = 1.0
DISTANCE_OFFSET_M = 0.0

OUT_DIR = OUTPUT_DIR
OUT_IMG = OUT_DIR / "target_result_depth.jpg"
OUT_TXT = OUT_DIR / "target_depth.txt"
ensure_runtime_directories()

def depth_to_meters(values):
    values = values.astype(np.float32)
    if values.size == 0:
        return values
    if np.nanmedian(values) > 20:
        values = values / 1000.0
    return values

def find_obb_points(obj, path="root"):
    if isinstance(obj, dict):
        if "obb_points" in obj:
            return obj["obb_points"], path + ".obb_points"
        for k, v in obj.items():
            found, found_path = find_obb_points(v, path + "." + str(k))
            if found is not None:
                return found, found_path
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found, found_path = find_obb_points(v, path + f"[{i}]")
            if found is not None:
                return found, found_path
    return None, None

def valid_meters_from_roi(depth_roi):
    values = depth_roi.astype(np.float32)
    values = values[np.isfinite(values)]
    values = values[values > 0]
    if values.size == 0:
        return values

    values_m = depth_to_meters(values)
    values_m = values_m[(values_m > 0.15) & (values_m < 3.0)]
    return values_m

def nearest_stable_cluster(values_m):
    """
    depth 값들 중 배경 median이 아니라,
    가장 가까운 안정적인 표면 군집을 선택함.
    """
    if values_m.size < 30:
        return None, 0

    values_m = np.sort(values_m)

    # 2cm 단위 히스토그램으로 가까운 군집 찾기
    bins = np.arange(0.15, 3.02, 0.02)
    hist, edges = np.histogram(values_m, bins=bins)

    for i, count in enumerate(hist):
        if count >= 20:
            lo = edges[i]
            hi = edges[i + 1]
            cluster = values_m[(values_m >= lo - 0.015) & (values_m <= hi + 0.035)]
            if cluster.size >= 20:
                return float(np.median(cluster)), int(cluster.size)

    # 군집이 없으면 너무 튀지 않도록 가까운 쪽 25% 사용
    q25 = np.percentile(values_m, 25)
    front = values_m[values_m <= q25]
    if front.size >= 20:
        return float(np.median(front)), int(front.size)

    return None, 0

def shrink_points(pts, ratio=0.72):
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    c = np.mean(pts, axis=0)
    return c + (pts - c) * ratio

def polygon_depth_values(depth, pts):
    h, w = depth.shape[:2]
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    pts_i = np.round(pts).astype(np.int32)

    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [pts_i], 255)

    ys, xs = np.where(mask > 0)
    if xs.size == 0:
        return np.array([], dtype=np.float32), None

    x1, x2 = int(xs.min()), int(xs.max())
    y1, y2 = int(ys.min()), int(ys.max())

    values = depth[mask > 0]
    return valid_meters_from_roi(values), (x1, y1, x2, y2)

def expanding_roi_distance(depth, cx, cy):
    h, w = depth.shape[:2]

    for size in [40, 70, 100, 140, 180, 240]:
        half = size // 2
        x1 = max(0, cx - half)
        x2 = min(w, cx + half)
        y1 = max(0, cy - half)
        y2 = min(h, cy + half)

        roi = depth[y1:y2, x1:x2]
        values_m = valid_meters_from_roi(roi)

        distance, count = nearest_stable_cluster(values_m)

        if distance is not None:
            return distance, count, (x1, y1, x2, y2), f"nearest_cluster_expanding_roi_{size}x{size}"

    return None, 0, None, "failed"

def draw_result(img, pts_img, distance_text, roi_box=None):
    out = img.copy()

    pts_i = np.asarray(pts_img, dtype=np.int32).reshape((-1, 1, 2))
    cv2.polylines(out, [pts_i], True, (0, 0, 255), 4)

    if False and roi_box is not None:
        x1, y1, x2, y2 = roi_box
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 255), 2)

    pts = np.asarray(pts_img, dtype=np.float32).reshape(4, 2)
    cx = int(np.mean(pts[:, 0]))
    cy = int(np.mean(pts[:, 1]))

    label = f"Distance: {distance_text}"
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.7
    thick = 2

    (tw, th), _ = cv2.getTextSize(label, font, font_scale, thick)
    lx = max(10, min(cx - tw // 2, out.shape[1] - tw - 20))
    ly = max(35, cy - 45)

    cv2.rectangle(out, (lx - 8, ly - th - 8), (lx + tw + 8, ly + 8), (0, 0, 255), -1)
    cv2.putText(out, label, (lx, ly), font, font_scale, (255, 255, 255), thick, cv2.LINE_AA)

    return out

def main():
    if len(sys.argv) < 4:
        print("usage: python3 src/estimate_book_distance.py target_info.json depth.npy target_result.jpg")
        sys.exit(1)

    info_path = Path(sys.argv[1])
    depth_path = Path(sys.argv[2])
    img_path = Path(sys.argv[3])

    info = json.loads(info_path.read_text(encoding="utf-8"))
    depth = np.load(str(depth_path))
    depth = np.squeeze(depth)

    img = cv2.imread(str(img_path))
    if img is None:
        print("[ERROR] image read failed:", img_path)
        sys.exit(1)

    pts_img, pts_path = find_obb_points(info)
    if pts_img is None:
        print("[ERROR] target_info.json에서 obb_points를 못 찾음")
        sys.exit(1)

    pts_img = np.asarray(pts_img, dtype=np.float32).reshape(4, 2)

    ih, iw = img.shape[:2]
    dh, dw = depth.shape[:2]
    sx = dw / iw
    sy = dh / ih

    pts_dep = pts_img.copy()
    pts_dep[:, 0] *= sx
    pts_dep[:, 1] *= sy

    cx_img = int(np.mean(pts_img[:, 0]))
    cy_img = int(np.mean(pts_img[:, 1]))
    cx_dep = int(np.mean(pts_dep[:, 0]))
    cy_dep = int(np.mean(pts_dep[:, 1]))

    # 1순위: TARGET OBB 안쪽 영역
    inner_pts = shrink_points(pts_dep, 0.72)
    values_m, roi_box = polygon_depth_values(depth, inner_pts)

    raw_distance = None
    valid_count = 0
    method = "inner_obb_nearest_cluster"

    d, count = nearest_stable_cluster(values_m)
    if d is not None and count >= 30:
        raw_distance = d
        valid_count = count
    else:
        # 2순위: 중심 주변을 넓혀가며 가까운 안정 군집 선택
        raw_distance, valid_count, roi_box, method = expanding_roi_distance(depth, cx_dep, cy_dep)

    if raw_distance is None:
        out = draw_result(img, pts_img, "N/A", roi_box)
        cv2.imwrite(str(OUT_IMG), out)

        with open(OUT_TXT, "w", encoding="utf-8") as f:
            f.write("distance_status: failed\n")
            f.write("reason: no stable depth cluster around target\n")
            f.write(f"selected_points_path: {pts_path}\n")
            f.write(f"center_rgb_pixel: ({cx_img}, {cy_img})\n")
            f.write(f"center_depth_pixel: ({cx_dep}, {cy_dep})\n")
            f.write(f"depth_shape: {depth.shape}\n")
            f.write(f"image_shape: {img.shape}\n")

        print("TARGET depth result using target_info OBB")
        print("distance_status: failed")
        print("reason: no stable depth cluster around target")
        return

    corrected = raw_distance * DISTANCE_SCALE + DISTANCE_OFFSET_M

    out = draw_result(img, pts_img, f"{corrected:.3f} m", roi_box)
    cv2.imwrite(str(OUT_IMG), out)

    with open(OUT_TXT, "w", encoding="utf-8") as f:
        f.write("TARGET depth result using target_info OBB\n")
        f.write("distance_status: success\n")
        f.write(f"selected_points_path: {pts_path}\n")
        f.write(f"method: {method}\n")
        f.write(f"raw_distance_m: {raw_distance:.4f}\n")
        f.write(f"scale: {DISTANCE_SCALE:.4f}\n")
        f.write(f"offset_m: {DISTANCE_OFFSET_M:.4f}\n")
        f.write(f"corrected_distance_m: {corrected:.4f}\n")
        f.write(f"final_distance_m: {corrected:.4f}\n")
        f.write(f"valid_depth_count: {valid_count}\n")
        f.write(f"center_rgb_pixel: ({cx_img}, {cy_img})\n")
        f.write(f"center_depth_pixel: ({cx_dep}, {cy_dep})\n")
        f.write(f"roi_depth_box: {roi_box}\n")
        f.write(f"depth_shape: {depth.shape}\n")
        f.write(f"image_shape: {img.shape}\n")

    print("TARGET depth result using target_info OBB")
    print("distance_status: success")
    print(f"selected_points_path: {pts_path}")
    print(f"method: {method}")
    print(f"raw_distance_m: {raw_distance:.4f}")
    print(f"scale: {DISTANCE_SCALE:.4f}")
    print(f"offset_m: {DISTANCE_OFFSET_M:.4f}")
    print(f"corrected_distance_m: {corrected:.4f}")
    print(f"final_distance_m: {corrected:.4f}")
    print(f"valid_depth_count: {valid_count}")
    print(f"center_rgb_pixel: ({cx_img}, {cy_img})")
    print(f"center_depth_pixel: ({cx_dep}, {cy_dep})")
    print(f"roi_depth_box: {roi_box}")
    print(f"depth_shape: {depth.shape}")
    print(f"image_shape: {img.shape}")

if __name__ == "__main__":
    main()
