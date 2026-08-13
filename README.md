# CPU Book Detection for ROS 2 / Physical AI

Astra 카메라 영상에서 YOLOv8-OBB로 책등을 검출하고 EasyOCR로 사용자가 입력한
책 제목을 찾는 ROS 2 프로젝트입니다. 일반 책은 초록색, 목표 책은 빨간색 OBB로
표시하며 결과를 Physical AI Manager에서 사용할 수 있는 영상 토픽으로 발행합니다.

![Book detection demo](docs/book_detection_demo.gif)

## 주요 특징

- GPU가 없는 컴퓨터에서도 실행되는 CPU 전용 기본 설정
- 세로·회전된 책등을 위한 YOLOv8 OBB 검출
- 영어 및 한글 제목 OCR과 유사도 기반 매칭
- OpenCV 실시간 뷰어 자동 실행
- ROS 2 raw 및 compressed 결과 동시 발행
- Physical AI Manager의 `web_video_server`와 호환되는 RELIABLE QoS
- 설치 위치와 Linux 사용자명에 의존하지 않는 실행 스크립트
- 한 대 카메라와 두 대 카메라 구성을 모두 지원

## 1. 새 컴퓨터 설치 및 시작

### 1.1 권장 환경

- Ubuntu 22.04
- ROS 2 Humble
- Python 3.10
- Git
- Orbbec Astra 계열 RGB 카메라와 동작하는 ROS 2 드라이버

시스템 패키지를 먼저 준비합니다.

```bash
sudo apt update
sudo apt install -y git python3-venv python3-pip \
  python3-opencv ros-humble-cv-bridge ros-humble-sensor-msgs \
  ros-humble-rmw-fastrtps-cpp
```

ROS 2 Humble 설치 자체는 공식 ROS 2 설치 문서를 따릅니다. 설치 확인:

```bash
source /opt/ros/humble/setup.bash
ros2 pkg list | grep -E 'cv_bridge|sensor_msgs'
```

### 1.2 프로젝트 다운로드

저장소 이름은 `1-`이지만 로컬 폴더 이름은 영문으로 지정합니다.

```bash
cd ~/Desktop
git clone https://github.com/higging-good/1-.git book_detection_project
cd book_detection_project
```

`졸작` 같은 한글 경로는 OpenCV/Qt 환경에 따라 깨질 수 있으므로 사용하지 않는 것을
권장합니다. 프로젝트는 다른 위치에 clone해도 스크립트가 현재 위치를 자동 감지합니다.

### 1.3 Python 환경 설치

```bash
./scripts/install.sh
```

설치 스크립트가 다음 작업을 수행합니다.

- `.venv` 생성
- PyTorch 및 TorchVision CPU wheel 설치
- Python 패키지 설치
- NumPy 2.x와 ROS `cv_bridge`의 호환 문제 방지
- 실행 권한 설정
- YOLO 모델과 주요 패키지 확인

`.venv`는 Git에 포함되지 않으므로 새 컴퓨터마다 한 번 실행해야 합니다.

### 1.4 카메라 드라이버 확인

이 프로젝트는 다음 workspace 중 설치된 것을 자동 탐색합니다.

```text
~/orbbec_ws/install/setup.bash
~/astra_ws/install/setup.bash
```

다른 위치에 설치했다면 실행할 때 지정할 수 있습니다.

```bash
ORBBEC_WS=/path/to/orbbec_ws ./scripts/run_detection_view.sh
```

카메라 드라이버 설치 방법은 카메라 모델과 기존 시스템 구성에 따라 다르므로 해당
드라이버 저장소의 ROS 2 Humble 빌드 안내를 따르십시오.

## 2. 빠른 실행 가이드

### 현재 Physical AI 두 카메라 구성

터미널 1에서 카메라 두 대를 실행합니다. 이 파일은 현재 시스템용 외부 실행기입니다.

```bash
~/run_two_astra_clean.sh
```

터미널 2에서 북디텍션을 실행합니다.

```bash
cd ~/Desktop/book_detection_project
./scripts/run_detection_view.sh
```

또는 현재 컴퓨터에 등록된 함수로 실행합니다.

```bash
run_detection
```

프롬프트에 책 제목을 입력합니다.

```text
찾을 책 제목을 입력하세요: BUTTER
```

현재 기본 입력은 `/camera2/color/image_raw`입니다.

### 카메라 한 대인 컴퓨터

카메라 토픽을 확인합니다.

```bash
ros2 topic list | grep image_raw
```

일반적인 한 대 카메라 토픽이 `/camera/color/image_raw`라면 다음처럼 실행합니다.

```bash
BOOK_CAMERA_TOPIC=/camera/color/image_raw ./scripts/run_detection_view.sh
```

카메라 네임스페이스가 다르면 실제 토픽으로 바꾸면 됩니다.

```bash
BOOK_CAMERA_TOPIC=/my_camera/color/image_raw ./scripts/run_detection_view.sh
```

책 제목을 명령행에서 바로 지정할 수도 있습니다.

```bash
./scripts/run_detection_view.sh "BUTTER"
```

### 환경변수 기본값

