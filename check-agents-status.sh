#!/bin/bash

# Agent Teams 상태 확인 스크립트

echo "🔍 Auth System Review - Agent Teams 상태 확인"
echo "================================================"
echo ""

TEAM_DIR="$HOME/.claude/teams/auth-review-team"

if [ ! -d "$TEAM_DIR" ]; then
    echo "❌ 팀 디렉토리를 찾을 수 없습니다: $TEAM_DIR"
    exit 1
fi

echo "📁 팀 디렉토리: $TEAM_DIR"
echo ""

# 각 에이전트의 inbox 메시지 수 확인
echo "📬 Agent Inbox 상태:"
echo "-------------------"

for agent in security-specialist code-quality-reviewer performance-analyst test-coverage-auditor; do
    inbox_file="$TEAM_DIR/inboxes/$agent.json"

    if [ -f "$inbox_file" ]; then
        size=$(du -h "$inbox_file" | awk '{print $1}')
        lines=$(wc -l < "$inbox_file")

        # 마지막 메시지 타입 확인 (jq 사용)
        if command -v jq &> /dev/null; then
            last_type=$(jq -r '.messages[-1].type // "empty"' "$inbox_file" 2>/dev/null)
            echo "  ✓ $agent: $lines 줄, $size (마지막: $last_type)"
        else
            echo "  ✓ $agent: $lines 줄, $size"
        fi
    else
        echo "  ✗ $agent: inbox 없음"
    fi
done

echo ""

# 팀 설정 확인
config_file="$TEAM_DIR/config.json"
if [ -f "$config_file" ] && command -v jq &> /dev/null; then
    echo "👥 팀 멤버:"
    echo "----------"
    jq -r '.members[] | "  • \(.name) (\(.agentType))"' "$config_file"
    echo ""
fi

echo "🎯 다음 단계:"
echo "-------------"
echo "  1. 실시간 모니터링: ./monitor-agents-pretty.sh"
echo "  2. 기본 모니터링: ./monitor-agents.sh"
echo "  3. 특정 에이전트 확인: tail -f $TEAM_DIR/inboxes/[에이전트명].json | jq"
echo ""
