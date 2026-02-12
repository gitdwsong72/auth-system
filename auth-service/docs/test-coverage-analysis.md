# Test Coverage Analysis Report

## Executive Summary

**Report Date**: 2026-02-10
**Auditor**: Test Coverage Auditor
**Current Coverage**: Authentication & Users domains (partial)

### Critical Findings

- **5개 주요 기능 영역 완전 미테스트** (OAuth, MFA, API Keys, Roles, Permissions)
- **Edge Case 테스트 부족** (토큰 만료, 동시성, 에러 복구)
- **통합 테스트 미흡** (E2E 플로우 제한적)

---

## 1. 현재 테스트 현황

### 1.1 기존 테스트 파일 목록

#### Unit Tests
- `/Users/sktl/WF/WF01/auth-system/auth-service/tests/unit/test_auth_service.py`
  - 로그인 성공/실패 (비밀번호 불일치, 계정 잠김, 비활성화 계정)
  - 로그아웃
  - 토큰 갱신 성공/실패
  - 전체 세션 종료

- `/Users/sktl/WF/WF01/auth-system/auth-service/tests/unit/test_users_service.py`
  - 회원가입 성공/실패 (이메일 중복, 약한 비밀번호)
  - 비밀번호 변경 성공/실패
  - 사용자 목록 조회

#### Integration Tests
- `/Users/sktl/WF/WF01/auth-system/auth-service/tests/integration/test_auth_api.py`
  - 로그인/로그아웃 API
  - 토큰 갱신 API
  - 세션 관리 API
  - 전체 인증 플로우 (회원가입 → 로그인 → 프로필 조회 → 토큰 갱신 → 로그아웃)

- `/Users/sktl/WF/WF01/auth-system/auth-service/tests/integration/test_users_api.py`
  - 회원가입 API
  - 프로필 조회/수정 API
  - 비밀번호 변경 API
  - 권한 검증 (users:read 없을 때 403)

---

## 2. 미테스트 기능 목록

### 2.1 Critical Priority (P0) - 핵심 보안 기능

#### A. OAuth/소셜 로그인 (oauth_accounts 테이블)
**Status**: 완전 미구현
**DB Schema**: `/Users/sktl/WF/WF01/auth-system/auth-service/scripts/init.sql:131-154`

**필수 테스트 케이스**:
1. OAuth 계정 연동 (Google, GitHub, Kakao)
2. OAuth 로그인 시 기존 사용자 매칭 (provider_email 기반)
3. OAuth 로그인 시 신규 사용자 생성
4. 하나의 사용자에게 여러 OAuth 계정 연결
5. OAuth 토큰 갱신 (token_expires_at 기반)
6. OAuth 계정 연결 해제
7. raw_data JSONB 저장/조회

**Edge Cases**:
- provider_email이 기존 사용자의 email과 충돌할 때
- OAuth 제공자에서 이메일을 제공하지 않을 때
- 이미 연결된 소셜 계정을 다른 사용자가 연결 시도할 때

---

#### B. Multi-Factor Authentication (mfa_devices 테이블)
**Status**: 완전 미구현
**DB Schema**: `/Users/sktl/WF/WF01/auth-system/auth-service/scripts/init.sql:194-216`

**필수 테스트 케이스**:
1. TOTP 디바이스 등록
   - QR 코드 생성
   - 6자리 코드 검증
   - secret_encrypted 암호화 저장
2. SMS 디바이스 등록
   - 전화번호 검증
   - SMS 코드 전송/검증
3. MFA 로그인 플로우
   - 1차 인증 (password) 성공 후 2차 인증 요구
   - TOTP 코드 검증
   - SMS 코드 검증
4. Primary 디바이스 설정
   - is_primary = true 변경 시 기존 primary 해제
5. MFA 디바이스 삭제 (soft delete)
6. 복수 디바이스 관리

**Edge Cases**:
- TOTP 코드 시간 윈도우 만료
- SMS 재전송 제한 (rate limiting)
- 모든 MFA 디바이스 삭제 시 MFA 비활성화
- MFA 코드 5회 실패 시 계정 잠금

