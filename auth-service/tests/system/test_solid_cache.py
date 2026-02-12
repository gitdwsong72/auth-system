"""Solid Cache System Tests.

이 테스트는 Solid Cache의 모든 기능을 검증합니다:
- set/get 기본 동작
- set_json/get_json JSON 처리
- TTL 동작 (만료 확인)
- delete 동작
- delete_pattern 패턴 매칭 삭제
- cleanup_expired 만료된 엔트리 정리
- get_stats 통계 조회
"""

import asyncio
from datetime import datetime, timedelta

import asyncpg
import pytest
import pytest_asyncio

from src.shared.database.solid_cache import SolidCache


@pytest_asyncio.fixture
async def db_pool() -> asyncpg.Pool:
    """Test database connection pool."""
    import os

    database_url = os.getenv(
        "DB_PRIMARY_DB_URL",
        "postgresql://devuser:devpassword@localhost:5432/appdb?sslmode=disable",
    )
    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
    yield pool
    await pool.close()


@pytest_asyncio.fixture
async def solid_cache(db_pool: asyncpg.Pool) -> SolidCache:
    """SolidCache instance for testing."""
    cache = SolidCache(db_pool)

    # 테스트 전 캐시 테이블 초기화
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM solid_cache_entries")

    yield cache

    # 테스트 후 정리
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM solid_cache_entries")


class TestSolidCacheBasicOperations:
    """Solid Cache 기본 동작 테스트."""

    @pytest.mark.asyncio
    async def test_set_and_get(self, solid_cache: SolidCache) -> None:
        """set/get 기본 동작 테스트."""
        # Arrange
        key = "test:key:1"
        value = "test_value"
        ttl = 3600  # 1 hour

        # Act
        await solid_cache.set(key, value, ttl)
        result = await solid_cache.get(key)

        # Assert
        assert result == value, "저장된 값과 조회된 값이 일치해야 함"

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self, solid_cache: SolidCache) -> None:
        """존재하지 않는 키 조회 시 None 반환."""
        # Arrange
        key = "nonexistent:key"

        # Act
        result = await solid_cache.get(key)

        # Assert
        assert result is None, "존재하지 않는 키는 None을 반환해야 함"

    @pytest.mark.asyncio
    async def test_set_overwrites_existing_key(self, solid_cache: SolidCache) -> None:
        """동일 키로 set 호출 시 값 덮어쓰기."""
        # Arrange
        key = "test:overwrite"
        original_value = "original"
        new_value = "updated"
        ttl = 3600

        # Act
        await solid_cache.set(key, original_value, ttl)
        await solid_cache.set(key, new_value, ttl)
        result = await solid_cache.get(key)

        # Assert
        assert result == new_value, "새 값으로 덮어써야 함"

    @pytest.mark.asyncio
    async def test_exists(self, solid_cache: SolidCache) -> None:
        """exists 메서드 테스트."""
        # Arrange
        key = "test:exists"
        value = "test"
        ttl = 3600

        # Act & Assert - 저장 전
        assert not await solid_cache.exists(key), "저장 전에는 존재하지 않아야 함"

        # Act & Assert - 저장 후
        await solid_cache.set(key, value, ttl)
        assert await solid_cache.exists(key), "저장 후에는 존재해야 함"


