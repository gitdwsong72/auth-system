#!/bin/bash
# Backend 환경 버전 체크 스크립트
# Claude Code hook에서 Bash 명령 실행 전 호출됨
# 지원 환경: venv, pyenv, conda

set -e

# ============================================
# 필수 버전 설정 (프로젝트에 맞게 수정)
# ============================================
REQUIRED_PYTHON_MAJOR=3
REQUIRED_PYTHON_MINOR=11

# 색상 정의
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 현재 Python 환경 감지
detect_python_env() {
    if [ -n "$CONDA_DEFAULT_ENV" ]; then
        echo "conda"
    elif [ -n "$PYENV_VERSION" ] || [ -n "$PYENV_VIRTUAL_ENV" ]; then
        echo "pyenv"
    elif [ -n "$VIRTUAL_ENV" ]; then
        echo "venv"
    else
        echo "system"
    fi
}

# Python 버전 가져오기
get_python_version() {
    local env_type=$1

    case $env_type in
        conda)
            # conda 환경의 python
            python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null
            ;;
        pyenv)
            # pyenv 환경의 python
            python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null
            ;;
        venv)
            # venv 환경의 python
            python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null
            ;;
        system)
            # 시스템 python3
            python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null
            ;;
    esac
}

# 환경 정보 출력
print_env_info() {
    local env_type=$1
    local env_name=""

    case $env_type in
        conda)
            env_name="$CONDA_DEFAULT_ENV"
            echo -e "${CYAN}[ENV] Conda: ${env_name}${NC}"
            ;;
        pyenv)
            if [ -n "$PYENV_VIRTUAL_ENV" ]; then
                env_name=$(basename "$PYENV_VIRTUAL_ENV")
            else
                env_name="$PYENV_VERSION"
            fi
            echo -e "${CYAN}[ENV] Pyenv: ${env_name}${NC}"
            ;;
        venv)
            env_name=$(basename "$VIRTUAL_ENV")
            echo -e "${CYAN}[ENV] Venv: ${env_name}${NC}"
            ;;
        system)
            echo -e "${YELLOW}[ENV] System Python (가상환경 미사용)${NC}"
            ;;
    esac
}

# Python 버전 체크
check_python() {
    local env_type=$(detect_python_env)

    # Python 명령 존재 확인
    if [ "$env_type" = "system" ]; then
        if ! command -v python3 &> /dev/null; then
            echo -e "${RED}[ERROR] Python이 설치되어 있지 않습니다.${NC}"
            echo "Python ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR} 이상을 설치해주세요."
            exit 1
        fi
    else
        if ! command -v python &> /dev/null; then
            echo -e "${RED}[ERROR] 가상환경에 Python이 없습니다.${NC}"
            exit 1
        fi
    fi

    # 버전 가져오기
    local python_version=$(get_python_version "$env_type")

    if [ -z "$python_version" ]; then
        echo -e "${RED}[ERROR] Python 버전을 확인할 수 없습니다.${NC}"
        exit 1
    fi

    local python_major=$(echo $python_version | cut -d. -f1)
    local python_minor=$(echo $python_version | cut -d. -f2)

    # 환경 정보 출력
    print_env_info "$env_type"

    # 버전 비교
    if [ "$python_major" -lt "$REQUIRED_PYTHON_MAJOR" ] || \
       ([ "$python_major" -eq "$REQUIRED_PYTHON_MAJOR" ] && [ "$python_minor" -lt "$REQUIRED_PYTHON_MINOR" ]); then
        echo -e "${RED}[ERROR] Python 버전이 맞지 않습니다.${NC}"
        echo "현재: Python ${python_version}, 필요: Python ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR} 이상"
        echo ""

        case $env_type in
            conda)
                echo "Conda 환경 재생성:"
                echo "  conda create -n myenv python=${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
                echo "  conda activate myenv"
                ;;
            pyenv)
                echo "Pyenv 버전 변경:"
                echo "  pyenv install ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
                echo "  pyenv local ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
                ;;
            venv)
                echo "Venv 재생성 (Python ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR} 필요):"
                echo "  rm -rf .venv"
                echo "  python${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR} -m venv .venv"
                echo "  source .venv/bin/activate"
                ;;
            system)
                echo "시스템 Python 업그레이드 또는 가상환경 사용 권장:"
                echo "  pyenv install ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
                echo "  또는 conda create -n myenv python=${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
                ;;
        esac
        exit 1
    fi

    echo -e "${GREEN}[OK] Python ${python_version}${NC}"
}

# 가상환경 활성화 경고
check_virtual_env() {
    local env_type=$(detect_python_env)

    if [ "$env_type" = "system" ]; then
        # .venv, venv 폴더 또는 .python-version 파일 존재 확인
        if [ -d ".venv" ] || [ -d "venv" ]; then
            echo -e "${YELLOW}[WARNING] 가상환경 폴더가 있지만 활성화되지 않았습니다.${NC}"
            if [ -d ".venv" ]; then
                echo "활성화: source .venv/bin/activate"
            else
                echo "활성화: source venv/bin/activate"
            fi
        elif [ -f ".python-version" ]; then
            echo -e "${YELLOW}[WARNING] pyenv 설정 파일이 있지만 pyenv가 활성화되지 않았습니다.${NC}"
            echo "활성화: pyenv local $(cat .python-version)"
        elif [ -f "environment.yml" ] || [ -f "environment.yaml" ]; then
            echo -e "${YELLOW}[WARNING] Conda 환경 파일이 있지만 conda가 활성화되지 않았습니다.${NC}"
            echo "활성화: conda activate <env-name>"
        fi
    fi
}

# uv 체크 (선택사항)
check_uv() {
    if ! command -v uv &> /dev/null; then
        echo -e "${YELLOW}[INFO] uv가 설치되어 있지 않습니다. (선택사항)${NC}"
        echo "설치: curl -LsSf https://astral.sh/uv/install.sh | sh"
    fi
}

# 메인 실행
check_python
check_virtual_env

exit 0
