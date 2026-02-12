"""pytest fixtures."""

import contextlib
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import fakeredis.aioredis
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient

# Load test environment variables before importing app
load_dotenv(".env.test", override=True)

from src.main import app
from src.shared.security.config import SecuritySettings


@pytest_asyncio.fixture(scope="function")
async def setup_app_dependencies(request) -> AsyncGenerator[None, None]:
    """Initialize app dependencies (DB, Redis) for integration tests.

    This fixture is used by API and middleware integration tests that need
    the full app stack. Repository tests use their own DB connections.

    For pytest-asyncio 0.23+, this ensures each test gets fresh connections
    and properly cleans up resources.
    """
    # Skip for repository tests - they manage their own connections
    if "repository" in request.node.nodeid:
        yield
        return

    from src.shared.database import db_pool
    from src.shared.security import redis_store

    # Force re-initialization to ensure new event loop compatibility
    # Close existing connections if any
    if redis_store._client:
        with contextlib.suppress(Exception):
            await redis_store.close()

    if db_pool._primary_pool:
        with contextlib.suppress(Exception):
            await db_pool.close()

    # Initialize with current event loop
    await redis_store.initialize()
    await db_pool.initialize()

    # Cleanup BEFORE test - flush Redis for complete test isolation
    # This is critical for rate limiter tests
    if redis_store._client:
        try:
            await redis_store.client.flushdb()
        except Exception:
            # Ignore cleanup errors
            pass

    yield

    # Cleanup AFTER test - ensure clean state for next test
    if redis_store._client:
        with contextlib.suppress(Exception):
            await redis_store.client.flushdb()

    # Close connections to release resources
    try:
        if redis_store._client:
            await redis_store.close()
    except Exception:
        pass

    try:
        if db_pool._primary_pool:
            await db_pool.close()
    except Exception:
        pass


@pytest_asyncio.fixture(scope="function")
async def client(setup_app_dependencies) -> AsyncGenerator[AsyncClient, None]:
    """Test HTTP client with function scope.

    Each test gets a fresh client to ensure test isolation.
    Depends on setup_app_dependencies to ensure proper initialization.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=30.0,  # Increase timeout for integration tests
    ) as ac:
        yield ac


@pytest.fixture
def mock_repository() -> MagicMock:
    """Mock repository for unit tests."""
    return MagicMock()


@pytest.fixture
def mock_db_connection() -> AsyncMock:
    """Mock asyncpg connection for unit tests."""
    mock_conn = AsyncMock(spec=asyncpg.Connection)
    # 트랜잭션 컨텍스트 매니저 mock
    mock_transaction = AsyncMock()
    mock_transaction.__aenter__ = AsyncMock()
    mock_transaction.__aexit__ = AsyncMock()
    mock_conn.transaction.return_value = mock_transaction
    return mock_conn


@pytest.fixture
def test_user_data() -> dict[str, Any]:
    """Test user data."""
    return {
        "email": "test@example.com",
        "password": "Test1234!",
        "username": "testuser",
        "display_name": "Test User",
    }


@pytest.fixture
def sample_data() -> dict[str, Any]:
    """Sample test data."""
    return {
        "id": 1,
        "name": "Test Item",
        "created_at": "2024-01-01T00:00:00Z",
    }


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, test_user_data: dict[str, Any]) -> dict[str, str]:
    """인증 헤더 (회원가입 → 로그인 → Bearer 토큰).

    실제 회원가입 + 로그인을 수행하여 실제 토큰을 반환합니다.
    통합 테스트에서 사용됩니다.
    """
    # 회원가입
    await client.post(
        "/api/v1/users/register",
        json={
            "email": test_user_data["email"],
            "password": test_user_data["password"],
            "username": test_user_data["username"],
            "display_name": test_user_data["display_name"],
        },
    )

    # 로그인
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user_data["email"],
            "password": test_user_data["password"],
        },
    )

    data = response.json()
    access_token = data["data"]["access_token"]

    return {"Authorization": f"Bearer {access_token}"}


# ===== Security Module Fixtures =====


@pytest.fixture
def mock_jwt_settings() -> SecuritySettings:
    """Mock JWT settings for testing."""
    return SecuritySettings(
        env="development",
        jwt_algorithm="HS256",
        jwt_secret_key="test-secret-key-for-unit-tests",
        jwt_access_token_expire_minutes=30,
        jwt_refresh_token_expire_days=7,
        jwt_issuer="test-auth-service",
        redis_url="redis://localhost:6380/0",
        password_min_length=8,
        password_max_failed_attempts=5,
        password_lockout_minutes=30,
    )


@pytest.fixture
def valid_jwt_payload() -> dict[str, Any]:
    """Valid JWT payload for testing."""
    now = datetime.now(UTC)
    return {
        "sub": "1",
        "email": "test@example.com",
        "roles": ["user"],
        "permissions": ["users:read"],
        "type": "access",
        "iss": "test-auth-service",
        "iat": now,
        "exp": now + timedelta(minutes=30),
        "jti": "test-jti-12345",
    }


@pytest.fixture
def expired_jwt_payload() -> dict[str, Any]:
    """Expired JWT payload for testing."""
    now = datetime.now(UTC)
    return {
        "sub": "1",
        "email": "test@example.com",
        "type": "access",
        "iss": "test-auth-service",
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
        "jti": "expired-jti-12345",
    }


@pytest_asyncio.fixture
async def fake_redis() -> fakeredis.aioredis.FakeRedis:
    """Fake Redis instance for testing."""
    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield redis_client
    await redis_client.flushall()
    await redis_client.aclose()


@pytest.fixture
def mock_password_settings() -> SecuritySettings:
    """Mock password settings for testing."""
    return SecuritySettings(
        env="development",
        jwt_algorithm="HS256",
        jwt_secret_key="test-secret",
        jwt_issuer="test",
        redis_url="redis://localhost:6380/0",
        password_min_length=8,
        password_max_failed_attempts=5,
        password_lockout_minutes=30,
    )
