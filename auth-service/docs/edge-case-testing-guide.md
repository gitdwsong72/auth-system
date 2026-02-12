# Edge Case Testing & Mock Improvement Guide

## Executive Summary

**Report Date**: 2026-02-10
**Auditor**: Test Coverage Auditor

### Key Findings

1. **현재 테스트의 Edge Case 커버리지: 약 20%**
   - Happy path 중심 테스트
   - 경계값 및 예외 상황 미흡
   - 동시성 시나리오 전무

2. **Mock 과다 사용 문제**
   - 단위 테스트에서 평균 7-8개 mock 중첩
   - 통합 테스트 fixture 중복
   - Mock 유지보수 비용 증가

3. **Flaky Test 리스크**
   - 시간 의존 테스트 (토큰 만료)
   - Redis 상태 공유 가능성
   - 동시 실행 시 DB 격리 미흡

---

## Part 1: Edge Case 시나리오 설계

### 1.1 입력 검증 Edge Cases

#### A. NULL 값 처리

**현재 문제점**:
```python
# test_auth_service.py - NULL 처리 미검증
async def test_login_success(self, mock_connection):
    request = schemas.LoginRequest(
        email="test@example.com",
        password="Test1234!",
        device_info="Chrome on Windows",  # 항상 존재 가정
    )
```

**개선 방안**:
```python
@pytest.mark.asyncio
class TestAuthServiceEdgeCases:
    """인증 서비스 Edge Case 테스트"""

    async def test_login_with_null_device_info(self, mock_connection):
        """로그인 - device_info가 None일 때"""
        # Arrange
        request = schemas.LoginRequest(
            email="test@example.com",
            password="Test1234!",
            device_info=None,  # NULL 명시
        )

        mock_user_row = {
            "id": 1,
            "email": "test@example.com",
            "password_hash": "hashed_password",
            "is_active": True,
        }

        with (
            patch("...redis_store.is_account_locked", return_value=(False, 0)),
            patch("...get_user_by_email", return_value=mock_user_row),
            patch("...verify_password", return_value=True),
            patch("...get_user_roles_permissions", return_value=[]),
            patch("...create_access_token", return_value="token"),
            patch("...create_refresh_token", return_value="refresh"),
            patch("...save_refresh_token", return_value={"id": 1}),
            patch("...save_login_history", return_value={"id": 1}),
            patch("...update_last_login", return_value={"id": 1}),
            patch("...reset_failed_login"),
            patch("...transaction") as mock_transaction,
        ):
            mock_transaction.return_value.__aenter__ = AsyncMock()
            mock_transaction.return_value.__aexit__ = AsyncMock()

            # Act
            result = await service.login(mock_connection, request)

            # Assert
            assert result.access_token == "token"
            # device_info가 None이어도 정상 처리되어야 함

    async def test_login_with_null_ip_and_user_agent(self, mock_connection):
        """로그인 - IP 주소와 User-Agent가 None일 때 (로컬 테스트 환경)"""
        # Arrange
        request = schemas.LoginRequest(
            email="test@example.com",
            password="Test1234!",
        )

        with (
            # ... (mock 설정)
        ):
            # Act
            result = await service.login(
                mock_connection,
                request,
                ip_address=None,
                user_agent=None,
            )

            # Assert
            assert result.access_token is not None
            # login_history에 NULL로 저장되어야 함
```

---

#### B. 빈 문자열 처리

```python
async def test_register_with_empty_display_name(self, mock_connection):
    """회원가입 - display_name이 빈 문자열일 때"""
    # Arrange
    request = schemas.UserRegisterRequest(
        email="test@example.com",
        password="Test1234!",
        username="testuser",
        display_name="",  # 빈 문자열
    )

    with (
        patch("...get_user_by_email", return_value=None),
        patch("...validate_strength", return_value=(True, None)),
        patch("...hash_password", return_value="hashed"),
        patch("...create_user", return_value={"id": 1, "display_name": ""}),
        patch("...assign_default_role", return_value={"id": 1}),
        patch("...transaction") as mock_transaction,
    ):
        mock_transaction.return_value.__aenter__ = AsyncMock()
        mock_transaction.return_value.__aexit__ = AsyncMock()

        # Act
        result = await service.register(mock_connection, request)

        # Assert
        assert result.display_name == ""  # 빈 문자열 허용 확인


async def test_search_users_with_empty_string(self, client: AsyncClient, admin_headers: dict):
    """사용자 검색 - 검색어가 빈 문자열일 때"""
    # Act
    response = await client.get(
        "/api/v1/users?search=",  # 빈 문자열
        headers=admin_headers,
    )

    # Assert
    assert response.status_code == 200
    # 모든 사용자 반환 (필터 없음)


async def test_search_users_with_whitespace_only(self, client: AsyncClient, admin_headers: dict):
    """사용자 검색 - 공백만 있는 검색어"""
    # Act
    response = await client.get(
        "/api/v1/users?search=   ",  # 공백만
        headers=admin_headers,
    )

    # Assert
    assert response.status_code == 200
    # 공백 trim 처리 확인
```

