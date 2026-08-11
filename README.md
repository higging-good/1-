Book Detection for Physical AI

Astra RGB-D Camera와 YOLOv8-OBB, EasyOCR을 이용한 목표 도서 인식 시스템입니다.

본 프로젝트는 Physical AI Manager와 OMX 로봇팔 Imitation Learning에서 사용할 수 있도록 책 인식 결과를 ROS2 영상 토픽으로 생성하는 것을 목표로 합니다.

주요 기능:

YOLOv8-OBB 기반 책등 검출
회전된 책등 인식
EasyOCR 기반 도서명 인식
목표 도서 판단
RGB-D Depth 기반 거리 계산
OBB 기반 책 기울기 각도 계산
ROS2 기반 라벨링 영상 토픽 생성
1. 새 컴퓨터 설치 방법
1-1. 개발 환경

필수 환경:

Ubuntu 22.04
ROS2 Humble
Python 3.10
Git
Orbbec Astra Mini RGB-D Camera

1-2. ROS2 Humble 설치

Ubuntu 22.04 환경에서 ROS2 Humble 설치 후 진행합니다.

설치 확인:

ros2 --version

1-3. Astra Mini RGB-D Camera Driver 설치

본 프로젝트는 Orbbec Astra Mini RGB-D Camera를 사용합니다.

ROS2에서 Astra 카메라 데이터를 사용하기 위해 Orbbec ROS2 Camera Driver 설치가 필요합니다.

Astra workspace 생성

cd ~

mkdir -p ~/astra_ws/src

cd ~/astra_ws/src

Orbbec Astra Driver 다운로드

git clone https://github.com/orbbec/ros2_astra_camera.git

Driver 빌드

cd ~/astra_ws

source /opt/ros/humble/setup.bash

rosdep update

rosdep install --from-paths src --ignore-src -r -y

colcon build

환경 적용:

source ~/astra_ws/install/setup.bash

설치 확인:

ros2 pkg list | grep astra_camera

정상 출력:

astra_camera

1-4. 프로젝트 다운로드

cd ~/Desktop

git clone https://github.com/higging-good/1-.git 졸작

cd ~/Desktop/졸작

2. 프로젝트 환경 설치
2-1. Python 가상환경 생성

python3 -m venv .venv

source .venv/bin/activate

2-2. Python 패키지 설치

pip install --upgrade pip

pip install -r requirements.txt

2-3. 실행 권한 설정

chmod +x scripts/*.sh

3. 코드 설명 및 데모 방법
3-1. 주요 파일

publish_book_detection_view.py

실시간 책 라벨링 ROS2 토픽 생성 코드

scripts/run_detection_view.sh

실시간 책 라벨링 실행

scripts/run_astra_camera.sh

Astra 카메라 실행

scripts/check_detection_topic.sh

책 라벨링 토픽 확인

run_pipeline.sh

RGB-D 촬영 → YOLO → OCR → 거리 계산 → 결과 생성

record_boxing_process_video.py

발표용 영상 저장

models/book_spine_detector.pt

YOLOv8-OBB 학습 모델

3-2. Astra 카메라 실행

터미널 1:

cd ~/Desktop/졸작

source /opt/ros/humble/setup.bash

source ~/astra_ws/install/setup.bash

./scripts/run_astra_camera.sh

정상 토픽:

/camera/color/image_raw

/camera/depth/image_raw

3-3. 실시간 책 라벨링 실행 (주요 기능)

터미널 2:

cd ~/Desktop/졸작

source /opt/ros/humble/setup.bash

source ~/astra_ws/install/setup.bash

source .venv/bin/activate

./scripts/run_detection_view.sh

실행 후:

찾을 책 제목 입력

예:

BUTTER

결과:

일반 책 → 초록색 박스

목표 책 → 빨간색 박스

생성 토픽:

/book_detection/image_raw/compressed

Physical AI Manager에서는 해당 토픽을 카메라 입력으로 사용합니다.

3-4. 전체 Pipeline 실행

실행:

./run_pipeline.sh

입력:

찾을 책 제목:

예:

BUTTER

생성 결과:

outputs/book_target_output.json

outputs/final_result.txt

outputs/target_result_depth.jpg

결과 이미지에는:

목표 책 위치
거리값
책 기울기 각도

가 표시됩니다.

3-5. 발표용 영상 저장

실행:

./scripts/run_record_demo_video.sh

저장 위치:

outputs/videos/

4. Imitation Learning 연동 방법

본 시스템은 OMX 로봇팔 Imitation Learning의 Vision 입력 데이터 생성에 활용됩니다.

데이터 흐름:

Astra RGB-D Camera

↓

YOLOv8-OBB 책 검출

↓

목표 책 위치 계산

↓

Depth 기반 거리 계산

↓

책 방향 및 각도 계산

↓

Robot Action 데이터 생성

↓

Imitation Learning 학습

↓

로봇팔 책 집기 수행

Physical AI Manager 입력 토픽:

/book_detection/image_raw/compressed

추천 데이터 구성:

dataset/

image/

depth/

book_position/

distance/

angle/

robot_action/

주의:

학습 데이터 수집 환경과 실제 추론 환경의 카메라 입력 형태는 동일하게 유지해야 합니다.

5. 삭제 및 재설치 방법
프로젝트 삭제

cd ~/Desktop

rm -rf 졸작

Astra Driver 삭제

rm -rf ~/astra_ws

다시 설치

cd ~/Desktop

git clone https://github.com/higging-good/1-.git 졸작

빠른 실행 요약

카메라 실행:

./scripts/run_astra_camera.sh

실시간 책 라벨링:

./scripts/run_detection_view.sh

전체 Pipeline:

./run_pipeline.sh

Physical AI Manager 입력:

/book_detection/image_raw/compressed