"""Solid Cache 자동 정리 백그라운드 태스크.

개발 환경에서는 pg_cron이 없으므로 애플리케이션 내에서
백그라운드 태스크로 만료된 캐시를 주기적으로 정리합니다.

프로덕션 환경에서는:
- pg_cron (Aurora PostgreSQL)
- AWS Lambda + EventBridge
- Kubernetes CronJob

중 하나를 사용하는 것을 권장합니다.
"""

import asyncio
from datetime import UTC, datetime

from src.shared.logging import get_logger

logger = get_logger(__name__)


class CacheCleanupTask:
    """Solid Cache 자동 정리 태스크."""

    def __init__(
        self,
        cleanup_interval_seconds: int = 3600,  # 기본 1시간
        enabled: bool = True,
    ):
        """
        CacheCleanupTask를 초기화한다.

        Args:
            cleanup_interval_seconds: Cleanup 실행 간격 (초)
            enabled: 태스크 활성화 여부
        """
        self.cleanup_interval = cleanup_interval_seconds
        self.enabled = enabled
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """백그라운드 태스크를 시작한다."""
        if not self.enabled:
            logger.info(
                "cache_cleanup_disabled",
                message="Solid Cache cleanup task is disabled",
            )
            return

        if self._running:
            logger.warning(
                "cache_cleanup_already_running",
                message="Cleanup task is already running",
            )
            return

        self._running = True
        self._task = asyncio.create_task(self._run_cleanup_loop())
        logger.info(
            "cache_cleanup_started",
            interval_seconds=self.cleanup_interval,
            message="Solid Cache cleanup task started",
        )

    async def stop(self) -> None:
        """백그라운드 태스크를 중지한다."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info(
            "cache_cleanup_stopped",
            message="Solid Cache cleanup task stopped",
        )

    async def _run_cleanup_loop(self) -> None:
        """Cleanup을 주기적으로 실행하는 루프."""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)

                if not self._running:
                    break

                # Cleanup 실행
                await self._execute_cleanup()

            except asyncio.CancelledError:
                logger.info("cache_cleanup_cancelled")
                break
            except Exception as e:
                logger.error(
                    "cache_cleanup_error",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                # 에러가 발생해도 계속 실행
                await asyncio.sleep(60)  # 에러 발생 시 1분 후 재시도

    async def _execute_cleanup(self) -> None:
        """Cleanup을 실행한다."""
        from src.shared.database import get_solid_cache

        try:
            solid_cache = get_solid_cache()
            deleted_count = await solid_cache.cleanup_expired()

            logger.info(
                "cache_cleanup_executed",
                deleted_count=deleted_count,
                timestamp=datetime.now(UTC).isoformat(),
            )

        except Exception as e:
            logger.error(
                "cache_cleanup_execution_error",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    async def manual_cleanup(self) -> int:
        """수동으로 Cleanup을 실행한다.

        Returns:
            삭제된 엔트리 수
        """
        from src.shared.database import get_solid_cache

        solid_cache = get_solid_cache()
        deleted_count = await solid_cache.cleanup_expired()

        logger.info(
            "cache_cleanup_manual",
            deleted_count=deleted_count,
        )

        return deleted_count


# 싱글톤 인스턴스
cache_cleanup_task = CacheCleanupTask(
    cleanup_interval_seconds=3600,  # 1시간
    enabled=True,
)
