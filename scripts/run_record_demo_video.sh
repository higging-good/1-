#!/bin/bash
cd ~/Desktop/졸작 || exit 1
source /opt/ros/humble/setup.bash
source ~/astra_ws/install/setup.bash
source .venv/bin/activate
export ROS_DOMAIN_ID=0
export ROS_LOCALHOST_ONLY=0

python3 record_boxing_process_video.py \
  --green_seconds 4 \
  --ocr_interval 1.5 \
  --confirm_hits 3 \
  --after_found_seconds 5 \
  --max_seconds 35 \
  --make_h264