---

#### C. API Keys (api_keys 테이블)
**Status**: 완전 미구현
**DB Schema**: `/Users/sktl/WF/WF01/auth-system/auth-service/scripts/init.sql:224-250`

**필수 테스트 케이스**:
1. API 키 생성
   - key_prefix 자동 생성 (예: `ak_3f8x`)
   - key_hash SHA-256 저장
   - 원본 키는 생성 시 1회만 반환
2. API 키 인증
   - Authorization: Bearer {api_key}
   - key_hash 검증
   - scopes 검증 (허용된 스코프만 접근 가능)
3. API 키 Rate Limiting
   - rate_limit 필드 기반 분당 요청 제한
   - Redis 카운터 사용
4. API 키 만료
   - expires_at 검증
   - 만료된 키로 요청 시 401
5. API 키 폐기 (revoked_at 설정)
6. last_used_at 업데이트

**Edge Cases**:
- 같은 키로 동시 요청 (rate limit 정확성)
- 키 생성 시 랜덤 collision (key_prefix 중복)
- scopes JSON 배열 검증 (잘못된 형식)

---

### 2.2 High Priority (P1) - 권한 관리 기능

#### D. Roles CRUD (roles 테이블)
**Status**: 조회만 구현, CRUD 미구현
**DB Schema**: `/Users/sktl/WF/WF01/auth-system/auth-service/scripts/init.sql:51-63`

**필수 테스트 케이스**:
1. 역할 생성
   - name, display_name, description 저장
   - name 유니크 제약 검증
2. 역할 수정
   - is_system = true 역할은 수정 제한
3. 역할 삭제 (soft delete)
   - is_system = true 역할은 삭제 불가
   - 사용자에게 할당된 역할 삭제 시 연쇄 동작 (CASCADE)
4. 역할 목록 조회
5. 역할 상세 조회 (권한 목록 포함)

**Edge Cases**:
- admin 역할 삭제 시도 (is_system = true)
- 역할 삭제 후 해당 역할을 가진 사용자의 권한 확인

---

#### E. Permissions CRUD (permissions 테이블)
**Status**: 조회만 구현, CRUD 미구현
**DB Schema**: `/Users/sktl/WF/WF01/auth-system/auth-service/scripts/init.sql:71-83`

**필수 테스트 케이스**:
1. 권한 생성
   - resource + action 조합 (예: users:read)
   - UNIQUE 제약 검증 (resource, action)
2. 권한 삭제
   - role_permissions 연쇄 삭제 확인
3. 권한 목록 조회
   - resource별 그룹화
4. 역할에 권한 부여/제거
   - role_permissions junction 테이블 조작

**Edge Cases**:
- 존재하지 않는 resource/action 조합 생성
- 권한 삭제 시 해당 권한을 가진 모든 역할에서 제거 확인

---

#### F. User-Role 관리 (user_roles 테이블)
**Status**: assign_default_role만 구현, 동적 관리 미구현
**DB Schema**: `/Users/sktl/WF/WF01/auth-system/auth-service/scripts/init.sql:90-106`

**필수 테스트 케이스**:
1. 사용자에게 역할 부여
   - granted_by (부여한 관리자) 저장
   - expires_at 설정 (임시 역할)
2. 사용자 역할 제거
3. 역할 만료 처리
   - expires_at 지난 역할 자동 무효화
4. 사용자별 역할 목록 조회

**Edge Cases**:
- 이미 가진 역할 중복 부여 시도
- expires_at 지난 역할로 권한 확인 시 거부
- granted_by 사용자가 삭제된 경우 (ON DELETE SET NULL)

---

### 2.3 Medium Priority (P2) - 감사 로그 및 세션 관리

