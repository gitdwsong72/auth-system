"""Users Repository 단위 테스트"""

from unittest.mock import AsyncMock, patch

import pytest

from src.domains.users import repository


@pytest.fixture
def mock_connection():
    """Mock asyncpg connection"""
    return AsyncMock()


@pytest.fixture
def sample_user_id():
    """샘플 사용자 ID"""
    return 1


@pytest.fixture
def sample_email():
    """샘플 이메일"""
    return "test@example.com"


class TestGetUserById:
    """사용자 ID로 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_user_by_id_found(self, mock_connection, sample_user_id):
        """사용자 ID로 조회 성공"""
        # Arrange
        expected_user = {
            "id": sample_user_id,
            "email": "test@example.com",
            "username": "testuser",
        }
        mock_connection.fetchrow.return_value = expected_user

        with patch("src.domains.users.repository.sql.load_query") as mock_sql:
            mock_sql.return_value = "SELECT * FROM users WHERE id = $1"

            # Act
            result = await repository.get_user_by_id(mock_connection, sample_user_id)

            # Assert
            assert result == expected_user

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, mock_connection, sample_user_id):
        """사용자를 찾을 수 없음"""
        # Arrange
        mock_connection.fetchrow.return_value = None

        with patch("src.domains.users.repository.sql.load_query") as mock_sql:
            mock_sql.return_value = "SELECT * FROM users WHERE id = $1"

            # Act
            result = await repository.get_user_by_id(mock_connection, sample_user_id)

            # Assert
            assert result is None


class TestGetUserByEmail:
    """이메일로 사용자 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_user_by_email_found(self, mock_connection, sample_email):
        """이메일로 조회 성공"""
        # Arrange
        expected_user = {
            "id": 1,
            "email": sample_email,
            "username": "testuser",
            "password_hash": "hashed_password",
        }
        mock_connection.fetchrow.return_value = expected_user

        with patch("src.domains.users.repository.sql.load_query") as mock_sql:
            mock_sql.return_value = "SELECT * FROM users WHERE email = $1"

            # Act
            result = await repository.get_user_by_email(mock_connection, sample_email)

            # Assert
            assert result == expected_user
            assert "password_hash" in result

    @pytest.mark.asyncio
    async def test_get_user_by_email_not_found(self, mock_connection, sample_email):
        """이메일로 조회 실패"""
        # Arrange
        mock_connection.fetchrow.return_value = None

        with patch("src.domains.users.repository.sql.load_query") as mock_sql:
            mock_sql.return_value = "SELECT * FROM users WHERE email = $1"

            # Act
            result = await repository.get_user_by_email(mock_connection, sample_email)

            # Assert
            assert result is None


