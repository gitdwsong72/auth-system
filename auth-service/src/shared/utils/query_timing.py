"""쿼리 실행 시간 측정 유틸리티."""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from src.shared.logging import security_logger

SLOW_QUERY_THRESHOLD_MS = 100


@asynccontextmanager
async def track_query(query_name: str) -> AsyncIterator[None]:
    """쿼리 실행 시간을 측정하고 느린 쿼리를 로깅한다.

    Args:
        query_name: 쿼리 식별자 (함수명)

    Usage:
        async with track_query("get_user_by_id"):
            result = await connection.fetchrow(query, user_id)
    """
    start = time.monotonic()
    try:
        yield
    finally:
        elapsed_ms = (time.monotonic() - start) * 1000
        if elapsed_ms > SLOW_QUERY_THRESHOLD_MS:
            security_logger.log_slow_query(query_name, elapsed_ms)
