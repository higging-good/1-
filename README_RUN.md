# 히낑이 졸작 실행 가이드

Astra RGB-D 카메라 1개로 책장을 보고, YOLOv8-OBB와 EasyOCR로 사용자가 입력한 목표 책을 찾는 프로젝트입니다.

일반 책은 초록색 박스, 목표 책은 빨간색 박스로 표시합니다.

## 주요 파일

- run_pipeline.sh : 원래 책 찾기 전체 데모
- record_boxing_process_video.py : 발표 영상 저장용 코드
- publish_book_detection_view.py : Physical AI Manager 입력용 실시간 라벨링 토픽 발행 코드
- models/book_spine_detector.pt : YOLOv8-OBB 책등 검출 모델
- scripts/run_astra_camera.sh : Astra 카메라 실행
- scripts/run_detection_view.sh : 실시간 라벨링 토픽 실행
- scripts/check_detection_topic.sh : 토픽 확인
- scripts/run_record_demo_video.sh : 발표 영상 저장

## 1. 카메라 실행

터미널 1에서 실행:

cd ~/Desktop/졸작
./scripts/run_astra_camera.sh

정상 토픽:
- /camera/color/image_raw
- /camera/depth/image_raw

## 2. 원래 책 찾기 데모 실행

터미널 2에서 실행:

cd ~/Desktop/졸작
source /opt/ros/humble/setup.bash
source ~/astra_ws/install/setup.bash
source .venv/bin/activate
export ROS_DOMAIN_ID=0
export ROS_LOCALHOST_ONLY=0
./run_pipeline.sh

## 3. 발표 영상 저장

cd ~/Desktop/졸작
./scripts/run_record_demo_video.sh

영상 저장 위치:
- outputs/videos/original/
- outputs/videos/h264/
- outputs/gifs/

## 4. Physical AI Manager용 실시간 라벨링 토픽

cd ~/Desktop/졸작
./scripts/run_detection_view.sh

책 제목을 물어보면 목표 책 제목을 입력합니다.

출력 토픽:
- /book_detection/image_raw/compressed

토픽 타입:
- sensor_msgs/msg/CompressedImage

## 5. 토픽 확인

cd ~/Desktop/졸작
./scripts/check_detection_topic.sh

정상 예시:
- /book_detection/image_raw/compressed
- sensor_msgs/msg/CompressedImage
- jpeg
- average rate: 약 4 Hz

## 6. 주의사항

- publish_book_detection_view.py는 계속 실행되는 것이 정상입니다.
- 멈추려면 Ctrl + C를 누릅니다.
- record_boxing_process_video.py는 발표 영상 저장용이며, 빨간 박스가 뜨면 일정 시간 뒤 자동 종료됩니다.
- Physical AI Manager에서는 /book_detection/image_raw/compressed 토픽을 카메라 입력으로 사용하면 됩니다.