class TestGetUserList:
    """사용자 목록 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_user_list_basic(self, mock_connection):
        """기본 사용자 목록 조회"""
        # Arrange
        expected_users = [
            {"id": 1, "email": "user1@example.com"},
            {"id": 2, "email": "user2@example.com"},
        ]
        mock_connection.fetch.return_value = expected_users

        with patch("src.domains.users.repository.sql.load_query") as mock_sql:
            mock_sql.return_value = "SELECT * FROM users LIMIT $2 OFFSET $1"

            # Act
            result = await repository.get_user_list(mock_connection, offset=0, limit=10)

            # Assert
            assert result == expected_users
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_user_list_with_search(self, mock_connection):
        """검색어로 사용자 목록 조회"""
        # Arrange
        expected_users = [{"id": 1, "email": "john@example.com"}]
        mock_connection.fetch.return_value = expected_users

        with patch("src.domains.users.repository.sql.load_query") as mock_sql:
            mock_sql.return_value = "SELECT * FROM users WHERE email ILIKE $3 LIMIT $2 OFFSET $1"

            # Act
            result = await repository.get_user_list(
                mock_connection, offset=0, limit=10, search="john"
            )

            # Assert
            assert result == expected_users
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_user_list_with_is_active_filter(self, mock_connection):
        """활성화 필터로 사용자 목록 조회"""
        # Arrange
        expected_users = [{"id": 1, "email": "active@example.com", "is_active": True}]
        mock_connection.fetch.return_value = expected_users

        with patch("src.domains.users.repository.sql.load_query") as mock_sql:
            mock_sql.return_value = "SELECT * FROM users WHERE is_active = $4 LIMIT $2 OFFSET $1"

            # Act
            result = await repository.get_user_list(
                mock_connection, offset=0, limit=10, is_active=True
            )

            # Assert
            assert result == expected_users


class TestGetUserCount:
    """사용자 총 개수 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_user_count_basic(self, mock_connection):
        """기본 사용자 개수 조회"""
        # Arrange
        mock_connection.fetchrow.return_value = {"count": 100}

        with patch("src.domains.users.repository.sql.load_query") as mock_sql:
            mock_sql.return_value = "SELECT COUNT(*) as count FROM users"

            # Act
            result = await repository.get_user_count(mock_connection)

            # Assert
            assert result == 100

    @pytest.mark.asyncio
    async def test_get_user_count_with_search(self, mock_connection):
        """검색어로 사용자 개수 조회"""
        # Arrange
        mock_connection.fetchrow.return_value = {"count": 5}

        with patch("src.domains.users.repository.sql.load_query") as mock_sql:
            mock_sql.return_value = "SELECT COUNT(*) as count FROM users WHERE email ILIKE $1"

            # Act
            result = await repository.get_user_count(mock_connection, search="john")

            # Assert
            assert result == 5

    @pytest.mark.asyncio
    async def test_get_user_count_no_results(self, mock_connection):
        """결과가 없을 때 0 반환"""
        # Arrange
        mock_connection.fetchrow.return_value = None

        with patch("src.domains.users.repository.sql.load_query") as mock_sql:
            mock_sql.return_value = "SELECT COUNT(*) as count FROM users WHERE email = $1"

            # Act
            result = await repository.get_user_count(mock_connection, search="nonexistent")

            # Assert
            assert result == 0


class TestGetUserListWithCount:
    """사용자 목록 + 총 개수 조회 테스트 (Window Function)"""

    @pytest.mark.asyncio
    async def test_get_user_list_with_count_success(self, mock_connection):
        """목록 + 개수 동시 조회 성공"""
        # Arrange
        expected_rows = [
            {"id": 1, "email": "user1@example.com", "total_count": 50},
            {"id": 2, "email": "user2@example.com", "total_count": 50},
        ]
        mock_connection.fetch.return_value = expected_rows

        with patch("src.domains.users.repository.sql.load_query") as mock_sql:
            mock_sql.return_value = (
                "SELECT *, COUNT(*) OVER() as total_count FROM users LIMIT $2 OFFSET $1"
            )

            # Act
            users, total_count = await repository.get_user_list_with_count(
                mock_connection, offset=0, limit=10
            )

            # Assert
            assert len(users) == 2
            assert total_count == 50
            assert users[0]["total_count"] == 50

    @pytest.mark.asyncio
    async def test_get_user_list_with_count_empty(self, mock_connection):
        """결과가 없을 때"""
        # Arrange
        mock_connection.fetch.return_value = []

        with patch("src.domains.users.repository.sql.load_query") as mock_sql:
            mock_sql.return_value = (
                "SELECT *, COUNT(*) OVER() as total_count FROM users LIMIT $2 OFFSET $1"
            )

            # Act
            users, total_count = await repository.get_user_list_with_count(
                mock_connection, offset=0, limit=10
            )

            # Assert
            assert users == []
            assert total_count == 0