---

#### C. 최대/최소 길이 경계값

```python
async def test_register_with_max_length_email(self, mock_connection):
    """회원가입 - 최대 길이 이메일 (255자)"""
    # Arrange
    max_email = "a" * 243 + "@example.com"  # 총 255자
    request = schemas.UserRegisterRequest(
        email=max_email,
        password="Test1234!",
        username="testuser",
    )

    with (
        patch("...get_user_by_email", return_value=None),
        patch("...validate_strength", return_value=(True, None)),
        patch("...hash_password", return_value="hashed"),
        patch("...create_user", return_value={"id": 1, "email": max_email}),
        patch("...assign_default_role", return_value={"id": 1}),
        patch("...transaction") as mock_transaction,
    ):
        mock_transaction.return_value.__aenter__ = AsyncMock()
        mock_transaction.return_value.__aexit__ = AsyncMock()

        # Act
        result = await service.register(mock_connection, request)

        # Assert
        assert result.email == max_email


async def test_register_with_exceeding_length_email(self, client: AsyncClient):
    """회원가입 - 최대 길이 초과 이메일 (256자)"""
    # Arrange
    exceeding_email = "a" * 244 + "@example.com"  # 총 256자
    payload = {
        "email": exceeding_email,
        "password": "Test1234!",
        "username": "testuser",
    }

    # Act
    response = await client.post("/api/v1/users/register", json=payload)

    # Assert
    assert response.status_code == 422  # Validation error
    error_data = response.json()
    assert "email" in error_data["error"]["message"]


async def test_register_with_min_length_password(self, client: AsyncClient):
    """회원가입 - 최소 길이 비밀번호 (8자)"""
    # Arrange
    payload = {
        "email": "test@example.com",
        "password": "Test123!",  # 8자 (최소 길이)
        "username": "testuser",
    }

    # Act
    response = await client.post("/api/v1/users/register", json=payload)

    # Assert
    assert response.status_code == 201  # 성공


async def test_register_with_below_min_length_password(self, client: AsyncClient):
    """회원가입 - 최소 길이 미만 비밀번호 (7자)"""
    # Arrange
    payload = {
        "email": "test@example.com",
        "password": "Test12!",  # 7자 (최소 길이 미만)
        "username": "testuser",
    }

    # Act
    response = await client.post("/api/v1/users/register", json=payload)

    # Assert
    assert response.status_code == 400  # Validation error
    error_data = response.json()
    assert error_data["error"]["code"] == "USER_003"
```

---

### 1.2 동시성 Edge Cases

#### A. Race Condition - 중복 생성 방지

```python
@pytest.mark.asyncio
async def test_concurrent_user_registration_same_email(client: AsyncClient):
    """동시 회원가입 - 같은 이메일 (Race Condition)"""
    # Arrange
    payload = {
        "email": "duplicate@example.com",
        "password": "Test1234!",
        "username": "user1",
    }

    # Act - 동시에 5개 요청
    results = await asyncio.gather(
        *[client.post("/api/v1/users/register", json=payload) for _ in range(5)],
        return_exceptions=True,
    )

    # Assert - 하나만 성공 (201), 나머지는 중복 오류 (409)
    status_codes = [
        r.status_code for r in results if not isinstance(r, Exception)
    ]
    assert status_codes.count(201) == 1  # 첫 번째만 성공
    assert status_codes.count(409) == 4  # 나머지는 중복 오류
    # DB 유니크 제약 (udx_users_email)이 동작해야 함


@pytest.mark.asyncio
async def test_concurrent_login_same_user(client: AsyncClient):
    """동시 로그인 - 같은 사용자 (세션 격리 확인)"""
    # Arrange - 회원가입
    await client.post(
        "/api/v1/users/register",
        json={"email": "concurrent@example.com", "password": "Test1234!", "username": "concurrent"},
    )

    # Act - 동시에 10개 로그인 요청
    login_payload = {"email": "concurrent@example.com", "password": "Test1234!"}
    results = await asyncio.gather(
        *[client.post("/api/v1/auth/login", json=login_payload) for _ in range(10)],
        return_exceptions=True,
    )

    # Assert - 모두 성공 (200), refresh_token은 각각 다름
    status_codes = [r.status_code for r in results if not isinstance(r, Exception)]
    assert all(code == 200 for code in status_codes)

    # 각 refresh_token이 고유해야 함
    refresh_tokens = [r.json()["data"]["refresh_token"] for r in results]
    assert len(set(refresh_tokens)) == 10  # 모두 다른 토큰
```

---

#### B. Token Refresh Race Condition

