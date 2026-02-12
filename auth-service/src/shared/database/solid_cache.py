"""Solid Cache implementation using Aurora PostgreSQL.

Solid Cache는 37signals가 만든 데이터베이스 기반 캐시 스토어입니다.
Redis의 단순 key-value 캐싱을 PostgreSQL로 대체하여 인프라를 단순화합니다.

주요 특징:
- PostgreSQL 기반 key-value 저장소
- TTL 자동 만료 (cleanup job 필요)
- 쿼리 결과 캐싱, 정적 데이터 캐싱에 최적화
- Redis의 Set, Counter 등 복잡한 연산은 지원하지 않음

권장 사용 케이스:
✅ 쿼리 결과 캐싱 (덜 자주 변경)
✅ 정적 설정 데이터
✅ 사용자 프로필 캐시 (선택사항)

비권장 사용 케이스:
❌ Rate limiting (INCR 필요)
❌ Active token registry (Set 필요)
❌ Real-time counters
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg


class SolidCache:
    """Aurora PostgreSQL 기반 캐시 스토어 (Solid Cache 패턴)."""

    def __init__(self, connection_pool: asyncpg.Pool) -> None:
        """
        Solid Cache 인스턴스를 초기화한다.

        Args:
            connection_pool: asyncpg connection pool
        """
        self.pool = connection_pool

    async def get(self, key: str) -> str | None:
        """
        캐시에서 값을 조회한다.

        Args:
            key: 캐시 키

        Returns:
            캐시된 값 (문자열) 또는 None (캐시 미스 또는 만료)
        """
        query = """
            SELECT value
            FROM solid_cache_entries
            WHERE key = $1 AND expires_at > NOW()
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, key)
            return row["value"] if row else None

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """
        캐시에 값을 저장한다.

        Args:
            key: 캐시 키
            value: 저장할 값 (문자열)
            ttl_seconds: TTL (초 단위)
        """
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        query = """
            INSERT INTO solid_cache_entries (key, value, expires_at)
            VALUES ($1, $2, $3)
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value,
                expires_at = EXCLUDED.expires_at
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, key, value, expires_at)

    async def get_json(self, key: str) -> dict | list | None:
        """
        JSON으로 저장된 캐시 값을 조회한다.

        Args:
            key: 캐시 키

        Returns:
            JSON 파싱된 값 또는 None
        """
        value = await self.get(key)
        if value:
            return json.loads(value)
        return None

    async def set_json(self, key: str, value: dict | list, ttl_seconds: int) -> None:
        """
        JSON 데이터를 캐시에 저장한다.

        Args:
            key: 캐시 키
            value: JSON 직렬화 가능한 값 (dict, list)
            ttl_seconds: TTL (초 단위)
        """
        await self.set(key, json.dumps(value), ttl_seconds)

    async def delete(self, key: str) -> None:
        """
        캐시에서 값을 삭제한다.

        Args:
            key: 캐시 키
        """
        query = "DELETE FROM solid_cache_entries WHERE key = $1"
        async with self.pool.acquire() as conn:
            await conn.execute(query, key)

    async def delete_pattern(self, pattern: str) -> int:
        """
        패턴에 매칭되는 모든 캐시 키를 삭제한다.

        Args:
            pattern: SQL LIKE 패턴 (예: 'permissions:user:%')

        Returns:
            삭제된 행 수
        """
        query = "DELETE FROM solid_cache_entries WHERE key LIKE $1"
        async with self.pool.acquire() as conn:
            result = await conn.execute(query, pattern)
            # DELETE 결과는 "DELETE N" 형식
            return int(result.split()[-1]) if result else 0

    async def exists(self, key: str) -> bool:
        """
        캐시 키가 존재하는지 확인한다 (만료되지 않은 값).

        Args:
            key: 캐시 키

        Returns:
            True if exists and not expired, False otherwise
        """
        query = """
            SELECT EXISTS(
                SELECT 1 FROM solid_cache_entries
                WHERE key = $1 AND expires_at > NOW()
            )
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, key)

    async def ttl(self, key: str) -> int:
        """
        캐시 키의 남은 TTL을 조회한다.

        Args:
            key: 캐시 키

        Returns:
            남은 시간 (초 단위), 없거나 만료되면 -1
        """
        query = """
            SELECT EXTRACT(EPOCH FROM (expires_at - NOW()))::INTEGER
            FROM solid_cache_entries
            WHERE key = $1 AND expires_at > NOW()
        """
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(query, key)
            return result if result is not None else -1

    async def cleanup_expired(self) -> int:
        """
        만료된 캐시 엔트리를 삭제한다.

        이 메서드는 수동 호출용이며, 일반적으로는 PostgreSQL의
        cleanup_expired_cache() 함수가 주기적으로 실행됩니다.

        Returns:
            삭제된 행 수
        """
        query = "DELETE FROM solid_cache_entries WHERE expires_at < NOW()"
        async with self.pool.acquire() as conn:
            result = await conn.execute(query)
            return int(result.split()[-1]) if result else 0

    async def get_stats(self) -> dict[str, Any]:
        """
        캐시 통계를 조회한다.

        Returns:
            캐시 통계 딕셔너리 (total_entries, expired_entries, total_size_bytes)
        """
        query = """
            SELECT
                COUNT(*) as total_entries,
                COUNT(*) FILTER (WHERE expires_at < NOW()) as expired_entries,
                pg_total_relation_size('solid_cache_entries') as total_size_bytes
            FROM solid_cache_entries
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query)
            return {
                "total_entries": row["total_entries"] if row else 0,
                "expired_entries": row["expired_entries"] if row else 0,
                "total_size_bytes": row["total_size_bytes"] if row else 0,
            }


# 싱글톤 인스턴스는 의존성 주입으로 생성
# 사용 예:
# from src.shared.database.connection import db_pool
# solid_cache = SolidCache(db_pool._primary_pool)