class TestGetUserRolesPermissions:
    """사용자 역할/권한 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_user_roles_permissions_multiple(self, mock_connection, sample_user_id):
        """여러 역할/권한 조회"""
        # Arrange
        expected_data = [
            {"role_name": "admin", "permission_name": "users:write"},
            {"role_name": "admin", "permission_name": "users:read"},
        ]
        mock_connection.fetch.return_value = expected_data

        with patch("src.domains.users.repository.sql.load_query") as mock_sql:
            mock_sql.return_value = (
                "SELECT r.name as role_name, p.resource || ':' || p.action as permission_name "
                "FROM users u JOIN user_roles ur ON u.id = ur.user_id "
                "JOIN roles r ON ur.role_id = r.id "
                "JOIN role_permissions rp ON r.id = rp.role_id "
                "JOIN permissions p ON rp.permission_id = p.id "
                "WHERE u.id = $1"
            )

            # Act
            result = await repository.get_user_roles_permissions(mock_connection, sample_user_id)

            # Assert
            assert result == expected_data
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_user_roles_permissions_empty(self, mock_connection, sample_user_id):
        """역할/권한이 없는 사용자"""
        # Arrange
        mock_connection.fetch.return_value = []

        with patch("src.domains.users.repository.sql.load_query") as mock_sql:
            mock_sql.return_value = "SELECT ... WHERE u.id = $1"

            # Act
            result = await repository.get_user_roles_permissions(mock_connection, sample_user_id)

            # Assert
            assert result == []


class TestCreateUser:
    """사용자 생성 테스트"""

    @pytest.mark.asyncio
    async def test_create_user_success(self, mock_connection, sample_email):
        """사용자 생성 성공"""
        # Arrange
        username = "testuser"
        password_hash = "hashed_password"
        display_name = "Test User"
        expected_user = {
            "id": 1,
            "email": sample_email,
            "username": username,
            "display_name": display_name,
        }
        mock_connection.fetchrow.return_value = expected_user

        with patch("src.domains.users.repository.sql.load_command") as mock_sql:
            mock_sql.return_value = (
                "INSERT INTO users (email, username, password_hash, display_name) "
                "VALUES ($1, $2, $3, $4) RETURNING *"
            )

            # Act
            result = await repository.create_user(
                mock_connection, sample_email, username, password_hash, display_name
            )

            # Assert
            assert result == expected_user
            assert result["email"] == sample_email

    @pytest.mark.asyncio
    async def test_create_user_without_display_name(self, mock_connection, sample_email):
        """display_name 없이 사용자 생성"""
        # Arrange
        username = "testuser"
        password_hash = "hashed_password"
        expected_user = {
            "id": 1,
            "email": sample_email,
            "username": username,
            "display_name": None,
        }
        mock_connection.fetchrow.return_value = expected_user

        with patch("src.domains.users.repository.sql.load_command") as mock_sql:
            mock_sql.return_value = (
                "INSERT INTO users (email, username, password_hash, display_name) "
                "VALUES ($1, $2, $3, $4) RETURNING *"
            )

            # Act
            result = await repository.create_user(
                mock_connection, sample_email, username, password_hash
            )

            # Assert
            assert result == expected_user
            assert result["display_name"] is None


class TestUpdateUser:
    """사용자 프로필 수정 테스트"""

    @pytest.mark.asyncio
    async def test_update_user_success(self, mock_connection, sample_user_id):
        """사용자 프로필 수정 성공"""
        # Arrange
        display_name = "Updated Name"
        phone = "010-1234-5678"
        avatar_url = "https://example.com/avatar.jpg"
        expected_user = {
            "id": sample_user_id,
            "display_name": display_name,
            "phone": phone,
            "avatar_url": avatar_url,
        }
        mock_connection.fetchrow.return_value = expected_user

        with patch("src.domains.users.repository.sql.load_command") as mock_sql:
            mock_sql.return_value = (
                "UPDATE users SET display_name = $2, phone = $3, avatar_url = $4 "
                "WHERE id = $1 RETURNING *"
            )

            # Act
            result = await repository.update_user(
                mock_connection, sample_user_id, display_name, phone, avatar_url
            )

            # Assert
            assert result == expected_user

    @pytest.mark.asyncio
    async def test_update_user_not_found(self, mock_connection, sample_user_id):
        """존재하지 않는 사용자 수정 시도"""
        # Arrange
        mock_connection.fetchrow.return_value = None

        with patch("src.domains.users.repository.sql.load_command") as mock_sql:
            mock_sql.return_value = (
                "UPDATE users SET display_name = $2, phone = $3, avatar_url = $4 "
                "WHERE id = $1 RETURNING *"
            )

            # Act
            result = await repository.update_user(mock_connection, sample_user_id)

            # Assert
            assert result is None


class TestChangePassword:
    """비밀번호 변경 테스트"""

    @pytest.mark.asyncio
    async def test_change_password_success(self, mock_connection, sample_user_id):
        """비밀번호 변경 성공"""
        # Arrange
        new_password_hash = "new_hashed_password"
        expected_user = {
            "id": sample_user_id,
            "password_hash": new_password_hash,
        }
        mock_connection.fetchrow.return_value = expected_user

        with patch("src.domains.users.repository.sql.load_command") as mock_sql:
            mock_sql.return_value = "UPDATE users SET password_hash = $2 WHERE id = $1 RETURNING *"

            # Act
            result = await repository.change_password(
                mock_connection, sample_user_id, new_password_hash
            )

            # Assert
            assert result == expected_user

    @pytest.mark.asyncio
    async def test_change_password_user_not_found(self, mock_connection, sample_user_id):
        """존재하지 않는 사용자 비밀번호 변경"""
        # Arrange
        mock_connection.fetchrow.return_value = None

        with patch("src.domains.users.repository.sql.load_command") as mock_sql:
            mock_sql.return_value = "UPDATE users SET password_hash = $2 WHERE id = $1 RETURNING *"

            # Act
            result = await repository.change_password(mock_connection, sample_user_id, "new_hash")

            # Assert
            assert result is None


class TestAssignDefaultRole:
    """기본 역할 부여 테스트"""

    @pytest.mark.asyncio
    async def test_assign_default_role_success(self, mock_connection, sample_user_id):
        """기본 역할 부여 성공"""
        # Arrange
        role_name = "user"
        expected_result = {
            "id": 1,
            "user_id": sample_user_id,
            "role_id": 1,
        }
        mock_connection.fetchrow.return_value = expected_result

        with patch("src.domains.users.repository.sql.load_command") as mock_sql:
            mock_sql.return_value = (
                "INSERT INTO user_roles (user_id, role_id) "
                "SELECT $1, id FROM roles WHERE name = $2 RETURNING *"
            )

            # Act
            result = await repository.assign_default_role(
                mock_connection, sample_user_id, role_name
            )

            # Assert
            assert result == expected_result

    @pytest.mark.asyncio
    async def test_assign_default_role_custom_role(self, mock_connection, sample_user_id):
        """커스텀 역할 부여"""
        # Arrange
        role_name = "admin"
        expected_result = {
            "id": 2,
            "user_id": sample_user_id,
            "role_id": 2,
        }
        mock_connection.fetchrow.return_value = expected_result

        with patch("src.domains.users.repository.sql.load_command") as mock_sql:
            mock_sql.return_value = (
                "INSERT INTO user_roles (user_id, role_id) "
                "SELECT $1, id FROM roles WHERE name = $2 RETURNING *"
            )

            # Act
            result = await repository.assign_default_role(
                mock_connection, sample_user_id, role_name
            )

            # Assert
            assert result == expected_result

    @pytest.mark.asyncio
    async def test_assign_default_role_not_found(self, mock_connection, sample_user_id):
        """존재하지 않는 역할 부여 시도"""
        # Arrange
        mock_connection.fetchrow.return_value = None

        with patch("src.domains.users.repository.sql.load_command") as mock_sql:
            mock_sql.return_value = (
                "INSERT INTO user_roles (user_id, role_id) "
                "SELECT $1, id FROM roles WHERE name = $2 RETURNING *"
            )

            # Act
            result = await repository.assign_default_role(
                mock_connection, sample_user_id, "nonexistent"
            )

            # Assert
            assert result is None


class TestILIKESanitization:
    """ILIKE pattern sanitization 테스트 (SQL injection 방지)"""

    def test_sanitize_ilike_pattern_none(self):
        """None 입력은 None 반환"""
        result = repository._sanitize_ilike_pattern(None)
        assert result is None

    def test_sanitize_ilike_pattern_normal_text(self):
        """일반 텍스트는 그대로 통과"""
        result = repository._sanitize_ilike_pattern("test")
        assert result == "test"

    def test_sanitize_ilike_pattern_escapes_percent(self):
        """%는 \\%로 escape"""
        result = repository._sanitize_ilike_pattern("test%")
        assert result == "test\\%"

    def test_sanitize_ilike_pattern_escapes_underscore(self):
        """_는 \\_로 escape"""
        result = repository._sanitize_ilike_pattern("test_")
        assert result == "test\\_"

    def test_sanitize_ilike_pattern_escapes_both(self):
        """%와 _ 모두 escape"""
        result = repository._sanitize_ilike_pattern("test%_abc")
        assert result == "test\\%\\_abc"

    def test_sanitize_ilike_pattern_escapes_backslash(self):
        """백슬래시도 escape (\\\\)"""
        result = repository._sanitize_ilike_pattern("test\\abc")
        assert result == "test\\\\abc"

    def test_sanitize_ilike_pattern_complex_injection_attempt(self):
        """복잡한 SQL injection 시도 차단"""
        # 모든 레코드 매칭 시도: %
        result = repository._sanitize_ilike_pattern("%")
        assert result == "\\%"

        # 와일드카드 패턴 시도: a%b_c
        result = repository._sanitize_ilike_pattern("a%b_c")
        assert result == "a\\%b\\_c"

    @pytest.mark.asyncio
    async def test_get_user_list_with_percent_search(self, mock_connection):
        """get_user_list에서 % 입력 시 sanitize 확인"""
        # Arrange
        mock_connection.fetch.return_value = []

        with patch("src.domains.users.repository.sql.load_query") as mock_sql:
            mock_sql.return_value = "SELECT * FROM users"

            # Act - % 입력
            await repository.get_user_list(mock_connection, 0, 10, search="%")

            # Assert - sanitized_search가 \\%로 전달되었는지 확인
            call_args = mock_connection.fetch.call_args[0]
            assert call_args[3] == "\\%"  # $3 parameter (search)

    @pytest.mark.asyncio
    async def test_get_user_count_with_underscore_search(self, mock_connection):
        """get_user_count에서 _ 입력 시 sanitize 확인"""
        # Arrange
        mock_connection.fetchrow.return_value = {"count": 0}

        with patch("src.domains.users.repository.sql.load_query") as mock_sql:
            mock_sql.return_value = "SELECT COUNT(*) FROM users"

            # Act - _ 입력
            await repository.get_user_count(mock_connection, search="_")

            # Assert - sanitized_search가 \\_로 전달되었는지 확인
            call_args = mock_connection.fetchrow.call_args[0]
            assert call_args[1] == "\\_"  # $1 parameter (search)

    @pytest.mark.asyncio
    async def test_get_user_list_with_count_sanitizes_search(self, mock_connection):
        """get_user_list_with_count에서도 sanitize 적용"""
        # Arrange
        mock_connection.fetch.return_value = []

        with patch("src.domains.users.repository.sql.load_query") as mock_sql:
            mock_sql.return_value = "SELECT * FROM users"

            # Act - %와 _ 모두 포함
            await repository.get_user_list_with_count(mock_connection, 0, 10, search="test%_attack")

            # Assert - 둘 다 escape되었는지 확인
            call_args = mock_connection.fetch.call_args[0]
            assert call_args[3] == "test\\%\\_attack"  # $3 parameter (search)