#### G. Login Histories 조회 (login_histories 테이블)
**Status**: 저장은 구현, 조회/분석 미구현
**DB Schema**: `/Users/sktl/WF/WF01/auth-system/auth-service/scripts/init.sql:258-282`
**SQL File**: `/Users/sktl/WF/WF01/auth-system/auth-service/src/domains/authentication/sql/queries/get_login_history.sql`

**필수 테스트 케이스**:
1. 로그인 이력 조회
   - 사용자별 로그인 이력 (success = true/false)
   - 날짜 범위 필터
   - login_type 필터 (password, oauth, api_key, mfa)
2. 로그인 실패 분석
   - failure_reason 통계
   - IP 주소별 실패 횟수
3. 보안 감사
   - 특정 IP에서 다수 계정 접근 시도 탐지
   - 특정 계정에 다수 IP에서 접근 시도 탐지

**Edge Cases**:
- user_id = NULL (존재하지 않는 계정 시도)
- ip_address = NULL (로컬 테스트 환경)

---

#### H. Refresh Token 세션 관리 강화
**Status**: 기본 기능만 구현, 세션 제어 미흡
**Current File**: `/Users/sktl/WF/WF01/auth-system/auth-service/src/domains/authentication/service.py:280-316`

**필수 테스트 케이스**:
1. 디바이스별 세션 구분
   - device_info JSONB 활용
   - 동일 사용자의 여러 디바이스 동시 로그인
2. 특정 세션 종료
   - 세션 ID로 개별 refresh_token 폐기
3. 세션 갱신 시 device_info 업데이트
4. 만료된 토큰 자동 정리 (cronjob)

**Edge Cases**:
- 100개 이상의 활성 세션 (세션 수 제한 정책)
- 동일 device_info로 동시 로그인 시도

---

### 2.4 Low Priority (P3) - 기타 기능

#### I. 사용자 Soft Delete 및 복구
**Status**: soft_delete_user.sql 존재하나 서비스 레이어 미구현
**SQL File**: `/Users/sktl/WF/WF01/auth-system/auth-service/src/domains/users/sql/commands/soft_delete_user.sql`

**필수 테스트 케이스**:
1. 사용자 비활성화 (deleted_at 설정)
2. 비활성화된 사용자 로그인 차단
3. 비활성화된 사용자 복구 (deleted_at = NULL)
4. 비활성화된 사용자의 이메일 재사용 불가

---

#### J. 이메일/전화번호 인증
**Status**: 컬럼만 존재, 인증 로직 미구현
**Schema**: `email_verified`, `phone_verified`

**필수 테스트 케이스**:
1. 이메일 인증 코드 발송
2. 이메일 인증 코드 검증
3. 전화번호 인증 코드 발송 (SMS)
4. 전화번호 인증 코드 검증

---

## 3. 우선순위 매트릭스

| 기능 영역 | 우선순위 | 보안 영향 | 비즈니스 영향 | 복잡도 | 권장 순서 |
|---------|---------|----------|-------------|--------|----------|
| A. OAuth/소셜 로그인 | **P0** | 높음 | 높음 | 높음 | 1 |
| B. MFA | **P0** | 매우 높음 | 중간 | 높음 | 2 |
| C. API Keys | **P0** | 매우 높음 | 높음 | 중간 | 3 |
| D. Roles CRUD | **P1** | 중간 | 높음 | 낮음 | 4 |
| E. Permissions CRUD | **P1** | 중간 | 높음 | 낮음 | 5 |
| F. User-Role 관리 | **P1** | 중간 | 높음 | 중간 | 6 |
| G. Login Histories | **P2** | 낮음 | 중간 | 낮음 | 7 |
| H. 세션 관리 강화 | **P2** | 중간 | 중간 | 중간 | 8 |
| I. Soft Delete | **P3** | 낮음 | 낮음 | 낮음 | 9 |
| J. 이메일/전화번호 인증 | **P3** | 낮음 | 중간 | 중간 | 10 |

---

## 4. 테스트 케이스 템플릿 (AAA 패턴)

### 4.1 Unit Test 템플릿

