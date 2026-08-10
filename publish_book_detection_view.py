#!/usr/bin/env python3
import argparse
import re
import time
import threading
from difflib import SequenceMatcher

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data, QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image, CompressedImage
from cv_bridge import CvBridge
from ultralytics import YOLO
import easyocr


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def word_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def strict_match_score(target: str, ocr_text: str):
    target_n = normalize_text(target)
    text_n = normalize_text(ocr_text)

    if not target_n or not text_n:
        return 0.0, False

    ratio = SequenceMatcher(None, target_n, text_n).ratio()

    if target_n in text_n:
        return max(ratio, 1.0), True

    target_words = [w for w in target_n.split() if len(w) >= 3]
    ocr_words = [w for w in text_n.split() if len(w) >= 3]

    if not target_words or not ocr_words:
        return ratio, False

    hit = 0
    for tw in target_words:
        best = max((word_similarity(tw, ow) for ow in ocr_words), default=0.0)
        if len(tw) <= 3:
            if best >= 0.90:
                hit += 1
        else:
            if best >= 0.80:
                hit += 1

    token_score = hit / max(1, len(target_words))
    final_score = max(ratio, token_score)

    ok = token_score >= 0.999
    return final_score, ok


def order_points(pts):
    pts = np.array(pts, dtype=np.float32).reshape(4, 2)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).reshape(-1)

    rect = np.zeros((4, 2), dtype=np.float32)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    rect[1] = pts[np.argmin(d)]
    rect[3] = pts[np.argmax(d)]
    return rect


def warp_obb_crop(frame, pts, pad=8):
    rect = order_points(pts)
    tl, tr, br, bl = rect

    w1 = np.linalg.norm(br - bl)
    w2 = np.linalg.norm(tr - tl)
    h1 = np.linalg.norm(tr - br)
    h2 = np.linalg.norm(tl - bl)

    width = int(max(w1, w2))
    height = int(max(h1, h2))

    if width < 8 or height < 8:
        return None

    dst = np.array([
        [0, 0],
        [width - 1, 0],
        [width - 1, height - 1],
        [0, height - 1],
    ], dtype=np.float32)

    M = cv2.getPerspectiveTransform(rect, dst)
    crop = cv2.warpPerspective(frame, M, (width, height))

    if pad > 0:
        crop = cv2.copyMakeBorder(crop, pad, pad, pad, pad, cv2.BORDER_REPLICATE)

    # OCR 잘 보이게 너무 작은 crop은 확대
    h, w = crop.shape[:2]
    scale = max(1.0, 180.0 / max(1, min(h, w)))
    if scale > 1.0:
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    return crop


def center_of_pts(pts):
    pts = np.array(pts, dtype=np.float32).reshape(4, 2)
    c = pts.mean(axis=0)
    return float(c[0]), float(c[1])


