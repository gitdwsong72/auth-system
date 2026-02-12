#!/bin/bash
# FastAPI + 모니터링 동시 시작
#
# Usage:
#   ./scripts/start-with-monitor.sh

set -e

PROJECT_ROOT="/Users/sktl/WF/WF01/auth-system/auth-service"
FASTAPI_LOG="/tmp/fastapi.log"
VENV_PATH="$PROJECT_ROOT/.venv"

echo "🚀 Auth System 시작 (FastAPI + Monitor)"
echo ""

# 1. 기존 FastAPI 프로세스 종료
echo "⏹️  기존 프로세스 종료 중..."
lsof -ti:8001 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 2

# 2. FastAPI 시작 (백그라운드)
echo "🔧 FastAPI 시작 중..."
cd "$PROJECT_ROOT" || exit 1
nohup "$VENV_PATH/bin/uvicorn" src.main:app --port 8001 --reload > "$FASTAPI_LOG" 2>&1 &
FASTAPI_PID=$!
echo "✅ FastAPI 시작됨 (PID: $FASTAPI_PID, Port: 8001)"

# 3. FastAPI 준비 대기
echo "⏳ FastAPI 준비 대기 중..."
for i in {1..30}; do
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
        echo "✅ FastAPI 준비 완료!"
        break
    fi
    sleep 1
    echo -n "."
done
echo ""

# 4. 모니터링 시작
echo "📊 모니터링 시작..."
sleep 1
exec "$PROJECT_ROOT/scripts/monitor.sh"