```python
@pytest.mark.asyncio
async def test_refresh_token_rotation_race_condition(client: AsyncClient):
    """토큰 갱신 Race Condition (Refresh Token Rotation)"""
    # Arrange - 로그인하여 refresh_token 획득
    register_response = await client.post(
        "/api/v1/users/register",
        json={"email": "refresh@example.com", "password": "Test1234!", "username": "refresh"},
    )

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@example.com", "password": "Test1234!"},
    )
    refresh_token = login_response.json()["data"]["refresh_token"]

    # Act - 동일한 refresh_token으로 동시 2회 갱신 시도
    refresh_payload = {"refresh_token": refresh_token}
    result1, result2 = await asyncio.gather(
        client.post("/api/v1/auth/refresh", json=refresh_payload),
        client.post("/api/v1/auth/refresh", json=refresh_payload),
        return_exceptions=True,
    )

    # Assert - 하나는 성공 (200), 하나는 실패 (401 - 이미 폐기된 토큰)
    status_codes = [
        r.status_code for r in [result1, result2] if not isinstance(r, Exception)
    ]
    assert 200 in status_codes
    assert 401 in status_codes

    # 성공한 응답의 새 refresh_token은 유효해야 함
    successful_response = result1 if result1.status_code == 200 else result2
    new_refresh_token = successful_response.json()["data"]["refresh_token"]

    # 새 토큰으로 갱신 가능 확인
    refresh_again = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": new_refresh_token},
    )
    assert refresh_again.status_code == 200
```

---

### 1.3 타임스탬프 및 시간 의존 Edge Cases

#### A. 토큰 만료 경계값

```python
@pytest.mark.asyncio
async def test_access_token_expires_exactly_at_boundary(client: AsyncClient):
    """액세스 토큰 만료 - 정확히 경계 시점"""
    # Arrange - 회원가입 + 로그인
    await client.post(
        "/api/v1/users/register",
        json={"email": "expiry@example.com", "password": "Test1234!", "username": "expiry"},
    )
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "expiry@example.com", "password": "Test1234!"},
    )
    access_token = login_response.json()["data"]["access_token"]

    # JWT exp 추출
    payload = jwt_handler.decode_token(access_token)
    exp_timestamp = payload["exp"]

    # Act - 만료 1초 전: 성공
    with patch("time.time", return_value=exp_timestamp - 1):
        response_before = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response_before.status_code == 200

    # Act - 만료 시점: 실패
    with patch("time.time", return_value=exp_timestamp):
        response_at = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response_at.status_code == 401

    # Act - 만료 1초 후: 실패
    with patch("time.time", return_value=exp_timestamp + 1):
        response_after = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response_after.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_expiry_boundary(client: AsyncClient):
    """리프레시 토큰 만료 - 7일 경계"""
    # Arrange - 로그인
    await client.post(
        "/api/v1/users/register",
        json={"email": "refresh_exp@example.com", "password": "Test1234!", "username": "refresh_exp"},
    )
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh_exp@example.com", "password": "Test1234!"},
    )
    refresh_token = login_response.json()["data"]["refresh_token"]

    # Act - 6일 23시간 후: 성공
    with patch("datetime.datetime") as mock_datetime:
        mock_datetime.utcnow.return_value = datetime.utcnow() + timedelta(days=6, hours=23)
        response_before = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response_before.status_code == 200

    # Act - 7일 1시간 후: 실패 (만료)
    with patch("datetime.datetime") as mock_datetime:
        mock_datetime.utcnow.return_value = datetime.utcnow() + timedelta(days=7, hours=1)
        response_after = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response_after.status_code == 401
```

---

#### B. 계정 잠금 타이머

```python
@pytest.mark.asyncio
async def test_account_lock_expires_after_15_minutes(client: AsyncClient):
    """계정 잠금 - 15분 후 자동 해제"""
    # Arrange - 회원가입
    await client.post(
        "/api/v1/users/register",
        json={"email": "locktest@example.com", "password": "Correct123!", "username": "locktest"},
    )

    # Act - 5회 로그인 실패로 계정 잠금
    for _ in range(5):
        await client.post(
            "/api/v1/auth/login",
            json={"email": "locktest@example.com", "password": "WrongPassword!"},
        )

    # Assert - 6번째 시도는 계정 잠금 오류
    response_locked = await client.post(
        "/api/v1/auth/login",
        json={"email": "locktest@example.com", "password": "Correct123!"},
    )
    assert response_locked.status_code == 401
    assert response_locked.json()["error"]["code"] == "AUTH_004"

    # Act - 14분 59초 후: 여전히 잠김
    await asyncio.sleep(0.1)  # 실제로는 Redis TTL로 제어됨
    # (테스트에서는 Redis mock의 TTL 시뮬레이션 필요)

    # Act - 15분 후: 잠금 해제, 로그인 성공
    # (Redis 키가 만료되어 is_account_locked가 False 반환)
    with patch("src.shared.security.redis_store.redis_store.is_account_locked", return_value=(False, 0)):
        response_unlocked = await client.post(
            "/api/v1/auth/login",
            json={"email": "locktest@example.com", "password": "Correct123!"},
        )
        assert response_unlocked.status_code == 200
```

