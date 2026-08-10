import sys
import re
import json
from pathlib import Path
from difflib import SequenceMatcher

import cv2
import numpy as np
import easyocr
from ultralytics import YOLO

from settings import CROP_DIR, MODEL_PATH, OUTPUT_DIR, ensure_runtime_directories


YOLO_CONF = 0.30
IMG_SIZE = 640
SAVE_DIR = OUTPUT_DIR
ensure_runtime_directories()


def normalize(s):
    s = s.lower()
    return re.sub(r"[^가-힣a-z0-9]", "", s)


def similarity(a, b):
    a = normalize(a)
    b = normalize(b)

    if not a or not b:
        return 0.0

    if a in b or b in a:
        return 0.95

    return SequenceMatcher(None, a, b).ratio()


def find_best_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"YOLO model not found: {MODEL_PATH}")
    return MODEL_PATH


def order_points(pts):
    pts = np.asarray(pts, dtype="float32")
    rect = np.zeros((4, 2), dtype="float32")

    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).reshape(-1)

    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    return rect


def expand_polygon(pts, image_shape, scale=1.03):
    h, w = image_shape[:2]
    pts = np.asarray(pts, dtype="float32")
    c = pts.mean(axis=0)
    pts2 = c + (pts - c) * scale
    pts2[:, 0] = np.clip(pts2[:, 0], 0, w - 1)
    pts2[:, 1] = np.clip(pts2[:, 1], 0, h - 1)
    return pts2


def four_point_warp(image, pts):
    pts = expand_polygon(pts, image.shape, scale=1.03)
    rect = order_points(pts)
    tl, tr, br, bl = rect

    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_w = int(max(width_a, width_b))

    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_h = int(max(height_a, height_b))

    if max_w < 8 or max_h < 8:
        return None

    dst = np.array([
        [0, 0],
        [max_w - 1, 0],
        [max_w - 1, max_h - 1],
        [0, max_h - 1],
    ], dtype="float32")

    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, M, (max_w, max_h))


def upscale(img):
    h, w = img.shape[:2]
    max_side = max(h, w)

    if max_side < 300:
        scale = 4
    elif max_side < 600:
        scale = 3
    elif max_side < 900:
        scale = 2
    else:
        scale = 1

    if scale > 1:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    return img


def make_variant(img, variant):
    img = upscale(img)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if variant == "clahe":
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        out = clahe.apply(gray)
        return cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)

    if variant == "adaptive":
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        c = clahe.apply(gray)
        th = cv2.adaptiveThreshold(
            c,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            7
        )
        return cv2.cvtColor(th, cv2.COLOR_GRAY2BGR)

    if variant == "sharp":
        blur = cv2.GaussianBlur(img, (0, 0), 1.0)
        out = cv2.addWeighted(img, 1.7, blur, -0.7, 0)
        return out

    if variant == "invert_clahe":
        inv = 255 - gray
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        out = clahe.apply(inv)
        return cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)

    return img


def rotate_img(img, angle):
    if angle == 0:
        return img
    if angle == 90:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    if angle == 270:
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return img


def clean_text(s):
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s


def ocr_quality_score(text, conf_sum, angle, variant):
    clean = "".join(
        ch for ch in text
        if ch.isalnum() or ("가" <= ch <= "힣") or ch in ["&", "+", "-", "(", ")", "."]
    )

    if len(clean) <= 1:
        return -999

    hangul = sum(1 for ch in clean if "가" <= ch <= "힣")
    latin = sum(1 for ch in clean if ("a" <= ch.lower() <= "z"))
    digit = sum(1 for ch in clean if ch.isdigit())

    score = 0.0
    score += len(clean) * 1.0
    score += hangul * 1.2
    score += latin * 0.9
    score += digit * 0.4
    score += conf_sum * 3.0

    if angle == 270:
        score += 2.0
    elif angle == 90:
        score += 1.0

    if variant == "clahe":
        score += 2.0
    elif variant == "sharp":
        score += 1.5
    elif variant == "invert_clahe":
        score += 0.8
    elif variant == "adaptive":
        score += 0.3

    return score


def read_ocr(reader, img):
    try:
        return reader.readtext(
            img,
            detail=1,
            paragraph=False,
            decoder="beamsearch",
            beamWidth=5,
            mag_ratio=2.0,
            contrast_ths=0.05,
            adjust_contrast=0.7,
            add_margin=0.1,
        )
    except TypeError:
        return reader.readtext(img, detail=1, paragraph=False)


