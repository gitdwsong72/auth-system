"""Comprehensive Authentication Router Integration Tests.

This module provides end-to-end tests for all authentication API endpoints,
including authentication flows, rate limiting, authorization, and error responses.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestAuthenticationFlows:
    """Test complete authentication flows."""

    async def test_successful_registration_and_login(self, client: AsyncClient):
        """Test successful user registration followed by login."""
        # Arrange
        register_payload = {
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "username": "newuser",
            "display_name": "New User",
        }

        # Act - Register
        register_response = await client.post("/api/v1/users/register", json=register_payload)

        # Assert registration
        assert register_response.status_code == 201
        register_data = register_response.json()
        assert register_data["success"] is True
        assert register_data["data"]["email"] == "newuser@example.com"

        # Act - Login
        login_payload = {
            "email": "newuser@example.com",
            "password": "SecurePass123!",
        }
        login_response = await client.post("/api/v1/auth/login", json=login_payload)

        # Assert login
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert login_data["success"] is True
        assert "access_token" in login_data["data"]
        assert "refresh_token" in login_data["data"]
        assert login_data["data"]["token_type"] == "bearer"
        assert login_data["data"]["expires_in"] == 900

    async def test_duplicate_email_registration(self, client: AsyncClient):
        """Test registration with duplicate email fails."""
        # Arrange
        register_payload = {
            "email": "duplicate@example.com",
            "password": "TestPass123!",
            "username": "duplicate1",
        }

        # Act - First registration
        first_response = await client.post("/api/v1/users/register", json=register_payload)
        assert first_response.status_code == 201

        # Act - Duplicate registration
        duplicate_payload = {
            "email": "duplicate@example.com",
            "password": "DifferentPass123!",
            "username": "duplicate2",
        }
        duplicate_response = await client.post("/api/v1/users/register", json=duplicate_payload)

        # Assert
        assert duplicate_response.status_code == 400
        data = duplicate_response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "USER_002"

    async def test_login_with_invalid_password(self, client: AsyncClient):
        """Test login with wrong password fails."""
        # Arrange - Register user
        await client.post(
            "/api/v1/users/register",
            json={
                "email": "validuser@example.com",
                "password": "CorrectPass123!",
                "username": "validuser",
            },
        )

        # Act - Login with wrong password
        login_payload = {
            "email": "validuser@example.com",
            "password": "WrongPassword123!",
        }
        response = await client.post("/api/v1/auth/login", json=login_payload)

        # Assert
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "AUTH_001"
        assert "이메일 또는 비밀번호" in data["error"]["message"]

    async def test_login_with_nonexistent_email(self, client: AsyncClient):
        """Test login with nonexistent email fails."""
        # Act
        login_payload = {
            "email": "doesnotexist@example.com",
            "password": "AnyPassword123!",
        }
        response = await client.post("/api/v1/auth/login", json=login_payload)

        # Assert
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "AUTH_001"

    async def test_token_refresh_success(self, client: AsyncClient):
        """Test successful token refresh."""
        # Arrange - Register and login
        await client.post(
            "/api/v1/users/register",
            json={
                "email": "refreshuser@example.com",
                "password": "RefreshPass123!",
                "username": "refreshuser",
            },
        )
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "refreshuser@example.com", "password": "RefreshPass123!"},
        )
        refresh_token = login_response.json()["data"]["refresh_token"]

        # Act - Refresh token
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        # Assert
        assert refresh_response.status_code == 200
        data = refresh_response.json()
        assert data["success"] is True
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]
        # Should get new tokens
        assert data["data"]["access_token"] != login_response.json()["data"]["access_token"]
        assert data["data"]["refresh_token"] != refresh_token

    async def test_token_refresh_with_invalid_token(self, client: AsyncClient):
        """Test token refresh with invalid token fails."""
        # Act
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )

        # Assert
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "AUTH_006"

    async def test_logout_invalidates_token(self, client: AsyncClient):
        """Test logout invalidates access token."""
        # Arrange - Register, login, get token
        await client.post(
            "/api/v1/users/register",
            json={
                "email": "logoutuser@example.com",
                "password": "LogoutPass123!",
                "username": "logoutuser",
            },
        )
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "logoutuser@example.com", "password": "LogoutPass123!"},
        )
        access_token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Act - Logout
        logout_response = await client.post("/api/v1/auth/logout", headers=headers)

        # Assert logout succeeded
        assert logout_response.status_code in [200, 204]

        # Verify token is now invalid
        profile_response = await client.get("/api/v1/users/me", headers=headers)
        assert profile_response.status_code == 401


@pytest.mark.asyncio
class TestRateLimiting:
    """Test rate limiting functionality."""

    async def test_login_rate_limit_after_5_failures(self, client: AsyncClient):
        """Test account lockout after 5 failed login attempts."""
        # Arrange - Register user
        email = "ratelimituser@example.com"
        await client.post(
            "/api/v1/users/register",
            json={
                "email": email,
                "password": "CorrectPass123!",
                "username": "ratelimituser",
            },
        )

        # Act - Attempt 5 failed logins
        for i in range(5):
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": f"WrongPass{i}!"},
            )
            # First 4 should return AUTH_001, 5th should lock account
            if i < 4:
                assert response.status_code == 401
                assert response.json()["error"]["code"] == "AUTH_001"

        # 5th attempt should trigger lockout
        lockout_response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "WrongPass5!"},
        )

        # Assert account is locked
        assert lockout_response.status_code == 401
        data = lockout_response.json()
        assert data["error"]["code"] == "AUTH_004"
        assert "잠겨있습니다" in data["error"]["message"]
        assert data["error"]["details"]["remaining_minutes"] == 15

    async def test_correct_password_after_lockout_still_fails(self, client: AsyncClient):
        """Test that correct password still fails when account is locked."""
        # Arrange - Register and trigger lockout
        email = "lockeduser@example.com"
        password = "CorrectPass123!"
        await client.post(
            "/api/v1/users/register",
            json={"email": email, "password": password, "username": "lockeduser"},
        )

        # Trigger lockout with 5 failed attempts
        for _ in range(5):
            await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "WrongPass!"},
            )

        # Act - Try with correct password
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )

        # Assert - Still locked
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "AUTH_004"


@pytest.mark.asyncio
class TestAuthorization:
    """Test authorization and permission checks."""

    async def test_protected_endpoint_requires_token(self, client: AsyncClient):
        """Test protected endpoint rejects requests without token."""
        # Act - Access protected endpoint without auth
        response = await client.get("/api/v1/users/me")

        # Assert
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False

    async def test_protected_endpoint_with_valid_token(self, client: AsyncClient):
        """Test protected endpoint accepts valid token."""
        # Arrange - Register and login
        await client.post(
            "/api/v1/users/register",
            json={
                "email": "authuser@example.com",
                "password": "AuthPass123!",
                "username": "authuser",
            },
        )
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "authuser@example.com", "password": "AuthPass123!"},
        )
        access_token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Act - Access protected endpoint
        response = await client.get("/api/v1/users/me", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["email"] == "authuser@example.com"

    async def test_expired_token_rejected(self, client: AsyncClient):
        """Test that expired tokens are rejected."""
        # Note: This test would require mocking time or waiting for expiration
        # For now, we test with an invalid token format
        headers = {"Authorization": "Bearer expired.token.here"}

        # Act
        response = await client.get("/api/v1/users/me", headers=headers)

        # Assert
        assert response.status_code == 401

    async def test_malformed_token_rejected(self, client: AsyncClient):
        """Test that malformed tokens are rejected."""
        # Act - Various malformed tokens
        test_cases = [
            "InvalidTokenFormat",
            "Bearer",
            "Bearer ",
            "NotBearer valid.token.here",
        ]

        for token in test_cases:
            response = await client.get(
                "/api/v1/users/me",
                headers={"Authorization": token},
            )
            assert response.status_code == 401


@pytest.mark.asyncio
class TestErrorResponses:
    """Test error response format consistency."""

    async def test_error_response_format_401(self, client: AsyncClient):
        """Test 401 error response has consistent format."""
        # Act
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "invalid@example.com", "password": "Invalid123!"},
        )

        # Assert
        assert response.status_code == 401
        data = response.json()
        assert "success" in data
        assert data["success"] is False
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert data["error"]["code"] == "AUTH_001"

    async def test_error_response_format_400(self, client: AsyncClient):
        """Test 400 error response has consistent format."""
        # Act - Invalid request body
        response = await client.post("/api/v1/auth/login", json={})

        # Assert
        assert response.status_code == 422  # Pydantic validation error
        data = response.json()
        assert "detail" in data  # FastAPI validation error format

    async def test_validation_error_for_invalid_email(self, client: AsyncClient):
        """Test validation error for invalid email format."""
        # Act
        response = await client.post(
            "/api/v1/users/register",
            json={
                "email": "not-an-email",
                "password": "ValidPass123!",
                "username": "testuser",
            },
        )

        # Assert
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    async def test_validation_error_for_weak_password(self, client: AsyncClient):
        """Test validation error for weak password."""
        # Act
        response = await client.post(
            "/api/v1/users/register",
            json={
                "email": "test@example.com",
                "password": "weak",
                "username": "testuser",
            },
        )

        # Assert
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data


@pytest.mark.asyncio
class TestSessionManagement:
    """Test session management endpoints."""

    async def test_get_active_sessions(self, client: AsyncClient):
        """Test retrieving list of active sessions."""
        # Arrange - Register and login
        await client.post(
            "/api/v1/users/register",
            json={
                "email": "sessionuser@example.com",
                "password": "SessionPass123!",
                "username": "sessionuser",
            },
        )
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "sessionuser@example.com",
                "password": "SessionPass123!",
                "device_info": "Chrome on Windows",
            },
        )
        access_token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Act
        response = await client.get("/api/v1/auth/sessions", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
        assert len(data["data"]) >= 1
        # Check session structure
        session = data["data"][0]
        assert "id" in session
        assert "device_info" in session
        assert "created_at" in session
        assert "expires_at" in session

    async def test_revoke_all_sessions_success(self, client: AsyncClient):
        """Test revoking all sessions."""
        # Arrange - Register and login
        await client.post(
            "/api/v1/users/register",
            json={
                "email": "revokealluser@example.com",
                "password": "RevokePass123!",
                "username": "revokealluser",
            },
        )
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "revokealluser@example.com", "password": "RevokePass123!"},
        )
        access_token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Act - Revoke all sessions
        response = await client.delete("/api/v1/auth/sessions", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify token is now invalid
        profile_response = await client.get("/api/v1/users/me", headers=headers)
        assert profile_response.status_code == 401


@pytest.mark.asyncio
class TestCompleteAuthFlows:
    """Test complete end-to-end authentication flows."""

    async def test_complete_user_lifecycle(self, client: AsyncClient):
        """Test complete user lifecycle: register -> login -> use -> refresh -> logout."""
        # 1. Register
        register_response = await client.post(
            "/api/v1/users/register",
            json={
                "email": "lifecycle@example.com",
                "password": "Lifecycle123!",
                "username": "lifecycle",
                "display_name": "Lifecycle User",
            },
        )
        assert register_response.status_code == 201

        # 2. Login
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "lifecycle@example.com", "password": "Lifecycle123!"},
        )
        assert login_response.status_code == 200
        login_data = login_response.json()["data"]
        access_token = login_data["access_token"]
        refresh_token = login_data["refresh_token"]

        # 3. Use token to access protected resource
        headers = {"Authorization": f"Bearer {access_token}"}
        profile_response = await client.get("/api/v1/users/me", headers=headers)
        assert profile_response.status_code == 200
        assert profile_response.json()["data"]["email"] == "lifecycle@example.com"

        # 4. Get sessions
        sessions_response = await client.get("/api/v1/auth/sessions", headers=headers)
        assert sessions_response.status_code == 200
        assert len(sessions_response.json()["data"]) >= 1

        # 5. Refresh token
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_response.status_code == 200
        new_access_token = refresh_response.json()["data"]["access_token"]

        # 6. Use new token
        new_headers = {"Authorization": f"Bearer {new_access_token}"}
        profile_response2 = await client.get("/api/v1/users/me", headers=new_headers)
        assert profile_response2.status_code == 200

        # 7. Logout
        logout_response = await client.post("/api/v1/auth/logout", headers=new_headers)
        assert logout_response.status_code in [200, 204]

        # 8. Verify token is invalidated
        profile_response3 = await client.get("/api/v1/users/me", headers=new_headers)
        assert profile_response3.status_code == 401

    async def test_multiple_device_sessions(self, client: AsyncClient):
        """Test user can have multiple active sessions from different devices."""
        # Arrange - Register
        await client.post(
            "/api/v1/users/register",
            json={
                "email": "multidevice@example.com",
                "password": "MultiDevice123!",
                "username": "multidevice",
            },
        )

        # Act - Login from device 1
        device1_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "multidevice@example.com",
                "password": "MultiDevice123!",
                "device_info": "Chrome on Windows",
            },
        )
        device1_token = device1_response.json()["data"]["access_token"]

        # Act - Login from device 2
        device2_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "multidevice@example.com",
                "password": "MultiDevice123!",
                "device_info": "Safari on iPhone",
            },
        )
        device2_token = device2_response.json()["data"]["access_token"]

        # Assert - Both tokens work
        device1_headers = {"Authorization": f"Bearer {device1_token}"}
        device2_headers = {"Authorization": f"Bearer {device2_token}"}

        profile1 = await client.get("/api/v1/users/me", headers=device1_headers)
        profile2 = await client.get("/api/v1/users/me", headers=device2_headers)

        assert profile1.status_code == 200
        assert profile2.status_code == 200

        # Check sessions count
        sessions = await client.get("/api/v1/auth/sessions", headers=device1_headers)
        assert len(sessions.json()["data"]) >= 2