class TestSolidCacheJSONOperations:
    """Solid Cache JSON 처리 테스트."""

    @pytest.mark.asyncio
    async def test_set_json_and_get_json_dict(self, solid_cache: SolidCache) -> None:
        """set_json/get_json으로 딕셔너리 저장 및 조회."""
        # Arrange
        key = "test:json:dict"
        value = {"user_id": 123, "name": "John", "roles": ["admin", "user"]}
        ttl = 3600

        # Act
        await solid_cache.set_json(key, value, ttl)
        result = await solid_cache.get_json(key)

        # Assert
        assert result == value, "저장된 JSON과 조회된 JSON이 일치해야 함"
        assert isinstance(result, dict), "결과는 dict 타입이어야 함"

    @pytest.mark.asyncio
    async def test_set_json_and_get_json_list(self, solid_cache: SolidCache) -> None:
        """set_json/get_json으로 리스트 저장 및 조회."""
        # Arrange
        key = "test:json:list"
        value = [1, 2, 3, "test", {"nested": True}]
        ttl = 3600

        # Act
        await solid_cache.set_json(key, value, ttl)
        result = await solid_cache.get_json(key)

        # Assert
        assert result == value, "저장된 JSON 리스트와 조회된 리스트가 일치해야 함"
        assert isinstance(result, list), "결과는 list 타입이어야 함"

    @pytest.mark.asyncio
    async def test_get_json_nonexistent_key(self, solid_cache: SolidCache) -> None:
        """존재하지 않는 키 조회 시 None 반환."""
        # Arrange
        key = "nonexistent:json:key"

        # Act
        result = await solid_cache.get_json(key)

        # Assert
        assert result is None, "존재하지 않는 키는 None을 반환해야 함"


class TestSolidCacheTTL:
    """Solid Cache TTL 동작 테스트."""

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, solid_cache: SolidCache) -> None:
        """TTL 만료 후 값이 조회되지 않음."""
        # Arrange
        key = "test:ttl:expire"
        value = "temporary_value"
        ttl = 2  # 2 seconds

        # Act
        await solid_cache.set(key, value, ttl)

        # Assert - 만료 전
        result_before = await solid_cache.get(key)
        assert result_before == value, "만료 전에는 값이 조회되어야 함"

        # Wait for expiration
        await asyncio.sleep(3)

        # Assert - 만료 후
        result_after = await solid_cache.get(key)
        assert result_after is None, "만료 후에는 None이 반환되어야 함"

    @pytest.mark.asyncio
    async def test_ttl_remaining_time(self, solid_cache: SolidCache) -> None:
        """ttl() 메서드로 남은 시간 확인."""
        # Arrange
        key = "test:ttl:remaining"
        value = "test"
        ttl = 10  # 10 seconds

        # Act
        await solid_cache.set(key, value, ttl)
        remaining_ttl = await solid_cache.ttl(key)

        # Assert
        assert remaining_ttl > 0, "남은 TTL이 0보다 커야 함"
        assert remaining_ttl <= ttl, f"남은 TTL이 설정 값({ttl})을 초과하면 안 됨"

    @pytest.mark.asyncio
    async def test_ttl_nonexistent_key(self, solid_cache: SolidCache) -> None:
        """존재하지 않는 키의 TTL은 -1."""
        # Arrange
        key = "nonexistent:ttl:key"

        # Act
        result = await solid_cache.ttl(key)

        # Assert
        assert result == -1, "존재하지 않는 키의 TTL은 -1이어야 함"

    @pytest.mark.asyncio
    async def test_exists_after_expiration(self, solid_cache: SolidCache) -> None:
        """만료 후 exists는 False 반환."""
        # Arrange
        key = "test:exists:expire"
        value = "test"
        ttl = 1  # 1 second

        # Act
        await solid_cache.set(key, value, ttl)
        await asyncio.sleep(2)

        # Assert
        assert not await solid_cache.exists(key), "만료 후 exists는 False여야 함"


