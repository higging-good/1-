# Vision-Based Book Bounding Pipeline

Astra RGB-D 영상에서 책등을 회전 바운딩 박스(OBB)로 검출하고, OCR로 목표 책을 고른 뒤 거리와 각도를 계산해 로봇이 사용할 JSON을 생성합니다.

## Pipeline

```text
Astra RGB-D camera
        │
        ▼
1. capture_rgbd.py
   책 3권 이상이 5초간 보일 때 RGB + depth 저장
        │
        ▼
2. detect_and_match_book.py
   YOLO OBB 검출 → 책등 원근 보정 → 회전/전처리별 EasyOCR
   → 제목 정규화 및 문자열 유사도 비교 → 목표 책 OBB 선택
        │
        ├──────────────► target_info.json (OBB, 중심점, 신뢰도)
        ▼
3. estimate_book_distance.py
   목표 OBB 내부 depth 추출 → 가까운 안정 군집 선택 → 거리 계산
        │
        ▼
4. build_final_result.py
   제목, OCR 결과, 거리, 책 기울기 각도를 final_result.txt로 통합
        │
        ▼
5. export_robot_target.py
   로봇 제어용 book_target_output.json 생성
```

## Directory layout

```text
.
├── run_pipeline.sh                 # 전체 파이프라인 진입점
├── src/
│   ├── settings.py                 # 공통 경로 설정
│   ├── capture_rgbd.py             # Astra RGB-D 자동 촬영
│   ├── detect_and_match_book.py    # OBB 검출, OCR, 제목 매칭
│   ├── estimate_book_distance.py   # depth 기반 거리 계산
│   ├── build_final_result.py       # 최종 텍스트 결과 통합
│   ├── export_robot_target.py      # 로봇용 JSON 변환
│   ├── publish_robot_target.py     # ROS 2 토픽 발행(선택)
│   ├── robot_search_controller.py  # 실패 시 로봇 재탐색(선택)
│   └── log_result.py               # 반복 실험 CSV 기록
├── models/book_spine_detector.pt   # 최종 YOLO OBB 모델
├── data/sample/                    # 카메라 없이 검증할 RGB-D 샘플
└── outputs/                        # 실행 결과(자동 생성)
```

## Run

ROS 2와 Astra 작업공간을 먼저 활성화한 뒤 실행합니다.

```bash
source /opt/ros/humble/setup.bash
source ~/astra_ws/install/setup.bash
source .venv/bin/activate
./run_pipeline.sh "책 제목"
```

카메라 없이 보존된 샘플로 실행하려면 RGB와 depth 경로를 함께 전달합니다.

```bash
./run_pipeline.sh "책 제목" data/sample/bookshelf_rgb.jpg data/sample/bookshelf_depth.npy
```

ROS 토픽 `/book_target_output`으로 결과를 계속 발행하려면 다음을 별도 터미널에서 실행합니다.

```bash
python3 src/publish_robot_target.py
```

## Main outputs

- `outputs/target_result.jpg`: 목표 책 OBB 표시 이미지
- `outputs/target_result_depth.jpg`: 거리까지 표시한 이미지
- `outputs/target_info.json`: 비전 검출 원본 정보
- `outputs/final_result.txt`: 사람이 읽는 요약
- `outputs/book_target_output.json`: 로봇 연동용 결과
- `outputs/target_test_log.csv`: 반복 실험 로그
