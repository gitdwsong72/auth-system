"""
Backpressure Middleware - 시스템 과부하 방지

시스템 수용 한계를 넘는 요청을 대기열에 추가하고 순차적으로 처리합니다.
임계치 초과 시 503 Service Unavailable을 반환하여 시스템을 보호합니다.
"""

import asyncio
import time

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class BackpressureMiddleware(BaseHTTPMiddleware):
    """
    Application-level Semaphore를 사용한 Backpressure 구현

    주요 기능:
    - 동시 처리 요청 수 제한 (Semaphore)
    - 대기열 초과 시 503 응답
    - 대기 타임아웃 설정
    - 실시간 메트릭 수집

    사용 예시:
        app.add_middleware(
            BackpressureMiddleware,
            max_concurrent=100,
            queue_capacity=1000,
            wait_timeout=3,
        )
    """

    def __init__(
        self,
        app,
        max_concurrent: int = 100,
        queue_capacity: int = 1000,
        wait_timeout: float = 3.0,
        reject_threshold: int | None = None,
    ):
        """
        Args:
            app: FastAPI 애플리케이션
            max_concurrent: 동시 처리 가능한 최대 요청 수 (DB Connection Pool과 동기화 권장)
            queue_capacity: 대기열 최대 크기 (초과 시 즉시 503 반환)
            wait_timeout: 대기열에서 대기할 최대 시간 (초)
            reject_threshold: 즉시 거부 임계치 (None이면 max_concurrent + queue_capacity)
        """
        super().__init__(app)
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent
        self.queue_capacity = queue_capacity
        self.wait_timeout = wait_timeout
        self.reject_threshold = reject_threshold or (max_concurrent + queue_capacity)

        # 메트릭
        self._current_requests = 0
        self._queued_requests = 0
        self._rejected_requests = 0
        self._timeout_requests = 0
        self._total_requests = 0
        self._total_wait_time = 0.0
        self._max_wait_time = 0.0

    async def dispatch(self, request: Request, call_next):
        """요청 처리 메인 로직"""

        # 1. Health check 및 Metrics 엔드포인트는 bypass
        if self._should_bypass(request):
            return await call_next(request)

        self._total_requests += 1

        # 2. 시스템 완전 과부하 체크 (즉시 거부)
        total_load = self._current_requests + self._queued_requests
        if total_load >= self.reject_threshold:
            self._rejected_requests += 1
            return self._create_overload_response()

        # 3. 대기열 포화 체크
        if self._queued_requests >= self.queue_capacity:
            self._rejected_requests += 1
            return self._create_queue_full_response()

        # 4. 대기열 진입
        self._queued_requests += 1
        wait_start = time.time()

        try:
            # 5. Semaphore 획득 대기 (timeout 적용)
            async with asyncio.timeout(self.wait_timeout):
                async with self.semaphore:
                    # 대기 완료 - 처리 시작
                    self._queued_requests -= 1
                    self._current_requests += 1

                    wait_time = time.time() - wait_start
                    self._total_wait_time += wait_time
                    self._max_wait_time = max(self._max_wait_time, wait_time)

                    try:
                        # 6. 실제 요청 처리
                        response = await call_next(request)

                        # 7. 대기 시간이 길었다면 헤더에 포함
                        if wait_time > 0.1:  # 100ms 이상
                            response.headers["X-Queue-Wait-Time"] = f"{wait_time:.3f}"
                            response.headers["X-Queue-Position"] = "processed"

                        return response

                    finally:
                        self._current_requests -= 1

        except TimeoutError:
            # 대기 타임아웃 발생
            self._queued_requests -= 1
            self._timeout_requests += 1
            return self._create_timeout_response()

        except Exception:
            # 예상치 못한 오류
            self._queued_requests -= 1
            if self._current_requests > 0:
                self._current_requests -= 1
            raise

    def _should_bypass(self, request: Request) -> bool:
        """특정 엔드포인트는 Backpressure 적용 제외"""
        bypass_paths = {
            "/health",
            "/metrics",
            "/api/v1/metrics",
            "/api/v1/health",
        }
        return request.url.path in bypass_paths

    def _create_overload_response(self) -> JSONResponse:
        """시스템 과부하 응답 (503)"""
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": "SYSTEM_OVERLOAD",
                    "message": "System is experiencing high load. Please try again later.",
                    "details": {
                        "active_requests": self._current_requests,
                        "queued_requests": self._queued_requests,
                        "retry_after_seconds": 5,
                    },
                },
            },
            headers={
                "Retry-After": "5",
                "X-Queue-Status": "rejected",
            },
        )

    def _create_queue_full_response(self) -> JSONResponse:
        """대기열 포화 응답 (503)"""
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": "QUEUE_FULL",
                    "message": "Service queue is full. Please retry shortly.",
                    "details": {
                        "queue_capacity": self.queue_capacity,
                        "retry_after_seconds": 1,
                    },
                },
            },
            headers={
                "Retry-After": "1",
                "X-Queue-Status": "full",
            },
        )

    def _create_timeout_response(self) -> JSONResponse:
        """대기 타임아웃 응답 (503)"""
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": "QUEUE_TIMEOUT",
                    "message": f"Request timed out after {self.wait_timeout}s in queue.",
                    "details": {
                        "wait_timeout": self.wait_timeout,
                        "retry_after_seconds": 2,
                    },
                },
            },
            headers={
                "Retry-After": "2",
                "X-Queue-Status": "timeout",
            },
        )

    def get_metrics(self) -> dict:
        """
        모니터링용 메트릭 반환

        Returns:
            dict: 현재 시스템 상태 메트릭
        """
        total_processed = max(
            1, self._total_requests - self._rejected_requests - self._timeout_requests
        )
        avg_wait = self._total_wait_time / total_processed if total_processed > 0 else 0
        utilization = self._current_requests / self.max_concurrent

        return {
            "current_requests": self._current_requests,
            "queued_requests": self._queued_requests,
            "total_requests": self._total_requests,
            "rejected_requests": self._rejected_requests,
            "timeout_requests": self._timeout_requests,
            "avg_wait_time_ms": avg_wait * 1000,
            "max_wait_time_ms": self._max_wait_time * 1000,
            "utilization_percent": utilization * 100,
            "rejection_rate_percent": (
                (self._rejected_requests / self._total_requests * 100)
                if self._total_requests > 0
                else 0
            ),
            "status": self._get_health_status(utilization),
        }

    def _get_health_status(self, utilization: float) -> str:
        """활용률 기반 상태 판단"""
        if utilization < 0.7:
            return "healthy"
        elif utilization < 0.85:
            return "warning"
        else:
            return "critical"

    def reset_metrics(self):
        """메트릭 초기화 (테스트용)"""
        self._rejected_requests = 0
        self._timeout_requests = 0
        self._total_requests = 0
        self._total_wait_time = 0.0
        self._max_wait_time = 0.0
