# 개발 워크플로우

## 개요
리서치 → 계획 → PRD작성 → 구현 → 테스트 순서로 진행합니다.

---

## Claude Code Agent 목록

### 구현 Agent
| Agent | 프로젝트 | 역할 |
|-------|---------|------|
| `react-specialist` | Frontend | React, AG-Grid, Recharts, Zustand 전문 |
| `fastapi-specialist` | Backend | FastAPI, API 설계 전문 |
| `sql-query-specialist` | Backend | PostgreSQL 쿼리 작성/최적화 |

### 품질 Agent
| Agent | 프로젝트 | 역할 |
|-------|---------|------|
| `code-quality-reviewer` | 공통 | 코드 품질, 보안 리뷰 |
| `e2e-test-specialist` | Frontend | Playwright E2E 테스트 전문 |
| `api-test-specialist` | Backend | pytest + httpx API 테스트 전문 |

---

## 1. 리서치 (Research)

### 목적
기존 코드 분석 및 기술 조사를 통해 구현 방향을 결정합니다.

### 체크리스트
- [ ] 기존 유사 기능 코드 분석
- [ ] 사용할 라이브러리/프레임워크 조사
- [ ] API 스펙 확인 (기존 API 있는 경우)
- [ ] 데이터베이스 스키마 확인

### Claude Code 활용
```bash
# 기존 코드 검색
/search "관련 키워드"

# 코드베이스 구조 파악
/explore
```

---

## 2. 계획 (Plan)

### 목적
구현 계획을 수립하고 팀과 공유합니다.

### Plan Mode 활용
```bash
# Plan Mode 진입
/plan

# 계획 수립 후 검토 요청
```

### 계획 문서 포함 사항
1. 구현 범위
2. 기술적 접근 방법
3. 예상 파일 변경 목록
4. 의존성 (다른 작업과의 관계)
5. 리스크 및 대안

---

## 3. PRD 작성 (Documentation)

### 목적
명확한 요구사항 문서화로 구현 품질을 보장합니다.

### PRD 파일 생성 절차

1. **인덱스에 등록** — `docs/prd/index.md`에 새 항목 추가
2. **템플릿 복사** — 적절한 템플릿을 복사하여 PRD 파일 생성
   ```bash
   # 화면 PRD
   cp docs/prd/screens/_template.md docs/prd/screens/{화면명}.md

   # API 엔드포인트 PRD
   cp docs/prd/endpoints/_template.md docs/prd/endpoints/{도메인명}.md
   ```
3. **내용 작성** — 템플릿의 각 섹션을 채워 넣기
4. **인덱스 상태 업데이트** — 작성 완료 시 인덱스 상태를 `Review`로 변경

### 화면 PRD vs API PRD 선택 기준

| 구분 | 화면 PRD (`screen.md`) | API PRD (`endpoint.md`) |
|------|----------------------|------------------------|
| 대상 | Frontend 화면/페이지 | Backend API 엔드포인트 |
| 초점 | UI 레이아웃, 사용자 인터랙션, 상태 관리 | 데이터 모델, Request/Response, 비즈니스 규칙 |
| 사용 시점 | 새 화면 개발 시 | 새 API 개발 시 |
| Fullstack | 하나의 기능에 화면 PRD + API PRD 모두 작성 권장 | |

### PRD 작성 원칙
1. **명확성**: 모호한 표현 지양
2. **완전성**: 모든 케이스 기술
3. **검증가능성**: 테스트 가능한 기준 제시

### PRD → Agent/Team 전달

PRD 작성 후 Agent 또는 Team에게 PRD 파일 경로를 전달하여 구현을 요청합니다.

```bash
# 화면 PRD 기반 Frontend 구현
@react-specialist docs/prd/screens/sales-list.md 기반으로 매출 목록 구현

# API PRD 기반 Backend 구현
@fastapi-specialist docs/prd/endpoints/sales.md 기반으로 매출 API 구현

# SQL 쿼리 작성
@sql-query-specialist docs/prd/endpoints/sales.md 기반으로 SQL 작성

# Fullstack Team에 PRD 전체 전달
@fullstack-team docs/prd/ 참조하여 매출 기능 전체 구현
```

---

## 4. 구현 (Implementation)

### Agent 활용

#### Frontend 구현
```bash
# React 컴포넌트 구현
@react-specialist AG-Grid 테이블 컴포넌트 구현 요청

# 예시 요청
@react-specialist 사용자 목록 페이지 구현 (AG-Grid, 검색, 페이지네이션)
```

