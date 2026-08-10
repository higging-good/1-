# Book Detection for Physical AI

Astra RGB-D 카메라와 YOLOv8-OBB, EasyOCR을 이용해 책장에서 목표 책을 찾는 프로젝트입니다.

주요 목적은 **Physical AI Manager / OMX 로봇팔 Imitation Learning에서 사용할 실시간 책 라벨링 카메라 토픽 생성**입니다.

일반 책은 초록색 박스, 목표 책은 빨간색 박스로 표시됩니다.

![book detection demo](docs/book_detection_demo.gif)

---

## 1. 프로젝트 기능

이 프로젝트는 크게 3가지 기능을 제공합니다.

### 1. 실시간 책 라벨링 토픽 생성

Physical AI Manager에서 사용할 수 있도록 라벨링된 카메라 영상을 ROS2 토픽으로 발행합니다.

    입력 토픽:
    /camera/color/image_raw

    출력 토픽:
    /book_detection/image_raw/compressed

흐름은 다음과 같습니다.

    Astra 카메라
    → /camera/color/image_raw
    → YOLOv8-OBB 책등 검출
    → EasyOCR 목표 책 제목 매칭
    → /book_detection/image_raw/compressed
    → Physical AI Manager 입력

### 2. 전체 책 탐지 파이프라인 실행

`run_pipeline.sh`를 사용하면 RGB-D 촬영, 책등 검출, OCR, 거리 계산, 결과 JSON 생성을 한 번에 수행합니다.

최종 결과 예시:

    outputs/book_target_output.json
    outputs/final_result.txt
    outputs/target_result_depth.jpg

### 3. 발표용 영상 저장

`record_boxing_process_video.py`를 사용하면 일반 책은 초록색, 목표 책은 빨간색으로 표시되는 발표용 영상을 저장할 수 있습니다.

---

## 2. 주요 파일

    publish_book_detection_view.py
    실시간 책 라벨링 토픽 생성 코드입니다.

    scripts/run_detection_view.sh
    실시간 책 라벨링 실행 스크립트입니다. 가장 자주 사용합니다.

    scripts/run_astra_camera.sh
    Astra 카메라 실행 스크립트입니다.

    scripts/check_detection_topic.sh
    /book_detection/image_raw/compressed 토픽 확인 스크립트입니다.

    run_pipeline.sh
    책 탐지 전체 파이프라인 실행 스크립트입니다.

    record_boxing_process_video.py
    발표용 영상 저장 코드입니다.

    src/
    촬영, 검출, OCR, 거리 계산, JSON 생성 관련 코드입니다.

    models/book_spine_detector.pt
    YOLOv8-OBB 책등 검출 모델입니다.

    docs/book_detection_demo.gif
    시연 GIF입니다.

---

## 3. 실행 전 필요 조건

다른 컴퓨터에서 실행하려면 아래 환경이 필요합니다.

    Ubuntu 22.04
    ROS2 Humble
    Astra RGB-D 카메라
    Astra ROS2 camera driver
    Python 3
    Git

Astra 카메라 드라이버는 아래 경로에 있다고 가정합니다.

    ~/astra_ws/install/setup.bash

확인 명령:

    ls /opt/ros/humble/setup.bash
    ls ~/astra_ws/install/setup.bash

두 파일이 모두 보여야 합니다.

---

## 4. 처음 사용하는 컴퓨터에서 설치

터미널에서 실행합니다.

    cd ~/Desktop
    git clone https://github.com/higging-good/1-.git "졸작"
    cd ~/Desktop/졸작

Python 가상환경 생성:

    python3 -m venv .venv
    source .venv/bin/activate

패키지 설치:

    pip install --upgrade pip
    pip install -r requirements.txt

