# PRD 인덱스 - [프로젝트명]

## 관리 규칙
- PRD는 기능 단위로 작성합니다.
- 새 PRD 작성 시 이 인덱스에 반드시 등록합니다.
- 상태: `Draft` → `Review` → `Approved` → `Done`

---

## 공통 PRD

| 문서 | 설명 | 경로 |
|------|------|------|
| 공통 사항 | 프로젝트 개요, 기술 스택, API 규약, 코딩 컨벤션 | [common.md](common/common.md) |

---

## 화면 PRD

| 화면명 | 상태 | 작성일 | 경로 |
|--------|------|--------|------|
| _(예시) 매출 목록_ | _Draft_ | _2025-01-01_ | _[sales-list.md](screens/sales-list.md)_ |

---

## API PRD

| 엔드포인트 | 상태 | 작성일 | 경로 |
|------------|------|--------|------|
| _(예시) /api/v1/sales_ | _Draft_ | _2025-01-01_ | _[sales.md](endpoints/sales.md)_ |

---

## PRD 작성 가이드

### 새 PRD 추가 절차

1. **이 인덱스에 항목 추가** — 위 테이블에 화면명 또는 엔드포인트 등록
2. **템플릿 복사** — 해당 디렉토리에 템플릿 파일 복사
   ```bash
   # 화면 PRD
   cp docs/prd/screens/_template.md docs/prd/screens/{화면명}.md

   # API PRD
   cp docs/prd/endpoints/_template.md docs/prd/endpoints/{도메인명}.md
   ```
3. **내용 작성** — 템플릿의 각 섹션을 채워 넣기
4. **상태 업데이트** — 작성 완료 시 인덱스의 상태를 `Review`로 변경

### 화면 PRD vs API PRD 선택 기준

| 구분 | 화면 PRD (`screen.md`) | API PRD (`endpoint.md`) |
|------|----------------------|------------------------|
| 대상 | Frontend 화면/페이지 | Backend API 엔드포인트 |
| 초점 | UI 레이아웃, 사용자 인터랙션, 상태 관리 | 데이터 모델, Request/Response, 비즈니스 규칙 |
| 사용 시점 | 새 화면 개발 시 | 새 API 개발 시 |
| Fullstack | 하나의 기능에 화면 PRD + API PRD 모두 작성 권장 | |

---

## PRD → Agent/Team 연결

PRD 작성 후 Agent 또는 Team에게 PRD 파일 경로를 전달하여 구현을 요청합니다.

### 단일 Agent 사용
```bash
# Frontend 구현
@react-specialist docs/prd/screens/sales-list.md 기반으로 매출 목록 구현

# Backend 구현
@fastapi-specialist docs/prd/endpoints/sales.md 기반으로 매출 API 구현

# SQL 쿼리 작성
@sql-query-specialist docs/prd/endpoints/sales.md 기반으로 SQL 작성
```

### Fullstack Team 사용
```bash
# PRD 전체를 참조하여 기능 구현
@fullstack-team docs/prd/ 참조하여 매출 기능 전체 구현
```