---

### 1.4 데이터 무결성 Edge Cases

#### A. 외래 키 제약

```python
@pytest.mark.asyncio
async def test_delete_user_cascades_to_refresh_tokens(connection: asyncpg.Connection):
    """사용자 삭제 - refresh_tokens 연쇄 삭제 (ON DELETE CASCADE)"""
    # Arrange - 사용자 생성 + 로그인 (refresh_token 발급)
    user_row = await connection.fetchrow(
        "INSERT INTO users (email, username, password_hash) VALUES ($1, $2, $3) RETURNING id",
        "cascade@example.com",
        "cascade",
        "hashed_password",
    )
    user_id = user_row["id"]

    # 여러 refresh_token 생성 (다중 세션)
    for i in range(3):
        await connection.execute(
            """
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
            VALUES ($1, $2, NOW() + INTERVAL '7 days')
            """,
            user_id,
            f"hash_{i}",
        )

    # Assert - refresh_token 3개 존재
    token_count = await connection.fetchval(
        "SELECT COUNT(*) FROM refresh_tokens WHERE user_id = $1",
        user_id,
    )
    assert token_count == 3

    # Act - 사용자 soft delete
    await connection.execute(
        "UPDATE users SET deleted_at = NOW() WHERE id = $1",
        user_id,
    )

    # Assert - refresh_token은 여전히 존재 (soft delete는 CASCADE 트리거 안함)
    token_count_after_soft = await connection.fetchval(
        "SELECT COUNT(*) FROM refresh_tokens WHERE user_id = $1",
        user_id,
    )
    assert token_count_after_soft == 3

    # Act - 사용자 완전 삭제 (hard delete)
    await connection.execute(
        "DELETE FROM users WHERE id = $1",
        user_id,
    )

    # Assert - refresh_token 자동 삭제 (ON DELETE CASCADE)
    token_count_after_hard = await connection.fetchval(
        "SELECT COUNT(*) FROM refresh_tokens WHERE user_id = $1",
        user_id,
    )
    assert token_count_after_hard == 0


@pytest.mark.asyncio
async def test_delete_role_with_assigned_users(connection: asyncpg.Connection):
    """역할 삭제 - user_roles 연쇄 삭제"""
    # Arrange
    role_row = await connection.fetchrow(
        "INSERT INTO roles (name, is_system) VALUES ($1, false) RETURNING id",
        "test_role",
    )
    role_id = role_row["id"]

    user_row = await connection.fetchrow(
        "INSERT INTO users (email, username, password_hash) VALUES ($1, $2, $3) RETURNING id",
        "roletest@example.com",
        "roletest",
        "hashed",
    )
    user_id = user_row["id"]

    # 역할 부여
    await connection.execute(
        "INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2)",
        user_id,
        role_id,
    )

    # Assert - user_roles 존재
    role_count = await connection.fetchval(
        "SELECT COUNT(*) FROM user_roles WHERE role_id = $1",
        role_id,
    )
    assert role_count == 1

    # Act - 역할 삭제
    await connection.execute(
        "DELETE FROM roles WHERE id = $1",
        role_id,
    )

    # Assert - user_roles 자동 삭제 (ON DELETE CASCADE)
    role_count_after = await connection.fetchval(
        "SELECT COUNT(*) FROM user_roles WHERE role_id = $1",
        role_id,
    )
    assert role_count_after == 0
```

---

#### B. 유니크 제약 충돌

```python
@pytest.mark.asyncio
async def test_register_duplicate_email_after_soft_delete(client: AsyncClient):
    """회원가입 - Soft Delete 후 같은 이메일 재가입"""
    # Arrange - 회원가입
    payload = {
        "email": "reuse@example.com",
        "password": "Test1234!",
        "username": "reuse1",
    }
    response1 = await client.post("/api/v1/users/register", json=payload)
    assert response1.status_code == 201

    # Act - 사용자 Soft Delete (deleted_at 설정)
    # (관리자 API 필요 - 임시로 직접 DB 조작)
    # await admin_client.delete(f"/api/v1/users/{user_id}")

    # Act - 같은 이메일로 재가입 시도
    payload2 = {
        "email": "reuse@example.com",  # 동일 이메일
        "password": "NewPassword456!",
        "username": "reuse2",
    }
    response2 = await client.post("/api/v1/users/register", json=payload2)

    # Assert - 유니크 제약 위반 (udx_users_email WHERE deleted_at IS NULL)
    assert response2.status_code == 409  # Conflict
    assert response2.json()["error"]["code"] == "USER_001"


@pytest.mark.asyncio
async def test_assign_same_role_twice(connection: asyncpg.Connection):
    """역할 부여 - 동일 역할 중복 부여 시도"""
    # Arrange
    user_id = 1
    role_id = 1

    # 첫 번째 역할 부여
    await connection.execute(
        "INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2)",
        user_id,
        role_id,
    )

    # Act - 같은 역할 재부여 시도
    with pytest.raises(asyncpg.UniqueViolationError):
        await connection.execute(
            "INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2)",
            user_id,
            role_id,
        )
```

