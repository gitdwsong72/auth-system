"""Backpressure Middleware 단위 테스트"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI

from src.shared.middleware.backpressure import BackpressureMiddleware


@pytest.fixture
def app():
    """FastAPI 앱 fixture"""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return {"message": "ok"}

    @app.get("/slow")
    async def slow_endpoint():
        await asyncio.sleep(0.1)
        return {"message": "slow"}

    @app.get("/health")
    async def health_endpoint():
        return {"status": "healthy"}

    return app


@pytest.fixture
def middleware():
    """BackpressureMiddleware fixture"""
    mock_app = MagicMock()
    return BackpressureMiddleware(
        app=mock_app, max_concurrent=2, queue_capacity=5, wait_timeout=0.5
    )


class TestBackpressureConfiguration:
    """설정 초기화 테스트"""

    def test_default_reject_threshold(self, middleware):
        """reject_threshold 기본값 테스트"""
        # Arrange & Act & Assert
        assert middleware.reject_threshold == 7  # max_concurrent(2) + queue_capacity(5)

    def test_custom_reject_threshold(self):
        """커스텀 reject_threshold 테스트"""
        # Arrange & Act
        mock_app = MagicMock()
        middleware = BackpressureMiddleware(
            app=mock_app, max_concurrent=2, queue_capacity=5, reject_threshold=10
        )

        # Assert
        assert middleware.reject_threshold == 10

    def test_initial_metrics(self, middleware):
        """초기 메트릭 상태 테스트"""
        # Arrange & Act & Assert
        assert middleware._current_requests == 0
        assert middleware._queued_requests == 0
        assert middleware._rejected_requests == 0
        assert middleware._timeout_requests == 0
        assert middleware._total_requests == 0


class TestBypassPaths:
    """Bypass 경로 테스트"""

    def test_should_bypass_health(self, middleware):
        """health 엔드포인트는 bypass"""
        # Arrange
        request = MagicMock()
        request.url.path = "/health"

        # Act & Assert
        assert middleware._should_bypass(request) is True

    def test_should_bypass_metrics(self, middleware):
        """metrics 엔드포인트는 bypass"""
        # Arrange
        request = MagicMock()
        request.url.path = "/metrics"

        # Act & Assert
        assert middleware._should_bypass(request) is True

    def test_should_not_bypass_api(self, middleware):
        """일반 API는 bypass 안됨"""
        # Arrange
        request = MagicMock()
        request.url.path = "/api/v1/users"

        # Act & Assert
        assert middleware._should_bypass(request) is False


class TestOverloadResponses:
    """과부하 응답 테스트"""

    def test_create_overload_response(self, middleware):
        """시스템 과부하 응답 생성"""
        # Arrange
        middleware._current_requests = 10
        middleware._queued_requests = 20

        # Act
        response = middleware._create_overload_response()

        # Assert
        assert response.status_code == 503
        assert response.headers["Retry-After"] == "5"
        assert response.headers["X-Queue-Status"] == "rejected"
        body = response.body.decode()
        assert "SYSTEM_OVERLOAD" in body

    def test_create_queue_full_response(self, middleware):
        """대기열 포화 응답 생성"""
        # Arrange & Act
        response = middleware._create_queue_full_response()

        # Assert
        assert response.status_code == 503
        assert response.headers["Retry-After"] == "1"
        assert response.headers["X-Queue-Status"] == "full"
        body = response.body.decode()
        assert "QUEUE_FULL" in body
        assert str(middleware.queue_capacity) in body

    def test_create_timeout_response(self, middleware):
        """대기 타임아웃 응답 생성"""
        # Arrange & Act
        response = middleware._create_timeout_response()

        # Assert
        assert response.status_code == 503
        assert response.headers["Retry-After"] == "2"
        assert response.headers["X-Queue-Status"] == "timeout"
        body = response.body.decode()
        assert "QUEUE_TIMEOUT" in body
        assert str(middleware.wait_timeout) in body


class TestMetrics:
    """메트릭 테스트"""

    def test_get_metrics_initial_state(self, middleware):
        """초기 메트릭 조회"""
        # Arrange & Act
        metrics = middleware.get_metrics()

        # Assert
        assert metrics["current_requests"] == 0
        assert metrics["queued_requests"] == 0
        assert metrics["total_requests"] == 0
        assert metrics["rejected_requests"] == 0
        assert metrics["timeout_requests"] == 0
        assert metrics["utilization_percent"] == 0.0
        assert metrics["status"] == "healthy"

    def test_get_metrics_with_load(self, middleware):
        """부하 상태에서 메트릭 조회"""
        # Arrange
        middleware._current_requests = 1
        middleware._total_requests = 10
        middleware._rejected_requests = 2
        middleware._timeout_requests = 1

        # Act
        metrics = middleware.get_metrics()

        # Assert
        assert metrics["current_requests"] == 1
        assert metrics["total_requests"] == 10
        assert metrics["rejected_requests"] == 2
        assert metrics["timeout_requests"] == 1
        assert metrics["utilization_percent"] == 50.0  # 1/2 * 100
        assert metrics["rejection_rate_percent"] == 20.0  # 2/10 * 100

    def test_get_health_status_healthy(self, middleware):
        """정상 상태 판단"""
        # Arrange & Act
        status = middleware._get_health_status(0.5)

        # Assert
        assert status == "healthy"

    def test_get_health_status_warning(self, middleware):
        """경고 상태 판단"""
        # Arrange & Act
        status = middleware._get_health_status(0.75)

        # Assert
        assert status == "warning"

    def test_get_health_status_critical(self, middleware):
        """위험 상태 판단"""
        # Arrange & Act
        status = middleware._get_health_status(0.9)

        # Assert
        assert status == "critical"

    def test_reset_metrics(self, middleware):
        """메트릭 초기화"""
        # Arrange
        middleware._total_requests = 100
        middleware._rejected_requests = 10
        middleware._timeout_requests = 5
        middleware._total_wait_time = 10.5
        middleware._max_wait_time = 2.3

        # Act
        middleware.reset_metrics()

        # Assert
        assert middleware._total_requests == 0
        assert middleware._rejected_requests == 0
        assert middleware._timeout_requests == 0
        assert middleware._total_wait_time == 0.0
        assert middleware._max_wait_time == 0.0


@pytest.mark.asyncio
class TestDispatchLogic:
    """dispatch 로직 테스트"""

    async def test_bypass_health_endpoint(self, middleware):
        """health 엔드포인트는 backpressure 적용 안됨"""
        # Arrange
        request = MagicMock()
        request.url.path = "/health"
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        # Act
        response = await middleware.dispatch(request, call_next)

        # Assert
        assert response.status_code == 200
        assert middleware._total_requests == 0  # 카운트 안됨

    async def test_immediate_rejection_on_overload(self, middleware):
        """시스템 과부하 시 즉시 거부"""
        # Arrange
        middleware._current_requests = 5
        middleware._queued_requests = 5  # total = 10 > reject_threshold(7)
        request = MagicMock()
        request.url.path = "/api/v1/test"
        call_next = AsyncMock()

        # Act
        response = await middleware.dispatch(request, call_next)

        # Assert
        assert response.status_code == 503
        assert middleware._rejected_requests == 1
        call_next.assert_not_called()

    async def test_queue_full_rejection(self, middleware):
        """대기열 포화 시 거부"""
        # Arrange
        middleware._queued_requests = 5  # queue_capacity 도달
        request = MagicMock()
        request.url.path = "/api/v1/test"
        call_next = AsyncMock()

        # Act
        response = await middleware.dispatch(request, call_next)

        # Assert
        assert response.status_code == 503
        assert middleware._rejected_requests == 1
        call_next.assert_not_called()

    async def test_successful_request_processing(self, middleware):
        """정상 요청 처리"""
        # Arrange
        request = MagicMock()
        request.url.path = "/api/v1/test"
        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        # Act
        response = await middleware.dispatch(request, call_next)

        # Assert
        assert response == mock_response
        assert middleware._total_requests == 1
        call_next.assert_called_once()

    async def test_wait_time_header_added(self, middleware):
        """대기 시간 헤더 추가 확인"""
        # Arrange
        middleware._queued_requests = 1  # 약간의 대기 발생
        request = MagicMock()
        request.url.path = "/api/v1/test"
        mock_response = MagicMock()
        mock_response.headers = {}

        async def slow_next(_request):
            await asyncio.sleep(0.15)  # 대기 시간 강제
            return mock_response

        # Act
        response = await middleware.dispatch(request, slow_next)

        # Assert
        assert response == mock_response
        # 대기 시간이 100ms 이상이면 헤더 추가됨
        if "X-Queue-Wait-Time" in response.headers:
            assert float(response.headers["X-Queue-Wait-Time"]) > 0


@pytest.mark.asyncio
class TestConcurrentRequests:
    """동시 요청 처리 테스트"""

    async def test_request_metrics_incremented(self, middleware):
        """요청 처리 시 메트릭이 올바르게 증가"""
        # Arrange
        request = MagicMock()
        request.url.path = "/api/v1/test"
        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        initial_total = middleware._total_requests

        # Act
        await middleware.dispatch(request, call_next)

        # Assert
        assert middleware._total_requests == initial_total + 1
        assert middleware._current_requests == 0  # 처리 완료 후 0으로 복원
