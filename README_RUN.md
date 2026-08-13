# 실행 요약

전체 설치·설정·코드 설명은 [README.md](README.md)를 확인하세요.

## 기본 실행: 카메라 한 대

```bash
# 터미널 1
cd ~/Desktop/book_detection_project
./scripts/run_astra_camera.sh

# 터미널 2
cd ~/Desktop/book_detection_project
./scripts/run_detection_view.sh
```

## 선택 사항: Physical AI 두 카메라 구성

```bash
BOOK_CAMERA_TOPIC=/camera2/color/image_raw ./scripts/run_detection_view.sh
```

## 토픽 확인

```bash
./scripts/check_detection_topic.sh
```

결과 토픽:

```text
/book_detection/image_raw
/book_detection/image_raw/compressed
```