```python
"""OAuth 인증 서비스 단위 테스트"""

from unittest.mock import AsyncMock, patch
import pytest
import pytest_asyncio

from src.domains.oauth import schemas, service
from src.shared.exceptions import ConflictException, NotFoundException

@pytest_asyncio.fixture
def mock_connection():
    """Mock database connection"""
    return AsyncMock()

@pytest.mark.asyncio
class TestOAuthService:
    """OAuth 인증 서비스 테스트"""

    async def test_link_oauth_account_success(self, mock_connection):
        """OAuth 계정 연동 성공"""
        # Arrange
        user_id = 1
        oauth_data = schemas.OAuthLinkRequest(
            provider="google",
            provider_user_id="google_123",
            provider_email="user@gmail.com",
            access_token="google_access_token",
            refresh_token="google_refresh_token",
            raw_data={"name": "Test User"},
        )

        mock_oauth_row = {
            "id": 1,
            "user_id": user_id,
            "provider": "google",
            "provider_user_id": "google_123",
            "linked_at": "2024-01-01T00:00:00Z",
        }

        with patch(
            "src.domains.oauth.repository.get_oauth_account_by_provider",
            return_value=None,  # 기존 연동 없음
        ), patch(
            "src.domains.oauth.repository.create_oauth_account",
            return_value=mock_oauth_row,
        ):
            # Act
            result = await service.link_oauth_account(mock_connection, user_id, oauth_data)

            # Assert
            assert result.provider == "google"
            assert result.provider_user_id == "google_123"

    async def test_link_oauth_account_already_linked(self, mock_connection):
        """OAuth 계정 연동 실패 - 이미 다른 사용자에게 연결됨"""
        # Arrange
        user_id = 1
        oauth_data = schemas.OAuthLinkRequest(
            provider="google",
            provider_user_id="google_123",
            provider_email="user@gmail.com",
        )

        mock_existing_oauth = {
            "id": 1,
            "user_id": 999,  # 다른 사용자
            "provider": "google",
            "provider_user_id": "google_123",
        }

        with patch(
            "src.domains.oauth.repository.get_oauth_account_by_provider",
            return_value=mock_existing_oauth,
        ):
            # Act & Assert
            with pytest.raises(ConflictException) as exc_info:
                await service.link_oauth_account(mock_connection, user_id, oauth_data)

            assert exc_info.value.error_code == "OAUTH_001"
            assert "이미 연결된" in exc_info.value.message
```

### 4.2 Integration Test 템플릿

```python
"""OAuth API 통합 테스트"""

import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
class TestOAuthAPI:
    """OAuth API 테스트"""

    async def test_oauth_login_flow_google(self, client: AsyncClient):
        """OAuth 로그인 플로우 - Google (신규 사용자)"""
        # Arrange - Mock OAuth callback data
        oauth_callback_payload = {
            "provider": "google",
            "code": "mock_authorization_code",
        }

        # Act - OAuth callback 처리
        response = await client.post("/api/v1/auth/oauth/callback", json=oauth_callback_payload)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]
        assert data["data"]["user"]["email"].endswith("@gmail.com")

    async def test_oauth_link_to_existing_user(self, client: AsyncClient, auth_headers: dict):
        """기존 사용자에게 OAuth 계정 연결"""
        # Arrange
        link_payload = {
            "provider": "github",
            "code": "mock_github_code",
        }

        # Act - 인증된 사용자가 GitHub 연결
        response = await client.post(
            "/api/v1/users/me/oauth/link",
            json=link_payload,
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["provider"] == "github"

        # Verify - 프로필 조회 시 OAuth 계정 포함
        profile_response = await client.get("/api/v1/users/me", headers=auth_headers)
        profile_data = profile_response.json()["data"]
        assert len(profile_data["oauth_accounts"]) >= 1
        assert any(oa["provider"] == "github" for oa in profile_data["oauth_accounts"])
```

---

## 5. Edge Case 테스트 시나리오

### 5.1 토큰 만료 및 갱신