def stable_ocr(reader, crop, prefix):
    crop = cv2.copyMakeBorder(crop, 8, 8, 8, 8, cv2.BORDER_REPLICATE)
    # 실험 결과 기준: 270 + clahe가 우선
    combos = [
        (270, "clahe"),
        (90, "clahe"),
        (270, "sharp"),
        (0, "sharp"),
        (270, "invert_clahe"),
        (90, "invert_clahe"),
    ]

    best = {
        "text": "읽기 실패",
        "angle": 0,
        "variant": "none",
        "score": -999,
    }

    for angle, variant in combos:
        r = rotate_img(crop, angle)
        pimg = make_variant(r, variant)

        try:
            results = read_ocr(reader, pimg)
        except Exception:
            continue

        pieces = []
        conf_sum = 0.0

        for item in results:
            text = clean_text(item[1])
            conf = float(item[2])

            if conf < 0.05:
                continue

            if not normalize(text):
                continue

            pieces.append(text)
            conf_sum += conf

        joined = clean_text(" ".join(pieces))
        score = ocr_quality_score(joined, conf_sum, angle, variant)

        if score > best["score"]:
            best = {
                "text": joined if joined else "읽기 실패",
                "angle": angle,
                "variant": variant,
                "score": score,
            }
            # speed: OCR debug image save disabled

            pass

    return best




ANGLE_SCALE = 1.0
ANGLE_OFFSET_DEG = 0.0

def calibrate_angle_deg(raw_angle):
    corrected = raw_angle * ANGLE_SCALE + ANGLE_OFFSET_DEG

    if corrected > 90.0:
        corrected = 90.0
    if corrected < -90.0:
        corrected = -90.0

    return corrected

def compute_book_angle_deg(pts):
    """
    OBB 4개 점을 이용해 책등의 화면 기준 기울기 각도를 계산함.
    기존처럼 긴 변 하나만 보지 않고, 책등의 양쪽 긴 변 방향을 평균내서 각도 흔들림을 줄임.
    0도: 화면에서 수직
    + / -: 화면 세로축 기준 좌우 기울기
    """
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)

    # 중심 기준으로 점 정렬
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

    # 긴 변 2개를 책등 방향으로 사용
    edges = sorted(edges, key=lambda x: x[0], reverse=True)[:2]

    if len(edges) == 0:
        return 0.0

    base = edges[0][1]
    vectors = []

    for _, v in edges:
        # 방향이 반대면 뒤집어서 같은 방향으로 맞춤
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

    # 화면 세로축 기준으로 변환
    angle_from_vertical = angle_from_x - 90.0

    while angle_from_vertical <= -90.0:
        angle_from_vertical += 180.0
    while angle_from_vertical > 90.0:
        angle_from_vertical -= 180.0

    return calibrate_angle_deg(angle_from_vertical)