def dist2(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


class BookDetectionViewPublisher(Node):
    def __init__(self, args):
        super().__init__("book_detection_view_publisher")

        self.args = args
        self.bridge = CvBridge()

        self.target_title = args.target.strip()
        if not self.target_title:
            self.target_title = input("찾을 책 제목을 입력하세요: ").strip()
        if not self.target_title:
            raise SystemExit("[ERROR] 책 제목이 비어 있습니다.")

        self.get_logger().info(f"찾을 책 제목: {self.target_title}")
        self.get_logger().info(f"입력 토픽: {args.input_topic}")
        self.get_logger().info(f"출력 토픽: {args.output_topic}")
        self.get_logger().info("영상에는 박스만 표시합니다.")

        self.model = YOLO(args.model)
        self.reader = easyocr.Reader(["en"], gpu=args.gpu)

        pub_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )
        self.pub = self.create_publisher(CompressedImage, args.output_topic, pub_qos)

        self.sub = self.create_subscription(
            Image,
            args.input_topic,
            self.image_callback,
            qos_profile_sensor_data,
        )

        self.lock = threading.Lock()
        self.ocr_busy = False
        self.last_ocr_time = 0.0
        self.last_pub_time = 0.0

        self.target_center = None
        self.candidate_center = None
        self.candidate_hits = 0
        self.last_ocr_text = ""
        self.last_score = 0.0

    def detect_books(self, frame):
        results = self.model(frame, conf=self.args.conf, verbose=False)
        if not results:
            return []

        r = results[0]
        detections = []

        if getattr(r, "obb", None) is not None and r.obb is not None and len(r.obb) > 0:
            pts_all = r.obb.xyxyxyxy.cpu().numpy()
            conf_all = r.obb.conf.cpu().numpy()
            for pts, conf in zip(pts_all, conf_all):
                pts = np.array(pts, dtype=np.float32).reshape(4, 2)
                detections.append({
                    "pts": pts,
                    "center": center_of_pts(pts),
                    "conf": float(conf),
                })
            return detections

        if getattr(r, "boxes", None) is not None and r.boxes is not None and len(r.boxes) > 0:
            xyxy_all = r.boxes.xyxy.cpu().numpy()
            conf_all = r.boxes.conf.cpu().numpy()
            for xyxy, conf in zip(xyxy_all, conf_all):
                x1, y1, x2, y2 = xyxy
                pts = np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.float32)
                detections.append({
                    "pts": pts,
                    "center": center_of_pts(pts),
                    "conf": float(conf),
                })

        return detections

    def ocr_worker(self, frame, detections):
        try:
            best = None

            for idx, det in enumerate(detections):
                crop = warp_obb_crop(frame, det["pts"])
                if crop is None:
                    continue

                crops = [
                    crop,
                    cv2.rotate(crop, cv2.ROTATE_90_CLOCKWISE),
                    cv2.rotate(crop, cv2.ROTATE_90_COUNTERCLOCKWISE),
                ]

                texts = []
                for c in crops:
                    try:
                        out = self.reader.readtext(c, detail=0, paragraph=True)
                        if out:
                            texts.append(" ".join(out))
                    except Exception:
                        pass

                merged = " ".join(texts).strip()
                score, ok = strict_match_score(self.target_title, merged)

                if best is None or score > best["score"]:
                    best = {
                        "idx": idx,
                        "center": det["center"],
                        "text": merged,
                        "score": score,
                        "ok": ok,
                    }

            if best is None:
                return

            self.get_logger().info(
                f"OCR best text='{best['text']}' score={best['score']:.3f} ok={best['ok']}"
            )

            if best["ok"] and best["score"] >= self.args.min_match:
                with self.lock:
                    if self.candidate_center is not None and dist2(best["center"], self.candidate_center) <= self.args.track_distance:
                        self.candidate_hits += 1
                    else:
                        self.candidate_center = best["center"]
                        self.candidate_hits = 1

                    self.last_ocr_text = best["text"]
                    self.last_score = best["score"]

                    if self.candidate_hits >= self.args.confirm_hits:
                        self.target_center = self.candidate_center
                        self.get_logger().info(
                            f"목표책 확정: hits={self.candidate_hits}, score={best['score']:.3f}"
                        )

        finally:
            self.ocr_busy = False

    def image_callback(self, msg):
        now = time.time()
        min_period = 1.0 / max(0.1, self.args.fps)
        if now - self.last_pub_time < min_period:
            return
        self.last_pub_time = now

        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as e:
            self.get_logger().warn(f"이미지 변환 실패: {e}")
            return

        try:
            detections = self.detect_books(frame)
        except Exception as e:
            self.get_logger().warn(f"YOLO 검출 실패: {e}")
            detections = []

        draw = frame.copy()

        with self.lock:
            target_center = self.target_center

        for det in detections:
            pts = np.array(det["pts"], dtype=np.int32).reshape(-1, 1, 2)
            color = (0, 255, 0)

            if target_center is not None and dist2(det["center"], target_center) <= self.args.track_distance:
                color = (0, 0, 255)

            cv2.polylines(draw, [pts], isClosed=True, color=color, thickness=3)

        if detections and (not self.ocr_busy) and (now - self.last_ocr_time >= self.args.ocr_interval):
            self.last_ocr_time = now
            self.ocr_busy = True
            frame_copy = frame.copy()
            det_copy = [
                {
                    "pts": np.array(d["pts"], dtype=np.float32).copy(),
                    "center": tuple(d["center"]),
                    "conf": d["conf"],
                }
                for d in detections
            ]
            threading.Thread(target=self.ocr_worker, args=(frame_copy, det_copy), daemon=True).start()

        ok, encoded = cv2.imencode(".jpg", draw, [int(cv2.IMWRITE_JPEG_QUALITY), int(self.args.jpeg_quality)])
        if ok:
            out = CompressedImage()
            out.header = msg.header
            out.format = "jpeg"
            out.data = encoded.tobytes()
            self.pub.publish(out)

        if self.args.preview:
            cv2.imshow("book_detection_view", draw)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                rclpy.shutdown()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default="", help="Target book title. If empty, ask interactively.")
    parser.add_argument("--input_topic", default="/camera/color/image_raw")
    parser.add_argument("--output_topic", default="/book_detection/image_raw/compressed")
    parser.add_argument("--model", default="models/book_spine_detector.pt")
    parser.add_argument("--conf", type=float, default=0.30)
    parser.add_argument("--ocr_interval", type=float, default=2.5)
    parser.add_argument("--min_match", type=float, default=0.75)
    parser.add_argument("--fps", type=float, default=15.0)
    parser.add_argument("--confirm_hits", type=int, default=2)
    parser.add_argument("--track_distance", type=float, default=70.0)
    parser.add_argument("--jpeg_quality", type=int, default=80)
    parser.add_argument("--gpu", action="store_true")
    parser.add_argument("--preview", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    rclpy.init()
    node = BookDetectionViewPublisher(args)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
