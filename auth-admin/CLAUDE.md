# CLAUDE.md - Frontend Project

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
- 새 기능은 `src/domains/{도메인}/` 하위에 작성
- 공통 컴포넌트는 `src/shared/components/`에 작성
- 상태 관리는 Zustand 사용
- 타입은 각 도메인의 `types/` 폴더에 정의

### 테스트 규칙
- E2E 테스트: `tests/e2e/` 디렉토리
- Page Object Model 패턴 사용
- 테스트 파일명: `*.spec.ts`


## 프로젝트 정보

**프로젝트명**: auth-admin

## 기술 스택
- **Framework**: React 18
- **Language**: TypeScript 5
- **Build Tool**: Vite
- **State Management**: Zustand
- **Grid**: AG-Grid
- **Charts**: Recharts

## 개발 명령어

```bash
pnpm dev          # 개발 서버
pnpm build        # 빌드
pnpm lint         # 린트 검사
pnpm format       # 포맷팅
pnpm typecheck    # 타입 체크
pnpm test:e2e     # E2E 테스트
```

## 프로젝트 구조

```
src/
├── domains/          # 업무 도메인별 폴더
│   └── {domain}/
│       ├── components/
│       ├── hooks/
│       ├── stores/
│       ├── pages/
│       ├── api/
│       └── types/
└── shared/           # 공통 모듈
    └── components/
```

## Claude Code Agents

- `@react-specialist` - React, AG-Grid, Zustand 전문
- `@e2e-test-specialist` - Playwright E2E 테스트
- `@code-quality-reviewer` - 코드 품질 리뷰

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
