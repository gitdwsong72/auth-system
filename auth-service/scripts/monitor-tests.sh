#!/bin/bash
# 시스템 테스트 tmux 모니터링
#
# 5-pane 레이아웃:
# ┌──────────────┬──────────────┬──────────────┐
# │ API Test     │ Cache Test   │ Perf Test    │
# ├──────────────┴──────────────┴──────────────┤
# │ Security Test│ Integration  │              │
# └──────────────┴──────────────┴──────────────┘

set -e

SESSION_NAME="${1:-test-monitor}"
PROJECT_ROOT="/Users/sktl/WF/WF01/auth-system/auth-service"

echo "🧪 시스템 테스트 모니터링 시작"
echo "Session: $SESSION_NAME"

# 기존 세션 종료
tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true

# 새 세션 생성
cd "$PROJECT_ROOT" || exit 1
tmux new-session -d -s "$SESSION_NAME" -n "tests"

# Pane 0: API Endpoint Tests (좌상단)
tmux send-keys -t "$SESSION_NAME:0.0" "cd $PROJECT_ROOT" C-m
tmux send-keys -t "$SESSION_NAME:0.0" "echo '━━━ API Endpoint Tests ━━━'" C-m
tmux send-keys -t "$SESSION_NAME:0.0" "tail -f ~/.claude/tasks/system-test-team/1/output.jsonl 2>/dev/null | jq -r '.content // empty' || echo 'Task 1 대기 중...'" C-m

# Pane 1: Solid Cache Tests (중앙 상단)
tmux split-window -t "$SESSION_NAME:0" -h
tmux send-keys -t "$SESSION_NAME:0.1" "cd $PROJECT_ROOT" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "echo '━━━ Solid Cache Tests ━━━'" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "tail -f ~/.claude/tasks/system-test-team/2/output.jsonl 2>/dev/null | jq -r '.content // empty' || echo 'Task 2 대기 중...'" C-m

# Pane 2: Performance Tests (우상단)
tmux split-window -t "$SESSION_NAME:0.1" -h
tmux send-keys -t "$SESSION_NAME:0.2" "cd $PROJECT_ROOT" C-m
tmux send-keys -t "$SESSION_NAME:0.2" "echo '━━━ Performance Tests ━━━'" C-m
tmux send-keys -t "$SESSION_NAME:0.2" "tail -f ~/.claude/tasks/system-test-team/3/output.jsonl 2>/dev/null | jq -r '.content // empty' || echo 'Task 3 대기 중...'" C-m

# Pane 3: Security Tests (좌하단)
tmux split-window -t "$SESSION_NAME:0.0" -v
tmux send-keys -t "$SESSION_NAME:0.3" "cd $PROJECT_ROOT" C-m
tmux send-keys -t "$SESSION_NAME:0.3" "echo '━━━ Security Tests ━━━'" C-m
tmux send-keys -t "$SESSION_NAME:0.3" "tail -f ~/.claude/tasks/system-test-team/4/output.jsonl 2>/dev/null | jq -r '.content // empty' || echo 'Task 4 대기 중...'" C-m

# Pane 4: Integration Tests (중앙 하단)
tmux split-window -t "$SESSION_NAME:0.1" -v
tmux send-keys -t "$SESSION_NAME:0.4" "cd $PROJECT_ROOT" C-m
tmux send-keys -t "$SESSION_NAME:0.4" "echo '━━━ Integration Tests ━━━'" C-m
tmux send-keys -t "$SESSION_NAME:0.4" "tail -f ~/.claude/tasks/system-test-team/5/output.jsonl 2>/dev/null | jq -r '.content // empty' || echo 'Task 5 대기 중...'" C-m

# 레이아웃 조정
tmux select-layout -t "$SESSION_NAME:0" tiled

echo "✅ 모니터링 세션 생성 완료!"
echo ""
echo "Attach: tmux attach -t $SESSION_NAME"
echo "Detach: Ctrl+B, D"

# 자동 attach
tmux attach-session -t "$SESSION_NAME"
