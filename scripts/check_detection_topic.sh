#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
source /opt/ros/humble/setup.bash
[[ -f "${ORBBEC_WS:-$HOME/orbbec_ws}/install/setup.bash" ]] && source "${ORBBEC_WS:-$HOME/orbbec_ws}/install/setup.bash"
[[ -f "${ASTRA_WS:-$HOME/astra_ws}/install/setup.bash" ]] && source "${ASTRA_WS:-$HOME/astra_ws}/install/setup.bash"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-30}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
export RMW_IMPLEMENTATION="${BOOK_RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
export FASTRTPS_DEFAULT_PROFILES_FILE="${FASTRTPS_DEFAULT_PROFILES_FILE:-${PROJECT_DIR}/config/fastdds_udp_only.xml}"

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
