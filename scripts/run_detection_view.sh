#!/bin/bash
cd ~/Desktop/졸작 || exit 1
source /opt/ros/humble/setup.bash
source ~/astra_ws/install/setup.bash
source .venv/bin/activate
export ROS_DOMAIN_ID=0
export ROS_LOCALHOST_ONLY=0

python3 publish_book_detection_view.py \
  --input_topic /camera/color/image_raw \
  --output_topic /book_detection/image_raw/compressed \
  --model models/book_spine_detector.pt \
  --conf 0.30 \
  --ocr_interval 2.5 \
  --min_match 0.75 \
  --fps 15 \
  --preview
