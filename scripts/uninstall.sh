#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd -P)"
EXPECTED_REMOTE="https://github.com/higging-good/1-.git"

if [[ "${PROJECT_DIR}" == "/" || "${PROJECT_DIR}" == "${HOME}" || ! -d "${PROJECT_DIR}/.git" ]]; then
  echo "[ERROR] 안전한 Git 프로젝트 루트가 아닙니다: ${PROJECT_DIR}"
  exit 1
fi

ACTUAL_REMOTE="$(git -C "${PROJECT_DIR}" remote get-url origin 2>/dev/null || true)"
if [[ "${ACTUAL_REMOTE}" != "${EXPECTED_REMOTE}" && "${ACTUAL_REMOTE}" != "git@github.com:higging-good/1-.git" ]]; then
  echo "[ERROR] 예상한 저장소가 아니므로 삭제하지 않습니다."
  echo "origin: ${ACTUAL_REMOTE:-없음}"
  exit 1
fi

echo "삭제 대상: ${PROJECT_DIR}"
echo "이 작업은 .venv와 outputs를 포함한 프로젝트 폴더 전체를 삭제합니다."
read -r -p "삭제하려면 DELETE book_detection_project 를 입력하세요: " CONFIRM
if [[ "${CONFIRM}" != "DELETE book_detection_project" ]]; then
  echo "취소했습니다."
  exit 0
fi

PARENT_DIR="$(dirname "${PROJECT_DIR}")"
PROJECT_NAME="$(basename "${PROJECT_DIR}")"
cd "${PARENT_DIR}"
python3 - "${PROJECT_DIR}" "${PROJECT_NAME}" <<'PY'
import os, shutil, sys
target = os.path.realpath(sys.argv[1])
name = sys.argv[2]
if os.path.basename(target) != name or not os.path.isdir(os.path.join(target, ".git")):
    raise SystemExit("[ERROR] 최종 안전 검사 실패")
shutil.rmtree(target)
print(f"삭제 완료: {target}")
PY
