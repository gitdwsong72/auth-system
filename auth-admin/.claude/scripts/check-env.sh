#!/bin/bash
# Frontend 환경 버전 체크 스크립트
# Claude Code hook에서 Bash 명령 실행 전 호출됨

set -e

# ============================================
# 필수 버전 설정 (프로젝트에 맞게 수정)
# ============================================
REQUIRED_NODE_MAJOR=20
REQUIRED_PNPM_MAJOR=9

# 색상 정의
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_node() {
    if ! command -v node &> /dev/null; then
        echo -e "${RED}[ERROR] Node.js가 설치되어 있지 않습니다.${NC}"
        echo "Node.js ${REQUIRED_NODE_MAJOR}.x 이상을 설치해주세요."
        exit 1
    fi

    NODE_VERSION=$(node -v | sed 's/v//' | cut -d. -f1)

    if [ "$NODE_VERSION" -lt "$REQUIRED_NODE_MAJOR" ]; then
        echo -e "${RED}[ERROR] Node.js 버전이 맞지 않습니다.${NC}"
        echo "현재: $(node -v), 필요: v${REQUIRED_NODE_MAJOR}.x 이상"
        echo ""
        echo "nvm 사용 시: nvm install ${REQUIRED_NODE_MAJOR} && nvm use ${REQUIRED_NODE_MAJOR}"
        exit 1
    fi
}

check_pnpm() {
    if ! command -v pnpm &> /dev/null; then
        echo -e "${YELLOW}[WARNING] pnpm이 설치되어 있지 않습니다.${NC}"
        echo "설치: npm install -g pnpm"
        return 0
    fi

    PNPM_VERSION=$(pnpm -v | cut -d. -f1)

    if [ "$PNPM_VERSION" -lt "$REQUIRED_PNPM_MAJOR" ]; then
        echo -e "${YELLOW}[WARNING] pnpm 버전 업그레이드를 권장합니다.${NC}"
        echo "현재: $(pnpm -v), 권장: ${REQUIRED_PNPM_MAJOR}.x 이상"
    fi
}

# 버전 체크 실행
check_node
check_pnpm

exit 0
