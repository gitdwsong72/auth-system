# auth-system

Fullstack 프로젝트 (Frontend + Backend)

## 구조

```
auth-system/
├── auth-admin/     # React + TypeScript
├── auth-service/      # FastAPI + PostgreSQL
└── docker-compose.yml # 통합 실행
```

## 시작하기

### Docker로 전체 실행
```bash
docker-compose up -d
```

### 개별 실행

**Frontend:**
```bash
cd auth-admin
pnpm install
pnpm dev
```

**Backend:**
```bash
cd auth-service
python -m venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
uvicorn src.main:app --reload --port 8000
```

## Claude Code Team

Fullstack 기능을 병렬로 개발하려면:
```bash
# Frontend 또는 Backend 디렉토리에서
@fullstack-team 매출 목록 페이지 구현
```

## 접속 URL

- Frontend: http://localhost:5173 (개발) / http://localhost:80 (Docker)
- Backend API: http://localhost:8000
- API 문서: http://localhost:8000/docs
