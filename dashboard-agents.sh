#!/bin/bash

# Auth System Review - Agent Teams 대시보드
# 모든 에이전트의 상태를 한 화면에 표시

TEAM_DIR="$HOME/.claude/teams/auth-review-team/inboxes"

show_agent_status() {
    local agent=$1
    local emoji=$2
    local color=$3

    echo ""
    echo "$emoji ========================================"
    echo "   $agent"
    echo "========================================"

    if [ ! -f "$TEAM_DIR/$agent.json" ]; then
        echo "❌ Inbox 파일 없음"
        return
    fi

    # 최근 3개 메시지의 summary 표시
    if command -v jq &> /dev/null; then
        echo ""
        jq -r '.[-3:] | .[] |
            if .summary then
                "[\(.timestamp[11:19])] \(.from): \(.summary)"
            elif .text then
                "[\(.timestamp[11:19])] \(.from): " + (.text | fromjson.type // "message")
            else
                "[\(.timestamp[11:19])] \(.from): idle"
            end' "$TEAM_DIR/$agent.json" 2>/dev/null | tail -3
    else
        echo "⚠️  jq가 필요합니다: brew install jq"
    fi

    # 총 메시지 수
    local count=$(jq '. | length' "$TEAM_DIR/$agent.json" 2>/dev/null)
    echo ""
    echo "📬 총 메시지: $count"
}

clear

echo "╔════════════════════════════════════════════════════╗"
echo "║   Auth System Review - Agent Teams Dashboard      ║"
echo "║                                                    ║"
echo "║   Press Ctrl+C to exit                             ║"
echo "╚════════════════════════════════════════════════════╝"

show_agent_status "security-specialist" "🔵" "blue"
show_agent_status "code-quality-reviewer" "🟢" "green"
show_agent_status "performance-analyst" "🟡" "yellow"
show_agent_status "test-coverage-auditor" "🟣" "purple"

echo ""
echo "========================================"
echo "⏱️  마지막 업데이트: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""
echo "💡 실시간 모니터링: watch -n 2 ./dashboard-agents.sh"
echo ""
