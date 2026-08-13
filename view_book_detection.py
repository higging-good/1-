#!/usr/bin/env python3
"""시스템 OpenCV/GTK로 표시하는 책 검출 전용 실시간 뷰어."""

import argparse
import threading

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.executors import ExternalShutdownException
from sensor_msgs.msg import Image


WINDOW_NAME = "book_detection_view"


class BookDetectionViewer(Node):
    def __init__(self, topic):
        super().__init__("book_detection_opencv_viewer")
        self.bridge = CvBridge()
        self.lock = threading.Lock()
        self.latest_frame = None

        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW_NAME, 960, 720)
        cv2.moveWindow(WINDOW_NAME, 20, 20)

        waiting = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(
            waiting,
            "Waiting for detection frames...",
            (65, 245),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
        )
        cv2.imshow(WINDOW_NAME, waiting)
        cv2.waitKey(1)

        self.create_subscription(Image, topic, self.image_callback, qos_profile_sensor_data)
        self.create_timer(1.0 / 30.0, self.render)
        self.get_logger().info(f"전용 OpenCV 뷰어 시작: {topic}")

    def image_callback(self, msg):
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as exc:
            self.get_logger().error(f"영상 변환 실패: {exc}")
            return

        with self.lock:
            self.latest_frame = frame

    def render(self):
        with self.lock:
            frame = self.latest_frame

        if frame is not None:
            cv2.imshow(WINDOW_NAME, frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="/book_detection/image_raw")
    args = parser.parse_args()

    rclpy.init()
    node = BookDetectionViewer(args.topic)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        cv2.destroyAllWindows()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