```python
async def test_access_token_expired_during_request(self, client: AsyncClient):
    """요청 중 액세스 토큰 만료"""
    # Arrange - 만료 직전 토큰 생성 (exp: 현재 + 1초)
    short_lived_token = jwt_handler.create_access_token(
        user_id=1,
        email="test@example.com",
        roles=["user"],
        permissions=["users:read"],
        expires_delta=timedelta(seconds=1),
    )

    # Wait for token to expire
    await asyncio.sleep(2)

    # Act - 만료된 토큰으로 요청
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {short_lived_token}"},
    )

    # Assert
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_003"


async def test_refresh_token_rotation_race_condition(self, client: AsyncClient):
    """동시 토큰 갱신 요청 (Refresh Token Rotation)"""
    # Arrange - 로그인하여 refresh_token 획득
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "Test1234!"},
    )
    refresh_token = login_response.json()["data"]["refresh_token"]

    # Act - 동일한 refresh_token으로 동시 2회 갱신 시도
    refresh_payload = {"refresh_token": refresh_token}
    results = await asyncio.gather(
        client.post("/api/v1/auth/refresh", json=refresh_payload),
        client.post("/api/v1/auth/refresh", json=refresh_payload),
        return_exceptions=True,
    )

    # Assert - 하나는 성공, 하나는 실패 (이미 폐기된 토큰)
    status_codes = [r.status_code for r in results if not isinstance(r, Exception)]
    assert 200 in status_codes
    assert 401 in status_codes
```

### 5.2 동시성 및 Race Condition

```python
async def test_concurrent_role_assignment(self, client: AsyncClient, admin_headers: dict):
    """동일 사용자에게 동시 역할 부여"""
    # Arrange
    user_id = 1
    assign_payload = {
        "role_name": "manager",
        "expires_at": None,
    }

    # Act - 동시 5회 역할 부여
    results = await asyncio.gather(
        *[
            client.post(f"/api/v1/users/{user_id}/roles", json=assign_payload, headers=admin_headers)
            for _ in range(5)
        ],
        return_exceptions=True,
    )

    # Assert - 첫 번째만 성공 (201), 나머지는 중복 오류 (409)
    status_codes = [r.status_code for r in results if not isinstance(r, Exception)]
    assert status_codes.count(201) == 1
    assert status_codes.count(409) == 4
```

### 5.3 보안 경계 테스트

```python
async def test_sql_injection_in_search_parameter(self, client: AsyncClient, admin_headers: dict):
    """사용자 검색 시 SQL Injection 시도"""
    # Arrange - SQL Injection 페이로드
    malicious_payloads = [
        "admin' OR '1'='1",
        "'; DROP TABLE users; --",
        "admin' UNION SELECT * FROM permissions --",
    ]

    for payload in malicious_payloads:
        # Act
        response = await client.get(
            f"/api/v1/users?search={payload}",
            headers=admin_headers,
        )

        # Assert - 정상 처리 (결과 없음 또는 에스케이핑)
        assert response.status_code in [200, 400]
        if response.status_code == 200:
            assert response.json()["data"]["items"] == []


async def test_jwt_token_tampering(self, client: AsyncClient):
    """JWT 토큰 변조 시도"""
    # Arrange - 유효한 토큰 생성 후 payload 변조
    valid_token = jwt_handler.create_access_token(
        user_id=1,
        email="user@example.com",
        roles=["user"],
        permissions=["users:read"],
    )

    # 토큰 분해 후 payload 변조 (user_id: 1 → 2)
    parts = valid_token.split(".")
    tampered_payload = base64.urlsafe_b64encode(
        json.dumps({"sub": 2, "email": "admin@example.com", "roles": ["admin"]}).encode()
    ).decode().rstrip("=")
    tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"

    # Act
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )

    # Assert - 서명 검증 실패로 401
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_003"
```

---

## 6. Mock 개선 제안

### 6.1 Redis Mock 추상화

현재 문제:
```python
# 테스트마다 Redis mock 중복
with patch("src.domains.authentication.service.redis_store.is_account_locked", return_value=(False, 0)):
    ...
```