#### Backend 구현
```bash
# API 엔드포인트 구현
@fastapi-specialist CRUD API 엔드포인트 구현 요청

# SQL 쿼리 작성
@sql-query-specialist 복잡한 조회 쿼리 최적화 요청

# 예시 요청
@fastapi-specialist 매출 목록 조회 API (필터링, 정렬, 페이지네이션)
@sql-query-specialist 월별 매출 집계 쿼리 작성
```

### 구현 순서 (권장)
1. **Backend First**: API 및 데이터 레이어 구현
2. **Frontend Integration**: API 연동 및 UI 구현
3. **Polish**: 에러 처리, 로딩 상태 등 완성도 향상

### 커밋 컨벤션
```bash
# 기능 추가
feat(domain): add user list page

# 버그 수정
fix(domain): resolve pagination issue

# 리팩토링
refactor(domain): extract common logic to hook

# 테스트 추가
test(domain): add unit tests for user service
```

---

## 5. 테스트 (Testing)

### 테스트 레벨

```
┌─────────────────────────────────────────────────────────────┐
│                      테스트 피라미드                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                    ▲  E2E 테스트                            │
│                   ╱ ╲  (Playwright)                         │
│                  ╱───╲                                      │
│                 ╱     ╲                                     │
│                ╱ 통합  ╲  API 테스트                         │
│               ╱ 테스트  ╲  (pytest + httpx)                  │
│              ╱───────────╲                                  │
│             ╱             ╲                                 │
│            ╱   단위 테스트  ╲  Unit Tests                    │
│           ╱   (vitest, pytest)╲                             │
│          ╱─────────────────────╲                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Frontend 테스트

#### 단위 테스트 (Vitest)
```bash
pnpm test              # 전체 실행
pnpm test:coverage     # 커버리지 포함
```

#### E2E 테스트 (Playwright)
```bash
pnpm test:e2e          # 전체 실행
pnpm test:e2e:ui       # UI 모드
pnpm test:e2e:headed   # 브라우저 표시
pnpm test:e2e:debug    # 디버그 모드
```

#### E2E 테스트 Agent 활용
```bash
# E2E 테스트 작성 요청
@e2e-test-specialist 매출 목록 페이지 E2E 테스트 작성

# 예시 요청
@e2e-test-specialist 로그인 → 매출 조회 → 상세 보기 시나리오 테스트 작성
@e2e-test-specialist 매출 등록 폼 유효성 검증 테스트 작성
```

#### E2E 테스트 패턴 (Page Object Model)
```typescript
// Page Object 사용
const salesPage = new SalesPage(page);
await salesPage.goto();
await salesPage.search('테스트');
await expect(salesPage.dataGrid).toBeVisible();
```

### Backend 테스트

#### 단위 테스트 (pytest)
```bash
pytest tests/unit/           # 단위 테스트
pytest tests/unit/ -v        # 상세 출력
pytest -k "test_create"      # 특정 테스트
```

#### 통합 테스트 (pytest + httpx)
```bash
pytest tests/integration/    # 통합 테스트
pytest --cov=src             # 커버리지 포함
pytest -x                    # 실패 시 중단
```

#### API 테스트 Agent 활용
```bash
# API 테스트 작성 요청
@api-test-specialist 매출 CRUD API 테스트 작성

# 예시 요청
@api-test-specialist GET /api/v1/sales 테스트 (페이지네이션, 필터링)
@api-test-specialist POST /api/v1/sales 유효성 검증 테스트 작성
@api-test-specialist 매출 Service 단위 테스트 Mock 활용하여 작성
```

#### API 테스트 패턴 (AAA)
```python
async def test_create_sale(client: AsyncClient, sample_data: dict):
    # Arrange (Given)
    data = {**sample_data, "quantity": 10}

    # Act (When)
    response = await client.post("/api/v1/sales", json=data)

    # Assert (Then)
    assert response.status_code == 201
    assert response.json()["quantity"] == 10
```

### 코드 리뷰
```bash
# 코드 품질 리뷰 요청
@code-quality-reviewer 리뷰 요청

# 쿼리 리뷰 요청
/query-review src/domains/sales/sql/queries/select_list.sql