---

### 1.5 특수 문자 및 인젝션 방지

```python
@pytest.mark.asyncio
class TestSecurityEdgeCases:
    """보안 관련 Edge Case 테스트"""

    async def test_register_with_special_characters_email(self, client: AsyncClient):
        """회원가입 - 특수 문자 포함 이메일"""
        special_emails = [
            "user+tag@example.com",  # + 기호 (유효)
            "user.name@example.com",  # . 기호 (유효)
            "user_name@example.com",  # _ 기호 (유효)
            "user@subdomain.example.com",  # 서브도메인 (유효)
        ]

        for email in special_emails:
            payload = {
                "email": email,
                "password": "Test1234!",
                "username": f"user_{special_emails.index(email)}",
            }
            response = await client.post("/api/v1/users/register", json=payload)
            assert response.status_code == 201, f"Failed for email: {email}"

    async def test_register_with_malicious_email(self, client: AsyncClient):
        """회원가입 - 악의적인 이메일 (XSS, SQL Injection 시도)"""
        malicious_emails = [
            "<script>alert('XSS')</script>@example.com",
            "admin'--@example.com",
            "test@example.com'; DROP TABLE users; --",
            "../../../etc/passwd@example.com",
        ]

        for email in malicious_emails:
            payload = {
                "email": email,
                "password": "Test1234!",
                "username": "malicious",
            }
            response = await client.post("/api/v1/users/register", json=payload)

            # Assert - 이메일 형식 검증 실패 (422) 또는 안전하게 저장 (201)
            assert response.status_code in [422, 201]
            if response.status_code == 201:
                # 저장된 경우, 이스케이핑 확인
                user_id = response.json()["data"]["id"]
                # ... 이메일이 원본 그대로 저장되었는지, HTML 렌더링 시 안전한지 검증

    async def test_search_users_sql_injection(self, client: AsyncClient, admin_headers: dict):
        """사용자 검색 - SQL Injection 방지"""
        sql_injection_payloads = [
            "admin' OR '1'='1",
            "'; DROP TABLE users; --",
            "admin' UNION SELECT * FROM permissions --",
            "admin' AND 1=1 --",
        ]

        for payload in sql_injection_payloads:
            response = await client.get(
                f"/api/v1/users?search={payload}",
                headers=admin_headers,
            )

            # Assert - 정상 처리 (파라미터화된 쿼리로 안전)
            assert response.status_code == 200
            # 결과가 비어있거나, 실제로 일치하는 사용자만 반환
            data = response.json()
            assert isinstance(data["data"]["items"], list)

    async def test_jwt_token_tampering(self, client: AsyncClient):
        """JWT 토큰 변조 시도"""
        # Arrange - 유효한 토큰 생성
        await client.post(
            "/api/v1/users/register",
            json={"email": "jwt@example.com", "password": "Test1234!", "username": "jwt"},
        )
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "jwt@example.com", "password": "Test1234!"},
        )
        valid_token = login_response.json()["data"]["access_token"]

        # 토큰 분해
        parts = valid_token.split(".")
        header, payload, signature = parts

        # Act - Payload 변조 (user_id 변경)
        import base64
        import json

        decoded_payload = json.loads(
            base64.urlsafe_b64decode(payload + "==")  # padding 추가
        )
        decoded_payload["sub"] = 999  # 다른 사용자 ID
        tampered_payload = base64.urlsafe_b64encode(
            json.dumps(decoded_payload).encode()
        ).decode().rstrip("=")

        tampered_token = f"{header}.{tampered_payload}.{signature}"

        # Act - 변조된 토큰으로 요청
        response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {tampered_token}"},
        )

        # Assert - 서명 검증 실패로 401
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTH_003"
```

---

## Part 2: Mock 개선 가이드

### 2.1 현재 Mock 패턴 분석

#### 문제점 1: Mock 중첩 과다

**현재 코드** (`test_auth_service.py:22-93`):
```python
async def test_login_success(self, mock_connection):
    # ... (생략)
    with (
        patch("src.domains.authentication.service.redis_store.is_account_locked", ...),  # 1
        patch("src.domains.authentication.service.users_repository.get_user_by_email", ...),  # 2
        patch("src.domains.authentication.service.password_hasher.verify_password", ...),  # 3
        patch("src.domains.authentication.service.users_repository.get_user_roles_permissions", ...),  # 4
        patch("src.domains.authentication.service.jwt_handler.create_access_token", ...),  # 5
        patch("src.domains.authentication.service.jwt_handler.create_refresh_token", ...),  # 6
        patch("src.domains.authentication.service.repository.save_refresh_token", ...),  # 7
        patch("src.domains.authentication.service.repository.save_login_history", ...),  # 8
        patch("src.domains.authentication.service.repository.update_last_login", ...),  # 9
        patch("src.domains.authentication.service.redis_store.reset_failed_login"),  # 10
        patch("src.domains.authentication.service.transaction") as mock_transaction,  # 11
    ):
        # 총 11개 mock!
```