개선 방안:
```python
# tests/fixtures/redis_mock.py
@pytest.fixture
def mock_redis_store():
    """Redis Store 통합 mock"""
    with patch("src.shared.security.redis_store.redis_store") as mock_redis:
        mock_redis.is_account_locked.return_value = (False, 0)
        mock_redis.increment_failed_login.return_value = 1
        mock_redis.reset_failed_login.return_value = None
        mock_redis.blacklist_token.return_value = None
        yield mock_redis

# 사용
async def test_login_success(self, mock_connection, mock_redis_store):
    ...
```

### 6.2 JWT Handler Mock Factory

```python
# tests/factories/jwt_factory.py
class JWTTokenFactory:
    """JWT 토큰 테스트 팩토리"""

    @staticmethod
    def create_access_token(
        user_id: int = 1,
        email: str = "test@example.com",
        roles: list[str] = None,
        permissions: list[str] = None,
        expires_delta: timedelta = None,
    ) -> str:
        """테스트용 액세스 토큰 생성"""
        if roles is None:
            roles = ["user"]
        if permissions is None:
            permissions = ["users:read"]

        return jwt_handler.create_access_token(
            user_id=user_id,
            email=email,
            roles=roles,
            permissions=permissions,
            expires_delta=expires_delta,
        )

    @staticmethod
    def create_expired_token(**kwargs) -> str:
        """만료된 토큰 생성"""
        return JWTTokenFactory.create_access_token(
            expires_delta=timedelta(seconds=-1),
            **kwargs,
        )

# 사용
async def test_expired_token(self, client: AsyncClient):
    expired_token = JWTTokenFactory.create_expired_token(user_id=1)
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
```

---

## 7. 통합 테스트 확대 제안

### 7.1 E2E 플로우 시나리오

#### Scenario 1: 완전한 사용자 라이프사이클
```python
async def test_complete_user_lifecycle(self, client: AsyncClient, admin_headers: dict):
    """완전한 사용자 라이프사이클 테스트"""
    # 1. 회원가입
    register_response = await client.post(
        "/api/v1/users/register",
        json={
            "email": "newuser@example.com",
            "password": "NewUser123!",
            "username": "newuser",
        },
    )
    assert register_response.status_code == 201
    user_id = register_response.json()["data"]["id"]

    # 2. 이메일 인증 (미구현 - skip)
    # verify_response = await client.post(f"/api/v1/users/{user_id}/verify-email", ...)

    # 3. 로그인
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "newuser@example.com", "password": "NewUser123!"},
    )
    assert login_response.status_code == 200
    tokens = login_response.json()["data"]
    user_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # 4. 프로필 조회
    profile_response = await client.get("/api/v1/users/me", headers=user_headers)
    assert profile_response.status_code == 200
    assert profile_response.json()["data"]["email"] == "newuser@example.com"

    # 5. OAuth 계정 연결 (미구현 - skip)
    # link_response = await client.post("/api/v1/users/me/oauth/link", ...)

    # 6. MFA 설정 (미구현 - skip)
    # mfa_response = await client.post("/api/v1/users/me/mfa/totp", ...)

    # 7. 관리자가 역할 부여 (미구현 - skip)
    # assign_role_response = await client.post(
    #     f"/api/v1/users/{user_id}/roles",
    #     json={"role_name": "manager"},
    #     headers=admin_headers,
    # )

    # 8. 비밀번호 변경
    change_password_response = await client.put(
        "/api/v1/users/me/password",
        json={"current_password": "NewUser123!", "new_password": "NewPassword456!"},
        headers=user_headers,
    )
    assert change_password_response.status_code == 200

    # 9. 새 비밀번호로 로그인 확인
    login2_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "newuser@example.com", "password": "NewPassword456!"},
    )
    assert login2_response.status_code == 200

    # 10. 모든 세션 종료
    revoke_response = await client.delete("/api/v1/auth/sessions", headers=user_headers)
    assert revoke_response.status_code == 200

    # 11. 종료된 토큰으로 접근 시도 (refresh_token 폐기됨)
    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 401
```

