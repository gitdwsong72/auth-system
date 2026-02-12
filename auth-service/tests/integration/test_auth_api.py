"""Authentication API 통합 테스트

실제 데이터베이스와 Redis를 사용하여 API 엔드포인트를 테스트합니다.
"""

import asyncio

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestAuthAPI:
    """인증 API 테스트"""

    async def test_login_success(self, client: AsyncClient):
        """로그인 성공"""
        # Arrange - 회원가입
        register_payload = {
            "email": "logintest@example.com",
            "password": "LoginTest123!",
            "username": "logintest",
        }
        await client.post("/api/v1/users/register", json=register_payload)

        # Act - 로그인
        login_payload = {
            "email": "logintest@example.com",
            "password": "LoginTest123!",
            "device_info": "Chrome on Windows",
        }
        response = await client.post("/api/v1/auth/login", json=login_payload)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]
        assert data["data"]["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient):
        """로그인 실패 - 비밀번호 불일치"""
        # Arrange - 회원가입
        register_payload = {
            "email": "wrongpass@example.com",
            "password": "CorrectPass123!",
            "username": "wrongpass",
        }
        await client.post("/api/v1/users/register", json=register_payload)

        # Act - 잘못된 비밀번호로 로그인
        login_payload = {
            "email": "wrongpass@example.com",
            "password": "WrongPass123!",
        }
        response = await client.post("/api/v1/auth/login", json=login_payload)

        # Assert
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "AUTH_001"

    async def test_login_nonexistent_user(self, client: AsyncClient):
        """로그인 실패 - 존재하지 않는 사용자"""
        # Act
        login_payload = {
            "email": "nonexistent@example.com",
            "password": "Test1234!",
        }
        response = await client.post("/api/v1/auth/login", json=login_payload)

        # Assert
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "AUTH_001"

    async def test_refresh_token_success(self, client: AsyncClient):
        """토큰 갱신 성공"""
        # Arrange - 회원가입 + 로그인
        register_payload = {
            "email": "refreshtest@example.com",
            "password": "RefreshTest123!",
            "username": "refreshtest",
        }
        await client.post("/api/v1/users/register", json=register_payload)

        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "refreshtest@example.com", "password": "RefreshTest123!"},
        )
        refresh_token = login_response.json()["data"]["refresh_token"]

        # Act - 토큰 갱신
        refresh_payload = {"refresh_token": refresh_token}
        response = await client.post("/api/v1/auth/refresh", json=refresh_payload)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]

    async def test_refresh_token_invalid(self, client: AsyncClient):
        """토큰 갱신 실패 - 유효하지 않은 토큰"""
        # Act
        refresh_payload = {"refresh_token": "invalid_refresh_token"}
        response = await client.post("/api/v1/auth/refresh", json=refresh_payload)

        # Assert
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "AUTH_006"

    async def test_logout_success(self, client: AsyncClient):
        """로그아웃 성공"""
        # Arrange - 회원가입 + 로그인
        register_payload = {
            "email": "logouttest@example.com",
            "password": "LogoutTest123!",
            "username": "logouttest",
        }
        await client.post("/api/v1/users/register", json=register_payload)

        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "logouttest@example.com", "password": "LogoutTest123!"},
        )
        access_token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Act - 로그아웃
        response = await client.post("/api/v1/auth/logout", headers=headers)

        # Assert
        assert response.status_code in {204, 200}

    async def test_get_sessions(self, client: AsyncClient, auth_headers: dict):
        """활성 세션 목록 조회"""
        # Act
        response = await client.get("/api/v1/auth/sessions", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    async def test_revoke_all_sessions(self, client: AsyncClient):
        """전체 세션 종료"""
        # Arrange - 회원가입 + 로그인
        register_payload = {
            "email": "revoketest@example.com",
            "password": "RevokeTest123!",
            "username": "revoketest",
        }
        await client.post("/api/v1/users/register", json=register_payload)

        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "revoketest@example.com", "password": "RevokeTest123!"},
        )
        access_token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Act - 전체 세션 종료
        response = await client.delete("/api/v1/auth/sessions", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    async def test_full_auth_flow(self, client: AsyncClient):
        """전체 인증 플로우 테스트 (회원가입 → 로그인 → 프로필 조회 → 토큰 갱신 → 로그아웃)"""
        # 1. 회원가입
        register_response = await client.post(
            "/api/v1/users/register",
            json={
                "email": "fullflow@example.com",
                "password": "FullFlow123!",
                "username": "fullflow",
            },
        )
        assert register_response.status_code == 201

        # 2. 로그인
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "fullflow@example.com", "password": "FullFlow123!"},
        )
        assert login_response.status_code == 200
        login_data = login_response.json()["data"]
        access_token = login_data["access_token"]
        refresh_token = login_data["refresh_token"]

        # 3. 프로필 조회
        profile_response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert profile_response.status_code == 200

        # 4. 토큰 갱신
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_response.status_code == 200
        new_access_token = refresh_response.json()["data"]["access_token"]

        # 5. 새 토큰으로 프로필 조회
        profile_response2 = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {new_access_token}"},
        )
        assert profile_response2.status_code == 200

        # 6. 로그아웃
        logout_response = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {new_access_token}"},
        )
        assert logout_response.status_code in [200, 204]

    async def test_concurrent_login_no_race_condition(self, client: AsyncClient):
        """동시 로그인 시 race condition이 발생하지 않음을 검증

        PostgreSQL advisory lock으로 동일 사용자의 동시 로그인을 직렬화하여
        토큰 저장 시 race condition을 방지한다.
        """
        # Arrange - 회원가입
        register_payload = {
            "email": "concurrent@example.com",
            "password": "Concurrent123!",
            "username": "concurrent",
        }
        await client.post("/api/v1/users/register", json=register_payload)

        # Act - 동일 사용자로 동시에 5번 로그인 시도
        login_payload = {
            "email": "concurrent@example.com",
            "password": "Concurrent123!",
            "device_info": "Chrome on Windows",
        }

        async def login_attempt():
            return await client.post("/api/v1/auth/login", json=login_payload)

        # 5개의 동시 로그인 요청
        responses = await asyncio.gather(*[login_attempt() for _ in range(5)])

        # Assert - 모든 요청이 성공해야 함
        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count == 5, f"Expected 5 successful logins, got {success_count}"

        # 모든 응답에 토큰이 있어야 함
        for response in responses:
            data = response.json()
            assert data["success"] is True
            assert "access_token" in data["data"]
            assert "refresh_token" in data["data"]

        # 각 토큰은 고유해야 함 (중복 토큰 생성 방지)
        access_tokens = [r.json()["data"]["access_token"] for r in responses]
        refresh_tokens = [r.json()["data"]["refresh_token"] for r in responses]
        assert len(set(access_tokens)) == 5, "Access tokens should be unique"
        assert len(set(refresh_tokens)) == 5, "Refresh tokens should be unique"

    async def test_revoked_token_rejected(self, client: AsyncClient):
        """취소된 토큰은 거부되어야 함 (블랙리스트 + active token tracking)

        로그아웃 또는 세션 종료 시 토큰은 블랙리스트에 추가되고
        active token registry에서도 제거된다.
        """
        # Arrange - 회원가입 + 로그인
        register_payload = {
            "email": "revokecheck@example.com",
            "password": "RevokeCheck123!",
            "username": "revokecheck",
        }
        await client.post("/api/v1/users/register", json=register_payload)

        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "revokecheck@example.com", "password": "RevokeCheck123!"},
        )
        access_token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Act 1 - 토큰으로 프로필 조회 (성공)
        profile_response_before = await client.get("/api/v1/users/me", headers=headers)
        assert profile_response_before.status_code == 200

        # Act 2 - 전체 세션 종료 (블랙리스트 + active token 모두 처리)
        revoke_response = await client.delete("/api/v1/auth/sessions", headers=headers)
        assert revoke_response.status_code == 200

        # Act 3 - 동일 토큰으로 다시 API 호출 시도
        profile_response_after = await client.get("/api/v1/users/me", headers=headers)

        # Assert - 취소된 토큰은 거부되어야 함
        # 블랙리스트 체크가 먼저 실행되므로 AUTH_003 반환
        assert profile_response_after.status_code == 401
        error_data = profile_response_after.json()
        assert error_data["error"]["code"] in ["AUTH_003", "AUTH_008"]