class TestSolidCacheDelete:
    """Solid Cache 삭제 동작 테스트."""

    @pytest.mark.asyncio
    async def test_delete_existing_key(self, solid_cache: SolidCache) -> None:
        """delete로 키 삭제."""
        # Arrange
        key = "test:delete:1"
        value = "test_value"
        ttl = 3600

        # Act
        await solid_cache.set(key, value, ttl)
        await solid_cache.delete(key)
        result = await solid_cache.get(key)

        # Assert
        assert result is None, "삭제 후 조회 시 None이 반환되어야 함"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key(self, solid_cache: SolidCache) -> None:
        """존재하지 않는 키 삭제 시 오류 없음."""
        # Arrange
        key = "nonexistent:delete:key"

        # Act & Assert - 예외 발생하지 않아야 함
        await solid_cache.delete(key)

    @pytest.mark.asyncio
    async def test_delete_pattern_single_match(self, solid_cache: SolidCache) -> None:
        """delete_pattern으로 패턴 매칭 삭제 (단일 매칭)."""
        # Arrange
        key = "permissions:user:123"
        value = "test"
        ttl = 3600
        pattern = "permissions:user:%"

        # Act
        await solid_cache.set(key, value, ttl)
        deleted_count = await solid_cache.delete_pattern(pattern)
        result = await solid_cache.get(key)

        # Assert
        assert deleted_count == 1, "1개 항목이 삭제되어야 함"
        assert result is None, "삭제된 키는 조회되지 않아야 함"

    @pytest.mark.asyncio
    async def test_delete_pattern_multiple_matches(
        self, solid_cache: SolidCache
    ) -> None:
        """delete_pattern으로 여러 키 동시 삭제."""
        # Arrange
        keys = [
            "permissions:user:1",
            "permissions:user:2",
            "permissions:user:3",
            "permissions:role:1",  # 이 키는 삭제되지 않아야 함
        ]
        ttl = 3600
        pattern = "permissions:user:%"

        for key in keys:
            await solid_cache.set(key, "test", ttl)

        # Act
        deleted_count = await solid_cache.delete_pattern(pattern)

        # Assert
        assert deleted_count == 3, "3개의 user 키만 삭제되어야 함"

        # 삭제된 키 확인
        for key in keys[:3]:
            assert await solid_cache.get(key) is None, f"{key}는 삭제되어야 함"

        # 삭제되지 않은 키 확인
        assert (
            await solid_cache.get(keys[3]) == "test"
        ), "permissions:role:1은 삭제되지 않아야 함"

    @pytest.mark.asyncio
    async def test_delete_pattern_no_matches(self, solid_cache: SolidCache) -> None:
        """delete_pattern에 매칭되는 키가 없을 때."""
        # Arrange
        pattern = "nonexistent:pattern:%"

        # Act
        deleted_count = await solid_cache.delete_pattern(pattern)

        # Assert
        assert deleted_count == 0, "매칭되는 키가 없으면 0을 반환해야 함"


class TestSolidCacheCleanup:
    """Solid Cache 정리 동작 테스트."""

    @pytest.mark.asyncio
    async def test_cleanup_expired_entries(self, solid_cache: SolidCache) -> None:
        """cleanup_expired로 만료된 엔트리 정리."""
        # Arrange
        expired_keys = [
            "test:cleanup:expired:1",
            "test:cleanup:expired:2",
        ]
        valid_key = "test:cleanup:valid"

        # 만료된 키 (1초 TTL)
        for key in expired_keys:
            await solid_cache.set(key, "expired", 1)

        # 유효한 키 (1시간 TTL)
        await solid_cache.set(valid_key, "valid", 3600)

        # 만료 대기
        await asyncio.sleep(2)

        # Act
        cleaned_count = await solid_cache.cleanup_expired()

        # Assert
        assert cleaned_count == 2, "2개의 만료된 엔트리가 정리되어야 함"

        # 유효한 키는 여전히 존재
        assert await solid_cache.get(valid_key) == "valid", "유효한 키는 유지되어야 함"

    @pytest.mark.asyncio
    async def test_cleanup_no_expired_entries(self, solid_cache: SolidCache) -> None:
        """만료된 엔트리가 없을 때 cleanup_expired."""
        # Arrange
        key = "test:cleanup:no_expired"
        ttl = 3600
        await solid_cache.set(key, "valid", ttl)

        # Act
        cleaned_count = await solid_cache.cleanup_expired()

        # Assert
        assert cleaned_count == 0, "만료된 엔트리가 없으면 0을 반환해야 함"
        assert await solid_cache.get(key) == "valid", "유효한 키는 유지되어야 함"


