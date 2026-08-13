#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_DIR}"

if [[ ! -f /opt/ros/humble/setup.bash ]]; then
  echo "[ERROR] ROS 2 Humble이 없습니다. Ubuntu 22.04에 ROS 2 Humble을 먼저 설치하세요."
  exit 1
fi

for command_name in python3 git; do
  command -v "${command_name}" >/dev/null || { echo "[ERROR] ${command_name} 명령이 없습니다."; exit 1; }
done

python3 -m venv --help >/dev/null 2>&1 || {
  echo "[ERROR] python3-venv가 없습니다: sudo apt install python3-venv"
  exit 1
}

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install --upgrade torch torchvision --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt

chmod +x scripts/*.sh run_pipeline.sh

python - <<'PY'
from pathlib import Path
import cv2, easyocr, numpy, ultralytics

model = Path("models/book_spine_detector.pt")
if not model.is_file():
    raise SystemExit("[ERROR] 모델 파일이 없습니다: models/book_spine_detector.pt")
print("[OK] OpenCV", cv2.__version__)
print("[OK] EasyOCR", easyocr.__version__)
print("[OK] NumPy", numpy.__version__)
print("[OK] Ultralytics", ultralytics.__version__)
print("[OK] Model", model)
PY

echo
echo "설치 완료"
echo "실행: ./scripts/run_detection_view.sh"
echo "한 대 카메라 예: BOOK_CAMERA_TOPIC=/camera/color/image_raw ./scripts/run_detection_view.sh"