# 컴포넌트 리뷰 요청
/component-review src/domains/sales/components/SalesList.tsx
```

### 테스트 커버리지 목표
| 구분 | 목표 | 비고 |
|------|-----|------|
| 단위 테스트 | 80% 이상 | 핵심 비즈니스 로직 |
| 통합 테스트 | 주요 API | CRUD 엔드포인트 |
| E2E 테스트 | 핵심 시나리오 | 사용자 주요 흐름 |

---

## 6. 완료 기준

### Definition of Done
- [ ] 모든 기능 구현 완료
- [ ] PRD 대비 검증 완료
- [ ] 단위 테스트 작성 및 통과 (커버리지 80% 이상)
- [ ] 통합/E2E 테스트 통과
- [ ] 코드 리뷰 완료
- [ ] lint/format 검사 통과
- [ ] 문서 업데이트 (필요시)

---

## 브랜치 전략

### Git Flow
```
master (production) ─────────────────────────────────►
   │                                    ▲
   │                                    │ (GitLab MR)
   ▼                                    │
SKTL-XXXX (작업 브랜치) ────────────────┼────────────►
   │                                    │
   │ (MR)                               │
   ▼                                    │
develop (테스트 환경) ──────────────────┴────────────►
```

### 워크플로우
1. **master에서 브랜치 생성**: `git checkout -b SKTL-1234`
2. **개발 완료 후 develop에 MR**: 테스트 환경에서 검증
3. **테스트 완료 후 master에 MR**: GitLab에서만 (로컬 금지)

### 브랜치 명명
```bash
# JIRA 티켓 기반 (필수)
SKTL-1234
SKTL-5678

# ⚠️ 주의: 로컬에서 master push/merge 금지!
```

---

## MR 가이드라인

### MR 템플릿
```markdown
## 변경 사항
- 주요 변경 내용 요약

## 관련 이슈
- SKTL-1234

## 테스트 방법
- 테스트 단계 설명

## 체크리스트
- [ ] 단위 테스트 추가
- [ ] 통합/E2E 테스트 추가 (필요시)
- [ ] lint 통과
- [ ] 자체 코드 리뷰 완료
```

### 리뷰 요청 전 확인
1. CI 통과 확인
2. 충돌 해결
3. 불필요한 파일 제외
4. 커밋 메시지 정리

---

## Agent 활용 요약

### 구현 단계
```bash
# Frontend
@react-specialist [구현 요청 내용]

# Backend
@fastapi-specialist [API 구현 요청]
@sql-query-specialist [쿼리 작성/최적화 요청]
```

### 테스트 단계
```bash
# Frontend E2E
@e2e-test-specialist [E2E 테스트 작성 요청]

# Backend API
@api-test-specialist [API 테스트 작성 요청]
```

### 리뷰 단계
```bash
# 코드 품질
@code-quality-reviewer [리뷰 요청]

# 특정 파일 리뷰
/component-review [파일 경로]
/query-review [파일 경로]
```

---

## Team 활용 (병렬 개발)

### 단일 에이전트 vs Team

| 비교 항목 | 단일 Agent | Fullstack Team |
|-----------|-----------|----------------|
| **적합한 작업** | 단일 파일/레이어 수정, 버그 수정 | Fullstack 기능 개발 (Backend + Frontend) |
| **실행 방식** | 순차 실행 | Phase별 병렬 실행 |
| **Agent 수** | 1개 | Team Lead + 최대 5개 |
| **소통 구조** | 사용자 ↔ Agent | 사용자 ↔ Team Lead ↔ Teammates |
| **API 사용량** | 낮음 | 높음 (병렬 실행) |

### 선택 기준
- **단일 Agent**: 하나의 레이어(Backend만 또는 Frontend만) 작업
- **Team**: Backend + Frontend + Test를 동시에 구현해야 하는 경우

### Team 사용 시나리오 예시

```bash
# Fullstack 기능 개발
@fullstack-team 매출 목록 페이지 구현

# 상세 요청
@fullstack-team 매출 관리 기능 구현
- 목록 조회: 검색, 필터링, 정렬, 페이지네이션
- CRUD: 등록/수정/삭제
- AG-Grid 테이블
- 기존 패턴 참조: src/domains/orders/
```

### Team 작업 흐름
```
Phase 0: 분석 & 계획 (Team Lead)
Phase 1: Backend + SQL (병렬) → sql-dev, backend-dev
Phase 2: Frontend + Test (병렬) → frontend-dev, api-tester
Phase 3: 코드 리뷰 → reviewer
Phase 4: 최종 확인 (Team Lead)
```

자세한 사용법은 [Fullstack Team Guide](fullstack-team-guide.md) 참조
