#!/bin/bash
# 간단한 터미널 대시보드 (tmux 대안)

PROJECT_ROOT="/Users/sktl/WF/WF01/auth-system/auth-service"
FASTAPI_LOG="/tmp/fastapi_refactor.log"

# 색상 정의
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

# 화면 클리어
clear

echo -e "${CYAN}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║         🚀 Auth System - Solid Cache Dashboard 🚀                ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

while true; do
    # 커서를 맨 위로 이동 (첫 루프 이후)
    if [ "$first_run" = "done" ]; then
        tput cup 4 0
    fi
    first_run="done"

    # ===== 1. Health Check =====
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}📊 Health Check (10초 갱신)${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    health_json=$(curl -s http://localhost:8001/health 2>/dev/null)
    if [ -n "$health_json" ]; then
        status=$(echo "$health_json" | jq -r '.status' 2>/dev/null)
        db_status=$(echo "$health_json" | jq -r '.services.database.healthy' 2>/dev/null)
        redis_status=$(echo "$health_json" | jq -r '.services.redis.status' 2>/dev/null)
        cache_entries=$(echo "$health_json" | jq -r '.services.solid_cache.total_entries' 2>/dev/null)
        cache_expired=$(echo "$health_json" | jq -r '.services.solid_cache.expired_entries' 2>/dev/null)
        cache_size=$(echo "$health_json" | jq -r '.services.solid_cache.total_size_kb' 2>/dev/null)

        echo -e "  Overall: ${GREEN}${status}${NC}"
        echo -e "  Database: ${GREEN}${db_status}${NC}"
        echo -e "  Redis: ${GREEN}${redis_status}${NC}"
        echo -e "  Solid Cache: ${CYAN}${cache_entries} entries${NC} (${cache_expired} expired, ${cache_size} KB)"
    else
        echo -e "  ${RED}FastAPI 연결 실패${NC}"
    fi
    echo ""

    # ===== 2. Solid Cache Stats =====
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}💾 Solid Cache Statistics${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    cache_stats=$(PGPASSWORD=devpassword psql -h localhost -p 5433 -U devuser -d appdb -t -c \
        "SELECT COUNT(*) as total, \
         COUNT(*) FILTER (WHERE expires_at < NOW()) as expired, \
         pg_size_pretty(pg_total_relation_size('solid_cache_entries')) as size \
         FROM solid_cache_entries;" 2>/dev/null)

    if [ -n "$cache_stats" ]; then
        echo -e "  ${cache_stats}"
    else
        echo -e "  ${RED}PostgreSQL 연결 실패${NC}"
    fi
    echo ""

    # ===== 3. Redis Status =====
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}🔴 Redis Status${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    redis_info=$(redis-cli -h localhost -p 6380 INFO stats 2>/dev/null | grep -E '(total_connections|total_commands|keyspace)')
    if [ -n "$redis_info" ]; then
        echo "$redis_info" | while read -r line; do
            echo -e "  ${line}"
        done
    else
        echo -e "  ${RED}Redis 연결 실패${NC}"
    fi
    echo ""

    # ===== 4. Recent Cleanup Events =====
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}🧹 Recent Cleanup Events${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    cleanup_logs=$(grep "cache_cleanup" "$FASTAPI_LOG" 2>/dev/null | tail -3)
    if [ -n "$cleanup_logs" ]; then
        echo "$cleanup_logs" | while read -r line; do
            echo -e "  ${CYAN}${line}${NC}"
        done
    else
        echo -e "  ${YELLOW}Cleanup 이벤트 대기 중...${NC}"
    fi
    echo ""

    # ===== 5. Latest Application Logs =====
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}📋 Latest Application Logs (최근 5줄)${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    tail -5 "$FASTAPI_LOG" 2>/dev/null | while read -r line; do
        echo -e "  ${line}"
    done
    echo ""

    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}마지막 갱신: $(date '+%Y-%m-%d %H:%M:%S')${NC} | ${BLUE}Ctrl+C로 종료${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # 10초 대기
    sleep 10
done
