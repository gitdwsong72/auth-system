#!/bin/bash
# 시스템 테스트 실시간 모니터링 대시보드
#
# 4-pane 레이아웃:
# ┌──────────────────┬──────────────────┐
# │ Task Status      │ FastAPI Logs     │
# ├──────────────────┼──────────────────┤
# │ Solid Cache Stats│ Test Results     │
# └──────────────────┴──────────────────┘

set -e

SESSION_NAME="${1:-test-dashboard}"
PROJECT_ROOT="/Users/sktl/WF/WF01/auth-system/auth-service"

echo "🔍 시스템 테스트 모니터링 시작"
echo "Session: $SESSION_NAME"

# 기존 세션 종료
tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true

# 새 세션 생성
cd "$PROJECT_ROOT" || exit 1
tmux new-session -d -s "$SESSION_NAME" -n "monitor"

# Pane 0: Task Status (좌상단)
tmux send-keys -t "$SESSION_NAME" "cd $PROJECT_ROOT" C-m
tmux send-keys -t "$SESSION_NAME" "echo '━━━ Task Status (실시간) ━━━'" C-m
tmux send-keys -t "$SESSION_NAME" "watch -n 2 'cat ~/.claude/tasks/system-test-team/*.json 2>/dev/null | jq -s \"map({id: .id, subject: .subject, status: .status, owner: .owner}) | sort_by(.id)\" 2>/dev/null || echo \"Loading...\"'" C-m

# Pane 1: FastAPI Logs (우상단)
tmux split-window -h
tmux send-keys "cd $PROJECT_ROOT" C-m
tmux send-keys "echo '━━━ FastAPI Server Logs ━━━'" C-m
tmux send-keys "tail -f /tmp/fastapi_final.log 2>/dev/null || echo 'Server not running. Start with: uvicorn src.main:app --port 8001'" C-m

# Pane 2: Solid Cache Stats (좌하단)
tmux select-pane -t 0
tmux split-window -v
tmux send-keys "cd $PROJECT_ROOT" C-m
tmux send-keys "echo '━━━ Solid Cache Statistics ━━━'" C-m
tmux send-keys "watch -n 3 'curl -s http://localhost:8001/metrics/solid-cache 2>/dev/null | jq . || echo \"API not responding\"'" C-m

# Pane 3: Test Results (우하단)
tmux select-pane -t 1
tmux split-window -v
tmux send-keys "cd $PROJECT_ROOT" C-m
tmux send-keys "echo '━━━ Latest Test Results ━━━'" C-m
tmux send-keys "watch -n 5 'ls -lt tests/system/*.py 2>/dev/null | head -10 || echo \"No tests found\"'" C-m

# 레이아웃 조정
tmux select-layout tiled
tmux select-pane -t 0

echo "✅ 모니터링 대시보드 생성 완료!"
echo ""
echo "Attach: tmux attach -t $SESSION_NAME"
echo "Detach: Ctrl+B, D"
echo ""
echo "Panes:"
echo "  - Top Left: Task 상태 (2초 갱신)"
echo "  - Top Right: FastAPI 로그"
echo "  - Bottom Left: Solid Cache 통계 (3초 갱신)"
echo "  - Bottom Right: 테스트 파일 목록 (5초 갱신)"

# 자동 attach
tmux attach-session -t "$SESSION_NAME"
