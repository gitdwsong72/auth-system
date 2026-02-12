"""Authentication Repository 단위 테스트"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from src.domains.authentication import repository


@pytest.fixture
def mock_connection():
    """Mock asyncpg connection"""
    return AsyncMock()


@pytest.fixture
def sample_token_hash():
    """샘플 토큰 해시"""
    return "abc123hash"


@pytest.fixture
def sample_user_id():
    """샘플 사용자 ID"""
    return 1


class TestGetRefreshToken:
    """리프레시 토큰 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_refresh_token_found(self, mock_connection, sample_token_hash):
        """리프레시 토큰 조회 성공"""
        # Arrange
        expected_token = {
            "id": 1,
            "user_id": 1,
            "token_hash": sample_token_hash,
            "expires_at": datetime.now() + timedelta(days=7),
        }
        mock_connection.fetchrow.return_value = expected_token

        with patch("src.domains.authentication.repository.sql.load_query") as mock_sql:
            mock_sql.return_value = "SELECT * FROM refresh_tokens WHERE token_hash = $1"

            # Act
            result = await repository.get_refresh_token(mock_connection, sample_token_hash)

            # Assert
            assert result == expected_token
            mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_refresh_token_not_found(self, mock_connection, sample_token_hash):
        """리프레시 토큰 없음"""
        # Arrange
        mock_connection.fetchrow.return_value = None

        with patch("src.domains.authentication.repository.sql.load_query") as mock_sql:
            mock_sql.return_value = "SELECT * FROM refresh_tokens WHERE token_hash = $1"

            # Act
            result = await repository.get_refresh_token(mock_connection, sample_token_hash)

            # Assert
            assert result is None


