# 코드 리팩토링 완료 보고서

**리팩토링 일자**: 2026-02-10
**목적**: 코드 품질 향상 및 유지보수성 개선

---

## ✅ 완료된 리팩토링 (2개)

### 1. SQLLoader 캐싱 이슈 해결 ⭐

#### 문제점 (MEMORY.md에 문서화됨)
```
SQL 파일을 수정해도 서버가 이전 쿼리를 계속 사용
- 원인: 모듈 레벨에서 SQLLoader 인스턴스가 캐시됨
- 결과: 서버 재시작 필요
- 개발 생산성: 저하
```

#### 해결 방안

**파일**: `src/shared/utils/sql_loader.py`

**주요 개선사항**:

1. **파일 수정 감지 (mtime tracking)**
   ```python
   def _is_file_modified(self, file_path: Path) -> bool:
       """파일 수정 시간 체크"""
       current_mtime = file_path.stat().st_mtime
       cached_mtime = self._mtime_cache[filename]
       return current_mtime > cached_mtime
   ```
   - SQL 파일 변경 시 자동으로 캐시 무효화
   - 개발 환경에서 서버 재시작 불필요

2. **Reload 메서드 추가**
   ```python
   def reload(self, filename: str | None = None):
       """특정 파일 또는 전체 캐시 리로드"""

   def clear_cache(self):
       """전체 캐시 클리어"""
   ```

3. **Singleton 패턴**
   ```python
   _loader_instances: dict[str, SQLLoader] = {}

   def create_sql_loader(domain: str) -> SQLLoader:
       """도메인당 하나의 인스턴스 유지"""
       if domain not in _loader_instances:
           _loader_instances[domain] = SQLLoader(domain)
       return _loader_instances[domain]
   ```

4. **캐시 통계**
   ```python
   def get_cache_stats(self) -> dict[str, int]:
       """캐시 상태 확인"""
       return {
           "cached_files": len(self._cache),
           "tracked_files": len(self._mtime_cache),
       }
   ```

**효과**:
- ✅ SQL 파일 수정 시 자동 reload
- ✅ 개발 생산성 향상 (재시작 불필요)
- ✅ 싱글톤 패턴으로 메모리 효율
- ✅ 명시적 reload API 제공

---

### 2. login() 함수 분해 (138줄 → 5개 함수)

#### 문제점
```python
# Before: 138줄의 거대한 함수
async def login(...):
    # 계정 잠금 확인
    # 사용자 조회
    # 비밀번호 검증
    # 계정 활성화 확인
    # 권한 조회
    # 토큰 생성
    # JTI 등록
    # 토큰 해시
    # DB 저장 (트랜잭션)
    # 실패 횟수 초기화
    # 138 lines...
```

**문제**:
- 단일 함수가 너무 많은 책임
- 테스트 어려움
- 재사용 불가능
- 가독성 저하

#### 해결 방안

**파일**: `src/domains/authentication/service.py`

**분해 결과**:

```python
# 1. 계정 잠금 확인 (15줄)
async def _check_account_locked(email: str) -> None:
    """계정 잠금 상태 확인"""

# 2. 사용자 인증 (45줄)
async def _authenticate_user(
    connection, email, password, ip_address, user_agent
) -> asyncpg.Record:
    """이메일/비밀번호 검증 + 실패 처리"""

# 3. 토큰 생성 (28줄)
async def _create_auth_tokens(
    connection, user_id, email
) -> tuple[str, str]:
    """Access Token + Refresh Token 생성"""

# 4. 로그인 데이터 저장 (35줄)
async def _save_login_success(
    connection, user_id, refresh_token, ...
) -> None:
    """DB 저장 (트랜잭션)"""

# 5. 메인 함수 (40줄)
async def login(...) -> schemas.TokenResponse:
    """각 단계를 순차적으로 호출"""
    await _check_account_locked(request.email)
    user_row = await _authenticate_user(...)
    access_token, refresh_token = await _create_auth_tokens(...)
    await _save_login_success(...)
    await redis_store.reset_failed_login(request.email)
    return TokenResponse(...)
```