#### Scenario 2: 다중 디바이스 세션 관리
```python
async def test_multi_device_session_management(self, client: AsyncClient):
    """다중 디바이스 세션 관리"""
    # 1. 회원가입
    await client.post(
        "/api/v1/users/register",
        json={"email": "multi@example.com", "password": "Multi123!", "username": "multi"},
    )

    # 2. Desktop 로그인
    desktop_login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "multi@example.com",
            "password": "Multi123!",
            "device_info": "Chrome on Windows",
        },
    )
    desktop_tokens = desktop_login.json()["data"]

    # 3. Mobile 로그인
    mobile_login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "multi@example.com",
            "password": "Multi123!",
            "device_info": "Safari on iPhone",
        },
    )
    mobile_tokens = mobile_login.json()["data"]

    # 4. Tablet 로그인
    tablet_login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "multi@example.com",
            "password": "Multi123!",
            "device_info": "Chrome on iPad",
        },
    )
    tablet_tokens = tablet_login.json()["data"]

    # 5. 활성 세션 목록 조회 (3개)
    sessions_response = await client.get(
        "/api/v1/auth/sessions",
        headers={"Authorization": f"Bearer {desktop_tokens['access_token']}"},
    )
    sessions = sessions_response.json()["data"]
    assert len(sessions) == 3
    assert any("Windows" in s["device_info"] for s in sessions)
    assert any("iPhone" in s["device_info"] for s in sessions)
    assert any("iPad" in s["device_info"] for s in sessions)

    # 6. Mobile 세션만 종료 (미구현 - 개별 세션 종료 기능 필요)
    # revoke_mobile_response = await client.delete(
    #     f"/api/v1/auth/sessions/{sessions[1]['id']}",
    #     headers={"Authorization": f"Bearer {desktop_tokens['access_token']}"},
    # )

    # 7. Desktop에서 전체 세션 종료
    revoke_all_response = await client.delete(
        "/api/v1/auth/sessions",
        headers={"Authorization": f"Bearer {desktop_tokens['access_token']}"},
    )
    assert revoke_all_response.status_code == 200

    # 8. 모든 디바이스의 refresh_token 무효화 확인
    for tokens in [desktop_tokens, mobile_tokens, tablet_tokens]:
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert refresh_response.status_code == 401
```

---

## 8. 테스트 커버리지 목표

### 8.1 목표 메트릭

| 레이어 | 현재 커버리지 (추정) | 목표 커버리지 | 우선순위 |
|--------|-------------------|--------------|----------|
| Service Layer | 40% | 85% | High |
| Repository Layer | 30% | 80% | Medium |
| Router Layer | 50% | 90% | High |
| Utils/Security | 20% | 70% | Medium |

### 8.2 단계별 로드맵

#### Phase 1: Critical Features (2-3주)
- OAuth 인증 시스템 (10개 테스트 케이스)
- MFA 시스템 (12개 테스트 케이스)
- API Keys 시스템 (8개 테스트 케이스)

#### Phase 2: Permission Management (1-2주)
- Roles CRUD (6개 테스트 케이스)
- Permissions CRUD (5개 테스트 케이스)
- User-Role 관리 (7개 테스트 케이스)

#### Phase 3: Edge Cases & Integration (1주)
- Edge Case 시나리오 (15개)
- E2E 통합 테스트 (5개)
- Mock 개선 및 리팩토링

---

## 9. 테스트 인프라 개선 제안

### 9.1 Fixture 중앙화

