#!/bin/bash

echo "===== 졸작 프로젝트 초기화 ====="

cd ~/Desktop || exit 1

if [ -d "졸작" ]; then
    rm -rf 졸작
    echo "졸작 폴더 삭제 완료"
else
    echo "졸작 폴더가 없습니다."
fi

echo ""
echo "다시 다운로드:"
echo "git clone https://github.com/higging-good/1-.git"

