"""
Rate Limiting Middleware

브루트포스 공격, DDoS, credential stuffing 방어를 위한 Rate Limiting 구현
"""

from collections.abc import Callable
from typing import ClassVar

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.shared.security.redis_store import redis_store
from src.shared.utils.client_ip import get_client_ip


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate Limiting 미들웨어

    엔드포인트별로 다른 제한을 적용하여 API 남용 방지
    """

    # 경로별 Rate Limit 설정 (경로: (최대 요청 수, 시간 윈도우(초)))
    RATE_LIMITS: ClassVar[dict[str, tuple[int, int]]] = {
        "/api/v1/auth/login": (5, 60),  # 로그인: 5회/분
        "/api/v1/auth/refresh": (10, 60),  # 토큰 갱신: 10회/분
        "/api/v1/users/register": (3, 3600),  # 회원가입: 3회/시간
        "/api/v1/auth/logout": (10, 60),  # 로그아웃: 10회/분
        "/api/v1/users/password": (5, 3600),  # 비밀번호 변경: 5회/시간
    }

    # 일반 API 기본 제한
    DEFAULT_RATE_LIMIT = (100, 60)  # 100회/분

    async def dispatch(self, request: Request, call_next: Callable):
        """
        요청 처리 전 Rate Limiting 검사

        Args:
            request: FastAPI Request 객체
            call_next: 다음 미들웨어/핸들러

        Returns:
            Response 객체

        Raises:
            HTTPException: Rate limit 초과 시 429 응답
        """
        # OPTIONS 요청은 Rate Limiting 제외 (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # 클라이언트 IP 추출 (trusted proxy validation 적용)
        client_ip = get_client_ip(request)

        # 경로별 Rate Limit 확인
        path = request.url.path
        max_requests, window_seconds = self._get_rate_limit(path)

        # Redis key 생성: rate_limit:{ip}:{path}
        key = f"rate_limit:{client_ip}:{path}"

        # Rate Limit 검사
        allowed = await redis_store.check_rate_limit(
            key=key, max_requests=max_requests, window_seconds=window_seconds
        )

        if not allowed:
            # Rate limit 초과 시 429 응답 (JSONResponse로 직접 반환)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error_code": "RATE_LIMIT_001",
                    "message": "너무 많은 요청입니다. 잠시 후 다시 시도해주세요.",
                },
                headers={
                    "Retry-After": str(window_seconds),
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Window": str(window_seconds),
                },
            )

        # 다음 핸들러로 진행
        response = await call_next(request)

        # Rate Limit 정보를 응답 헤더에 추가 (선택사항)
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Window"] = str(window_seconds)

        return response

    def _get_rate_limit(self, path: str) -> tuple[int, int]:
        """
        경로에 맞는 Rate Limit 설정 반환

        Args:
            path: API 경로

        Returns:
            (최대 요청 수, 시간 윈도우(초)) 튜플
        """
        # 정확히 일치하는 경로 확인
        if path in self.RATE_LIMITS:
            return self.RATE_LIMITS[path]

        # /api/v1로 시작하는 경로는 기본 제한 적용
        if path.startswith("/api/v1/"):
            return self.DEFAULT_RATE_LIMIT

        # 그 외 경로는 제한 없음 (정적 파일 등)
        return (1000, 60)  # 매우 관대한 제한
