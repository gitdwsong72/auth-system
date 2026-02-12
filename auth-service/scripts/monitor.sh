#!/bin/bash
# Solid Cache + FastAPI 통합 모니터링 (tmux)
#
# 4-pane 레이아웃:
# ┌─────────────────────┬─────────────────────┐
# │  FastAPI Logs       │  Solid Cache Stats  │
# ├─────────────────────┼─────────────────────┤
# │  Redis Status       │  Health Check       │
# └─────────────────────┴─────────────────────┘
#
# Usage:
#   ./scripts/monitor.sh
#   ./scripts/monitor.sh --session-name my-monitor

set -e

# 변수 설정
SESSION_NAME="${1:-auth-monitor}"
PROJECT_ROOT="/Users/sktl/WF/WF01/auth-system/auth-service"
FASTAPI_LOG="/tmp/fastapi.log"
DB_URL="postgresql://devuser:devpassword@localhost:5433/appdb"
REDIS_URL="redis://localhost:6380/0"
API_URL="http://localhost:8001"

# 색상 정의
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Auth System Monitor 시작${NC}"
echo -e "${BLUE}Session: ${SESSION_NAME}${NC}"

# 기존 세션 종료
tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true

# 새 세션 생성 (detached)
cd "$PROJECT_ROOT" || exit 1
tmux new-session -d -s "$SESSION_NAME" -n "monitor"

# ===== Pane 0: FastAPI Logs (좌상단) =====
tmux send-keys -t "$SESSION_NAME:0.0" "cd $PROJECT_ROOT" C-m
tmux send-keys -t "$SESSION_NAME:0.0" "echo -e '${YELLOW}━━━ FastAPI Application Logs ━━━${NC}'" C-m
tmux send-keys -t "$SESSION_NAME:0.0" "tail -f $FASTAPI_LOG 2>/dev/null || echo 'FastAPI 로그 대기 중...'" C-m

# ===== Pane 1: Solid Cache Stats (우상단) =====
tmux split-window -t "$SESSION_NAME:0" -h
tmux send-keys -t "$SESSION_NAME:0.1" "cd $PROJECT_ROOT" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "echo -e '${YELLOW}━━━ Solid Cache Statistics (실시간) ━━━${NC}'" C-m
tmux send-keys -t "$SESSION_NAME:0.1" 'watch -n 5 "PGPASSWORD=devpassword psql -h localhost -p 5433 -U devuser -d appdb -c \"SELECT COUNT(*) as total_entries, COUNT(*) FILTER (WHERE expires_at < NOW()) as expired_entries, pg_size_pretty(pg_total_relation_size('\''solid_cache_entries'\'')) as total_size FROM solid_cache_entries;\" 2>/dev/null || echo '\''PostgreSQL 연결 대기 중...'\''"' C-m

# ===== Pane 2: Redis Status (좌하단) =====
tmux split-window -t "$SESSION_NAME:0.0" -v
tmux send-keys -t "$SESSION_NAME:0.2" "cd $PROJECT_ROOT" C-m
tmux send-keys -t "$SESSION_NAME:0.2" "echo -e '${YELLOW}━━━ Redis Status ━━━${NC}'" C-m
tmux send-keys -t "$SESSION_NAME:0.2" 'watch -n 5 "redis-cli -h localhost -p 6380 INFO stats 2>/dev/null | grep -E '\''(total_connections|total_commands|keyspace_hits|keyspace_misses)'\'' || echo '\''Redis 연결 대기 중...'\''"' C-m

# ===== Pane 3: Health Check + Cleanup Logs (우하단) =====
tmux split-window -t "$SESSION_NAME:0.1" -v
tmux send-keys -t "$SESSION_NAME:0.3" "cd $PROJECT_ROOT" C-m
tmux send-keys -t "$SESSION_NAME:0.3" "echo -e '${YELLOW}━━━ Health Check + Cleanup Events ━━━${NC}'" C-m
tmux send-keys -t "$SESSION_NAME:0.3" 'while true; do clear; echo "=== Health Check ==="; curl -s http://localhost:8001/health 2>/dev/null | jq -C 2>/dev/null || echo "API 연결 대기 중..."; echo ""; echo "=== Recent Cleanup Events ==="; grep "cache_cleanup" /tmp/fastapi.log 2>/dev/null | tail -5 || echo "로그 대기 중..."; sleep 10; done' C-m

# 레이아웃 조정 (pane 크기 균등화)
tmux select-layout -t "$SESSION_NAME:0" tiled

# 세션 attach
echo -e "${GREEN}✅ Monitor 세션 생성 완료${NC}"
echo -e "${BLUE}Attaching to session: ${SESSION_NAME}${NC}"
echo ""
echo -e "${YELLOW}사용법:${NC}"
echo "  • Ctrl+B, D         : Detach (백그라운드로)"
echo "  • Ctrl+B, 화살표   : Pane 이동"
echo "  • Ctrl+B, [        : 스크롤 모드 (q로 종료)"
echo "  • exit 또는 Ctrl+D : 세션 종료"
echo ""
sleep 2

tmux attach-session -t "$SESSION_NAME"