| 설정 | 기본값 | 용도 |
|---|---|---|
| `BOOK_CAMERA_TOPIC` | `/camera2/color/image_raw` | 북디텍션 입력 영상 |
| `ROS_DOMAIN_ID` | `30` | ROS 2 통신 도메인 |
| `ROS_LOCALHOST_ONLY` | `0` | 다른 프로세스·컨테이너 통신 허용 |
| `BOOK_RMW_IMPLEMENTATION` | `rmw_fastrtps_cpp` | 북디텍션에서 사용할 RMW |
| `FASTRTPS_DEFAULT_PROFILES_FILE` | `config/fastdds_udp_only.xml` | UDP 전송 프로파일 |
| `ORBBEC_WS` | `~/orbbec_ws` | Orbbec workspace 위치 |
| `ASTRA_WS` | `~/astra_ws` | Astra workspace 위치 |

북디텍션 실행기는 `CUDA_VISIBLE_DEVICES=""`를 설정하고 `--gpu`를 사용하지 않으므로
GPU가 장착된 컴퓨터에서도 CPU로 실행됩니다.

## 3. 결과 및 데모 방법

실행 결과:

- 검출된 일반 책: 초록색 OBB
- OCR로 찾은 목표 책: 빨간색 OBB
- `q`: OpenCV 뷰어 종료

발행 토픽:

```text
/book_detection/image_raw
/book_detection/image_raw/compressed
```

토픽과 실제 FPS 확인:

```bash
./scripts/check_detection_topic.sh
```

Physical AI Manager에서는 Robot Type을 `omx_f`로 선택하고 다음 영상을 선택합니다.

```text
/camera1/color/image_raw
/book_detection/image_raw
```

Manager 화면에는 raw 이름만 표시되지만 웹 영상 서버는 내부적으로 compressed 결과를
사용합니다.

발표용 영상 녹화:

```bash
./scripts/run_record_demo_video.sh
```

결과는 `outputs/videos/`에 저장됩니다.

RGB-D 거리 계산을 포함한 기존 전체 파이프라인:

```bash
source .venv/bin/activate
./run_pipeline.sh
```

이 파이프라인은 depth 토픽이 활성화된 단일 Astra 구성용이며, 실시간 Physical AI
북디텍션 데모와는 별도 기능입니다.

## 4. 중요 코드 간략 설명

| 파일 | 역할 |
|---|---|
| `publish_book_detection_view.py` | 카메라 구독, YOLO OBB, OCR, 제목 매칭, 박스 표시 및 ROS 결과 발행 |
| `view_book_detection.py` | 시스템 OpenCV로 raw 결과를 표시하는 독립 GUI 뷰어 |
| `scripts/run_detection_view.sh` | ROS/FastDDS/CPU 환경 설정, 뷰어와 추론 프로세스 실행·종료 관리 |
| `scripts/install.sh` | 새 컴퓨터의 Python 환경 설치와 모델 검증 |
| `scripts/check_detection_topic.sh` | 결과 토픽 타입·메시지·FPS 확인 |
| `scripts/run_astra_camera.sh` | 단일 `ros2_astra_camera` RGB 카메라 실행 |
| `scripts/run_record_demo_video.sh` | 발표용 데모 영상 녹화 |
| `run_pipeline.sh` | RGB-D 캡처부터 거리·각도·로봇용 JSON까지 생성하는 기존 파이프라인 |
| `models/book_spine_detector.pt` | 학습된 YOLOv8-OBB 책등 검출 모델 |
| `config/fastdds_udp_only.xml` | 호스트와 컨테이너 통신용 Fast DDS UDP 프로파일 |

실시간 처리 흐름:

```text
camera image
  -> YOLOv8-OBB book-spine detection
  -> rotated crop generation
  -> EasyOCR in multiple orientations
  -> target-title similarity matching
  -> green/red OBB drawing
  -> raw + JPEG compressed ROS topics
```

## 5. 업데이트 방법

로컬 수정이 없다면:

```bash
cd ~/Desktop/book_detection_project
git pull origin main
./scripts/install.sh
```

`requirements.txt`가 변경될 수 있으므로 업데이트 후 설치 스크립트를 다시 실행하는 것이
안전합니다.

## 6. 프로젝트 삭제

프로젝트 폴더, `.venv`, 생성 결과를 모두 삭제하려면 프로젝트 안에서 실행합니다.

```bash
cd ~/Desktop/book_detection_project
./scripts/uninstall.sh
```

스크립트는 다음 조건을 모두 확인한 뒤에만 삭제합니다.

- 현재 폴더가 Git 저장소인지 확인
- `origin`이 `https://github.com/higging-good/1-.git`인지 확인
- 실제 삭제 대상 절대 경로 출력
- `DELETE book_detection_project` 확인 문구 요구

ROS 2, 카메라 드라이버 workspace 및 시스템 패키지는 다른 프로젝트에서도 사용할 수
있으므로 삭제하지 않습니다.

## 문제 해결

카메라 토픽이 안 보이는 경우:

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=30
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
ros2 topic list | grep image_raw
```

Physical AI Manager에서 영상이 비어 있으면 북디텍션이 실행 중인지 확인하고 Manager에서
`Refresh` 후 `/book_detection/image_raw`를 다시 선택합니다.

CPU 실행 확인은 시작 로그의 다음 문구로 할 수 있습니다.

```text
Using CPU
```