**개선 효과**:
- ✅ 단일 책임 원칙 (SRP) 준수
- ✅ 각 함수 독립 테스트 가능
- ✅ 재사용 가능 (예: _create_auth_tokens를 OAuth에서 재사용)
- ✅ 가독성 향상 (함수명으로 의도 명확)
- ✅ 유지보수 쉬움

**테스트 결과**:
```bash
$ python test_login.py
Success: True
Has access_token: True
Has refresh_token: True
Status code: 200
```

---

## 📊 코드 품질 개선 효과

### Before (리팩토링 전)

```
SQLLoader:
  - SQL 파일 수정 시 서버 재시작 필요
  - 개발 생산성: 낮음

login() 함수:
  - 138줄의 거대한 함수
  - 복잡도: 높음
  - 테스트: 어려움
  - 재사용: 불가능
```

### After (리팩토링 후)

```
SQLLoader:
  - 파일 수정 자동 감지
  - 개발 생산성: 높음 ✅

login() 함수:
  - 5개의 작은 함수 (평균 30줄)
  - 복잡도: 낮음 ✅
  - 테스트: 쉬움 ✅
  - 재사용: 가능 ✅
```

---

## 🔍 추가 리팩토링 후보

### 1. 다른 긴 함수들

```python
# 아직 리팩토링 필요
src/domains/authentication/service.py:204 - refresh_access_token() (89줄)
src/domains/users/service.py:65 - register() (61줄)
src/domains/users/service.py:206 - change_password() (57줄)
```

**권장 사항**:
- `refresh_access_token()` 함수도 login()과 유사하게 분해
- `register()` 함수: 비밀번호 검증, 사용자 생성, 역할 할당 분리
- `change_password()`: 검증, 업데이트 분리

### 2. Magic Strings/Numbers 제거

```python
# Before
if failed_count >= 5:  # Magic number
    raise UnauthorizedException(
        error_code="AUTH_004",  # Magic string
        ...
    )

# After (constants.py 생성)
from src.shared.constants import (
    MAX_LOGIN_ATTEMPTS,
    ERROR_CODE_ACCOUNT_LOCKED,
)

if failed_count >= MAX_LOGIN_ATTEMPTS:
    raise UnauthorizedException(
        error_code=ERROR_CODE_ACCOUNT_LOCKED,
        ...
    )
```

### 3. 중복 코드 제거

```python
# 여러 곳에서 반복되는 패턴
user_row = await repository.get_user_by_id(connection, user_id)
if not user_row:
    raise NotFoundException(
        error_code="USER_002",
        message="사용자를 찾을 수 없습니다",
    )

# 헬퍼 함수로 추출
async def get_user_or_404(connection, user_id) -> asyncpg.Record:
    """사용자 조회 또는 404 에러"""
    user_row = await repository.get_user_by_id(connection, user_id)
    if not user_row:
        raise NotFoundException(...)
    return user_row
```

### 4. 예외 처리 데코레이터

```python
# 공통 예외 처리 패턴
@handle_db_errors
@log_execution_time
async def some_function(...):
    """자동으로 예외 처리 및 로깅"""
```

---

## 📝 변경된 파일 목록

### 수정 (2개)
```
src/shared/utils/sql_loader.py
  - 파일 수정 감지 추가
  - reload(), clear_cache() 메서드 추가
  - 싱글톤 패턴 적용
  - get_cache_stats() 통계 추가
  - 200줄로 확장 (35줄 → 200줄)

src/domains/authentication/service.py
  - login() 함수 분해 (5개 헬퍼 함수)
  - 138줄 → 평균 30줄씩 5개 함수
  - 가독성 및 테스트 용이성 향상
```

---

## 🎯 리팩토링 Best Practices 적용

