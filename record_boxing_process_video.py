#!/usr/bin/env python3
import os
import re
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
from ultralytics import YOLO
import easyocr


def norm_text(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def target_words(target: str):
    return [norm_text(w) for w in target.split() if norm_text(w)]


def strict_match_score(target: str, ocr_text: str):
    """
    빨간 박스 조건:
    1. OCR 결과에 목표 제목 단어들이 거의 다 들어와야 함
    2. 또는 전체 문자열 유사도가 매우 높아야 함

    부분 단어 하나만 맞았다고 빨간색 절대 안 침.
    """
    t_norm = norm_text(target)
    o_norm = norm_text(ocr_text)

    if not t_norm or not o_norm:
        return 0.0, False

    ratio = SequenceMatcher(None, t_norm, o_norm).ratio()

    words = target_words(target)
    if not words:
        return ratio, ratio >= 0.90

    hit = 0
    for w in words:
        if w in o_norm:
            hit += 1

    word_ratio = hit / len(words)

    # 목표 제목 전체가 OCR 안에 들어온 경우
    # OCR 일부 글자만 목표 제목에 포함되는 경우는 오탐으로 처리한다.
    full_contained = len(t_norm) >= 3 and t_norm in o_norm

    # 단어가 3개 이상이면 거의 전부 맞아야 함
    if len(words) >= 3:
        word_ok = hit >= len(words) - 1 and ratio >= 0.70
    else:
        word_ok = hit == len(words) and ratio >= 0.70

    # 아주 유사한 경우
    ratio_ok = ratio >= 0.90

    ok = full_contained or word_ok or ratio_ok
    score = max(ratio, word_ratio)

    return score, ok


def crop_from_pts(frame, pts, scale=1.02):
    """Rectify one OBB so neighboring book spines do not enter the OCR crop."""
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    center = pts.mean(axis=0)
    pts = center + (pts - center) * scale
    pts[:, 0] = np.clip(pts[:, 0], 0, frame.shape[1] - 1)
    pts[:, 1] = np.clip(pts[:, 1], 0, frame.shape[0] - 1)

    sums = pts.sum(axis=1)
    diffs = np.diff(pts, axis=1).reshape(-1)
    rect = np.array([
        pts[np.argmin(sums)], pts[np.argmin(diffs)],
        pts[np.argmax(sums)], pts[np.argmax(diffs)],
    ], dtype=np.float32)
    tl, tr, br, bl = rect
    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    if width < 8 or height < 8:
        return None

    dst = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(frame, matrix, (width, height))


def center_of_pts(pts):
    return float(np.mean(pts[:, 0])), float(np.mean(pts[:, 1]))


def dist2(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


class BoxingProcessRecorder(Node):
    def __init__(self, args):
        super().__init__("record_boxing_process_video")

        self.args = args
        self.bridge = CvBridge()

        self.frame = None
        self.frame_count = 0

        self.model = YOLO(args.model)
        self.reader = easyocr.Reader(["en"], gpu=args.gpu)

        self.sub = self.create_subscription(
            Image,
            args.topic,
            self.image_cb,
            10
        )

        self.original_dir = os.path.join(args.output_dir, "original")
        self.h264_dir = os.path.join(args.output_dir, "h264")

        Path(self.original_dir).mkdir(parents=True, exist_ok=True)
        Path(self.h264_dir).mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_path = os.path.join(self.original_dir, f"boxing_process_strict_{ts}.mp4")

        self.writer = None
        self.record_start_time = None

        self.target_locked = False
        self.target_center = None
        self.target_found_time = None

        self.candidate_tracks = []
        self.last_ocr_time = 0.0

        self.get_logger().info(f"찾을 책 제목: {args.target}")
        self.get_logger().info("영상에는 박스만 표시합니다.")
        self.get_logger().info("OCR이 입력한 책 제목과 확실히 맞을 때만 빨간 박스로 바뀝니다.")
        self.get_logger().info("빨간 박스가 뜨면 5초 더 저장 후 자동 종료합니다.")

    def image_cb(self, msg):
        try:
            self.frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as e:
            self.get_logger().error(f"cv_bridge error: {e}")

    def init_writer(self, frame):
        h, w = frame.shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.writer = cv2.VideoWriter(self.output_path, fourcc, self.args.fps, (w, h))

        if not self.writer.isOpened():
            raise RuntimeError("VideoWriter open failed")

        self.record_start_time = time.time()
        self.get_logger().info(f"영상 저장 시작: {self.output_path}")

    def detect_books(self, frame):
        results = self.model.predict(
            source=frame,
            conf=self.args.conf,
            verbose=False
        )

        books = []

        for result in results:
            if result.obb is None or result.obb.xyxyxyxy is None:
                continue

            pts_all = result.obb.xyxyxyxy.cpu().numpy()
            confs = result.obb.conf.cpu().numpy() if result.obb.conf is not None else np.zeros(len(pts_all))

            for pts, conf in zip(pts_all, confs):
                pts = pts.reshape(4, 2).astype(np.float32)
                xs = pts[:, 0]
                ys = pts[:, 1]

                if (xs.max() - xs.min()) < 10 or (ys.max() - ys.min()) < 30:
                    continue

                books.append({
                    "pts": pts,
                    "conf": float(conf),
                    "center": center_of_pts(pts)
                })

        return books

    def ocr_one_book(self, frame, pts):
        crop = crop_from_pts(frame, pts)
        if crop is None or crop.size == 0:
            return "", 0.0, False

        candidates = []

        # 책등은 세로 글씨가 많으니까 회전 OCR 시도
        imgs = [
            crop,
            cv2.rotate(crop, cv2.ROTATE_90_CLOCKWISE),
            cv2.rotate(crop, cv2.ROTATE_90_COUNTERCLOCKWISE),
            cv2.rotate(crop, cv2.ROTATE_180),
        ]

        for img in imgs:
            try:
                texts = self.reader.readtext(img, detail=0, paragraph=True)
                text = " ".join(texts).strip()
                score, ok = strict_match_score(self.args.target, text)
                candidates.append((text, score, ok))
            except Exception:
                pass

        if not candidates:
            return "", 0.0, False

        # ok인 후보 우선, 그다음 score 높은 후보
        candidates.sort(key=lambda x: (x[2], x[1]), reverse=True)
        return candidates[0]

    def try_lock_target_by_ocr(self, frame, books):
        if self.target_locked:
            return

        if self.record_start_time is None:
            return

        elapsed = time.time() - self.record_start_time

        # 영상 초반은 무조건 초록 박스만 남김
        if elapsed < self.args.green_seconds:
            return

        # OCR 너무 자주 하면 느리니까 간격 둠
        now = time.time()
        if now - self.last_ocr_time < self.args.ocr_interval:
            return
        self.last_ocr_time = now

        if not books:
            return

        self.get_logger().info("OCR 확인 중...")

        best_i = None
        best_text = ""
        best_score = 0.0
        best_ok = False

        for i, book in enumerate(books):
            text, score, ok = self.ocr_one_book(frame, book["pts"])

            # 터미널에는 OCR 결과를 보여줌. 영상에는 안 나옴.
            if text:
                self.get_logger().info(
                    f"[OCR] book#{i+1} text='{text}' score={score:.3f} ok={ok}"
                )

            if ok and score > best_score:
                best_i = i
                best_text = text
                best_score = score
                best_ok = ok

        if best_i is None or not best_ok:
            return

        candidate_center = books[best_i]["center"]
        nearest = None
        if self.candidate_tracks:
            nearest = min(
                self.candidate_tracks,
                key=lambda track: dist2(track["center"], candidate_center),
            )
            if dist2(nearest["center"], candidate_center) > self.args.track_distance ** 2:
                nearest = None
        hits = (nearest["hits"] if nearest else 0) + 1
        self.candidate_tracks = [{"center": candidate_center, "hits": hits}]

        self.get_logger().info(
            f"목표책 후보 확인 {hits}/{self.args.confirm_hits}: "
            f"book#{best_i+1}, OCR='{best_text}', score={best_score:.3f}"
        )

        # 한 번 맞았다고 바로 빨간색 안 침. confirm_hits번 확인돼야 빨간색.
        if hits >= self.args.confirm_hits:
            self.target_locked = True
            self.target_center = books[best_i]["center"]
            self.target_found_time = time.time()

            self.get_logger().info(
                f"목표책 최종 확정. 이제 빨간 박스 표시: OCR='{best_text}', score={best_score:.3f}"
            )

    def choose_red_index(self, books):
        if not self.target_locked or self.target_center is None or not books:
            return None

        best_i = None
        best_d = float("inf")

        for i, book in enumerate(books):
            d = dist2(book["center"], self.target_center)
            if d < best_d:
                best_d = d
                best_i = i

        if best_i is not None:
            self.target_center = books[best_i]["center"]

        return best_i

    def draw_boxes_only(self, frame, books):
        vis = frame.copy()
        red_idx = self.choose_red_index(books)

        for i, book in enumerate(books):
            pts = book["pts"].astype(np.int32)

            if red_idx is not None and i == red_idx:
                color = (0, 0, 255)
                thickness = 5
            else:
                color = (0, 255, 0)
                thickness = 3

            cv2.polylines(vis, [pts], True, color, thickness)

        return vis

    def run(self):
        while rclpy.ok():
            rclpy.spin_once(self, timeout_sec=0.01)

            if self.frame is None:
                continue

            frame = self.frame.copy()

            if self.writer is None:
                self.init_writer(frame)

            books = self.detect_books(frame)
            self.try_lock_target_by_ocr(frame, books)

            vis = self.draw_boxes_only(frame, books)
            self.writer.write(vis)
            self.frame_count += 1

            if not self.args.no_preview:
                cv2.imshow("boxing process: green boxes to target red box", vis)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break

            if self.target_found_time is not None:
                if time.time() - self.target_found_time >= self.args.after_found_seconds:
                    break

            if self.args.max_seconds > 0 and self.record_start_time is not None:
                if time.time() - self.record_start_time >= self.args.max_seconds:
                    self.get_logger().warn("max_seconds 도달. 목표책을 찾지 못했거나 시간이 초과되었습니다.")
                    break

        if self.writer is not None:
            self.writer.release()

        cv2.destroyAllWindows()

        if not self.target_locked:
            try:
                os.remove(self.output_path)
                print(f"[INFO] 빨간 박스 미검출 영상을 삭제했습니다: {self.output_path}")
            except FileNotFoundError:
                pass
            return

        print("")
        print("===== 저장된 영상 =====")
        print(self.output_path)

        if self.args.make_h264:
            base_name = os.path.basename(self.output_path).replace(".mp4", "_h264.mp4")
            fixed = os.path.join(self.h264_dir, base_name)
            try:
                subprocess.run(
                    [
                        "ffmpeg", "-y",
                        "-i", self.output_path,
                        "-c:v", "libx264",
                        "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart",
                        fixed
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                print("")
                print("===== 변환된 영상 H264 =====")
                print(fixed)
            except Exception:
                print("")
                print("[WARN] ffmpeg 변환 실패. 원본 mp4는 저장되어 있습니다.")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--target", default="", help="찾을 책 제목. 비워두면 직접 입력")
    parser.add_argument("--topic", default="/camera/color/image_raw")
    parser.add_argument("--model", default="models/book_spine_detector.pt")
    parser.add_argument("--output_dir", default="outputs/videos")

    parser.add_argument("--conf", type=float, default=0.30)
    parser.add_argument("--fps", type=float, default=10.0)

    parser.add_argument("--green_seconds", type=float, default=2.0)
    parser.add_argument("--after_found_seconds", type=float, default=5.0)
    parser.add_argument("--ocr_interval", type=float, default=1.0)
    parser.add_argument("--confirm_hits", type=int, default=2)
    parser.add_argument("--track_distance", type=float, default=80.0)
    parser.add_argument("--max_seconds", type=float, default=60.0)

    parser.add_argument("--gpu", action="store_true")
    parser.add_argument("--no_preview", action="store_true")
    parser.add_argument("--make_h264", action="store_true")

    args = parser.parse_args()

    if not args.target.strip():
        args.target = input("찾을 책 제목을 입력하세요: ").strip()

    if not args.target:
        print("[ERROR] 책 제목이 비어 있습니다.")
        return

    rclpy.init()
    node = BoxingProcessRecorder(args)

    try:
        node.run()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
