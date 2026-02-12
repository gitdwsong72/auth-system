#!/bin/bash
# 간단한 시스템 모니터링 대시보드
# 4-pane 레이아웃으로 실시간 정보 표시

set -e

SESSION_NAME="${1:-monitor}"
PROJECT_ROOT="/Users/sktl/WF/WF01/auth-system/auth-service"

echo "🔍 시스템 모니터링 시작"
echo "Session: $SESSION_NAME"

# 기존 세션 종료
tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true

# 새 세션 생성 및 첫 번째 창 설정
cd "$PROJECT_ROOT" || exit 1
tmux new-session -d -s "$SESSION_NAME"

# 첫 번째 pane (기본)
tmux send-keys -t "$SESSION_NAME" "cd $PROJECT_ROOT" Enter
tmux send-keys -t "$SESSION_NAME" "clear && echo '━━━ Task Status ━━━' && echo '' && cat ~/.claude/tasks/system-test-team/*.json 2>/dev/null | jq -r '.subject + \" [\" + .status + \"]\"' || echo 'Loading...'" Enter

# 수평 분할 (오른쪽)
tmux split-window -h -t "$SESSION_NAME"
tmux send-keys -t "$SESSION_NAME" "cd $PROJECT_ROOT" Enter
tmux send-keys -t "$SESSION_NAME" "clear && echo '━━━ FastAPI Logs ━━━' && echo '' && tail -f /tmp/fastapi_final.log 2>/dev/null || echo 'Server not running'" Enter

# 첫 번째 pane 선택 후 수직 분할 (아래)
tmux select-pane -t "$SESSION_NAME:0.0"
tmux split-window -v -t "$SESSION_NAME"
tmux send-keys -t "$SESSION_NAME" "cd $PROJECT_ROOT" Enter
tmux send-keys -t "$SESSION_NAME" "clear && echo '━━━ Solid Cache Stats ━━━' && echo '' && watch -n 3 'curl -s http://localhost:8001/metrics/solid-cache 2>/dev/null | jq . || echo \"API not responding\"'" Enter

# 두 번째 pane (오른쪽) 선택 후 수직 분할 (아래)
tmux select-pane -t "$SESSION_NAME:0.1"
tmux split-window -v -t "$SESSION_NAME"
tmux send-keys -t "$SESSION_NAME" "cd $PROJECT_ROOT" Enter
tmux send-keys -t "$SESSION_NAME" "clear && echo '━━━ Test Files ━━━' && echo '' && ls -lht tests/system/*.py | head -10" Enter

echo ""
echo "✅ 모니터링 세션 생성 완료!"
echo ""
echo "Attach: tmux attach -t $SESSION_NAME"
echo "Detach: Ctrl+B, D"
echo ""

# 자동 attach
tmux attach-session -t "$SESSION_NAME"