### 1. 단일 책임 원칙 (SRP)
- ✅ 각 함수가 하나의 명확한 책임만 가짐
- ✅ `_check_account_locked`: 계정 잠금만 확인
- ✅ `_authenticate_user`: 인증만 수행

### 2. 함수 이름으로 의도 표현
- ✅ `_check_account_locked` - 무엇을 하는지 명확
- ✅ `_create_auth_tokens` - 토큰 생성임을 알 수 있음

### 3. 작은 함수 (20-40줄)
- ✅ 화면 하나에 전체 로직 파악 가능
- ✅ 빠른 이해 및 수정

### 4. 테스트 가능성
- ✅ 각 함수 독립적으로 테스트 가능
- ✅ Mock 최소화

### 5. 재사용성
- ✅ `_create_auth_tokens`를 OAuth 로그인에서 재사용 가능
- ✅ `_check_account_locked`를 다른 인증 플로우에서 재사용

---

## 🛠️ 사용 가이드

### SQLLoader 수정 감지 테스트

```bash
# 1. 서버 시작
uvicorn src.main:app --port 8000

# 2. SQL 파일 수정
echo "-- Updated query" >> src/domains/users/sql/queries/get_user_by_id.sql

# 3. API 호출 (자동으로 수정된 쿼리 사용)
curl http://localhost:8000/api/v1/users/profile

# 4. 서버 재시작 불필요! ✅
```

### 수동 Reload (필요 시)

```python
from src.shared.utils.sql_loader import reload_all_loaders

# 모든 SQLLoader 캐시 클리어
reload_all_loaders()

# 또는 특정 loader만
sql = create_sql_loader("users")
sql.reload()  # users 도메인 캐시만 클리어
```

---

## ✅ 완료 체크리스트

### SQLLoader 개선
- [x] 파일 수정 감지 (mtime tracking)
- [x] reload() 메서드 추가
- [x] clear_cache() 메서드 추가
- [x] 싱글톤 패턴 적용
- [x] get_cache_stats() 통계 추가
- [x] 테스트 완료

### login() 함수 리팩토링
- [x] 5개 헬퍼 함수로 분해
- [x] 단일 책임 원칙 적용
- [x] 가독성 향상
- [x] 테스트 완료

### 문서화
- [x] 리팩토링 보고서 작성
- [x] 코드 주석 업데이트

---

## 📚 참고 자료

- [Clean Code by Robert C. Martin](https://www.amazon.com/Clean-Code-Handbook-Software-Craftsmanship/dp/0132350882)
- [Refactoring by Martin Fowler](https://refactoring.com/)
- [Python Best Practices](https://docs.python-guide.org/writing/style/)

---

## 🎓 학습 내용

### 1. 파일 수정 감지 (mtime)
```python
# os.stat()로 파일 수정 시간 확인
mtime = file_path.stat().st_mtime

# 캐시된 mtime과 비교
if current_mtime > cached_mtime:
    # 파일이 수정됨, 캐시 무효화
    invalidate_cache()
```

### 2. 함수 분해 원칙
- 50줄 이상 → 분해 고려
- 여러 책임 → 각각 함수로 분리
- 반복 패턴 → 헬퍼 함수 추출

### 3. 네이밍 컨벤션
- Private 헬퍼: `_check_something`
- Public API: `check_something`
- 의도 표현: `_authenticate_user` > `_check_password`

---

**종합 평가**: 🎉 **코드 리팩토링 성공!**

- SQLLoader 캐싱 이슈 해결 (개발 생산성 향상)
- login() 함수 분해 (가독성 및 유지보수성 향상)
- 추가 리팩토링 후보 식별

**다음 단계**:
- 다른 긴 함수 리팩토링 (refresh_access_token, register, change_password)
- Magic strings/numbers 상수화
- 중복 코드 제거

**문의**: 추가 리팩토링이 필요하면 말씀해주세요!
