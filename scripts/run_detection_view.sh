#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_DIR}"

source /opt/ros/humble/setup.bash
if [[ -f "${ORBBEC_WS:-$HOME/orbbec_ws}/install/setup.bash" ]]; then
  source "${ORBBEC_WS:-$HOME/orbbec_ws}/install/setup.bash"
elif [[ -f "${ASTRA_WS:-$HOME/astra_ws}/install/setup.bash" ]]; then
  source "${ASTRA_WS:-$HOME/astra_ws}/install/setup.bash"
fi

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-30}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
export RMW_IMPLEMENTATION="${BOOK_RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
export FASTRTPS_DEFAULT_PROFILES_FILE="${FASTRTPS_DEFAULT_PROFILES_FILE:-${PROJECT_DIR}/config/fastdds_udp_only.xml}"
export CUDA_VISIBLE_DEVICES=""

BOOK_CAMERA_TOPIC="${BOOK_CAMERA_TOPIC:-/camera2/color/image_raw}"
BOOK_TARGET="${1:-}"
TARGET_ARGS=()
[[ -n "${BOOK_TARGET}" ]] && TARGET_ARGS=(--target "${BOOK_TARGET}")

if [[ ! -x "${PROJECT_DIR}/.venv/bin/python3" ]]; then
  echo "[ERROR] 가상환경이 없습니다. 먼저 ./scripts/install.sh 를 실행하세요."
  exit 1
fi

PYTHONNOUSERSITE=1 /usr/bin/python3 view_book_detection.py \
  --topic /book_detection/image_raw &
VIEWER_PID=$!

cleanup() {
  if kill -0 "$VIEWER_PID" 2>/dev/null; then
    kill "$VIEWER_PID" 2>/dev/null || true
    wait "$VIEWER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

source .venv/bin/activate

python3 publish_book_detection_view.py \
  "${TARGET_ARGS[@]}" \
  --input_topic "${BOOK_CAMERA_TOPIC}" \
  --output_topic /book_detection/image_raw/compressed \
  --raw_output_topic /book_detection/image_raw \
  --model models/book_spine_detector.pt \
  --conf 0.35 \
  --ocr_interval 0.7 \
  --min_match 0.90 \
  --confirm_hits 1 \
  --track_distance 25 \
  --fps 15 \
  --torch_threads 4 \
  --languages auto
