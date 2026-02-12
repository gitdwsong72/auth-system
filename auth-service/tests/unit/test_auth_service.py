"""Authentication 도메인 Service 단위 테스트"""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from src.domains.authentication import schemas, service
from src.shared.exceptions import UnauthorizedException


@pytest_asyncio.fixture
def mock_connection():
    """Mock database connection"""
    return AsyncMock()


@pytest.mark.asyncio
class TestAuthService:
    """인증 서비스 테스트"""

    async def test_login_success(self, mock_connection):
        """로그인 성공"""
        # Arrange
        request = schemas.LoginRequest(
            email="test@example.com",
            password="Test1234!",
            device_info="Chrome on Windows",
        )

        mock_user_row = {
            "id": 1,
            "email": "test@example.com",
            "username": "testuser",
            "password_hash": "hashed_password",
            "is_active": True,
        }

        mock_roles_permissions = [
            {"role_name": "user", "permission_name": "users:read"},
        ]

        with (
            patch(
                "src.domains.authentication.service.redis_store.is_account_locked",
                return_value=(False, 0),
            ),
            patch(
                "src.domains.authentication.service.users_repository.get_user_by_email",
                return_value=mock_user_row,
            ),
            patch(
                "src.domains.authentication.service.password_hasher.verify_async",
                return_value=True,
            ),
            patch(
                "src.domains.authentication.service.users_repository.get_user_roles_permissions",
                return_value=mock_roles_permissions,
            ),
            patch(
                "src.domains.authentication.service.jwt_handler.create_access_token",
                return_value="access_token",
            ),
            patch(
                "src.domains.authentication.service.jwt_handler.create_refresh_token",
                return_value="refresh_token",
            ),
            patch(
                "src.domains.authentication.service.jwt_handler.decode_token",
                return_value={"jti": "test-jti", "exp": 1234567890, "sub": "1"},
            ),
            patch(
                "src.domains.authentication.service.repository.save_refresh_token",
                return_value={"id": 1},
            ),
            patch(
                "src.domains.authentication.service.repository.save_login_history",
                return_value={"id": 1},
            ),
            patch(
                "src.domains.authentication.service.repository.update_last_login",
                return_value={"id": 1},
            ),
            patch("src.domains.authentication.service.redis_store.reset_failed_login"),
            patch("src.domains.authentication.service.redis_store.register_active_token"),
            patch(
                "src.domains.authentication.service.redis_store.get_cached_user_permissions",
                return_value=None,
            ),
            patch(
                "src.domains.authentication.service.redis_store.cache_user_permissions",
            ),
            patch("src.domains.authentication.service.transaction") as mock_transaction,
        ):
            # transaction context manager mock
            mock_transaction.return_value.__aenter__ = AsyncMock()
            mock_transaction.return_value.__aexit__ = AsyncMock()

            # Act
            result = await service.login(mock_connection, request)

            # Assert
            assert result.access_token == "access_token"
            assert result.refresh_token == "refresh_token"
            assert result.token_type == "bearer"

    async def test_login_wrong_password(self, mock_connection):
        """로그인 실패 - 비밀번호 불일치"""
        # Arrange
        request = schemas.LoginRequest(
            email="test@example.com",
            password="WrongPassword!",
        )

        mock_user_row = {
            "id": 1,
            "email": "test@example.com",
            "password_hash": "hashed_password",
            "is_active": True,
        }

        with (
            patch(
                "src.domains.authentication.service.redis_store.is_account_locked",
                return_value=(False, 0),
            ),
            patch(
                "src.domains.authentication.service.users_repository.get_user_by_email",
                return_value=mock_user_row,
            ),
            patch(
                "src.domains.authentication.service.password_hasher.verify_async",
                return_value=False,
            ),
            patch(
                "src.domains.authentication.service.redis_store.increment_failed_login",
                return_value=1,
            ),
            patch(
                "src.domains.authentication.service.repository.save_login_history",
                return_value={"id": 1},
            ),
        ):
            # Act & Assert
            with pytest.raises(UnauthorizedException) as exc_info:
                await service.login(mock_connection, request)

            assert exc_info.value.error_code == "AUTH_001"

    async def test_login_account_locked(self, mock_connection):
        """로그인 실패 - 계정 잠김 (일반 메시지로 계정 존재 여부 숨김)"""
        # Arrange
        request = schemas.LoginRequest(
            email="test@example.com",
            password="Test1234!",
        )

        with patch(
            "src.domains.authentication.service.redis_store.is_account_locked",
            return_value=(True, 10),
        ):
            # Act & Assert
            with pytest.raises(UnauthorizedException) as exc_info:
                await service.login(mock_connection, request)

            # 계정 존재 여부 노출 방지를 위해 일반 에러 코드 사용
            assert exc_info.value.error_code == "AUTH_001"
            assert exc_info.value.message == "이메일 또는 비밀번호가 올바르지 않습니다"
            # 잠금 시간 정보가 노출되지 않아야 함
            assert "잠금" not in exc_info.value.message
            assert "locked" not in exc_info.value.message.lower()

    async def test_login_inactive_account(self, mock_connection):
        """로그인 실패 - 비활성화된 계정 (일반 메시지로 계정 상태 숨김)"""
        # Arrange
        request = schemas.LoginRequest(
            email="test@example.com",
            password="Test1234!",
        )

        mock_user_row = {
            "id": 1,
            "email": "test@example.com",
            "password_hash": "hashed_password",
            "is_active": False,
        }

        with (
            patch(
                "src.domains.authentication.service.redis_store.is_account_locked",
                return_value=(False, 0),
            ),
            patch(
                "src.domains.authentication.service.users_repository.get_user_by_email",
                return_value=mock_user_row,
            ),
            patch(
                "src.domains.authentication.service.password_hasher.verify_async",
                return_value=True,
            ),
        ):
            # Act & Assert
            with pytest.raises(UnauthorizedException) as exc_info:
                await service.login(mock_connection, request)

            # 계정 상태 노출 방지를 위해 일반 에러 코드 사용
            assert exc_info.value.error_code == "AUTH_001"
            assert exc_info.value.message == "이메일 또는 비밀번호가 올바르지 않습니다"
            # 계정 상태 정보가 노출되지 않아야 함
            assert "비활성" not in exc_info.value.message
            assert "inactive" not in exc_info.value.message.lower()

    async def test_logout(self, mock_connection):
        """로그아웃"""
        # Arrange
        access_token = "valid_access_token"
        mock_payload = {"jti": "unique-jti", "exp": 1234567890}

        with (
            patch(
                "src.domains.authentication.service.jwt_handler.decode_token",
                return_value=mock_payload,
            ),
            patch("src.domains.authentication.service.redis_store.blacklist_token"),
        ):
            # Act
            await service.logout(mock_connection, access_token)

            # Assert - no exception raised

    async def test_refresh_token_success(self, mock_connection):
        """토큰 갱신 성공"""
        # Arrange
        request = schemas.RefreshTokenRequest(refresh_token="valid_refresh_token")

        mock_payload = {"sub": 1}
        mock_token_row = {
            "id": 1,
            "user_id": 1,
            "device_info": "Chrome",
            "expires_at": "2024-12-31T23:59:59Z",
        }
        mock_user_row = {
            "id": 1,
            "email": "test@example.com",
            "is_active": True,
        }
        mock_roles_permissions = [{"role_name": "user", "permission_name": "users:read"}]

        with (
            patch(
                "src.domains.authentication.service.jwt_handler.decode_token",
                return_value=mock_payload,
            ),
            patch(
                "src.domains.authentication.service.repository.get_refresh_token",
                return_value=mock_token_row,
            ),
            patch(
                "src.domains.authentication.service.users_repository.get_user_by_email",
                return_value=mock_user_row,
            ),
            patch(
                "src.domains.authentication.service.users_repository.get_user_roles_permissions",
                return_value=mock_roles_permissions,
            ),
            patch(
                "src.domains.authentication.service.jwt_handler.create_access_token",
                return_value="new_access_token",
            ),
            patch(
                "src.domains.authentication.service.jwt_handler.create_refresh_token",
                return_value="new_refresh_token",
            ),
            patch(
                "src.domains.authentication.service.repository.revoke_refresh_token",
                return_value={"id": 1},
            ),
            patch(
                "src.domains.authentication.service.repository.save_refresh_token",
                return_value={"id": 2},
            ),
            patch(
                "src.domains.authentication.service.redis_store.get_cached_user_permissions",
                return_value=None,
            ),
            patch(
                "src.domains.authentication.service.redis_store.cache_user_permissions",
            ),
            patch(
                "src.domains.authentication.service.redis_store.register_active_token",
            ),
            patch("src.domains.authentication.service.transaction") as mock_transaction,
        ):
            # transaction context manager mock
            mock_transaction.return_value.__aenter__ = AsyncMock()
            mock_transaction.return_value.__aexit__ = AsyncMock()

            # 이메일 조회용 mock
            mock_connection.fetchval.return_value = "test@example.com"

            # Act
            result = await service.refresh_access_token(mock_connection, request)

            # Assert
            assert result.access_token == "new_access_token"
            assert result.refresh_token == "new_refresh_token"

    async def test_refresh_token_invalid(self, mock_connection):
        """토큰 갱신 실패 - 유효하지 않은 리프레시 토큰"""
        # Arrange
        request = schemas.RefreshTokenRequest(refresh_token="invalid_token")

        from src.shared.security.jwt_handler import InvalidTokenError

        with patch(
            "src.domains.authentication.service.jwt_handler.decode_token",
            side_effect=InvalidTokenError("Invalid"),
        ):
            # Act & Assert
            with pytest.raises(UnauthorizedException) as exc_info:
                await service.refresh_access_token(mock_connection, request)

            assert exc_info.value.error_code == "AUTH_006"

    async def test_revoke_all_sessions(self, mock_connection):
        """전체 세션 종료"""
        # Arrange
        user_id = 1

        with (
            patch(
                "src.domains.authentication.service.repository.revoke_all_user_tokens",
                return_value=[{"id": 1}],
            ),
            patch(
                "src.domains.authentication.service.redis_store.get_user_active_tokens",
                return_value={"jti1", "jti2"},
            ),
            patch(
                "src.domains.authentication.service.redis_store.blacklist_token",
            ),
            patch(
                "src.domains.authentication.service.redis_store.clear_user_active_tokens",
            ),
        ):
            # Act
            await service.revoke_all_sessions(mock_connection, user_id)

            # Assert - no exception raised


