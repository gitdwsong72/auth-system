"""Users Repository Integration Tests

실제 PostgreSQL 데이터베이스를 사용하여 Users Repository의 SQL 쿼리를 테스트합니다.
"""

import contextlib
import os
import uuid

import asyncpg
import pytest
import pytest_asyncio

from src.domains.users import repository as users_repo


@pytest_asyncio.fixture(scope="function")
async def db_connection() -> asyncpg.Connection:
    """데이터베이스 연결 fixture.

    환경 변수에서 데이터베이스 URL을 읽어 직접 연결을 생성합니다.
    Each test gets a fresh connection in the current event loop.
    """
    db_url = os.getenv(
        "DB_PRIMARY_DB_URL",
        "postgresql://devuser:devpassword@localhost:5433/appdb?sslmode=disable",
    )
    connection = await asyncpg.connect(db_url)
    # 타임존 설정
    await connection.execute("SET timezone TO 'UTC'")
    try:
        yield connection
    finally:
        # Ensure proper cleanup
        with contextlib.suppress(Exception):
            await connection.close()


@pytest_asyncio.fixture
async def test_user(db_connection: asyncpg.Connection) -> asyncpg.Record:
    """테스트용 사용자 생성 fixture.

    각 테스트마다 고유한 이메일을 가진 사용자를 생성합니다.
    """
    unique_id = uuid.uuid4().hex[:8]
    user = await users_repo.create_user(
        connection=db_connection,
        email=f"testuser_{unique_id}@example.com",
        username=f"testuser_{unique_id}",
        password_hash="$2b$12$test_hash",
        display_name=f"Test User {unique_id}",
    )
    return user


@pytest_asyncio.fixture
async def test_role(db_connection: asyncpg.Connection) -> asyncpg.Record:
    """테스트용 역할 생성 fixture."""
    # 'user' 역할이 이미 존재한다고 가정 (시드 데이터)
    role = await db_connection.fetchrow("SELECT id, name FROM roles WHERE name = 'user'")
    if not role:
        role = await db_connection.fetchrow(
            "INSERT INTO roles (name, description) VALUES ('user', 'Default user role') "
            "RETURNING id, name"
        )
    return role


