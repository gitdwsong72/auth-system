"""Users API 통합 테스트

실제 데이터베이스와 Redis를 사용하여 API 엔드포인트를 테스트합니다.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestUsersAPI:
    """사용자 API 테스트"""

    async def test_register_success(self, client: AsyncClient):
        """회원가입 성공"""
        # Arrange - 고유한 이메일/유저명 사용
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        payload = {
            "email": f"newuser-{unique_id}@example.com",
            "password": "NewUser123!",
            "username": f"newuser-{unique_id}",
            "display_name": "New User",
        }

        # Act
        response = await client.post("/api/v1/users/register", json=payload)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["email"] == payload["email"]
        assert data["data"]["username"] == payload["username"]

    async def test_register_duplicate_email(self, client: AsyncClient):
        """회원가입 실패 - 이메일 중복"""
        # Arrange
        payload = {
            "email": "duplicate@example.com",
            "password": "Test1234!",
            "username": "user1",
        }

        # 첫 번째 회원가입
        await client.post("/api/v1/users/register", json=payload)

        # Act - 같은 이메일로 재시도
        response = await client.post("/api/v1/users/register", json=payload)

        # Assert
        assert response.status_code == 409
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "USER_001"

    async def test_get_my_profile_without_auth(self, client: AsyncClient):
        """내 프로필 조회 실패 - 인증 없음"""
        # Act
        response = await client.get("/api/v1/users/me")

        # Assert
        assert response.status_code == 422  # Missing header

    async def test_get_my_profile_with_invalid_token(self, client: AsyncClient):
        """내 프로필 조회 실패 - 유효하지 않은 토큰"""
        # Act
        response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer invalid_token"},
        )

        # Assert
        assert response.status_code == 401

    async def test_get_my_profile_success(self, client: AsyncClient, auth_headers: dict):
        """내 프로필 조회 성공"""
        # Act
        response = await client.get("/api/v1/users/me", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "email" in data["data"]
        assert "username" in data["data"]

    async def test_update_profile(self, client: AsyncClient, auth_headers: dict):
        """프로필 수정"""
        # Arrange
        payload = {
            "display_name": "Updated Name",
            "phone": "010-1234-5678",
        }

        # Act
        response = await client.put("/api/v1/users/me", json=payload, headers=auth_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["display_name"] == "Updated Name"

    async def test_change_password_success(self, client: AsyncClient):
        """비밀번호 변경 성공"""
        # Arrange - 회원가입 (고유한 이메일/유저명 사용)
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        email = f"changepass-{unique_id}@example.com"
        register_payload = {
            "email": email,
            "password": "OldPass123!",
            "username": f"changepassuser-{unique_id}",
        }
        await client.post("/api/v1/users/register", json=register_payload)

        # 로그인
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "OldPass123!"},
        )
        access_token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Act - 비밀번호 변경
        change_payload = {
            "current_password": "OldPass123!",
            "new_password": "NewPass456!",
        }
        response = await client.put(
            "/api/v1/users/me/password", json=change_payload, headers=headers
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify - 새 비밀번호로 로그인 가능
        login_response2 = await client.post(
            "/api/v1/auth/login",
            json={"email": "changepass@example.com", "password": "NewPass456!"},
        )
        assert login_response2.status_code == 200

    async def test_list_users_without_permission(self, client: AsyncClient, auth_headers: dict):
        """사용자 목록 조회 실패 - 권한 없음"""
        # Act
        response = await client.get("/api/v1/users", headers=auth_headers)

        # Assert
        assert response.status_code == 403  # Forbidden

    async def test_get_user_detail_without_permission(
        self, client: AsyncClient, auth_headers: dict
    ):
        """사용자 상세 조회 실패 - 권한 없음"""
        # Act
        response = await client.get("/api/v1/users/1", headers=auth_headers)

        # Assert
        assert response.status_code == 403  # Forbidden