@pytest.mark.asyncio
class TestAccountEnumerationPrevention:
    """계정 열거 공격 방지 테스트 (보안)"""

    async def test_account_locked_uses_generic_message(self, mock_connection):
        """계정 잠금 시 일반 메시지 사용 (계정 존재 여부 숨김)"""
        # Arrange
        request = schemas.LoginRequest(
            email="existing@example.com",
            password="WrongPassword123!",
        )

        with patch(
            "src.domains.authentication.service.redis_store.is_account_locked",
            return_value=(True, 15),  # 15분 잠금
        ):
            # Act & Assert
            with pytest.raises(UnauthorizedException) as exc_info:
                await service.login(mock_connection, request)

            # 일반 메시지 확인
            assert exc_info.value.error_code == "AUTH_001"
            assert exc_info.value.message == "이메일 또는 비밀번호가 올바르지 않습니다"

            # 계정 존재 여부를 암시하는 정보가 없어야 함
            assert "잠금" not in exc_info.value.message
            assert "locked" not in exc_info.value.message.lower()
            assert "15" not in exc_info.value.message  # 시간 정보 노출 방지

    async def test_inactive_account_uses_generic_message(self, mock_connection):
        """비활성화된 계정에 일반 메시지 사용 (계정 상태 숨김)"""
        # Arrange
        request = schemas.LoginRequest(
            email="inactive@example.com",
            password="CorrectPassword123!",
        )

        mock_user_row = {
            "id": 1,
            "email": "inactive@example.com",
            "password_hash": "hashed_password",
            "is_active": False,  # 비활성화
        }

        with (
            patch(
                "src.domains.authentication.service.redis_store.is_account_locked",
                return_value=(False, 0),
            ),
            patch(
                "src.domains.authentication.service.users_repository.get_user_by_email",
                return_value=mock_user_row,
            ),
            patch(
                "src.domains.authentication.service.password_hasher.verify_async",
                return_value=True,  # 비밀번호는 맞음
            ),
        ):
            # Act & Assert
            with pytest.raises(UnauthorizedException) as exc_info:
                await service.login(mock_connection, request)

            # 일반 메시지 확인
            assert exc_info.value.error_code == "AUTH_001"
            assert exc_info.value.message == "이메일 또는 비밀번호가 올바르지 않습니다"

            # 계정 상태 정보가 노출되지 않아야 함
            assert "비활성" not in exc_info.value.message
            assert "inactive" not in exc_info.value.message.lower()
            assert "disabled" not in exc_info.value.message.lower()

    async def test_five_failed_attempts_uses_generic_message(self, mock_connection):
        """5회 실패 후 계정 잠금 시에도 일반 메시지 사용"""
        # Arrange
        request = schemas.LoginRequest(
            email="victim@example.com",
            password="WrongPassword123!",
        )

        mock_user_row = {
            "id": 1,
            "email": "victim@example.com",
            "password_hash": "hashed_password",
            "is_active": True,
        }

        with (
            patch(
                "src.domains.authentication.service.redis_store.is_account_locked",
                return_value=(False, 0),
            ),
            patch(
                "src.domains.authentication.service.users_repository.get_user_by_email",
                return_value=mock_user_row,
            ),
            patch(
                "src.domains.authentication.service.password_hasher.verify_async",
                return_value=False,  # 비밀번호 틀림
            ),
            patch(
                "src.domains.authentication.service.redis_store.increment_failed_login",
                return_value=5,  # 5회 실패
            ),
            patch(
                "src.domains.authentication.service.repository.save_login_history",
                return_value={"id": 1},
            ),
        ):
            # Act & Assert
            with pytest.raises(UnauthorizedException) as exc_info:
                await service.login(mock_connection, request)

            # 일반 메시지 확인 (계정 잠금 사실 숨김)
            assert exc_info.value.error_code == "AUTH_001"
            assert exc_info.value.message == "이메일 또는 비밀번호가 올바르지 않습니다"

            # 잠금 정보가 노출되지 않아야 함
            assert "잠금" not in exc_info.value.message
            assert "15분" not in exc_info.value.message