스크립트 권한 설정:

    chmod +x scripts/*.sh

---

## 5. 실시간 책 라벨링 실행 방법

터미널 2개를 사용합니다.

### 터미널 1: Astra 카메라 실행

    cd ~/Desktop/졸작
    ./scripts/run_astra_camera.sh

이 터미널은 계속 켜두어야 합니다.

정상 토픽:

    /camera/color/image_raw
    /camera/depth/image_raw

### 터미널 2: 실시간 라벨링 실행

새 터미널에서 실행합니다.

    cd ~/Desktop/졸작
    ./scripts/run_detection_view.sh

실행하면 찾을 책 제목을 입력합니다.

예시:

    Book of Jam

또는:

    THINGS ARE WHAT

정상 동작:

    일반 책: 초록색 OBB 박스
    목표 책: 빨간색 OBB 박스

출력 토픽:

    /book_detection/image_raw/compressed

---

## 6. 토픽 확인

새 터미널에서 실행합니다.

    cd ~/Desktop/졸작
    ./scripts/check_detection_topic.sh

정상 예시:

    /book_detection/image_raw/compressed
    sensor_msgs/msg/CompressedImage
    jpeg
    average rate: 약 4Hz 근처

---

## 7. 현재 실시간 라벨링 설정

`scripts/run_detection_view.sh`에는 현재 아래 설정이 적용되어 있습니다.

    --conf 0.35
    --ocr_interval 0.7
    --min_match 0.90
    --confirm_hits 1
    --track_distance 25
    --fps 15

의미:

    conf 0.35
    YOLO 책등 검출 신뢰도 기준입니다.

    ocr_interval 0.7
    0.7초마다 OCR을 시도합니다.

    min_match 0.90
    입력한 책 제목과 OCR 결과가 90% 이상 비슷할 때 목표 책으로 판단합니다.

    confirm_hits 1
    한 번 제대로 매칭되면 바로 빨간색으로 표시합니다.

    track_distance 25
    빨간 박스가 옆 책으로 튀는 것을 줄이기 위한 추적 거리입니다.

---

## 8. Physical AI Manager와 연결

Physical AI Manager에서 카메라 입력으로 아래 토픽을 사용합니다.

    /book_detection/image_raw/compressed

중요한 점:

    학습 때 사용한 카메라 입력과
    추론 때 사용하는 카메라 입력이 같아야 합니다.

추천 구조:

    데이터 수집:
    /book_detection/image_raw/compressed 사용

    Imitation Learning 학습:
    라벨링된 영상으로 수집한 데이터셋 사용

    추론:
    다시 /book_detection/image_raw/compressed 사용

학습 때 원본 카메라를 사용하고 추론 때 라벨링 영상을 사용하면 입력 형태가 달라져 성능이 떨어질 수 있습니다.

---

## 9. 전체 파이프라인 실행

실시간 토픽이 아니라, 책 탐지 결과와 JSON 파일까지 생성하고 싶을 때 사용합니다.

터미널 1에서 Astra 카메라 실행:

    cd ~/Desktop/졸작
    ./scripts/run_astra_camera.sh

터미널 2에서 전체 파이프라인 실행:

    cd ~/Desktop/졸작
    source /opt/ros/humble/setup.bash
    source ~/astra_ws/install/setup.bash
    source .venv/bin/activate

    ./run_pipeline.sh

또는 제목을 바로 입력해서 실행:

    ./run_pipeline.sh "THINGS ARE WHAT"

주요 결과:

    outputs/book_target_output.json
    outputs/final_result.txt
    outputs/target_result_depth.jpg

---

## 10. 발표용 영상 저장

터미널 1에서 Astra 카메라 실행 후, 다른 터미널에서 실행합니다.

    cd ~/Desktop/졸작
    ./scripts/run_record_demo_video.sh

저장 위치:

    outputs/videos/original/
    outputs/videos/h264/
    outputs/gifs/

---

## 11. 사용 시 주의사항

책 인식과 OCR은 카메라 구도와 조명의 영향을 받습니다.

권장 조건:

    카메라 위치 고정
    책장과 카메라 거리 고정
    조명 유지
    목표 책 제목이 잘 보이도록 배치
    책등이 너무 가려지지 않게 배치

카메라 구도를 계속 바꾸면 가끔 다른 책에 빨간 라벨이 표시될 수 있습니다.  
하지만 고정된 구도에서는 현재 설정으로 목표 책을 안정적으로 찾을 수 있습니다.

---

## 12. 자주 생기는 문제

### 카메라 토픽이 안 보이는 경우

확인:

    ros2 topic list | grep camera

안 보이면 Astra 카메라를 다시 실행합니다.

    cd ~/Desktop/졸작
    ./scripts/run_astra_camera.sh

### Resource busy 오류

Astra 카메라를 다른 프로세스가 잡고 있는 상태입니다.

    pkill -9 -f astra_camera_node 2>/dev/null || true
    pkill -9 -f "ros2 launch astra_camera" 2>/dev/null || true
    pkill -9 -f publish_book_detection_view.py 2>/dev/null || true

    source /opt/ros/humble/setup.bash
    source ~/astra_ws/install/setup.bash

    ros2 daemon stop 2>/dev/null || true
    sleep 2
    ros2 daemon start 2>/dev/null || true

그 다음 카메라 USB를 뽑고 10초 뒤 다시 꽂은 후 카메라를 실행합니다.

### 빨간 박스가 다른 책으로 튀는 경우

`scripts/run_detection_view.sh`에서 아래 값을 줄입니다.

    --track_distance 25

예시:

    --track_distance 20

너무 줄이면 빨간 박스가 자주 풀릴 수 있습니다.

---

## 13. GitHub 사용 방법

처음 받는 컴퓨터:

    cd ~/Desktop
    git clone https://github.com/higging-good/1-.git "졸작"

이미 받은 컴퓨터에서 최신 코드 받기:

    cd ~/Desktop/졸작
    git pull

내 컴퓨터에서 수정 후 GitHub에 올리기:

    cd ~/Desktop/졸작

    git status
    git add 수정한파일
    git commit -m "수정 내용 설명"
    git push

실시간 라벨링 설정만 수정했다면:

    git add scripts/run_detection_view.sh
    git commit -m "Tune realtime detection settings"
    git push

---

## 14. GitHub에 올리지 않는 파일

보통 아래 파일은 GitHub에 올리지 않습니다.

    .venv/
    outputs/
    backups/
    data/
    *.zip
    *_backup_*.py
    *_broken_*.py
    __pycache__/

이 프로젝트에서는 아래 모델 파일이 실행에 필요하므로 저장소에 포함합니다.

    models/book_spine_detector.pt

---

## 15. 빠른 요약

처음 받기:

    git clone https://github.com/higging-good/1-.git "졸작"

카메라 실행:

    ./scripts/run_astra_camera.sh

실시간 라벨링 실행:

    ./scripts/run_detection_view.sh

Physical AI Manager 입력 토픽:

    /book_detection/image_raw/compressed
