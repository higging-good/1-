#!/usr/bin/env python3
import json
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from settings import OUTPUT_DIR


class BookTargetPublisher(Node):
    def __init__(self):
        super().__init__("book_target_output_publisher")

        self.pub = self.create_publisher(String, "/book_target_output", 10)

        self.json_path = OUTPUT_DIR / "book_target_output.json"
        self.last_text = ""

        self.timer = self.create_timer(0.5, self.publish_json)

        self.get_logger().info("Publishing /book_target_output")
        self.get_logger().info(f"JSON file: {self.json_path}")

    def publish_json(self):
        if not self.json_path.exists():
            data = {
                "target_found": False,
                "quality": "NO_FILE",
                "message": "book_target_output.json not found"
            }
        else:
            try:
                data = json.loads(self.json_path.read_text(encoding="utf-8"))
            except Exception as e:
                data = {
                    "target_found": False,
                    "quality": "JSON_ERROR",
                    "message": str(e)
                }

        msg = String()
        msg.data = json.dumps(data, ensure_ascii=False)
        self.pub.publish(msg)


def main():
    rclpy.init()
    node = BookTargetPublisher()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("\n[STOP] book target publisher 종료")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
