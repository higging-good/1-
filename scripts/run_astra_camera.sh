#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_DIR}"
source /opt/ros/humble/setup.bash
ASTRA_SETUP="${ASTRA_WS:-$HOME/astra_ws}/install/setup.bash"
[[ -f "${ASTRA_SETUP}" ]] || { echo "[ERROR] Astra driver not found: ${ASTRA_SETUP}"; exit 1; }
source "${ASTRA_SETUP}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-30}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"

ros2 launch astra_camera astra.launch.xml \
product_id:=0x0404 \
depth_registration:=false \
color_depth_synchronization:=false \
enable_color:=true \
enable_depth:=false \
enable_ir:=false \
enable_point_cloud:=false \
enable_colored_point_cloud:=false \
color_width:=640 \
color_height:=480 \
color_fps:=30
