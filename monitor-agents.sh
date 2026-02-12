#!/bin/bash

# Auth System Review - Agent Teams 모니터링 스크립트
# 4개 패널로 각 에이전트의 작업을 실시간 모니터링

SESSION_NAME="auth-review-agents"

# 기존 세션이 있으면 종료
tmux kill-session -t $SESSION_NAME 2>/dev/null

# 새 세션 생성
tmux new-session -d -s $SESSION_NAME -n "Agents Monitor"

# 윈도우를 4개 패널로 분할
# 패널 0: Security Specialist (좌상단)
tmux select-pane -t 0
tmux send-keys "clear && echo '🔵 Security Specialist' && echo '===================' && tail -f ~/.claude/teams/auth-review-team/inboxes/security-specialist.json 2>/dev/null || echo 'Waiting for messages...'" C-m

# 패널 1: Code Quality Reviewer (우상단)
tmux split-window -h
tmux send-keys "clear && echo '🟢 Code Quality Reviewer' && echo '=======================' && tail -f ~/.claude/teams/auth-review-team/inboxes/code-quality-reviewer.json 2>/dev/null || echo 'Waiting for messages...'" C-m

# 패널 2: Performance Analyst (좌하단)
tmux select-pane -t 0
tmux split-window -v
tmux send-keys "clear && echo '🟡 Performance Analyst' && echo '======================' && tail -f ~/.claude/teams/auth-review-team/inboxes/performance-analyst.json 2>/dev/null || echo 'Waiting for messages...'" C-m

# 패널 3: Test Coverage Auditor (우하단)
tmux select-pane -t 2
tmux split-window -v
tmux send-keys "clear && echo '🟣 Test Coverage Auditor' && echo '========================' && tail -f ~/.claude/teams/auth-review-team/inboxes/test-coverage-auditor.json 2>/dev/null || echo 'Waiting for messages...'" C-m

# 레이아웃 조정 (모든 패널 균등 분할)
tmux select-layout tiled

# 세션에 attach
tmux attach-session -t $SESSION_NAME
