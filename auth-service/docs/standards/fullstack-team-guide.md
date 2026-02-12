# Fullstack Team 사용 가이드

## 개요
Fullstack Team은 Claude Code의 Agent Teams 기능을 활용하여 여러 전문 에이전트가 병렬로 작업하는 팀 구성 템플릿입니다. Backend, SQL, Frontend, Test, Review 전문 에이전트가 체계적으로 협업하여 하나의 기능을 빠르게 구현합니다.

---

## 사전 준비

### 1. Agent 템플릿 복사

Fullstack Team은 기존 Agent 템플릿을 Teammate로 활용합니다. 프로젝트에 필요한 Agent 템플릿을 먼저 복사합니다.

```bash
# 프로젝트 .claude/agents/ 디렉토리 생성
mkdir -p your-project/.claude/agents/

# Team Lead 템플릿 복사
cp dev-standards/templates/claude-teams/fullstack-team.md your-project/.claude/agents/

# Backend Agent 복사
cp dev-standards/templates/claude-agents/fastapi-specialist.md your-project/.claude/agents/
cp dev-standards/templates/claude-agents/sql-query-specialist.md your-project/.claude/agents/

# Frontend Agent 복사
cp dev-standards/templates/claude-agents/react-specialist.md your-project/.claude/agents/

# 테스트/리뷰 Agent 복사
cp dev-standards/templates/claude-agents/api-test-specialist.md your-project/.claude/agents/
cp dev-standards/templates/claude-agents/code-quality-reviewer.md your-project/.claude/agents/
```

### 2. 프로젝트 디렉토리 구조 확인

Team이 효과적으로 작업하려면 프로젝트가 표준 구조를 따라야 합니다.

```
your-project/
├── .claude/
│   └── agents/
│       ├── fullstack-team.md         # Team Lead
│       ├── fastapi-specialist.md     # Backend
│       ├── sql-query-specialist.md   # SQL
│       ├── react-specialist.md       # Frontend
│       ├── api-test-specialist.md    # API Test
│       └── code-quality-reviewer.md  # Reviewer
├── src/
│   └── domains/                      # 도메인별 코드
├── tests/
│   ├── unit/
│   └── integration/
└── ...
```

---

## 사용법

### 기본 호출

```bash
@fullstack-team 매출 목록 페이지 구현
```

### 상세 요청 예시

```bash
@fullstack-team 매출 관리 기능 구현
- 매출 목록 조회: 검색, 필터링(날짜, 상태, 고객), 정렬, 페이지네이션
- 매출 등록: 상품명, 수량, 단가, 고객명, 매출일
- 매출 수정: 등록과 동일 필드
- 매출 삭제: soft delete
- AG-Grid 테이블: 컬럼 정렬, 필터, 행 선택
- 기존 패턴 참조: src/domains/orders/
```

### 요청 시 포함하면 좋은 정보
- **기능 범위**: CRUD 중 필요한 것, 특수 기능
- **참조 도메인**: 기존 유사 코드 경로
- **UI 요구사항**: 테이블 종류, 차트, 폼 구성
- **비즈니스 규칙**: 유효성 검증, 권한, 상태 전환

---

## 작업 흐름

```
사용자 요청
    │
    ▼
┌─────────────────────────────────┐
│ Phase 0: 분석 & 계획 (Team Lead) │
│  - 요구사항 분석                   │
│  - 코드베이스 탐색                 │
│  - Task 분해                     │
│  - 사용자 승인 요청                │
└─────────────┬───────────────────┘
              │ 승인
              ▼
┌─────────────────────────────────┐
│ Phase 1: Backend + SQL (병렬)    │
│                                  │
│  ┌──────────┐  ┌──────────────┐ │
│  │ sql-dev  │  │ backend-dev  │ │
│  │ SQL 작성  │  │ API 구현     │ │
│  └────┬─────┘  └──────┬───────┘ │
│       └───────┬────────┘         │
└───────────────┼─────────────────┘
                │ 완료
                ▼
┌─────────────────────────────────┐
│ Phase 2: Frontend + Test (병렬)  │
│                                  │
│  ┌──────────────┐  ┌──────────┐ │
│  │ frontend-dev │  │api-tester│ │
│  │ UI 구현      │  │ 테스트    │ │
│  └──────┬───────┘  └────┬─────┘ │
│         └───────┬────────┘       │
└─────────────────┼───────────────┘
                  │ 완료
                  ▼
┌─────────────────────────────────┐
│ Phase 3: 코드 리뷰               │
│                                  │
│       ┌──────────┐               │
│       │ reviewer │               │
│       │ 품질 리뷰 │               │
│       └────┬─────┘               │
└────────────┼────────────────────┘
             │ 완료
             ▼
┌─────────────────────────────────┐
│ Phase 4: 최종 확인 (Team Lead)   │
│  - 리뷰 지적사항 수정 지시         │
│  - 최종 검증                      │
│  - 사용자 보고                    │
│  - 팀 종료                       │
└─────────────────────────────────┘
```

