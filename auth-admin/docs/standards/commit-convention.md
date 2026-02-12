# Commit Convention

## 형식

```
<type>(<scope>): <subject>

<body>

<footer>
```

---

## Type

| Type | 설명 | 예시 |
|------|------|------|
| `feat` | 새로운 기능 추가 | feat(user): add login page |
| `fix` | 버그 수정 | fix(cart): resolve quantity update issue |
| `docs` | 문서 수정 | docs(readme): update installation guide |
| `style` | 코드 포맷팅 (기능 변경 없음) | style(button): fix indentation |
| `refactor` | 리팩토링 | refactor(api): extract common fetch logic |
| `perf` | 성능 개선 | perf(list): implement virtual scrolling |
| `test` | 테스트 추가/수정 | test(user): add login unit tests |
| `chore` | 빌드, 설정 변경 | chore(deps): update eslint to v9 |
| `ci` | CI 설정 변경 | ci(github): add lint workflow |
| `revert` | 커밋 되돌리기 | revert: feat(user): add login page |

---

## Scope

도메인 또는 모듈 이름을 사용합니다.

### Frontend
- `user`, `order`, `product` (도메인)
- `grid`, `chart`, `modal` (컴포넌트)
- `auth`, `api` (기능)

### Backend
- `user`, `order`, `product` (도메인)
- `db`, `auth`, `cache` (인프라)

---

## Subject

- 50자 이내
- 소문자로 시작
- 마침표 없음
- 명령형 사용 (add, fix, update, remove)

### Good Examples
```
feat(user): add email verification flow
fix(order): resolve payment calculation error
refactor(api): simplify error handling logic
```

### Bad Examples
```
feat(user): Added email verification  # 과거형 사용
Fix: bug in order module  # scope 누락, 대문자
feat(user): add email verification flow.  # 마침표
```

---

## Body (선택)

- 72자마다 줄바꿈
- **무엇**을, **왜** 변경했는지 설명
- 어떻게(how)보다 무엇을/왜(what/why) 중심

```
feat(order): add bulk order processing

기존에는 주문을 하나씩만 처리할 수 있었으나,
대량 주문 처리 요구사항이 있어 일괄 처리 기능을 추가함.

- 최대 100건까지 동시 처리 가능
- 트랜잭션 단위로 롤백 지원
```

---

## Footer (선택)

### Breaking Changes
```
BREAKING CHANGE: remove deprecated getUserById API

Migration: getUserById(id) → getUser({ id })
```

### Issue Reference
```
Closes #123
Fixes #456
Refs #789
```

---

## 전체 예시

```
feat(cart): add product quantity validation

사용자가 재고 이상의 수량을 입력하는 것을 방지하기 위해
장바구니에 수량 검증 로직을 추가함.

- 최대 수량을 재고량으로 제한
- 초과 시 에러 메시지 표시
- 실시간 재고 확인 API 연동

Closes #234
```

---

## 자주 사용하는 동사

| 동사 | 사용 상황 |
|------|----------|
| add | 새로운 기능/파일 추가 |
| remove | 기능/파일 삭제 |
| update | 기존 기능 수정/개선 |
| fix | 버그 수정 |
| refactor | 코드 구조 개선 |
| rename | 이름 변경 |
| move | 파일/코드 이동 |
| extract | 코드 분리/추출 |
| simplify | 코드 단순화 |
| optimize | 성능 최적화 |

---

## Commit Lint 설정

```javascript
// commitlint.config.js
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      ['feat', 'fix', 'docs', 'style', 'refactor', 'perf', 'test', 'chore', 'ci', 'revert']
    ],
    'scope-case': [2, 'always', 'lower-case'],
    'subject-case': [2, 'always', 'lower-case'],
    'subject-max-length': [2, 'always', 50],
    'body-max-line-length': [2, 'always', 72]
  }
};
```