def main():
    if len(sys.argv) < 3:
        print('사용법: python3 src/detect_and_match_book.py "찾을책제목" 이미지경로')
        return

    target = sys.argv[1]
    img_path = Path(sys.argv[2]).expanduser()

    frame = cv2.imread(str(img_path))
    if frame is None:
        raise RuntimeError(f"이미지 읽기 실패: {img_path}")

    for old in CROP_DIR.glob("*"):
        old.unlink()

    print(f"[INFO] 찾을 책 제목: {target}")
    print(f"[INFO] 이미지: {img_path}")

    model_path = find_best_model()
    print(f"[INFO] YOLO 모델: {model_path}")

    model = YOLO(str(model_path))

    print("[INFO] EasyOCR 로딩 중...")
    reader = easyocr.Reader(["ko", "en"], gpu=False)

    print("[INFO] YOLO 책등 검출 중...")
    result = model(frame, imgsz=IMG_SIZE, conf=YOLO_CONF, iou=0.40, max_det=20, verbose=False)[0]

    if result.obb is None or len(result.obb) == 0:
        print("[ERROR] 책등 검출 없음")
        return

    polygons = result.obb.xyxyxyxy.cpu().numpy()
    confs = result.obb.conf.cpu().numpy()

    items = []
    for pts, conf in zip(polygons, confs):
        cx = float(np.mean(pts[:, 0]))
        items.append((cx, pts, float(conf)))

    items.sort(key=lambda x: x[0])

    print(f"[INFO] 검출된 책등 개수: {len(items)}")

    annotated = frame.copy()
    candidates = []

    for idx, (_, pts, yolo_conf) in enumerate(items, start=1):
        crop = four_point_warp(frame, pts)
        if crop is None:
            continue

        cv2.imwrite(str(CROP_DIR / f"crop_{idx:02d}_raw.jpg"), crop)

        ocr = stable_ocr(reader, crop, f"crop_{idx:02d}")
        match = similarity(target, ocr["text"])

        candidates.append({
            "idx": idx,
            "pts": pts,
            "yolo_conf": yolo_conf,
            "ocr_text": ocr["text"],
            "ocr_angle": ocr["angle"],
            "variant": ocr["variant"],
            "match_score": match,
            "target_angle_deg": compute_book_angle_deg(pts),
        })

        print(
            f"{idx:02d}. match={match:.2f}, yolo={yolo_conf:.2f}, "
            f"angle={ocr['angle']}, variant={ocr['variant']}, text={ocr['text']}"
        )

    if not candidates:
        print("[ERROR] 후보 없음")
        return

    candidates.sort(key=lambda x: x["match_score"], reverse=True)
    best = candidates[0]

    # 화면 표시용 초록 박스
    # YOLO_CONF는 검정책을 찾기 위해 낮게 유지하지만,
    # 결과 화면에는 신뢰도 높은 박스만 보여서 중구난방 표시를 줄임.
    DISPLAY_CONF = 0.45

    for c in candidates:
        if c["yolo_conf"] < DISPLAY_CONF:
            continue

        pts_i = c["pts"].astype(np.int32).reshape((-1, 1, 2))
        cv2.polylines(annotated, [pts_i], True, (0, 180, 0), 2)

        cx = int(np.mean(c["pts"][:, 0]))
        cy = int(np.mean(c["pts"][:, 1]))

        cv2.putText(
            annotated,
            str(c["idx"]),
            (cx, cy),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 180, 0),
            2,
            cv2.LINE_AA,
        )

    # 목표 후보 빨간색
    if best["match_score"] >= 0.75:
        pts_i = best["pts"].astype(np.int32).reshape((-1, 1, 2))
        cv2.polylines(annotated, [pts_i], True, (0, 0, 255), 5)

        cx = int(np.mean(best["pts"][:, 0]))
        cy = int(np.mean(best["pts"][:, 1]))

        label = f"TARGET {best['idx']:02d}" if best["match_score"] >= 0.60 else f"CANDIDATE {best['idx']:02d}"

        cv2.putText(
            annotated,
            label,
            (max(10, cx - 130), max(40, cy - 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 0, 255),
            3,
            cv2.LINE_AA,
        )

    out_img = SAVE_DIR / "target_result.jpg"
    out_txt = SAVE_DIR / "target_result.txt"
    out_json = SAVE_DIR / "target_info.json"

    cv2.imwrite(str(out_img), annotated)

    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(f"입력 제목: {target}\n")
        f.write(f"선택된 책 번호: {best['idx']:02d}\n")
        f.write(f"OCR 결과: {best['ocr_text']}\n")
        f.write(f"유사도 점수: {best['match_score']:.2f}\n")
        f.write(f"YOLO confidence: {best['yolo_conf']:.2f}\n")
        f.write(f"OCR angle: {best['ocr_angle']}\n")
        f.write(f"OCR variant: {best['variant']}\n")
        f.write(f"TARGET angle: {best['target_angle_deg']:.2f} deg\n")

        if best["match_score"] >= 0.75:
            f.write("판정: 목표 책 확정\n")
        elif best["match_score"] >= 0.60:
            f.write("판정: 후보 책 발견\n")
        else:
            f.write("판정: 목표 책 미검출\n")

        f.write("\n상위 후보 TOP 3:\n")
        for rank, c in enumerate(candidates[:3], start=1):
            f.write(
                f"{rank}순위: {c['idx']:02d}번 / match={c['match_score']:.2f} / "
                f"yolo={c['yolo_conf']:.2f} / text={c['ocr_text']}\n"
            )

        f.write("\n전체 후보:\n")
        for c in candidates:
            f.write(
                f"{c['idx']:02d}. match={c['match_score']:.2f}, "
                f"yolo={c['yolo_conf']:.2f}, text={c['ocr_text']}\n"
            )

    info = {
        "input_title": target,
        "selected_index": int(best["idx"]),
        "ocr_text": best["ocr_text"],
        "match_score": float(best["match_score"]),
        "yolo_confidence": float(best["yolo_conf"]),
        "center_pixel": {
            "x": float(np.mean(best["pts"][:, 0])),
            "y": float(np.mean(best["pts"][:, 1])),
        },
        "obb_points": best["pts"].astype(float).tolist(),
    }

    with open(out_json, "w", encoding="utf-8") as jf:
        json.dump(info, jf, ensure_ascii=False, indent=2)

    print()
    print("========== 최종 결과 ==========")
    print(f"입력 제목: {target}")
    print(f"선택된 책 번호: {best['idx']:02d}")
    print(f"OCR 결과: {best['ocr_text']}")
    print(f"유사도 점수: {best['match_score']:.2f}")

    print()
    print("상위 후보 TOP 3:")
    for rank, c in enumerate(candidates[:3], start=1):
        print(f"{rank}순위: {c['idx']:02d}번 / match={c['match_score']:.2f} / text={c['ocr_text']}")

    print()
    print(f"결과 이미지: {out_img}")
    print(f"결과 텍스트: {out_txt}")
    print(f"crop 확인 폴더: {CROP_DIR}")


if __name__ == "__main__":
    main()
