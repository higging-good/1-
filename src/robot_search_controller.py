#!/usr/bin/env python3
import argparse
import subprocess
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class BookSearchRobotFlow(Node):
    def __init__(self, cmd_vel_topic="/cmd_vel"):
        super().__init__("book_search_robot_flow")
        self.cmd_pub = self.create_publisher(Twist, cmd_vel_topic, 10)

    def cmd(self, x=0.0, y=0.0, yaw=0.0):
        msg = Twist()
        msg.linear.x = float(x)
        msg.linear.y = float(y)
        msg.angular.z = float(yaw)
        self.cmd_pub.publish(msg)

    def stop(self, sec=1.0):
        end = time.time() + sec
        while time.time() < end:
            self.cmd(0, 0, 0)
            rclpy.spin_once(self, timeout_sec=0.05)

    def move_left(self, sec=0.8, mode="rotate"):
        end = time.time() + sec
        while time.time() < end:
            if mode == "strafe":
                self.cmd(0.0, 0.10, 0.0)
            else:
                self.cmd(0.0, 0.0, 0.25)
            rclpy.spin_once(self, timeout_sec=0.05)
        self.stop(1.0)

    def search_book(self, title):
        project = Path(__file__).resolve().parents[1]
        final_txt = project / "outputs/final_result.txt"
        target_json = project / "outputs/target_info.json"

        cmd = f'''
        cd "{project}"
        source /opt/ros/humble/setup.bash
        source ~/astra_ws/install/setup.bash
        source .venv/bin/activate
        ./run_pipeline.sh "{title}"
        '''

        result = subprocess.run(
            ["bash", "-lc", cmd],
            text=True,
            capture_output=True,
            timeout=80
        )

        print(result.stdout)

        if result.returncode != 0:
            return False

        if not target_json.exists():
            return False

        if not final_txt.exists():
            return False

        text = final_txt.read_text(encoding="utf-8", errors="ignore")

        if "N/A" in text:
            return False

        return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("book_title")
    parser.add_argument("--cmd_vel", default="/cmd_vel")
    parser.add_argument("--left_mode", default="rotate", choices=["rotate", "strafe"])
    parser.add_argument("--left_time", type=float, default=0.8)
    args = parser.parse_args()

    rclpy.init()
    node = BookSearchRobotFlow(args.cmd_vel)

    try:
        print("[1] 정지")
        node.stop(1.0)

        print("[2] 2초 대기")
        node.stop(2.0)

        print("[3] 1차 자동 촬영 + OCR")
        ok = node.search_book(args.book_title)

        if ok:
            print("[SUCCESS] 1차에서 책 찾음")
            node.stop(1.0)
            return

        print("[4] 실패 → 왼쪽 이동")
        node.move_left(sec=args.left_time, mode=args.left_mode)

        print("[5] 2초 대기")
        node.stop(2.0)

        print("[6] 2차 자동 촬영 + OCR")
        ok = node.search_book(args.book_title)

        if ok:
            print("[SUCCESS] 2차에서 책 찾음")
        else:
            print("[FAIL] 2차까지 실패")

        node.stop(1.0)

    finally:
        node.stop(0.5)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
