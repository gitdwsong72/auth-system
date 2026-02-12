"""Dependencies unit tests"""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from src.shared.dependencies import get_current_user
from src.shared.exceptions import UnauthorizedException


@pytest_asyncio.fixture
def mock_connection():
    """Mock database connection"""
    return AsyncMock()


@pytest.mark.asyncio
class TestGetCurrentUser:
    """get_current_user dependency tests"""

    async def test_active_token_tracking_enforced(self, mock_connection):
        """Active token이 아닌 경우 거부되어야 함

        블랙리스트에는 없지만 active token registry에도 없는 경우
        AUTH_008 에러를 반환해야 한다.
        """
        # Arrange
        authorization = "Bearer valid_token"
        mock_payload = {
            "sub": "123",
            "jti": "test-jti-123",
            "email": "test@example.com",
        }

        with (
            patch(
                "src.shared.dependencies.jwt_handler.decode_token",
                return_value=mock_payload,
            ),
            patch(
                "src.shared.dependencies.redis_store.is_blacklisted",
                return_value=False,  # 블랙리스트에 없음
            ),
            patch(
                "src.shared.dependencies.redis_store.is_token_active",
                return_value=False,  # Active token이 아님
            ),
        ):
            # Act & Assert
            with pytest.raises(UnauthorizedException) as exc_info:
                await get_current_user(authorization, mock_connection)

            assert exc_info.value.error_code == "AUTH_008"
            assert "취소" in exc_info.value.message

    async def test_active_token_allowed(self, mock_connection):
        """Active token인 경우 허용되어야 함"""
        # Arrange
        authorization = "Bearer valid_token"
        mock_payload = {
            "sub": "123",
            "jti": "test-jti-123",
            "email": "test@example.com",
        }
        mock_user_row = {
            "id": 123,
            "email": "test@example.com",
            "username": "testuser",
            "is_active": True,
        }
        mock_permissions_data = {
            "roles": ["user"],
            "permissions": ["users:read"],
        }

        with (
            patch(
                "src.shared.dependencies.jwt_handler.decode_token",
                return_value=mock_payload,
            ),
            patch(
                "src.shared.dependencies.redis_store.is_blacklisted",
                return_value=False,
            ),
            patch(
                "src.shared.dependencies.redis_store.is_token_active",
                return_value=True,  # Active token
            ),
            patch(
                "src.shared.dependencies.users_repository.get_user_by_id",
                return_value=mock_user_row,
            ),
            patch(
                "src.shared.dependencies.users_service.get_user_permissions_with_cache",
                return_value=mock_permissions_data,
            ),
        ):
            # Act
            result = await get_current_user(authorization, mock_connection)

            # Assert
            assert result["id"] == 123
            assert result["email"] == "test@example.com"
            assert result["is_active"] is True
            assert "user" in result["roles"]
            assert "users:read" in result["permissions"]

    async def test_blacklisted_token_rejected_before_active_check(self, mock_connection):
        """블랙리스트 체크가 active token 체크보다 먼저 실행됨"""
        # Arrange
        authorization = "Bearer blacklisted_token"
        mock_payload = {
            "sub": "123",
            "jti": "blacklisted-jti",
        }

        with (
            patch(
                "src.shared.dependencies.jwt_handler.decode_token",
                return_value=mock_payload,
            ),
            patch(
                "src.shared.dependencies.redis_store.is_blacklisted",
                return_value=True,  # 블랙리스트에 있음
            ),
            patch(
                "src.shared.dependencies.redis_store.is_token_active",
                return_value=True,  # Active token이지만 블랙리스트가 우선
            ) as mock_is_active,
        ):
            # Act & Assert
            with pytest.raises(UnauthorizedException) as exc_info:
                await get_current_user(authorization, mock_connection)

            # 블랙리스트 체크가 먼저이므로 AUTH_003
            assert exc_info.value.error_code == "AUTH_003"

            # is_token_active는 호출되지 않음 (블랙리스트에서 먼저 거부)
            mock_is_active.assert_not_called()

    async def test_token_without_jti_skips_checks(self, mock_connection):
        """JTI가 없는 토큰은 블랙리스트/active 체크를 건너뜀"""
        # Arrange
        authorization = "Bearer token_without_jti"
        mock_payload = {
            "sub": "123",
            # jti 없음
        }
        mock_user_row = {
            "id": 123,
            "email": "test@example.com",
            "username": "testuser",
            "is_active": True,
        }
        mock_permissions_data = {
            "roles": ["user"],
            "permissions": ["users:read"],
        }

        with (
            patch(
                "src.shared.dependencies.jwt_handler.decode_token",
                return_value=mock_payload,
            ),
            patch(
                "src.shared.dependencies.redis_store.is_blacklisted",
            ) as mock_blacklist,
            patch(
                "src.shared.dependencies.redis_store.is_token_active",
            ) as mock_is_active,
            patch(
                "src.shared.dependencies.users_repository.get_user_by_id",
                return_value=mock_user_row,
            ),
            patch(
                "src.shared.dependencies.users_service.get_user_permissions_with_cache",
                return_value=mock_permissions_data,
            ),
        ):
            # Act
            result = await get_current_user(authorization, mock_connection)

            # Assert
            assert result["id"] == 123
            # JTI가 없으므로 블랙리스트/active 체크가 호출되지 않음
            mock_blacklist.assert_not_called()
            mock_is_active.assert_not_called()