class TestSolidCacheStats:
    """Solid Cache 통계 테스트."""

    @pytest.mark.asyncio
    async def test_get_stats_empty_cache(self, solid_cache: SolidCache) -> None:
        """빈 캐시의 통계 조회."""
        # Act
        stats = await solid_cache.get_stats()

        # Assert
        assert stats["total_entries"] == 0, "총 엔트리 수는 0이어야 함"
        assert stats["expired_entries"] == 0, "만료된 엔트리 수는 0이어야 함"
        assert "total_size_bytes" in stats, "total_size_bytes 키가 존재해야 함"
        assert isinstance(stats["total_size_bytes"], int), "크기는 정수여야 함"

    @pytest.mark.asyncio
    async def test_get_stats_with_entries(self, solid_cache: SolidCache) -> None:
        """엔트리가 있는 캐시의 통계 조회."""
        # Arrange
        keys = ["stats:1", "stats:2", "stats:3"]
        ttl = 3600

        for key in keys:
            await solid_cache.set(key, "test_value", ttl)

        # Act
        stats = await solid_cache.get_stats()

        # Assert
        assert stats["total_entries"] == 3, "총 엔트리 수는 3이어야 함"
        assert stats["expired_entries"] == 0, "만료된 엔트리는 0이어야 함"
        assert stats["total_size_bytes"] > 0, "총 크기는 0보다 커야 함"

    @pytest.mark.asyncio
    async def test_get_stats_with_expired_entries(
        self, solid_cache: SolidCache
    ) -> None:
        """만료된 엔트리가 포함된 통계 조회."""
        # Arrange
        expired_keys = ["stats:expired:1", "stats:expired:2"]
        valid_key = "stats:valid"

        # 만료된 키
        for key in expired_keys:
            await solid_cache.set(key, "expired", 1)

        # 유효한 키
        await solid_cache.set(valid_key, "valid", 3600)

        # 만료 대기
        await asyncio.sleep(2)

        # Act
        stats = await solid_cache.get_stats()

        # Assert
        assert stats["total_entries"] == 3, "총 엔트리 수는 3이어야 함"
        assert stats["expired_entries"] == 2, "만료된 엔트리는 2개여야 함"


class TestSolidCacheEdgeCases:
    """Solid Cache 엣지 케이스 테스트."""

    @pytest.mark.asyncio
    async def test_set_empty_value(self, solid_cache: SolidCache) -> None:
        """빈 문자열 저장 및 조회."""
        # Arrange
        key = "test:empty:value"
        value = ""
        ttl = 3600

        # Act
        await solid_cache.set(key, value, ttl)
        result = await solid_cache.get(key)

        # Assert
        assert result == "", "빈 문자열도 정상적으로 저장되어야 함"

    @pytest.mark.asyncio
    async def test_set_special_characters(self, solid_cache: SolidCache) -> None:
        """특수 문자가 포함된 값 저장."""
        # Arrange
        key = "test:special:chars"
        value = "테스트 !@#$%^&*() 한글 🚀"
        ttl = 3600

        # Act
        await solid_cache.set(key, value, ttl)
        result = await solid_cache.get(key)

        # Assert
        assert result == value, "특수 문자도 정상적으로 저장되어야 함"

    @pytest.mark.asyncio
    async def test_set_json_with_nested_structure(
        self, solid_cache: SolidCache
    ) -> None:
        """중첩된 JSON 구조 저장."""
        # Arrange
        key = "test:json:nested"
        value = {
            "user": {
                "id": 123,
                "profile": {"name": "John", "tags": ["admin", "user"]},
            },
            "metadata": {"created_at": "2024-01-01", "updated_at": None},
        }
        ttl = 3600

        # Act
        await solid_cache.set_json(key, value, ttl)
        result = await solid_cache.get_json(key)

        # Assert
        assert result == value, "중첩된 JSON 구조도 정상적으로 저장되어야 함"

    @pytest.mark.asyncio
    async def test_very_short_ttl(self, solid_cache: SolidCache) -> None:
        """매우 짧은 TTL (1초) 테스트."""
        # Arrange
        key = "test:short:ttl"
        value = "short_lived"
        ttl = 1

        # Act
        await solid_cache.set(key, value, ttl)
        result_immediate = await solid_cache.get(key)

        await asyncio.sleep(1.5)
        result_after_expiry = await solid_cache.get(key)

        # Assert
        assert result_immediate == value, "즉시 조회 시 값이 있어야 함"
        assert result_after_expiry is None, "1초 후에는 만료되어야 함"
