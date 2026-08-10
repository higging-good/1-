#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"
export MPLCONFIGDIR="${TMPDIR:-/tmp}/book-bounding-matplotlib"
mkdir -p "$MPLCONFIGDIR"

TITLE="${1:-}"
RGB_IMAGE="${2:-}"
DEPTH_FILE="${3:-}"

if [[ -z "$TITLE" ]]; then
    read -r -p "찾을 책 제목: " TITLE
fi
if [[ -z "$TITLE" ]]; then
    echo "[ERROR] 책 제목이 비어 있습니다."
    exit 1
fi

mkdir -p outputs data/captures
find outputs -maxdepth 1 -type f ! -name 'target_test_log.csv' -delete

if [[ -z "$RGB_IMAGE" || -z "$DEPTH_FILE" ]]; then
    echo "[1/5] Astra RGB-D 자동 촬영"
    python3 src/capture_rgbd.py --settle 5.0 --timeout 45.0 --min_books 3
    RGB_IMAGE="$(sed -n '1p' outputs/latest_capture.txt)"
    DEPTH_FILE="$(sed -n '2p' outputs/latest_capture.txt)"
else
    echo "[1/5] 전달받은 RGB-D 파일 사용"
fi

[[ -f "$RGB_IMAGE" ]] || { echo "[ERROR] RGB image not found: $RGB_IMAGE"; exit 2; }
[[ -f "$DEPTH_FILE" ]] || { echo "[ERROR] depth file not found: $DEPTH_FILE"; exit 2; }

echo "[2/5] YOLO OBB 검출 + OCR 제목 매칭"
python3 src/detect_and_match_book.py "$TITLE" "$RGB_IMAGE"

echo "[3/5] 목표 책 깊이 거리 계산"
python3 src/estimate_book_distance.py \
    outputs/target_info.json "$DEPTH_FILE" outputs/target_result.jpg

echo "[4/5] 사람이 읽는 최종 결과 생성"
python3 src/build_final_result.py

echo "[5/5] 로봇 연동용 JSON 생성"
python3 src/export_robot_target.py
python3 src/log_result.py

echo
cat outputs/final_result.txt
echo "결과 이미지: outputs/target_result_depth.jpg"
echo "로봇용 JSON: outputs/book_target_output.json"