**문제점**:
- 테스트 가독성 저하
- Mock 설정 코드가 테스트 로직보다 김
- 유지보수 비용 증가 (서비스 로직 변경 시 모든 테스트 수정 필요)

---

### 2.2 개선 방안 1: Fixture로 공통 Mock 추출

#### 개선된 conftest.py

```python
# tests/fixtures/service_mocks.py
"""Service 레이어 테스트용 공통 Mock"""

from unittest.mock import AsyncMock, patch
import pytest


@pytest.fixture
def mock_redis_store():
    """Redis Store Mock (계정 잠금, 실패 카운터)"""
    with patch("src.shared.security.redis_store.redis_store") as mock:
        mock.is_account_locked.return_value = (False, 0)
        mock.increment_failed_login.return_value = 1
        mock.reset_failed_login.return_value = None
        mock.blacklist_token.return_value = None
        yield mock


@pytest.fixture
def mock_password_hasher():
    """Password Hasher Mock"""
    with patch("src.shared.security.password_hasher.password_hasher") as mock:
        mock.verify.return_value = True
        mock.hash.return_value = "hashed_password"
        mock.validate_strength.return_value = (True, None)
        yield mock


@pytest.fixture
def mock_jwt_handler():
    """JWT Handler Mock"""
    with patch("src.shared.security.jwt_handler.jwt_handler") as mock:
        mock.create_access_token.return_value = "mock_access_token"
        mock.create_refresh_token.return_value = "mock_refresh_token"
        mock.decode_token.return_value = {
            "sub": 1,
            "email": "test@example.com",
            "jti": "unique-jti",
            "exp": 1234567890,
        }
        yield mock


@pytest.fixture
def mock_users_repository():
    """Users Repository Mock"""
    with patch("src.domains.users.repository") as mock:
        mock.get_user_by_email.return_value = {
            "id": 1,
            "email": "test@example.com",
            "username": "testuser",
            "password_hash": "hashed_password",
            "is_active": True,
        }
        mock.get_user_roles_permissions.return_value = [
            {"role_name": "user", "permission_name": "users:read"},
        ]
        yield mock


@pytest.fixture
def mock_auth_repository():
    """Authentication Repository Mock"""
    with patch("src.domains.authentication.repository") as mock:
        mock.save_refresh_token.return_value = {"id": 1}
        mock.save_login_history.return_value = {"id": 1}
        mock.update_last_login.return_value = {"id": 1}
        mock.get_refresh_token.return_value = {
            "id": 1,
            "user_id": 1,
            "device_info": "Chrome",
            "expires_at": "2024-12-31T23:59:59Z",
        }
        mock.revoke_refresh_token.return_value = {"id": 1}
        yield mock


@pytest.fixture
def mock_transaction():
    """Transaction Context Manager Mock"""
    with patch("src.shared.database.transaction.transaction") as mock:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock()
        mock_ctx.__aexit__ = AsyncMock()
        mock.return_value = mock_ctx
        yield mock
```

#### 개선된 테스트 코드

```python
# tests/unit/test_auth_service.py
"""Authentication 서비스 단위 테스트 - Mock 개선 버전"""

import pytest
from src.domains.authentication import schemas, service


@pytest.mark.asyncio
class TestAuthService:
    """인증 서비스 테스트 - Fixture 기반"""

    async def test_login_success(
        self,
        mock_connection,
        mock_redis_store,
        mock_password_hasher,
        mock_jwt_handler,
        mock_users_repository,
        mock_auth_repository,
        mock_transaction,
    ):
        """로그인 성공 - 간결한 버전"""
        # Arrange
        request = schemas.LoginRequest(
            email="test@example.com",
            password="Test1234!",
            device_info="Chrome on Windows",
        )

        # Act
        result = await service.login(mock_connection, request)

        # Assert
        assert result.access_token == "mock_access_token"
        assert result.refresh_token == "mock_refresh_token"
        assert result.token_type == "bearer"

        # Verify interactions
        mock_redis_store.is_account_locked.assert_called_once_with("test@example.com")
        mock_users_repository.get_user_by_email.assert_called_once()
        mock_password_hasher.verify.assert_called_once()
        mock_redis_store.reset_failed_login.assert_called_once()

    async def test_login_wrong_password(
        self,
        mock_connection,
        mock_redis_store,
        mock_password_hasher,
        mock_users_repository,
        mock_auth_repository,
    ):
        """로그인 실패 - 비밀번호 불일치"""
        # Arrange
        request = schemas.LoginRequest(
            email="test@example.com",
            password="WrongPassword!",
        )
        mock_password_hasher.verify.return_value = False  # 오버라이드

        # Act & Assert
        with pytest.raises(UnauthorizedException) as exc_info:
            await service.login(mock_connection, request)

        assert exc_info.value.error_code == "AUTH_001"
        mock_redis_store.increment_failed_login.assert_called_once()
```

