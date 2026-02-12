# CLAUDE.md - Backend Project

## 필수 참조 문서
**중요**: 코드 작성 전 반드시 아래 문서를 읽고 규칙을 준수하세요.
- `docs/standards/git-workflow.md` - Git 브랜치 전략, 커밋 규칙
- `docs/standards/commit-convention.md` - 커밋 메시지 컨벤션
- `docs/standards/development-workflow.md` - 개발 워크플로우

## 핵심 규칙 요약

### Git 규칙
- 브랜치: `master` → `SKTL-XXXX` (JIRA 티켓) → `develop` → `master`
- 로컬에서 master 직접 push/merge 금지
- 커밋 메시지: `type(scope): description` 형식

### 코드 규칙
- 새 도메인은 `src/domains/{도메인}/` 하위에 작성
- 레이어 패턴 준수: Router → Service → Repository
- SQL은 `sql/` 폴더에 파일로 분리
- ORM 사용 금지, 순수 SQL + asyncpg 사용

### 트랜잭션 규칙
- Service 레벨에서 트랜잭션 관리
- Repository는 connection만 받아서 사용 (트랜잭션 시작 금지)
- 복수 DB 작업 시 Saga 패턴 사용

### 테스트 규칙
- 단위 테스트: `tests/unit/`
- 통합 테스트: `tests/integration/`
- AAA 패턴 (Arrange-Act-Assert) 사용


## 프로젝트 정보

**프로젝트명**: auth-service

## 기술 스택
- **Framework**: FastAPI
- **Database**: PostgreSQL
- **Driver**: asyncpg
- **Validation**: Pydantic v2
- **Python**: 3.11+

## 개발 명령어

```bash
# 개발 서버
uvicorn src.main:app --reload --port 8000

# 린트
ruff check src tests

# 포맷팅
ruff format src tests

# 타입 체크
mypy src

# 테스트
pytest
pytest --cov=src
```

## 프로젝트 구조

```
src/
├── domains/              # 업무 도메인
│   └── {domain}/
│       ├── router.py     # API 엔드포인트
│       ├── service.py    # 비즈니스 로직
│       ├── repository.py # 데이터 접근
│       ├── schemas.py    # Pydantic 스키마
│       └── sql/          # SQL 파일
├── shared/
│   ├── database/         # DB 연결, 트랜잭션
│   └── utils/            # 유틸리티
└── main.py
```

## Claude Code Agents

- `@fastapi-specialist` - FastAPI API 설계
- `@sql-query-specialist` - PostgreSQL 쿼리
- `@api-test-specialist` - pytest API 테스트

## 문서
- [Git 워크플로우](docs/standards/git-workflow.md)
- [커밋 컨벤션](docs/standards/commit-convention.md)
- [개발 워크플로우](docs/standards/development-workflow.md)

## Claude Code Team

- `@fullstack-team` - Fullstack 기능 병렬 개발 (Backend + Frontend + Test + Review)

### Team 사용 예시
```bash
@fullstack-team 매출 목록 페이지 구현
```

자세한 사용법은 [Fullstack Team Guide](docs/standards/fullstack-team-guide.md) 참조
