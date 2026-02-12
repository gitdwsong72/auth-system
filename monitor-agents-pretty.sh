#!/bin/bash

# Auth System Review - Agent Teams 모니터링 스크립트 (Pretty 버전)
# 4개 패널로 각 에이전트의 작업을 실시간 모니터링 (jq 포맷팅)

SESSION_NAME="auth-review-agents"

# jq 설치 확인
if ! command -v jq &> /dev/null; then
    echo "⚠️  jq가 설치되어 있지 않습니다. 기본 버전을 실행합니다."
    exec ./monitor-agents.sh
fi

# 기존 세션이 있으면 종료
tmux kill-session -t $SESSION_NAME 2>/dev/null

# 새 세션 생성
tmux new-session -d -s $SESSION_NAME -n "Agents Monitor"

# 패널 0: Security Specialist (좌상단)
tmux select-pane -t 0
tmux send-keys "clear && echo '🔵 Security Specialist' && echo '===================' && tail -f ~/.claude/teams/auth-review-team/inboxes/security-specialist.json 2>/dev/null | jq -C '.' || echo 'Waiting...'" C-m

# 패널 1: Code Quality Reviewer (우상단)
tmux split-window -h
tmux send-keys "clear && echo '🟢 Code Quality Reviewer' && echo '=======================' && tail -f ~/.claude/teams/auth-review-team/inboxes/code-quality-reviewer.json 2>/dev/null | jq -C '.' || echo 'Waiting...'" C-m

# 패널 2: Performance Analyst (좌하단)
tmux select-pane -t 0
tmux split-window -v
tmux send-keys "clear && echo '🟡 Performance Analyst' && echo '======================' && tail -f ~/.claude/teams/auth-review-team/inboxes/performance-analyst.json 2>/dev/null | jq -C '.' || echo 'Waiting...'" C-m

# 패널 3: Test Coverage Auditor (우하단)
tmux select-pane -t 2
tmux split-window -v
tmux send-keys "clear && echo '🟣 Test Coverage Auditor' && echo '========================' && tail -f ~/.claude/teams/auth-review-team/inboxes/test-coverage-auditor.json 2>/dev/null | jq -C '.' || echo 'Waiting...'" C-m

# 레이아웃 조정
tmux select-layout tiled

# 패널 0으로 포커스
tmux select-pane -t 0

echo ""
echo "✅ tmux 세션 '$SESSION_NAME' 생성 완료!"
echo ""
echo "📌 사용법:"
echo "   - Ctrl+B, 방향키: 패널 간 이동"
echo "   - Ctrl+B, d: 세션 detach (백그라운드 실행)"
echo "   - Ctrl+B, [: 스크롤 모드 (q로 종료)"
echo "   - Ctrl+B, z: 현재 패널 전체화면 토글"
echo ""
echo "🔗 재접속: tmux attach -t $SESSION_NAME"
echo "🛑 종료: tmux kill-session -t $SESSION_NAME"
echo ""

# 세션에 attach
tmux attach-session -t $SESSION_NAME