class TestGetActiveSessions:
    """활성 세션 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_active_sessions_multiple(self, mock_connection, sample_user_id):
        """여러 활성 세션 조회"""
        # Arrange
        expected_sessions = [
            {"id": 1, "device_info": "Chrome on Windows"},
            {"id": 2, "device_info": "Safari on macOS"},
        ]
        mock_connection.fetch.return_value = expected_sessions

        with patch("src.domains.authentication.repository.sql.load_query") as mock_sql:
            mock_sql.return_value = "SELECT * FROM refresh_tokens WHERE user_id = $1"

            # Act
            result = await repository.get_active_sessions(mock_connection, sample_user_id)

            # Assert
            assert result == expected_sessions
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_active_sessions_empty(self, mock_connection, sample_user_id):
        """활성 세션 없음"""
        # Arrange
        mock_connection.fetch.return_value = []

        with patch("src.domains.authentication.repository.sql.load_query") as mock_sql:
            mock_sql.return_value = "SELECT * FROM refresh_tokens WHERE user_id = $1"

            # Act
            result = await repository.get_active_sessions(mock_connection, sample_user_id)

            # Assert
            assert result == []


class TestSaveRefreshToken:
    """리프레시 토큰 저장 테스트"""

    @pytest.mark.asyncio
    async def test_save_refresh_token_success(
        self, mock_connection, sample_user_id, sample_token_hash
    ):
        """리프레시 토큰 저장 성공"""
        # Arrange
        device_info = "Chrome on Windows"
        expires_at = datetime.now() + timedelta(days=7)
        expected_result = {
            "id": 1,
            "user_id": sample_user_id,
            "token_hash": sample_token_hash,
            "device_info": device_info,
            "expires_at": expires_at,
        }
        mock_connection.fetchrow.return_value = expected_result

        with patch("src.domains.authentication.repository.sql.load_command") as mock_sql:
            mock_sql.return_value = (
                "INSERT INTO refresh_tokens (user_id, token_hash, device_info, expires_at) "
                "VALUES ($1, $2, $3, $4) RETURNING *"
            )

            # Act
            result = await repository.save_refresh_token(
                mock_connection, sample_user_id, sample_token_hash, device_info, expires_at
            )

            # Assert
            assert result == expected_result
            mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_refresh_token_without_device_info(
        self, mock_connection, sample_user_id, sample_token_hash
    ):
        """디바이스 정보 없이 토큰 저장"""
        # Arrange
        expires_at = datetime.now() + timedelta(days=7)
        expected_result = {
            "id": 1,
            "user_id": sample_user_id,
            "token_hash": sample_token_hash,
            "device_info": None,
            "expires_at": expires_at,
        }
        mock_connection.fetchrow.return_value = expected_result

        with patch("src.domains.authentication.repository.sql.load_command") as mock_sql:
            mock_sql.return_value = (
                "INSERT INTO refresh_tokens (user_id, token_hash, device_info, expires_at) "
                "VALUES ($1, $2, $3, $4) RETURNING *"
            )

            # Act
            result = await repository.save_refresh_token(
                mock_connection, sample_user_id, sample_token_hash, None, expires_at
            )

            # Assert
            assert result == expected_result
            assert result["device_info"] is None


class TestRevokeRefreshToken:
    """리프레시 토큰 폐기 테스트"""

    @pytest.mark.asyncio
    async def test_revoke_refresh_token_success(self, mock_connection, sample_token_hash):
        """리프레시 토큰 폐기 성공"""
        # Arrange
        expected_result = {"id": 1, "token_hash": sample_token_hash, "revoked_at": datetime.now()}
        mock_connection.fetchrow.return_value = expected_result

        with patch("src.domains.authentication.repository.sql.load_command") as mock_sql:
            mock_sql.return_value = (
                "UPDATE refresh_tokens SET revoked_at = NOW() " "WHERE token_hash = $1 RETURNING *"
            )

            # Act
            result = await repository.revoke_refresh_token(mock_connection, sample_token_hash)

            # Assert
            assert result == expected_result

    @pytest.mark.asyncio
    async def test_revoke_refresh_token_not_found(self, mock_connection, sample_token_hash):
        """존재하지 않는 토큰 폐기 시도"""
        # Arrange
        mock_connection.fetchrow.return_value = None

        with patch("src.domains.authentication.repository.sql.load_command") as mock_sql:
            mock_sql.return_value = (
                "UPDATE refresh_tokens SET revoked_at = NOW() " "WHERE token_hash = $1 RETURNING *"
            )

            # Act
            result = await repository.revoke_refresh_token(mock_connection, sample_token_hash)

            # Assert
            assert result is None


class TestRevokeAllUserTokens:
    """사용자의 모든 토큰 폐기 테스트"""

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens_multiple(self, mock_connection, sample_user_id):
        """여러 토큰 한번에 폐기"""
        # Arrange
        expected_result = [
            {"id": 1, "user_id": sample_user_id},
            {"id": 2, "user_id": sample_user_id},
        ]
        mock_connection.fetch.return_value = expected_result

        with patch("src.domains.authentication.repository.sql.load_command") as mock_sql:
            mock_sql.return_value = (
                "UPDATE refresh_tokens SET revoked_at = NOW() " "WHERE user_id = $1 RETURNING *"
            )

            # Act
            result = await repository.revoke_all_user_tokens(mock_connection, sample_user_id)

            # Assert
            assert result == expected_result
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens_empty(self, mock_connection, sample_user_id):
        """폐기할 토큰이 없음"""
        # Arrange
        mock_connection.fetch.return_value = []

        with patch("src.domains.authentication.repository.sql.load_command") as mock_sql:
            mock_sql.return_value = (
                "UPDATE refresh_tokens SET revoked_at = NOW() " "WHERE user_id = $1 RETURNING *"
            )

            # Act
            result = await repository.revoke_all_user_tokens(mock_connection, sample_user_id)

            # Assert
            assert result == []


class TestSaveLoginHistory:
    """로그인 이력 저장 테스트"""

    @pytest.mark.asyncio
    async def test_save_login_history_success(self, mock_connection, sample_user_id):
        """로그인 이력 저장 성공"""
        # Arrange
        ip_address = "192.168.1.1"
        user_agent = "Mozilla/5.0"
        success = True
        expected_result = {
            "id": 1,
            "user_id": sample_user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "success": success,
        }
        mock_connection.fetchrow.return_value = expected_result

        with patch("src.domains.authentication.repository.sql.load_command") as mock_sql:
            mock_sql.return_value = (
                "INSERT INTO login_histories (user_id, ip_address, user_agent, success) "
                "VALUES ($1, $2, $3, $4) RETURNING *"
            )

            # Act
            result = await repository.save_login_history(
                mock_connection, sample_user_id, ip_address, user_agent, success
            )

            # Assert
            assert result == expected_result

    @pytest.mark.asyncio
    async def test_save_login_history_failed_login(self, mock_connection, sample_user_id):
        """실패한 로그인 이력 저장"""
        # Arrange
        ip_address = "192.168.1.1"
        user_agent = "Mozilla/5.0"
        success = False
        expected_result = {
            "id": 2,
            "user_id": sample_user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "success": success,
        }
        mock_connection.fetchrow.return_value = expected_result

        with patch("src.domains.authentication.repository.sql.load_command") as mock_sql:
            mock_sql.return_value = (
                "INSERT INTO login_histories (user_id, ip_address, user_agent, success) "
                "VALUES ($1, $2, $3, $4) RETURNING *"
            )

            # Act
            result = await repository.save_login_history(
                mock_connection, sample_user_id, ip_address, user_agent, success
            )

            # Assert
            assert result == expected_result
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_save_login_history_with_none_values(self, mock_connection, sample_user_id):
        """IP/UserAgent가 None인 경우"""
        # Arrange
        expected_result = {
            "id": 3,
            "user_id": sample_user_id,
            "ip_address": None,
            "user_agent": None,
            "success": True,
        }
        mock_connection.fetchrow.return_value = expected_result

        with patch("src.domains.authentication.repository.sql.load_command") as mock_sql:
            mock_sql.return_value = (
                "INSERT INTO login_histories (user_id, ip_address, user_agent, success) "
                "VALUES ($1, $2, $3, $4) RETURNING *"
            )

            # Act
            result = await repository.save_login_history(
                mock_connection, sample_user_id, None, None, True
            )

            # Assert
            assert result == expected_result
            assert result["ip_address"] is None
            assert result["user_agent"] is None


class TestUpdateLastLogin:
    """마지막 로그인 시각 업데이트 테스트"""

    @pytest.mark.asyncio
    async def test_update_last_login_success(self, mock_connection, sample_user_id):
        """마지막 로그인 시각 업데이트 성공"""
        # Arrange
        expected_result = {
            "id": sample_user_id,
            "last_login_at": datetime.now(),
        }
        mock_connection.fetchrow.return_value = expected_result

        with patch("src.domains.authentication.repository.sql.load_command") as mock_sql:
            mock_sql.return_value = (
                "UPDATE users SET last_login_at = NOW() " "WHERE id = $1 RETURNING *"
            )

            # Act
            result = await repository.update_last_login(mock_connection, sample_user_id)

            # Assert
            assert result == expected_result
            assert result["id"] == sample_user_id

    @pytest.mark.asyncio
    async def test_update_last_login_user_not_found(self, mock_connection, sample_user_id):
        """존재하지 않는 사용자"""
        # Arrange
        mock_connection.fetchrow.return_value = None

        with patch("src.domains.authentication.repository.sql.load_command") as mock_sql:
            mock_sql.return_value = (
                "UPDATE users SET last_login_at = NOW() " "WHERE id = $1 RETURNING *"
            )

            # Act
            result = await repository.update_last_login(mock_connection, sample_user_id)

            # Assert
            assert result is None
