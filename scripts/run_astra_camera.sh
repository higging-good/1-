#!/bin/bash
cd ~/Desktop/졸작 || exit 1
source /opt/ros/humble/setup.bash
source ~/astra_ws/install/setup.bash
export ROS_DOMAIN_ID=0
export ROS_LOCALHOST_ONLY=0

ros2 launch astra_camera astra.launch.xml \
product_id:=0x0404 \
depth_registration:=true \
color_depth_synchronization:=true \
enable_color:=true \
enable_depth:=true \
enable_ir:=false \
enable_point_cloud:=false \
enable_colored_point_cloud:=false \
color_width:=640 \
color_height:=480 \
color_fps:=15 \
depth_width:=640 \
depth_height:=480 \
depth_fps:=15
