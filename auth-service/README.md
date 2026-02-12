# auth-service

FastAPI + PostgreSQL 기반 백엔드 프로젝트입니다.

## 시작하기

```bash
# 가상환경 생성
python -m venv .venv
source .venv/bin/activate

# 의존성 설치
uv pip install -e ".[dev]"

# 환경 변수 설정
cp .env.example .env

# 개발 서버 실행
uvicorn src.main:app --reload --port 8000
```

## 기술 스택

- FastAPI
- PostgreSQL + asyncpg
- Pydantic v2
- Python 3.11+

## 문서

- [CLAUDE.md](CLAUDE.md) - Claude Code 가이드
- [Git 워크플로우](docs/standards/git-workflow.md)
- [커밋 컨벤션](docs/standards/commit-convention.md)
- [개발 워크플로우](docs/standards/development-workflow.md)
