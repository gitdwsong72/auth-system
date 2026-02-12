"""Users 도메인 Service 단위 테스트"""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from src.domains.users import schemas, service
from src.shared.exceptions import ConflictException, UnauthorizedException, ValidationException


@pytest_asyncio.fixture
def mock_connection():
    """Mock database connection"""
    return AsyncMock()


@pytest.mark.asyncio
class TestUserService:
    """사용자 서비스 테스트"""

    async def test_register_success(self, mock_connection):
        """회원가입 성공"""
        # Arrange
        request = schemas.UserRegisterRequest(
            email="test@example.com",
            password="Test1234!",
            username="testuser",
            display_name="Test User",
        )

        mock_user_row = {
            "id": 1,
            "email": "test@example.com",
            "username": "testuser",
            "display_name": "Test User",
            "created_at": "2024-01-01T00:00:00Z",
        }

        with (
            patch("src.domains.users.service.repository.get_user_by_email", return_value=None),
            patch(
                "src.domains.users.service.password_hasher.validate_strength",
                return_value=[],
            ),
            patch(
                "src.domains.users.service.password_hasher.hash",
                return_value="hashed_password",
            ),
            patch("src.domains.users.service.repository.create_user", return_value=mock_user_row),
            patch(
                "src.domains.users.service.repository.assign_default_role", return_value={"id": 1}
            ),
            patch("src.domains.users.service.transaction") as mock_transaction,
        ):
            # transaction context manager mock
            mock_transaction.return_value.__aenter__ = AsyncMock()
            mock_transaction.return_value.__aexit__ = AsyncMock()

            # Act
            result = await service.register(mock_connection, request)

            # Assert
            assert result.email == "test@example.com"
            assert result.username == "testuser"

    async def test_register_duplicate_email(self, mock_connection):
        """회원가입 실패 - 이메일 중복"""
        # Arrange
        request = schemas.UserRegisterRequest(
            email="test@example.com",
            password="Test1234!",
            username="testuser",
        )

        with patch(
            "src.domains.users.service.repository.get_user_by_email", return_value={"id": 1}
        ):
            # Act & Assert
            with pytest.raises(ConflictException) as exc_info:
                await service.register(mock_connection, request)

            assert exc_info.value.error_code == "USER_001"

    async def test_register_weak_password(self, mock_connection):
        """회원가입 실패 - 비밀번호 강도 부족"""
        # Arrange - Pydantic validation을 통과하는 최소 길이지만 강도 부족
        request = schemas.UserRegisterRequest(
            email="test@example.com",
            password="weakpass",  # 8자 이상이지만 대문자/숫자/특수문자 없음
            username="testuser",
        )

        with (
            patch("src.domains.users.service.repository.get_user_by_email", return_value=None),
            patch(
                "src.domains.users.service.password_hasher.validate_strength",
                return_value=[
                    "대문자를 최소 1개 포함해야 합니다",
                    "숫자를 최소 1개 포함해야 합니다",
                ],
            ),
        ):
            # Act & Assert
            with pytest.raises(ValidationException) as exc_info:
                await service.register(mock_connection, request)

            assert exc_info.value.error_code == "USER_003"

    async def test_change_password_success(self, mock_connection):
        """비밀번호 변경 성공"""
        # Arrange
        user_id = 1
        request = schemas.ChangePasswordRequest(
            current_password="OldPass123!",
            new_password="NewPass456!",
        )

        mock_connection.fetchrow.return_value = {"password_hash": "hashed_old_password"}

        with (
            patch(
                "src.domains.users.service.password_hasher.verify_async",
                return_value=True,
            ),
            patch(
                "src.domains.users.service.password_hasher.validate_strength",
                return_value=[],
            ),
            patch(
                "src.domains.users.service.password_hasher.hash_async",
                return_value="hashed_new_password",
            ),
            patch(
                "src.domains.users.service.repository.change_password",
                return_value={"id": 1},
            ),
        ):
            # Act
            await service.change_password(mock_connection, user_id, request)

            # Assert - no exception raised

    async def test_change_password_wrong_current_password(self, mock_connection):
        """비밀번호 변경 실패 - 현재 비밀번호 불일치"""
        # Arrange
        user_id = 1
        request = schemas.ChangePasswordRequest(
            current_password="WrongPass!",
            new_password="NewPass456!",
        )

        mock_connection.fetchrow.return_value = {"password_hash": "hashed_old_password"}

        with patch(
            "src.domains.users.service.password_hasher.verify_async",
            return_value=False,
        ):
            # Act & Assert
            with pytest.raises(UnauthorizedException) as exc_info:
                await service.change_password(mock_connection, user_id, request)

            assert exc_info.value.error_code == "USER_004"

    async def test_list_users(self, mock_connection):
        """사용자 목록 조회"""
        # Arrange
        mock_user_rows = [
            {
                "id": 1,
                "email": "user1@example.com",
                "username": "user1",
                "display_name": "User 1",
                "is_active": True,
                "email_verified": False,
                "created_at": "2024-01-01T00:00:00Z",
                "last_login_at": None,
            },
            {
                "id": 2,
                "email": "user2@example.com",
                "username": "user2",
                "display_name": "User 2",
                "is_active": True,
                "email_verified": True,
                "created_at": "2024-01-02T00:00:00Z",
                "last_login_at": "2024-01-03T00:00:00Z",
            },
        ]

        with patch(
            "src.domains.users.service.repository.get_user_list_with_count",
            return_value=(mock_user_rows, 2),
        ):
            # Act
            users, total = await service.list_users(mock_connection, page=1, page_size=20)

            # Assert
            assert len(users) == 2
            assert total == 2
            assert users[0].email == "user1@example.com"