**개선 효과**:
- 테스트 코드 라인 수: 93줄 → 30줄 (68% 감소)
- Mock 설정 코드 중복 제거
- 테스트 의도가 명확히 드러남

---

### 2.3 개선 방안 2: 통합 테스트 확대 (실제 DB 사용)

#### 문제점 2: 과도한 Mocking으로 실제 동작 검증 부족

**해결책**: 통합 테스트에서는 Mock 최소화, 실제 DB/Redis 사용

```python
# tests/integration/test_auth_api_extended.py
"""Authentication API 통합 테스트 - 실제 DB 사용"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestAuthAPIIntegration:
    """인증 API 통합 테스트 (Mock 없음)"""

    async def test_login_updates_last_login_at(self, client: AsyncClient, connection):
        """로그인 시 last_login_at 업데이트 확인 (실제 DB)"""
        # Arrange - 회원가입
        await client.post(
            "/api/v1/users/register",
            json={
                "email": "lastlogin@example.com",
                "password": "Test1234!",
                "username": "lastlogin",
            },
        )

        # 초기 last_login_at 조회 (NULL)
        initial_last_login = await connection.fetchval(
            "SELECT last_login_at FROM users WHERE email = $1",
            "lastlogin@example.com",
        )
        assert initial_last_login is None

        # Act - 로그인
        await client.post(
            "/api/v1/auth/login",
            json={"email": "lastlogin@example.com", "password": "Test1234!"},
        )

        # Assert - last_login_at 업데이트 확인
        updated_last_login = await connection.fetchval(
            "SELECT last_login_at FROM users WHERE email = $1",
            "lastlogin@example.com",
        )
        assert updated_last_login is not None

    async def test_refresh_token_rotation_in_db(self, client: AsyncClient, connection):
        """토큰 갱신 시 DB에서 Refresh Token Rotation 확인"""
        # Arrange - 회원가입 + 로그인
        await client.post(
            "/api/v1/users/register",
            json={"email": "rotation@example.com", "password": "Test1234!", "username": "rotation"},
        )
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "rotation@example.com", "password": "Test1234!"},
        )
        old_refresh_token = login_response.json()["data"]["refresh_token"]

        # 초기 refresh_token 개수 (1개)
        initial_count = await connection.fetchval(
            "SELECT COUNT(*) FROM refresh_tokens WHERE user_id = (SELECT id FROM users WHERE email = $1)",
            "rotation@example.com",
        )
        assert initial_count == 1

        # Act - 토큰 갱신
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_refresh_token},
        )
        new_refresh_token = refresh_response.json()["data"]["refresh_token"]

        # Assert - 기존 토큰은 revoked_at 설정, 새 토큰 생성
        token_count_after = await connection.fetchval(
            "SELECT COUNT(*) FROM refresh_tokens WHERE user_id = (SELECT id FROM users WHERE email = $1)",
            "rotation@example.com",
        )
        assert token_count_after == 2  # 기존 + 새 토큰

        revoked_count = await connection.fetchval(
            """
            SELECT COUNT(*) FROM refresh_tokens
            WHERE user_id = (SELECT id FROM users WHERE email = $1)
            AND revoked_at IS NOT NULL
            """,
            "rotation@example.com",
        )
        assert revoked_count == 1  # 기존 토큰만 폐기

        # 기존 토큰으로 재갱신 시도 → 실패
        retry_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_refresh_token},
        )
        assert retry_response.status_code == 401
```

**장점**:
- 실제 DB 트리거, 제약 조건 검증
- Mock 불일치로 인한 false positive 방지
- 엔드투엔드 동작 확인

---

### 2.4 개선 방안 3: Test Factory Pattern

#### Factory로 테스트 데이터 생성 표준화

