"""Database connection management."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

import asyncpg
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database connection settings."""

    primary_db_url: str = ""
    replica_db_url: str | None = None

    # Connection Pool 설정
    env: Literal["development", "production", "test"] = "development"
    pool_min_size: int = 5
    pool_max_size: int = 20
    pool_command_timeout: int = 60
    pool_max_queries: int = 50000
    pool_max_inactive_connection_lifetime: float = 300.0

    model_config = SettingsConfigDict(
        env_prefix="DB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_db_url(self) -> "DatabaseSettings":
        if not self.primary_db_url:
            raise ValueError(
                "DB_PRIMARY_DB_URL 환경변수가 설정되지 않았습니다. "
                ".env 파일 또는 환경변수를 확인하세요."
            )
        return self

    def get_pool_config(self) -> dict:
        """환경별 Connection Pool 설정을 반환한다.

        Returns:
            Connection Pool 설정 딕셔너리
        """
        # 환경별 기본 설정
        if self.env == "production":
            # Phase 2: Connection Pool 확대 (50 → 100)
            base_config = {
                "min_size": 20,
                "max_size": 100,  # Phase 2: 50 → 100으로 증가
                "command_timeout": 60,
                "max_queries": 50000,
                "max_inactive_connection_lifetime": 300.0,
            }
        elif self.env == "test":
            base_config = {
                "min_size": 2,
                "max_size": 10,  # Phase 2: 5 → 10으로 증가 (테스트 안정성)
                "command_timeout": 30,
                "max_queries": 10000,
                "max_inactive_connection_lifetime": 60.0,
            }
        else:  # development
            # Phase 2: Development도 증가 (20 → 50)
            base_config = {
                "min_size": 10,
                "max_size": 50,  # Phase 2: 20 → 50으로 증가
                "command_timeout": 60,
                "max_queries": 50000,
                "max_inactive_connection_lifetime": 300.0,
            }

        # 환경 변수로 오버라이드 가능
        if self.pool_min_size != 5:  # 기본값이 아니면 오버라이드
            base_config["min_size"] = self.pool_min_size
        if self.pool_max_size != 20:
            base_config["max_size"] = self.pool_max_size
        if self.pool_command_timeout != 60:
            base_config["command_timeout"] = self.pool_command_timeout
        if self.pool_max_queries != 50000:
            base_config["max_queries"] = self.pool_max_queries
        if self.pool_max_inactive_connection_lifetime != 300.0:
            base_config["max_inactive_connection_lifetime"] = (
                self.pool_max_inactive_connection_lifetime
            )

        return base_config


class DatabasePool:
    """Manages database connection pools."""

    def __init__(self) -> None:
        self._primary_pool: asyncpg.Pool | None = None
        self._replica_pool: asyncpg.Pool | None = None
        self._settings = DatabaseSettings()

    async def _init_connection(self, connection: asyncpg.Connection) -> None:
        """연결 초기화 콜백.

        각 새 연결에 대해 타임존 및 기타 설정을 초기화한다.

        Args:
            connection: 초기화할 데이터베이스 연결
        """
        await connection.execute("SET timezone TO 'UTC'")

    async def initialize(self) -> None:
        """Initialize database connection pools with optimized settings."""
        pool_config = self._settings.get_pool_config()

        self._primary_pool = await asyncpg.create_pool(
            self._settings.primary_db_url,
            init=self._init_connection,
            **pool_config,
        )

        if self._settings.replica_db_url:
            self._replica_pool = await asyncpg.create_pool(
                self._settings.replica_db_url,
                init=self._init_connection,
                **pool_config,
            )

    async def close(self) -> None:
        """Close all database connection pools."""
        if self._primary_pool:
            await self._primary_pool.close()
        if self._replica_pool:
            await self._replica_pool.close()

    def get_pool_stats(self) -> dict:
        """Connection Pool 통계를 반환한다.

        Returns:
            Pool 통계 딕셔너리 (size, free, used 등)
        """
        stats = {}

        if self._primary_pool:
            stats["primary"] = {
                "size": self._primary_pool.get_size(),
                "free": self._primary_pool.get_idle_size(),
                "used": self._primary_pool.get_size() - self._primary_pool.get_idle_size(),
                "min_size": self._primary_pool.get_min_size(),
                "max_size": self._primary_pool.get_max_size(),
            }

        if self._replica_pool:
            stats["replica"] = {
                "size": self._replica_pool.get_size(),
                "free": self._replica_pool.get_idle_size(),
                "used": self._replica_pool.get_size() - self._replica_pool.get_idle_size(),
                "min_size": self._replica_pool.get_min_size(),
                "max_size": self._replica_pool.get_max_size(),
            }

        return stats

    async def health_check(self) -> dict:
        """Connection Pool Health Check를 수행한다.

        Returns:
            Health check 결과 딕셔너리 (healthy, pools)
        """
        result = {
            "healthy": True,
            "pools": {},
        }

        # Primary Pool 체크
        if self._primary_pool:
            try:
                async with self._primary_pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                result["pools"]["primary"] = {
                    "status": "healthy",
                    "size": self._primary_pool.get_size(),
                    "free": self._primary_pool.get_idle_size(),
                }
            except Exception as e:
                result["healthy"] = False
                result["pools"]["primary"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }

        # Replica Pool 체크
        if self._replica_pool:
            try:
                async with self._replica_pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                result["pools"]["replica"] = {
                    "status": "healthy",
                    "size": self._replica_pool.get_size(),
                    "free": self._replica_pool.get_idle_size(),
                }
            except Exception as e:
                result["healthy"] = False
                result["pools"]["replica"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }

        return result

    @asynccontextmanager
    async def acquire_primary(self) -> AsyncIterator[asyncpg.Connection]:
        """Acquire a connection from the primary pool."""
        if not self._primary_pool:
            raise RuntimeError("Database pool not initialized")
        async with self._primary_pool.acquire() as connection:
            yield connection

    @asynccontextmanager
    async def acquire_replica(self) -> AsyncIterator[asyncpg.Connection]:
        """Acquire a connection from the replica pool."""
        pool = self._replica_pool or self._primary_pool
        if not pool:
            raise RuntimeError("Database pool not initialized")
        async with pool.acquire() as connection:
            yield connection


db_pool = DatabasePool()


async def get_db_connection() -> AsyncIterator[asyncpg.Connection]:
    """FastAPI dependency for database connection."""
    async with db_pool.acquire_primary() as connection:
        yield connection


async def get_readonly_connection() -> AsyncIterator[asyncpg.Connection]:
    """FastAPI dependency for read-only database connection."""
    async with db_pool.acquire_replica() as connection:
        yield connection
