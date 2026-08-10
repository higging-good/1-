#!/bin/bash
source /opt/ros/humble/setup.bash
source ~/astra_ws/install/setup.bash
export ROS_DOMAIN_ID=0
export ROS_LOCALHOST_ONLY=0

echo "===== 토픽 목록 ====="
ros2 topic list | grep -E "book_detection|compressed|camera"

echo ""
echo "===== 타입 확인 ====="
ros2 topic type /book_detection/image_raw/compressed

echo ""
echo "===== 메시지 확인 ====="
timeout 8 ros2 topic echo /book_detection/image_raw/compressed --once --field format

echo ""
echo "===== FPS 확인 ====="
timeout 15 ros2 topic hz /book_detection/image_raw/compressed
