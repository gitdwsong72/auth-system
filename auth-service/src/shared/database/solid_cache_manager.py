"""Solid Cache 싱글톤 관리자.

SolidCache 인스턴스를 애플리케이션 전역에서 재사용할 수 있도록
싱글톤 패턴으로 관리합니다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.shared.database.solid_cache import SolidCache


class SolidCacheManager:
    """Solid Cache 싱글톤 관리자."""

    _instance: SolidCache | None = None

    @classmethod
    def initialize(cls, pool) -> None:
        """
        Solid Cache 인스턴스를 초기화한다.

        애플리케이션 시작 시 한 번만 호출해야 합니다.

        Args:
            pool: asyncpg connection pool
        """
        if cls._instance is not None:
            return

        from src.shared.database.solid_cache import SolidCache

        cls._instance = SolidCache(pool)

    @classmethod
    def get_instance(cls) -> SolidCache:
        """
        Solid Cache 인스턴스를 반환한다.

        Returns:
            SolidCache 인스턴스

        Raises:
            RuntimeError: 초기화되지 않은 경우
        """
        if cls._instance is None:
            raise RuntimeError(
                "SolidCache가 초기화되지 않았습니다. "
                "애플리케이션 시작 시 SolidCacheManager.initialize()를 호출하세요."
            )
        return cls._instance

    @classmethod
    def is_initialized(cls) -> bool:
        """
        Solid Cache가 초기화되었는지 확인한다.

        Returns:
            초기화 여부
        """
        return cls._instance is not None


# 편의 함수
def get_solid_cache() -> SolidCache:
    """
    Solid Cache 인스턴스를 반환하는 편의 함수.

    Returns:
        SolidCache 인스턴스
    """
    return SolidCacheManager.get_instance()
