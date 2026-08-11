from pathlib import Path
#!/usr/bin/env python3
import argparse
import time
from datetime import datetime

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
from ultralytics import YOLO

from settings import CAPTURE_DIR, LATEST_CAPTURE_FILE, MODEL_PATH, ensure_runtime_directories


class AutoCapture(Node):
    def __init__(self):
        super().__init__("book_rgbd_capture")
        self.bridge = CvBridge()
        self.color = None
        self.depth = None

        self.create_subscription(Image, "/camera/color/image_raw", self.color_cb, 10)
        self.create_subscription(Image, "/camera/depth/image_raw", self.depth_cb, 10)

    def color_cb(self, msg):
        self.color = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")

    def depth_cb(self, msg):
        self.depth = self.bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")


def detect_books(model, img, conf=0.30, margin=20):
    h, w = img.shape[:2]
    vis = img.copy()
    good_count = 0

    results = model.predict(img, conf=conf, imgsz=640, verbose=False)

    if results and results[0].obb is not None and results[0].obb.xyxyxyxy is not None:
        polys = results[0].obb.xyxyxyxy.cpu().numpy()

        for poly in polys:
            pts = poly.reshape(-1, 2).astype(np.int32)

            xs = pts[:, 0]
            ys = pts[:, 1]

            x1, x2 = xs.min(), xs.max()
            y1, y2 = ys.min(), ys.max()

            box_w = x2 - x1
            box_h = y2 - y1

            if box_w < 10 or box_h < 30:
                continue

            cut = (
                x1 < margin or
                y1 < margin or
                x2 > w - margin or
                y2 > h - margin
            )

            if cut:
                color = (0, 165, 255)
                label = "CUT"
            else:
                color = (0, 255, 0)
                label = "BOOK"
                good_count += 1

            cv2.polylines(vis, [pts], True, color, 2)
            cv2.putText(
                vis,
                label,
                (int(x1), max(20, int(y1) - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2
            )

    return good_count, vis


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--settle", type=float, default=5.0)
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--min_books", type=int, default=3)
    parser.add_argument("--model", default=str(MODEL_PATH))
    parser.add_argument("--conf", type=float, default=0.30)
    parser.add_argument("--no_show", action="store_true")
    args = parser.parse_args()

    rclpy.init()
    node = AutoCapture()

    model_path = Path(args.model)
    if not model_path.exists():
        print(f"[ERROR] YOLO 모델 없음: {model_path}")
        raise SystemExit(1)

    model = YOLO(str(model_path))

    start = time.time()
    visible_start = None
    last_check = 0.0
    last_count = 0
    last_vis = None

    print(f"[AUTO_CAPTURE] BOOK {args.min_books}권 이상, {args.settle}초 연속 감지 대기")

    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.03)

        if node.color is None or node.depth is None:
            if time.time() - start > args.timeout:
                print("[ERROR] RGB-D 수신 실패")
                raise SystemExit(1)
            continue

        now = time.time()

        if now - last_check >= 0.35:
            last_count, last_vis = detect_books(model, node.color, conf=args.conf)
            last_check = now

            if last_count >= args.min_books:
                if visible_start is None:
                    visible_start = now
            else:
                visible_start = None

        vis = last_vis if last_vis is not None else node.color.copy()

        elapsed = now - visible_start if visible_start is not None else 0.0
        ok = last_count >= args.min_books

        color = (0, 255, 0) if ok else (0, 0, 255)
        status = f"BOOKS {last_count}/{args.min_books} | {elapsed:.1f}/{args.settle:.1f}s" if ok else f"WAITING BOOKS {last_count}/{args.min_books}"

        cv2.putText(vis, status, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        if not args.no_show:
            cv2.imshow("AUTO BOOK SEARCH PREVIEW", vis)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                cv2.destroyAllWindows()
                raise SystemExit(0)

        if ok and visible_start is not None and elapsed >= args.settle:
            break

        if now - start > args.timeout:
            print("[ERROR] BOOK 3권 이상이 5초 연속 보이지 않음")
            cv2.destroyAllWindows()
            raise SystemExit(2)

    ensure_runtime_directories()
    out = CAPTURE_DIR

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rgb_path = out / f"astra_auto_rgb_{stamp}.jpg"
    depth_path = out / f"astra_auto_depth_{stamp}.npy"

    cv2.imwrite(str(rgb_path), node.color)
    np.save(str(depth_path), node.depth)

    LATEST_CAPTURE_FILE.write_text(f"{rgb_path}\n{depth_path}\n", encoding="utf-8")

    print("[AUTO_CAPTURE] 저장 완료")
    print(f"[RGB]   {rgb_path}")
    print(f"[DEPTH] {depth_path}")

    cv2.destroyAllWindows()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