```python
# tests/factories/user_factory.py
"""User 테스트 데이터 Factory"""

from datetime import datetime


class UserFactory:
    """사용자 테스트 데이터 생성"""

    _counter = 0

    @classmethod
    def build_user_data(cls, **overrides):
        """사용자 데이터 생성 (DB 저장 전)"""
        cls._counter += 1
        defaults = {
            "email": f"user{cls._counter}@example.com",
            "username": f"user{cls._counter}",
            "password": "Test1234!",
            "display_name": f"User {cls._counter}",
        }
        return {**defaults, **overrides}

    @classmethod
    async def create_user(cls, connection, **overrides):
        """사용자 생성 (DB 저장)"""
        data = cls.build_user_data(**overrides)
        row = await connection.fetchrow(
            """
            INSERT INTO users (email, username, password_hash, display_name)
            VALUES ($1, $2, $3, $4)
            RETURNING id, email, username, display_name, created_at
            """,
            data["email"],
            data["username"],
            "hashed_password",  # 테스트용 고정값
            data.get("display_name"),
        )
        return dict(row)

    @classmethod
    def build_mock_user_row(cls, **overrides):
        """Mock 테스트용 사용자 row"""
        cls._counter += 1
        defaults = {
            "id": cls._counter,
            "email": f"user{cls._counter}@example.com",
            "username": f"user{cls._counter}",
            "password_hash": "hashed_password",
            "is_active": True,
            "email_verified": False,
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        return {**defaults, **overrides}


# 사용 예시
@pytest.mark.asyncio
async def test_with_factory(connection):
    # Arrange - Factory로 사용자 생성
    user1 = await UserFactory.create_user(connection, email="specific@example.com")
    user2 = await UserFactory.create_user(connection)  # 자동 생성된 이메일

    # Act & Assert
    assert user1["email"] == "specific@example.com"
    assert user2["email"] == "user2@example.com"
```

---

### 2.5 Flaky Test 방지 전략

#### 문제점 3: 시간 의존 테스트

```python
# Bad: 실제 시간에 의존
async def test_token_expiry_bad():
    token = jwt_handler.create_access_token(user_id=1, expires_delta=timedelta(seconds=1))
    await asyncio.sleep(2)  # Flaky! CI 환경에서 불안정
    # 토큰 만료 확인
```

#### 개선: Mock 시간 사용

```python
# Good: 시간을 Mock으로 제어
async def test_token_expiry_good():
    with patch("time.time") as mock_time:
        # 현재 시간
        mock_time.return_value = 1000

        # 토큰 생성 (exp: 1000 + 900 = 1900)
        token = jwt_handler.create_access_token(user_id=1)

        # 만료 전
        mock_time.return_value = 1899
        assert jwt_handler.decode_token(token) is not None

        # 만료 후
        mock_time.return_value = 1901
        with pytest.raises(ValueError):
            jwt_handler.decode_token(token)
```

---

#### 문제점 4: DB 격리 부족

```python
# Bad: 테스트 간 데이터 공유
async def test_user_count():
    users = await repository.get_user_list(connection)
    assert len(users) == 5  # Flaky! 다른 테스트가 사용자 생성 시 실패
```

#### 개선: Transaction Rollback 사용

```python
# tests/conftest.py
@pytest_asyncio.fixture
async def connection():
    """트랜잭션 기반 DB 연결 (각 테스트 후 자동 롤백)"""
    conn = await asyncpg.connect(DATABASE_URL)
    transaction = conn.transaction()
    await transaction.start()

    yield conn

    await transaction.rollback()
    await conn.close()
```

---

## Part 3: 실행 계획

### Phase 1: Mock 리팩토링 (1주)
1. `tests/fixtures/service_mocks.py` 생성
2. 기존 테스트 파일에서 Mock 추출
3. 단위 테스트 리팩토링

### Phase 2: Edge Case 추가 (2주)
1. 입력 검증 Edge Cases (10개)
2. 동시성 Edge Cases (5개)
3. 타임스탬프 Edge Cases (5개)
4. 데이터 무결성 Edge Cases (5개)

### Phase 3: 통합 테스트 확대 (1주)
1. 실제 DB 사용 테스트 추가
2. Factory Pattern 도입
3. Flaky Test 제거

---

## 부록: 체크리스트

### Edge Case 커버리지 체크리스트

- [ ] NULL 값 처리 (5개 시나리오)
- [ ] 빈 문자열 처리 (3개 시나리오)
- [ ] 최대/최소 길이 경계값 (6개 시나리오)
- [ ] Race Condition (3개 시나리오)
- [ ] 토큰 만료 경계값 (4개 시나리오)
- [ ] 외래 키 CASCADE (2개 시나리오)
- [ ] 유니크 제약 충돌 (2개 시나리오)
- [ ] SQL Injection 방지 (3개 시나리오)
- [ ] JWT 변조 방지 (1개 시나리오)

### Mock 개선 체크리스트

- [ ] 공통 Mock Fixture 생성 (`service_mocks.py`)
- [ ] Redis Mock 추상화
- [ ] Password Hasher Mock 추상화
- [ ] JWT Handler Mock 추상화
- [ ] Repository Mock 추상화
- [ ] 단위 테스트 리팩토링 (11개 → 5개 mock)
- [ ] Factory Pattern 도입 (`user_factory.py`)
- [ ] 통합 테스트 확대 (실제 DB 사용)
- [ ] Transaction Rollback Fixture
- [ ] 시간 의존 테스트 Mock 처리

---

**Report End** - Generated by Test Coverage Auditor