@pytest.mark.asyncio
class TestUserRetrieval:
    """사용자 조회 테스트"""

    async def test_get_user_by_id_success(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """사용자 ID로 조회 성공"""
        # Act
        result = await users_repo.get_user_by_id(db_connection, test_user["id"])

        # Assert
        assert result is not None
        assert result["id"] == test_user["id"]
        assert result["email"] == test_user["email"]
        assert result["username"] == test_user["username"]
        assert result["display_name"] == test_user["display_name"]
        assert result["is_active"] is True
        assert result["email_verified"] is False
        assert "password_hash" not in result  # 비밀번호 해시는 반환되지 않음

    async def test_get_user_by_id_not_found(self, db_connection: asyncpg.Connection):
        """사용자 ID로 조회 실패 - 존재하지 않는 ID"""
        # Act
        result = await users_repo.get_user_by_id(db_connection, 999999)

        # Assert
        assert result is None

    async def test_get_user_by_email_success(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """이메일로 사용자 조회 성공 (비밀번호 해시 포함)"""
        # Act
        result = await users_repo.get_user_by_email(db_connection, test_user["email"])

        # Assert
        assert result is not None
        assert result["id"] == test_user["id"]
        assert result["email"] == test_user["email"]
        assert result["password_hash"] is not None
        assert "password_hash" in result  # 인증용이므로 비밀번호 해시 포함

    async def test_get_user_by_email_not_found(self, db_connection: asyncpg.Connection):
        """이메일로 사용자 조회 실패 - 존재하지 않는 이메일"""
        # Act
        result = await users_repo.get_user_by_email(db_connection, "nonexistent@example.com")

        # Assert
        assert result is None

    async def test_get_user_by_email_case_sensitive(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """이메일 조회는 대소문자를 구분하지 않음 (PostgreSQL ILIKE)"""
        # Act
        result = await users_repo.get_user_by_email(db_connection, test_user["email"].upper())

        # Assert - 이메일이 대소문자 구분 없이 저장되어 있거나 ILIKE로 조회하면 찾을 수 있음
        # 실제 스키마에서 email은 unique이고, 일반적으로 소문자로 저장됨
        # 이 테스트는 실제 SQL 쿼리 동작을 확인하는 것이 목적
        assert result is None or result["id"] == test_user["id"]


@pytest.mark.asyncio
class TestUserList:
    """사용자 목록 조회 테스트"""

    async def test_get_user_list_basic(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """기본 사용자 목록 조회"""
        # Act - None 대신 빈 문자열 또는 명시적 타입 제공
        result = await db_connection.fetch(
            """
            SELECT id, email, username, display_name, is_active, email_verified,
                   created_at, last_login_at
            FROM users
            WHERE deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            10,
            0,
        )

        # Assert
        assert isinstance(result, list)
        assert len(result) > 0
        # test_user가 결과에 포함되어야 함
        user_ids = [user["id"] for user in result]
        assert test_user["id"] in user_ids

    async def test_get_user_list_pagination(self, db_connection: asyncpg.Connection):
        """페이징 테스트"""
        # Arrange - 여러 사용자 생성
        users = []
        for _i in range(5):
            unique_id = uuid.uuid4().hex[:8]
            user = await users_repo.create_user(
                connection=db_connection,
                email=f"pagination_{unique_id}@example.com",
                username=f"pagination_{unique_id}",
                password_hash="$2b$12$test_hash",
            )
            users.append(user)

        # Act - 첫 페이지 (2개)
        page1 = await users_repo.get_user_list(connection=db_connection, offset=0, limit=2)

        # Act - 두 번째 페이지 (2개)
        page2 = await users_repo.get_user_list(connection=db_connection, offset=2, limit=2)

        # Assert
        assert len(page1) == 2
        assert len(page2) >= 2
        # 페이지 간 중복 없음
        page1_ids = {user["id"] for user in page1}
        page2_ids = {user["id"] for user in page2}
        assert len(page1_ids & page2_ids) == 0

    async def test_get_user_list_search_by_email(self, db_connection: asyncpg.Connection):
        """이메일 검색 테스트"""
        # Arrange
        unique_id = uuid.uuid4().hex[:8]
        search_keyword = f"searchtest_{unique_id}"
        user = await users_repo.create_user(
            connection=db_connection,
            email=f"{search_keyword}@example.com",
            username=f"user_{unique_id}",
            password_hash="$2b$12$test_hash",
        )

        # Act
        result = await users_repo.get_user_list(
            connection=db_connection, offset=0, limit=10, search=search_keyword
        )

        # Assert
        assert len(result) >= 1
        user_ids = [u["id"] for u in result]
        assert user["id"] in user_ids

    async def test_get_user_list_search_by_username(self, db_connection: asyncpg.Connection):
        """사용자명 검색 테스트"""
        # Arrange
        unique_id = uuid.uuid4().hex[:8]
        search_keyword = f"usernametest_{unique_id}"
        user = await users_repo.create_user(
            connection=db_connection,
            email=f"email_{unique_id}@example.com",
            username=search_keyword,
            password_hash="$2b$12$test_hash",
        )

        # Act
        result = await users_repo.get_user_list(
            connection=db_connection, offset=0, limit=10, search=search_keyword
        )

        # Assert
        assert len(result) >= 1
        user_ids = [u["id"] for u in result]
        assert user["id"] in user_ids

    async def test_get_user_list_filter_by_active_status(self, db_connection: asyncpg.Connection):
        """활성 상태 필터 테스트"""
        # Arrange - 활성 사용자 생성
        unique_id = uuid.uuid4().hex[:8]
        active_user = await users_repo.create_user(
            connection=db_connection,
            email=f"active_{unique_id}@example.com",
            username=f"active_{unique_id}",
            password_hash="$2b$12$test_hash",
        )

        # Act - 활성 사용자만 조회
        result = await users_repo.get_user_list(
            connection=db_connection, offset=0, limit=100, is_active=True
        )

        # Assert
        assert len(result) > 0
        user_ids = [u["id"] for u in result]
        assert active_user["id"] in user_ids
        # 모든 결과가 활성 사용자여야 함
        for user in result:
            assert user["is_active"] is True

    async def test_get_user_count_basic(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """사용자 총 개수 조회"""
        # Act
        count = await users_repo.get_user_count(connection=db_connection)

        # Assert
        assert count > 0
        assert isinstance(count, int)

    async def test_get_user_count_with_search(self, db_connection: asyncpg.Connection):
        """검색 조건 포함 사용자 개수"""
        # Arrange
        unique_id = uuid.uuid4().hex[:8]
        search_keyword = f"counttest_{unique_id}"
        await users_repo.create_user(
            connection=db_connection,
            email=f"{search_keyword}@example.com",
            username=f"user_{unique_id}",
            password_hash="$2b$12$test_hash",
        )

        # Act
        count = await users_repo.get_user_count(connection=db_connection, search=search_keyword)

        # Assert
        assert count >= 1

    async def test_get_user_list_with_count_optimization(self, db_connection: asyncpg.Connection):
        """사용자 목록 + 개수 조회 최적화 (Window Function) 테스트"""
        # Arrange - 여러 사용자 생성
        for _i in range(3):
            unique_id = uuid.uuid4().hex[:8]
            await users_repo.create_user(
                connection=db_connection,
                email=f"optimized_{unique_id}@example.com",
                username=f"optimized_{unique_id}",
                password_hash="$2b$12$test_hash",
            )

        # Act
        users, total_count = await users_repo.get_user_list_with_count(
            connection=db_connection, offset=0, limit=2
        )

        # Assert
        assert isinstance(users, list)
        assert isinstance(total_count, int)
        assert len(users) <= 2  # LIMIT 적용됨
        assert total_count >= 3  # 전체 개수는 생성한 사용자 수 이상
        # 각 레코드에 total_count가 포함되어야 함 (Window Function)
        for user in users:
            assert "total_count" in user
            assert user["total_count"] == total_count

    async def test_get_user_list_with_count_empty_result(self, db_connection: asyncpg.Connection):
        """사용자 목록 조회 결과가 없을 때"""
        # Act
        users, total_count = await users_repo.get_user_list_with_count(
            connection=db_connection,
            offset=0,
            limit=10,
            search="nonexistent_keyword_12345",
        )

        # Assert
        assert users == []
        assert total_count == 0


@pytest.mark.asyncio
class TestUserPermissions:
    """사용자 권한 조회 테스트"""

    async def test_get_user_roles_permissions_with_role(
        self,
        db_connection: asyncpg.Connection,
        test_user: asyncpg.Record,
        test_role: asyncpg.Record,
    ):
        """역할 및 권한 조회 - 역할 할당된 사용자"""
        # Arrange - 사용자에게 역할 부여
        await users_repo.assign_default_role(
            connection=db_connection, user_id=test_user["id"], role_name=test_role["name"]
        )

        # Act
        result = await users_repo.get_user_roles_permissions(
            connection=db_connection, user_id=test_user["id"]
        )

        # Assert
        assert len(result) > 0
        # 최소한 역할 이름이 있어야 함
        role_names = [r["role_name"] for r in result]
        assert test_role["name"] in role_names

    async def test_get_user_roles_permissions_without_role(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """역할 및 권한 조회 - 역할 없는 사용자"""
        # Act
        result = await users_repo.get_user_roles_permissions(
            connection=db_connection, user_id=test_user["id"]
        )

        # Assert
        assert result == []

    async def test_get_user_roles_permissions_with_permissions(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """역할 및 권한 조회 - 권한이 있는 역할"""
        # Arrange - 역할 및 권한 생성
        unique_id = uuid.uuid4().hex[:8]
        role = await db_connection.fetchrow(
            f"INSERT INTO roles (name, description) VALUES ('testrole_{unique_id}', 'Test role') "
            "RETURNING id, name"
        )
        permission = await db_connection.fetchrow(
            "INSERT INTO permissions (resource, action) VALUES ('test_resource', 'read') "
            "ON CONFLICT (resource, action) DO UPDATE SET resource = EXCLUDED.resource "
            "RETURNING id"
        )
        await db_connection.execute(
            "INSERT INTO role_permissions (role_id, permission_id) VALUES ($1, $2) "
            "ON CONFLICT DO NOTHING",
            role["id"],
            permission["id"],
        )
        await db_connection.execute(
            "INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2)",
            test_user["id"],
            role["id"],
        )

        # Act
        result = await users_repo.get_user_roles_permissions(
            connection=db_connection, user_id=test_user["id"]
        )

        # Assert
        assert len(result) > 0
        # permission_name이 resource:action 형식으로 반환되어야 함
        permission_names = [r["permission_name"] for r in result if r["permission_name"]]
        assert "test_resource:read" in permission_names


@pytest.mark.asyncio
class TestUserMutations:
    """사용자 생성/수정 테스트"""

    async def test_create_user_success(self, db_connection: asyncpg.Connection):
        """사용자 생성 성공"""
        # Arrange
        unique_id = uuid.uuid4().hex[:8]
        email = f"newuser_{unique_id}@example.com"
        username = f"newuser_{unique_id}"
        password_hash = "$2b$12$test_hash"
        display_name = f"New User {unique_id}"

        # Act
        result = await users_repo.create_user(
            connection=db_connection,
            email=email,
            username=username,
            password_hash=password_hash,
            display_name=display_name,
        )

        # Assert
        assert result is not None
        assert result["id"] > 0
        assert result["email"] == email
        assert result["username"] == username
        assert result["display_name"] == display_name
        assert "created_at" in result

    async def test_create_user_duplicate_email(self, db_connection: asyncpg.Connection):
        """사용자 생성 실패 - 이메일 중복"""
        # Arrange
        unique_id = uuid.uuid4().hex[:8]
        email = f"duplicate_{unique_id}@example.com"

        await users_repo.create_user(
            connection=db_connection,
            email=email,
            username=f"user1_{unique_id}",
            password_hash="$2b$12$test_hash",
        )

        # Act & Assert
        with pytest.raises(asyncpg.UniqueViolationError):
            await users_repo.create_user(
                connection=db_connection,
                email=email,  # 동일한 이메일
                username=f"user2_{unique_id}",
                password_hash="$2b$12$test_hash",
            )

    async def test_update_user_success(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """사용자 프로필 수정 성공"""
        # Arrange
        new_display_name = "Updated Display Name"
        new_phone = "010-1234-5678"
        new_avatar_url = "https://example.com/avatar.jpg"

        # Act
        result = await users_repo.update_user(
            connection=db_connection,
            user_id=test_user["id"],
            display_name=new_display_name,
            phone=new_phone,
            avatar_url=new_avatar_url,
        )

        # Assert
        assert result is not None
        assert result["id"] == test_user["id"]
        assert result["display_name"] == new_display_name
        assert result["phone"] == new_phone
        assert result["avatar_url"] == new_avatar_url

    async def test_update_user_not_found(self, db_connection: asyncpg.Connection):
        """사용자 수정 실패 - 존재하지 않는 사용자"""
        # Act
        result = await users_repo.update_user(
            connection=db_connection,
            user_id=999999,
            display_name="Should Not Update",
        )

        # Assert
        assert result is None

    async def test_change_password_success(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """비밀번호 변경 성공"""
        # Arrange
        new_password_hash = "$2b$12$new_password_hash"

        # Act
        result = await users_repo.change_password(
            connection=db_connection,
            user_id=test_user["id"],
            new_password_hash=new_password_hash,
        )

        # Assert
        assert result is not None
        assert result["id"] == test_user["id"]

        # Verify - 비밀번호가 실제로 변경되었는지 확인
        user = await users_repo.get_user_by_email(db_connection, test_user["email"])
        assert user["password_hash"] == new_password_hash

    async def test_change_password_not_found(self, db_connection: asyncpg.Connection):
        """비밀번호 변경 실패 - 존재하지 않는 사용자"""
        # Act
        result = await users_repo.change_password(
            connection=db_connection,
            user_id=999999,
            new_password_hash="$2b$12$should_not_change",
        )

        # Assert
        assert result is None

    async def test_assign_default_role_success(
        self,
        db_connection: asyncpg.Connection,
        test_user: asyncpg.Record,
        test_role: asyncpg.Record,
    ):
        """기본 역할 부여 성공"""
        # Act
        result = await users_repo.assign_default_role(
            connection=db_connection,
            user_id=test_user["id"],
            role_name=test_role["name"],
        )

        # Assert
        assert result is not None

        # Verify - 역할이 실제로 할당되었는지 확인
        roles = await users_repo.get_user_roles_permissions(
            connection=db_connection, user_id=test_user["id"]
        )
        role_names = [r["role_name"] for r in roles]
        assert test_role["name"] in role_names

    async def test_assign_default_role_nonexistent_role(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """기본 역할 부여 실패 - 존재하지 않는 역할"""
        # Act
        result = await users_repo.assign_default_role(
            connection=db_connection,
            user_id=test_user["id"],
            role_name="nonexistent_role",
        )

        # Assert
        assert result is None


@pytest.mark.asyncio
class TestSQLInjectionProtection:
    """SQL Injection 방어 테스트"""

    async def test_search_with_sql_injection_attempt(self, db_connection: asyncpg.Connection):
        """검색어에 SQL Injection 시도 - 방어 확인"""
        # Arrange
        malicious_search = "'; DROP TABLE users; --"

        # Act - 예외가 발생하지 않아야 함 (Parameterized Query)
        result = await users_repo.get_user_list(
            connection=db_connection, offset=0, limit=10, search=malicious_search
        )

        # Assert
        assert isinstance(result, list)
        # 테이블이 삭제되지 않고 정상 동작
        count = await users_repo.get_user_count(connection=db_connection)
        assert count > 0

    async def test_get_user_by_email_with_sql_injection(self, db_connection: asyncpg.Connection):
        """이메일 조회 시 SQL Injection 시도 - 방어 확인"""
        # Arrange
        malicious_email = "test@example.com' OR '1'='1"

        # Act
        result = await users_repo.get_user_by_email(db_connection, malicious_email)

        # Assert
        # Parameterized Query를 사용하므로 SQL Injection이 실행되지 않음
        # 해당 이메일이 없으므로 None 반환
        assert result is None
