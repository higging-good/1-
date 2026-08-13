#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_DIR}"
source /opt/ros/humble/setup.bash
[[ -f "${ASTRA_WS:-$HOME/astra_ws}/install/setup.bash" ]] && source "${ASTRA_WS:-$HOME/astra_ws}/install/setup.bash"
source .venv/bin/activate
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-30}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"

python3 record_boxing_process_video.py \
  --green_seconds 4 \
  --ocr_interval 1.5 \
  --confirm_hits 3 \
  --after_found_seconds 5 \
  --max_seconds 35 \
  --make_h264
