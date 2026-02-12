# PRD 인덱스 - Auth Service

## 관리 규칙
- PRD는 기능 단위로 작성합니다.
- 새 PRD 작성 시 이 인덱스에 반드시 등록합니다.
- 상태: `Draft` → `Review` → `Approved` → `Done`

---

## 공통 PRD

| 문서 | 설명 | 경로 |
|------|------|------|
| 공통 사항 | 프로젝트 개요, 기술 스택, 인증 아키텍처, API 규약 | [common.md](common/common.md) |

---

## API PRD

| 엔드포인트 | 상태 | 작성일 | 경로 |
|------------|------|--------|------|
| `/api/v1/users` | Draft | - | [users.md](endpoints/users.md) |
| `/api/v1/auth` | Draft | - | [authentication.md](endpoints/authentication.md) |
| `/api/v1/roles`, `/api/v1/permissions` | Draft | - | [roles.md](endpoints/roles.md) |
| `/api/v1/oauth` | Draft | - | [oauth.md](endpoints/oauth.md) |
| `/api/v1/mfa` | Draft | - | [mfa.md](endpoints/mfa.md) |
| `/api/v1/api-keys` | Draft | - | [api-keys.md](endpoints/api-keys.md) |

---

## PRD 작성 가이드

### 새 PRD 추가 절차

1. **이 인덱스에 항목 추가** — 위 테이블에 엔드포인트 등록
2. **템플릿 복사** — 해당 디렉토리에 템플릿 파일 복사
   ```bash
   cp docs/prd/endpoints/_template.md docs/prd/endpoints/{도메인명}.md
   ```
3. **내용 작성** — 템플릿의 각 섹션을 채워 넣기
4. **상태 업데이트** — 작성 완료 시 인덱스의 상태를 `Review`로 변경

---

## PRD → Agent/Team 연결

PRD 작성 후 Agent 또는 Team에게 PRD 파일 경로를 전달하여 구현을 요청합니다.

### 단일 Agent 사용
```bash
# Backend 구현
@fastapi-specialist docs/prd/endpoints/users.md 기반으로 users 도메인 구현
@fastapi-specialist docs/prd/endpoints/authentication.md 기반으로 인증 API 구현

# SQL 쿼리 작성
@sql-query-specialist docs/prd/endpoints/users.md 기반으로 SQL 작성
```

### Fullstack Team 사용
```bash
# RBAC 기능 전체 구현
@fullstack-team docs/prd/endpoints/roles.md 기반으로 역할/권한 관리 기능 구현
```