---

## 주의사항

### 프로젝트 구조
- 프로젝트가 도메인 기반 구조(`src/domains/`)를 따라야 Team이 효과적으로 작업합니다
- 기존 도메인 코드가 있으면 Team이 패턴을 참조하여 일관성을 유지합니다
- 프로젝트 구조가 다른 경우 Phase 0에서 Team Lead에게 구조를 설명합니다

### 커밋 전략
- Team은 코드 생성만 수행하고, **커밋은 하지 않습니다**
- 모든 작업 완료 후 사용자가 직접 검토하고 커밋합니다
- 필요 시 `@commit` 등 별도 명령으로 커밋합니다

### 비용/성능
- Team은 최대 5개 Agent를 동시에 실행하므로 API 사용량이 단일 Agent 대비 높습니다
- Phase별 Lazy Spawning으로 불필요한 Agent 생성을 최소화합니다
- 단순한 작업(단일 파일 수정, 버그 수정 등)은 개별 Agent를 직접 호출하는 것이 효율적입니다

---

## 커스터마이징

### Teammate 추가

E2E 테스트가 필요한 경우 Phase 2에 e2e-tester를 추가할 수 있습니다.

```markdown
## Team 구성 (커스텀)
| Teammate | Agent 기반 | 역할 |
|----------|-----------|------|
| ... (기존 5명) | ... | ... |
| `e2e-tester` | e2e-test-specialist | Playwright E2E 테스트 작성 |
```

Phase 2에서 frontend-dev, api-tester와 함께 병렬로 실행합니다.

### Teammate 제거

Backend만 필요한 경우 frontend-dev를 제거하고 Phase 2를 테스트만으로 구성합니다.

### Phase 조정

- **Phase 병합**: 간단한 기능이면 Phase 1+2를 동시에 진행 가능
- **Phase 추가**: 데이터 마이그레이션 등 추가 단계가 필요하면 Phase를 삽입

---

## FAQ

### Q: 단일 Agent vs Team, 어떤 걸 선택해야 하나요?

| 상황 | 권장 |
|------|------|
| 단일 파일 수정, 버그 수정 | 단일 Agent (`@react-specialist` 등) |
| 하나의 레이어만 작업 (Backend만, Frontend만) | 단일 Agent |
| Fullstack 기능 개발 (Backend + Frontend + Test) | Team (`@fullstack-team`) |
| 여러 도메인에 걸친 대규모 작업 | Team |

**기준**: Backend + Frontend를 모두 구현해야 하면 Team, 한쪽만이면 단일 Agent가 효율적입니다.

### Q: 작업 중 요구사항이 변경되면?

Team Lead에게 변경사항을 전달하면 됩니다.

```bash
# 진행 중인 팀에 추가 요청
매출 목록에 차트(월별 매출 추이)도 추가해 주세요
```

Team Lead가 변경 영향을 분석하고 필요한 Teammate에게 추가 Task를 할당합니다.

### Q: 특정 Phase만 실행할 수 있나요?

Team Lead에게 범위를 명시하면 됩니다.

```bash
@fullstack-team 매출 API만 구현 (Backend + SQL + Test만, Frontend 제외)
```

### Q: 기존에 일부 구현된 코드가 있는 경우?

Team Lead가 Phase 0에서 기존 코드를 분석하고, 이미 구현된 부분은 건너뜁니다. 요청 시 기존 코드 경로를 알려주면 더 정확합니다.

```bash
@fullstack-team 매출 기능 Frontend 추가
- Backend API 구현 완료: src/domains/sales/
- Frontend만 추가 구현 필요
```
