"""Authentication Repository Integration Tests

실제 PostgreSQL 데이터베이스를 사용하여 Authentication Repository의 SQL 쿼리를 테스트합니다.
"""

import contextlib
import hashlib
import os
import uuid
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
import pytest_asyncio

from src.domains.authentication import repository as auth_repo
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
        email=f"authtest_{unique_id}@example.com",
        username=f"authtest_{unique_id}",
        password_hash="$2b$12$test_hash",
        display_name=f"Auth Test User {unique_id}",
    )
    return user


@pytest_asyncio.fixture
async def test_refresh_token(
    db_connection: asyncpg.Connection, test_user: asyncpg.Record
) -> tuple[asyncpg.Record, str]:
    """테스트용 리프레시 토큰 생성 fixture.

    Returns:
        (token_record, token_hash) 튜플
    """
    token_hash = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(days=7)

    token_record = await auth_repo.save_refresh_token(
        connection=db_connection,
        user_id=test_user["id"],
        token_hash=token_hash,
        device_info="Test Device",
        expires_at=expires_at,
    )

    return token_record, token_hash


@pytest.mark.asyncio
class TestRefreshToken:
    """리프레시 토큰 관리 테스트"""

    async def test_save_refresh_token_success(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """리프레시 토큰 저장 성공"""
        # Arrange
        token_hash = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
        device_info = "Chrome on Windows 10"
        expires_at = datetime.now(UTC) + timedelta(days=7)

        # Act
        result = await auth_repo.save_refresh_token(
            connection=db_connection,
            user_id=test_user["id"],
            token_hash=token_hash,
            device_info=device_info,
            expires_at=expires_at,
        )

        # Assert
        assert result is not None
        assert result["id"] > 0
        assert "created_at" in result

        # Verify - 토큰이 실제로 저장되었는지 확인
        saved_token = await auth_repo.get_refresh_token(db_connection, token_hash)
        assert saved_token is not None
        assert saved_token["user_id"] == test_user["id"]

    async def test_save_refresh_token_with_null_device_info(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """리프레시 토큰 저장 - device_info NULL"""
        # Arrange
        token_hash = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
        expires_at = datetime.now(UTC) + timedelta(days=7)

        # Act
        result = await auth_repo.save_refresh_token(
            connection=db_connection,
            user_id=test_user["id"],
            token_hash=token_hash,
            device_info=None,
            expires_at=expires_at,
        )

        # Assert
        assert result is not None

    async def test_get_refresh_token_success(
        self,
        db_connection: asyncpg.Connection,
        test_user: asyncpg.Record,
        test_refresh_token: tuple,
    ):
        """리프레시 토큰 조회 성공 (유효한 토큰)"""
        # Arrange
        _token_record, token_hash = test_refresh_token

        # Act
        result = await auth_repo.get_refresh_token(db_connection, token_hash)

        # Assert
        assert result is not None
        assert result["user_id"] == test_user["id"]
        assert result["token_hash"] == token_hash
        assert result["is_revoked"] is False
        assert result["expires_at"] > datetime.now(UTC)

    async def test_get_refresh_token_not_found(self, db_connection: asyncpg.Connection):
        """리프레시 토큰 조회 실패 - 존재하지 않는 토큰"""
        # Arrange
        nonexistent_hash = hashlib.sha256(b"nonexistent").hexdigest()

        # Act
        result = await auth_repo.get_refresh_token(db_connection, nonexistent_hash)

        # Assert
        assert result is None

    async def test_get_refresh_token_revoked(
        self,
        db_connection: asyncpg.Connection,
        test_user: asyncpg.Record,
        test_refresh_token: tuple,
    ):
        """리프레시 토큰 조회 실패 - 폐기된 토큰"""
        # Arrange
        _token_record, token_hash = test_refresh_token
        await auth_repo.revoke_refresh_token(db_connection, token_hash)

        # Act
        result = await auth_repo.get_refresh_token(db_connection, token_hash)

        # Assert
        # 폐기된 토큰은 조회되지 않아야 함 (SQL에서 is_revoked = false 필터)
        assert result is None

    async def test_get_refresh_token_expired(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """리프레시 토큰 조회 실패 - 만료된 토큰"""
        # Arrange - 이미 만료된 토큰 생성
        token_hash = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
        expires_at = datetime.now(UTC) - timedelta(days=1)  # 과거 시간

        await auth_repo.save_refresh_token(
            connection=db_connection,
            user_id=test_user["id"],
            token_hash=token_hash,
            device_info="Expired Token",
            expires_at=expires_at,
        )

        # Act
        result = await auth_repo.get_refresh_token(db_connection, token_hash)

        # Assert
        # 만료된 토큰은 조회되지 않아야 함 (SQL에서 expires_at > NOW() 필터)
        assert result is None

    async def test_revoke_refresh_token_success(
        self,
        db_connection: asyncpg.Connection,
        test_refresh_token: tuple,
    ):
        """리프레시 토큰 폐기 성공"""
        # Arrange
        _token_record, token_hash = test_refresh_token

        # Act
        result = await auth_repo.revoke_refresh_token(db_connection, token_hash)

        # Assert
        assert result is not None
        assert result["is_revoked"] is True
        assert "revoked_at" in result

        # Verify - 폐기된 토큰은 조회되지 않음
        revoked_token = await auth_repo.get_refresh_token(db_connection, token_hash)
        assert revoked_token is None

    async def test_revoke_refresh_token_not_found(self, db_connection: asyncpg.Connection):
        """리프레시 토큰 폐기 실패 - 존재하지 않는 토큰"""
        # Arrange
        nonexistent_hash = hashlib.sha256(b"nonexistent").hexdigest()

        # Act
        result = await auth_repo.revoke_refresh_token(db_connection, nonexistent_hash)

        # Assert
        assert result is None

    async def test_revoke_all_user_tokens_success(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """사용자의 모든 리프레시 토큰 폐기 성공"""
        # Arrange - 여러 토큰 생성
        token_hashes = []
        for i in range(3):
            token_hash = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
            expires_at = datetime.now(UTC) + timedelta(days=7)
            await auth_repo.save_refresh_token(
                connection=db_connection,
                user_id=test_user["id"],
                token_hash=token_hash,
                device_info=f"Device {i}",
                expires_at=expires_at,
            )
            token_hashes.append(token_hash)

        # Act
        result = await auth_repo.revoke_all_user_tokens(
            connection=db_connection, user_id=test_user["id"]
        )

        # Assert
        assert len(result) == 3
        for token in result:
            assert token["is_revoked"] is True

        # Verify - 모든 토큰이 폐기되었는지 확인
        for token_hash in token_hashes:
            revoked_token = await auth_repo.get_refresh_token(db_connection, token_hash)
            assert revoked_token is None

    async def test_revoke_all_user_tokens_no_tokens(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """사용자의 모든 리프레시 토큰 폐기 - 토큰 없음"""
        # Act
        result = await auth_repo.revoke_all_user_tokens(
            connection=db_connection, user_id=test_user["id"]
        )

        # Assert
        assert result == []

    async def test_get_active_sessions(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """활성 세션 목록 조회"""
        # Arrange - 여러 활성 토큰 생성
        for i in range(3):
            token_hash = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
            expires_at = datetime.now(UTC) + timedelta(days=7)
            await auth_repo.save_refresh_token(
                connection=db_connection,
                user_id=test_user["id"],
                token_hash=token_hash,
                device_info=f"Device {i}",
                expires_at=expires_at,
            )

        # Act
        result = await auth_repo.get_active_sessions(
            connection=db_connection, user_id=test_user["id"]
        )

        # Assert
        assert len(result) >= 3
        for session in result:
            assert session["is_revoked"] is False
            assert session["expires_at"] > datetime.now(UTC)


@pytest.mark.asyncio
class TestLoginHistory:
    """로그인 이력 관리 테스트"""

    async def test_save_login_history_success(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """로그인 이력 저장 성공 (성공)"""
        # Arrange
        ip_address = "192.168.1.1"
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

        # Act
        result = await auth_repo.save_login_history(
            connection=db_connection,
            user_id=test_user["id"],
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
        )

        # Assert
        assert result is not None
        assert result["id"] > 0
        # SQL RETURNING만 id를 반환하므로, 다시 조회하여 확인
        saved_history = await db_connection.fetchrow(
            "SELECT * FROM login_histories WHERE id = $1", result["id"]
        )
        assert saved_history["user_id"] == test_user["id"]
        assert saved_history["ip_address"] == ip_address
        assert saved_history["user_agent"] == user_agent
        assert saved_history["success"] is True

    async def test_save_login_history_failure(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """로그인 이력 저장 성공 (실패)"""
        # Arrange
        ip_address = "192.168.1.2"
        user_agent = "Mozilla/5.0"

        # Act
        result = await auth_repo.save_login_history(
            connection=db_connection,
            user_id=test_user["id"],
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
        )

        # Assert
        assert result is not None
        assert result["success"] is False

    async def test_save_login_history_with_null_fields(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """로그인 이력 저장 - NULL 필드 (ip_address, user_agent)"""
        # Act
        result = await auth_repo.save_login_history(
            connection=db_connection,
            user_id=test_user["id"],
            ip_address=None,
            user_agent=None,
            success=True,
        )

        # Assert
        assert result is not None
        assert result["ip_address"] is None
        assert result["user_agent"] is None

    async def test_save_multiple_login_histories(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """여러 로그인 이력 저장"""
        # Arrange & Act
        histories = []
        for i in range(5):
            history = await auth_repo.save_login_history(
                connection=db_connection,
                user_id=test_user["id"],
                ip_address=f"192.168.1.{i}",
                user_agent=f"Browser {i}",
                success=i % 2 == 0,  # 짝수는 성공, 홀수는 실패
            )
            histories.append(history)

        # Assert
        assert len(histories) == 5
        # 성공 횟수 확인
        success_count = sum(1 for h in histories if h["success"])
        assert success_count == 3  # 0, 2, 4


@pytest.mark.asyncio
class TestLastLogin:
    """마지막 로그인 시각 업데이트 테스트"""

    async def test_update_last_login_success(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """마지막 로그인 시각 업데이트 성공"""
        # Arrange
        before_update = datetime.now(UTC)

        # Act
        result = await auth_repo.update_last_login(
            connection=db_connection, user_id=test_user["id"]
        )

        # Assert
        assert result is not None
        assert result["id"] == test_user["id"]
        assert "last_login_at" in result
        assert result["last_login_at"] is not None
        # last_login_at이 현재 시간과 비슷해야 함
        assert result["last_login_at"] >= before_update

    async def test_update_last_login_not_found(self, db_connection: asyncpg.Connection):
        """마지막 로그인 시각 업데이트 실패 - 존재하지 않는 사용자"""
        # Act
        result = await auth_repo.update_last_login(connection=db_connection, user_id=999999)

        # Assert
        assert result is None

    async def test_update_last_login_multiple_times(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """마지막 로그인 시각 여러 번 업데이트"""
        # Act
        first_update = await auth_repo.update_last_login(
            connection=db_connection, user_id=test_user["id"]
        )

        # 약간의 시간 경과
        import asyncio

        await asyncio.sleep(0.1)

        second_update = await auth_repo.update_last_login(
            connection=db_connection, user_id=test_user["id"]
        )

        # Assert
        assert first_update is not None
        assert second_update is not None
        # 두 번째 업데이트가 첫 번째보다 나중 시간이어야 함
        assert second_update["last_login_at"] >= first_update["last_login_at"]


@pytest.mark.asyncio
class TestEdgeCases:
    """엣지 케이스 테스트"""

    async def test_concurrent_token_operations(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """동시 토큰 작업 테스트"""
        # Arrange
        token_hashes = [hashlib.sha256(uuid.uuid4().bytes).hexdigest() for _ in range(5)]
        expires_at = datetime.now(UTC) + timedelta(days=7)

        # Act - 동시에 여러 토큰 저장
        import asyncio

        tasks = [
            auth_repo.save_refresh_token(
                connection=db_connection,
                user_id=test_user["id"],
                token_hash=token_hash,
                device_info=f"Device {i}",
                expires_at=expires_at,
            )
            for i, token_hash in enumerate(token_hashes)
        ]

        results = await asyncio.gather(*tasks)

        # Assert
        assert len(results) == 5
        # 모든 토큰이 저장되었는지 확인
        for token_hash in token_hashes:
            saved_token = await auth_repo.get_refresh_token(db_connection, token_hash)
            assert saved_token is not None

    async def test_revoke_already_revoked_token(
        self,
        db_connection: asyncpg.Connection,
        test_refresh_token: tuple,
    ):
        """이미 폐기된 토큰을 다시 폐기"""
        # Arrange
        _token_record, token_hash = test_refresh_token
        await auth_repo.revoke_refresh_token(db_connection, token_hash)

        # Act - 다시 폐기 시도
        result = await auth_repo.revoke_refresh_token(db_connection, token_hash)

        # Assert
        # 이미 폐기된 토큰은 UPDATE가 영향을 주지 않으므로 None 반환
        assert result is None

    async def test_save_login_history_for_nonexistent_user(self, db_connection: asyncpg.Connection):
        """존재하지 않는 사용자의 로그인 이력 저장 (Foreign Key 제약)"""
        # Act & Assert
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await auth_repo.save_login_history(
                connection=db_connection,
                user_id=999999,  # 존재하지 않는 사용자
                ip_address="192.168.1.1",
                user_agent="Test",
                success=True,
            )

    async def test_token_hash_uniqueness(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """토큰 해시 유일성 제약 테스트"""
        # Arrange
        token_hash = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
        expires_at = datetime.now(UTC) + timedelta(days=7)

        await auth_repo.save_refresh_token(
            connection=db_connection,
            user_id=test_user["id"],
            token_hash=token_hash,
            device_info="Device 1",
            expires_at=expires_at,
        )

        # Act & Assert - 동일한 token_hash로 저장 시도
        with pytest.raises(asyncpg.UniqueViolationError):
            await auth_repo.save_refresh_token(
                connection=db_connection,
                user_id=test_user["id"],
                token_hash=token_hash,  # 동일한 해시
                device_info="Device 2",
                expires_at=expires_at,
            )

    async def test_login_history_ordering(
        self, db_connection: asyncpg.Connection, test_user: asyncpg.Record
    ):
        """로그인 이력이 시간순으로 저장되는지 확인"""
        # Arrange & Act
        import asyncio

        for i in range(3):
            await auth_repo.save_login_history(
                connection=db_connection,
                user_id=test_user["id"],
                ip_address=f"192.168.1.{i}",
                user_agent=f"Browser {i}",
                success=True,
            )
            await asyncio.sleep(0.05)  # 약간의 시간 차이

        # Verify - 이력 조회 (실제 SQL 파일에 get_login_history가 있다면)
        # 여기서는 직접 쿼리로 확인
        histories = await db_connection.fetch(
            "SELECT * FROM login_histories WHERE user_id = $1 ORDER BY attempted_at DESC LIMIT 3",
            test_user["id"],
        )

        # Assert
        assert len(histories) >= 3
        # 최신 이력이 먼저 오는지 확인
        for i in range(len(histories) - 1):
            assert histories[i]["attempted_at"] >= histories[i + 1]["attempted_at"]