```python
# tests/fixtures/auth_fixtures.py
@pytest.fixture
async def authenticated_user(client: AsyncClient) -> dict:
    """인증된 일반 사용자 fixture"""
    # 회원가입
    await client.post(
        "/api/v1/users/register",
        json={"email": "testuser@example.com", "password": "Test1234!", "username": "testuser"},
    )

    # 로그인
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "testuser@example.com", "password": "Test1234!"},
    )
    tokens = login_response.json()["data"]

    return {
        "email": "testuser@example.com",
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "headers": {"Authorization": f"Bearer {tokens['access_token']}"},
    }


@pytest.fixture
async def admin_user(client: AsyncClient) -> dict:
    """인증된 관리자 fixture"""
    # 회원가입
    register_response = await client.post(
        "/api/v1/users/register",
        json={"email": "admin@example.com", "password": "Admin1234!", "username": "admin"},
    )
    user_id = register_response.json()["data"]["id"]

    # TODO: 관리자 역할 부여 (Roles CRUD 구현 후)
    # await assign_role(user_id, "admin")

    # 로그인
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin1234!"},
    )
    tokens = login_response.json()["data"]

    return {
        "user_id": user_id,
        "email": "admin@example.com",
        "access_token": tokens["access_token"],
        "headers": {"Authorization": f"Bearer {tokens['access_token']}"},
    }
```

### 9.2 Database Seeding

```python
# tests/fixtures/db_seed.py
async def seed_roles_and_permissions(connection):
    """역할 및 권한 초기 데이터 생성"""
    # 이미 init.sql에서 생성되지만, 테스트 격리를 위해 명시적 시드
    roles = ["admin", "user", "manager"]
    permissions = [
        ("users", "read"),
        ("users", "write"),
        ("users", "delete"),
        ("roles", "admin"),
    ]

    # 역할 생성
    for role in roles:
        await connection.execute(
            "INSERT INTO roles (name, is_system) VALUES ($1, true) ON CONFLICT (name) DO NOTHING",
            role,
        )

    # 권한 생성
    for resource, action in permissions:
        await connection.execute(
            """
            INSERT INTO permissions (resource, action)
            VALUES ($1, $2)
            ON CONFLICT (resource, action) DO NOTHING
            """,
            resource,
            action,
        )
```

---

## 10. 실행 계획 요약

### 10.1 즉시 실행 (Phase 1)
1. **OAuth 인증 시스템 테스트 작성** (10 test cases)
2. **MFA 시스템 테스트 작성** (12 test cases)
3. **API Keys 시스템 테스트 작성** (8 test cases)

### 10.2 단기 실행 (Phase 2)
4. **Roles/Permissions CRUD 테스트 작성** (18 test cases)
5. **Edge Case 시나리오 작성** (15 test cases)

### 10.3 중기 실행 (Phase 3)
6. **E2E 통합 테스트 확대** (5 scenarios)
7. **Mock/Fixture 리팩토링**
8. **테스트 커버리지 측정 및 보고서 생성**

---

## 부록: 테스트 파일 구조

```
tests/
├── unit/
│   ├── test_auth_service.py           # 기존
│   ├── test_users_service.py          # 기존
│   ├── test_oauth_service.py          # 신규 (Phase 1)
│   ├── test_mfa_service.py            # 신규 (Phase 1)
│   ├── test_api_keys_service.py       # 신규 (Phase 1)
│   ├── test_roles_service.py          # 신규 (Phase 2)
│   └── test_permissions_service.py    # 신규 (Phase 2)
├── integration/
│   ├── test_auth_api.py               # 기존
│   ├── test_users_api.py              # 기존
│   ├── test_oauth_api.py              # 신규 (Phase 1)
│   ├── test_mfa_api.py                # 신규 (Phase 1)
│   ├── test_api_keys_api.py           # 신규 (Phase 1)
│   ├── test_roles_api.py              # 신규 (Phase 2)
│   └── test_e2e_flows.py              # 신규 (Phase 3)
├── fixtures/
│   ├── auth_fixtures.py               # 신규 (Phase 3)
│   ├── redis_mock.py                  # 신규 (Phase 3)
│   └── db_seed.py                     # 신규 (Phase 3)
└── factories/
    └── jwt_factory.py                 # 신규 (Phase 3)
```

---

**Report End** - Generated by Test Coverage Auditor
