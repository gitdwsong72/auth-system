"""Unit tests for Rate Limiter Middleware.

Tests rate limiting functionality with mocked Redis to ensure
proper isolation and no external dependencies.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request, status
from starlette.responses import Response

from src.shared.middleware.rate_limiter import RateLimitMiddleware


@pytest.fixture
def mock_request():
    """Create a mock FastAPI Request."""
    request = MagicMock(spec=Request)
    request.method = "POST"
    request.url = MagicMock()
    request.url.path = "/api/v1/auth/login"
    request.headers = {}
    request.client = MagicMock()
    request.client.host = "192.168.1.100"
    return request


@pytest.fixture
def mock_call_next():
    """Create a mock call_next function."""

    async def _call_next(request: Request) -> Response:
        return Response(content="OK", status_code=200)

    return _call_next


@pytest.fixture
def rate_limiter():
    """Create a RateLimitMiddleware instance."""
    app = MagicMock()
    return RateLimitMiddleware(app)


@pytest.mark.asyncio
class TestRateLimitMiddleware:
    """Test RateLimitMiddleware functionality."""

    async def test_allows_request_within_limit(
        self,
        rate_limiter: RateLimitMiddleware,
        mock_request: Request,
        mock_call_next: Any,
    ):
        """Test that requests within rate limit are allowed."""
        # Arrange - Mock Redis to allow request
        with patch("src.shared.middleware.rate_limiter.redis_store") as mock_redis:
            mock_redis.check_rate_limit = AsyncMock(return_value=True)

            # Act
            response = await rate_limiter.dispatch(mock_request, mock_call_next)

            # Assert
            assert response.status_code == 200
            mock_redis.check_rate_limit.assert_called_once()
            # Verify rate limit headers are added
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Window" in response.headers

    async def test_blocks_request_exceeding_limit(
        self,
        rate_limiter: RateLimitMiddleware,
        mock_request: Request,
        mock_call_next: Any,
    ):
        """Test that requests exceeding rate limit are blocked."""
        # Arrange - Mock Redis to block request
        with patch("src.shared.middleware.rate_limiter.redis_store") as mock_redis:
            mock_redis.check_rate_limit = AsyncMock(return_value=False)

            # Act
            response = await rate_limiter.dispatch(mock_request, mock_call_next)

            # Assert
            assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
            body = response.body.decode()
            assert "RATE_LIMIT_001" in body
            assert "너무 많은 요청입니다" in body
            # Verify retry-after header
            assert "Retry-After" in response.headers

    async def test_options_request_bypasses_rate_limit(
        self,
        rate_limiter: RateLimitMiddleware,
        mock_request: Request,
        mock_call_next: Any,
    ):
        """Test that OPTIONS requests (CORS preflight) bypass rate limiting."""
        # Arrange
        mock_request.method = "OPTIONS"

        with patch("src.shared.middleware.rate_limiter.redis_store") as mock_redis:
            mock_redis.check_rate_limit = AsyncMock(return_value=False)

            # Act
            response = await rate_limiter.dispatch(mock_request, mock_call_next)

            # Assert - Should pass even if rate limit would block
            assert response.status_code == 200
            mock_redis.check_rate_limit.assert_not_called()

    async def test_different_limits_per_endpoint(
        self,
        rate_limiter: RateLimitMiddleware,
        mock_call_next: Any,
    ):
        """Test that different endpoints have different rate limits."""
        # Test cases: (path, expected_max_requests, expected_window)
        test_cases = [
            ("/api/v1/auth/login", 5, 60),
            ("/api/v1/auth/refresh", 10, 60),
            ("/api/v1/users/register", 3, 3600),
            ("/api/v1/users/password", 5, 3600),
        ]

        for path, expected_max, expected_window in test_cases:
            # Arrange
            mock_request = MagicMock(spec=Request)
            mock_request.method = "POST"
            mock_request.url = MagicMock()
            mock_request.url.path = path
            mock_request.headers = {}
            mock_request.client = MagicMock()
            mock_request.client.host = "192.168.1.100"

            with patch("src.shared.middleware.rate_limiter.redis_store") as mock_redis:
                mock_redis.check_rate_limit = AsyncMock(return_value=True)

                # Act
                await rate_limiter.dispatch(mock_request, mock_call_next)

                # Assert
                call_args = mock_redis.check_rate_limit.call_args
                assert call_args.kwargs["max_requests"] == expected_max
                assert call_args.kwargs["window_seconds"] == expected_window

    async def test_default_rate_limit_for_api_endpoints(
        self,
        rate_limiter: RateLimitMiddleware,
        mock_call_next: Any,
    ):
        """Test default rate limit for unspecified API endpoints."""
        # Arrange
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url = MagicMock()
        mock_request.url.path = "/api/v1/some/random/endpoint"
        mock_request.headers = {}
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.100"

        with patch("src.shared.middleware.rate_limiter.redis_store") as mock_redis:
            mock_redis.check_rate_limit = AsyncMock(return_value=True)

            # Act
            await rate_limiter.dispatch(mock_request, mock_call_next)

            # Assert - Should use default rate limit
            call_args = mock_redis.check_rate_limit.call_args
            assert call_args.kwargs["max_requests"] == 100
            assert call_args.kwargs["window_seconds"] == 60

    async def test_extracts_ip_from_x_forwarded_for_header(
        self,
        rate_limiter: RateLimitMiddleware,
        mock_call_next: Any,
    ):
        """Test IP extraction from X-Forwarded-For header (proxy scenario)."""
        # Arrange
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url = MagicMock()
        mock_request.url.path = "/api/v1/auth/login"
        mock_request.headers = {"X-Forwarded-For": "203.0.113.1, 198.51.100.1"}
        mock_request.client = MagicMock()
        mock_request.client.host = "10.0.0.1"

        with patch("src.shared.middleware.rate_limiter.redis_store") as mock_redis:
            mock_redis.check_rate_limit = AsyncMock(return_value=True)

            # Act
            await rate_limiter.dispatch(mock_request, mock_call_next)

            # Assert - Should use first IP from X-Forwarded-For
            call_args = mock_redis.check_rate_limit.call_args
            redis_key = call_args.kwargs["key"]
            assert "203.0.113.1" in redis_key

    async def test_extracts_ip_from_x_real_ip_header(
        self,
        rate_limiter: RateLimitMiddleware,
        mock_call_next: Any,
    ):
        """Test IP extraction from X-Real-IP header (Nginx scenario)."""
        # Arrange
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url = MagicMock()
        mock_request.url.path = "/api/v1/auth/login"
        mock_request.headers = {"X-Real-IP": "203.0.113.5"}
        mock_request.client = MagicMock()
        mock_request.client.host = "10.0.0.1"

        with patch("src.shared.middleware.rate_limiter.redis_store") as mock_redis:
            mock_redis.check_rate_limit = AsyncMock(return_value=True)

            # Act
            await rate_limiter.dispatch(mock_request, mock_call_next)

            # Assert
            call_args = mock_redis.check_rate_limit.call_args
            redis_key = call_args.kwargs["key"]
            assert "203.0.113.5" in redis_key

    async def test_uses_client_host_when_no_proxy_headers(
        self,
        rate_limiter: RateLimitMiddleware,
        mock_request: Request,
        mock_call_next: Any,
    ):
        """Test direct client IP is used when no proxy headers present."""
        # Arrange - No proxy headers
        mock_request.headers = {}
        mock_request.client.host = "192.168.1.100"

        with patch("src.shared.middleware.rate_limiter.redis_store") as mock_redis:
            mock_redis.check_rate_limit = AsyncMock(return_value=True)

            # Act
            await rate_limiter.dispatch(mock_request, mock_call_next)

            # Assert
            call_args = mock_redis.check_rate_limit.call_args
            redis_key = call_args.kwargs["key"]
            assert "192.168.1.100" in redis_key

    async def test_handles_missing_client_gracefully(
        self,
        rate_limiter: RateLimitMiddleware,
        mock_call_next: Any,
    ):
        """Test handling of missing client information."""
        # Arrange
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url = MagicMock()
        mock_request.url.path = "/api/v1/auth/login"
        mock_request.headers = {}
        mock_request.client = None

        with patch("src.shared.middleware.rate_limiter.redis_store") as mock_redis:
            mock_redis.check_rate_limit = AsyncMock(return_value=True)

            # Act
            await rate_limiter.dispatch(mock_request, mock_call_next)

            # Assert - Should use "unknown" as fallback
            call_args = mock_redis.check_rate_limit.call_args
            redis_key = call_args.kwargs["key"]
            assert "unknown" in redis_key

    async def test_redis_key_format(
        self,
        rate_limiter: RateLimitMiddleware,
        mock_request: Request,
        mock_call_next: Any,
    ):
        """Test Redis key format is correct."""
        # Arrange
        mock_request.url.path = "/api/v1/auth/login"
        mock_request.client.host = "192.168.1.100"

        with patch("src.shared.middleware.rate_limiter.redis_store") as mock_redis:
            mock_redis.check_rate_limit = AsyncMock(return_value=True)

            # Act
            await rate_limiter.dispatch(mock_request, mock_call_next)

            # Assert
            call_args = mock_redis.check_rate_limit.call_args
            redis_key = call_args.kwargs["key"]
            assert redis_key == "rate_limit:192.168.1.100:/api/v1/auth/login"

    async def test_redis_connection_failure_handling(
        self,
        rate_limiter: RateLimitMiddleware,
        mock_request: Request,
        mock_call_next: Any,
    ):
        """Test graceful handling of Redis connection failures."""
        # Arrange - Mock Redis to raise exception
        with patch("src.shared.middleware.rate_limiter.redis_store") as mock_redis:
            mock_redis.check_rate_limit = AsyncMock(
                side_effect=ConnectionError("Redis unavailable")
            )

            # Act & Assert - Should raise the exception
            # In production, you might want to allow requests when Redis is down
            with pytest.raises(ConnectionError):
                await rate_limiter.dispatch(mock_request, mock_call_next)


@pytest.mark.asyncio
class TestRateLimitHelperMethods:
    """Test helper methods of RateLimitMiddleware."""

    def test_get_rate_limit_for_known_path(self, rate_limiter: RateLimitMiddleware):
        """Test _get_rate_limit returns correct values for known paths."""
        # Act & Assert
        max_req, window = rate_limiter._get_rate_limit("/api/v1/auth/login")
        assert max_req == 5
        assert window == 60

        max_req, window = rate_limiter._get_rate_limit("/api/v1/users/register")
        assert max_req == 3
        assert window == 3600

    def test_get_rate_limit_for_default_api_path(self, rate_limiter: RateLimitMiddleware):
        """Test _get_rate_limit returns default for unknown API paths."""
        # Act
        max_req, window = rate_limiter._get_rate_limit("/api/v1/unknown/endpoint")

        # Assert
        assert max_req == 100
        assert window == 60

    def test_get_rate_limit_for_non_api_path(self, rate_limiter: RateLimitMiddleware):
        """Test _get_rate_limit returns lenient limit for non-API paths."""
        # Act
        max_req, window = rate_limiter._get_rate_limit("/static/image.png")

        # Assert
        assert max_req == 1000
        assert window == 60

    def test_get_client_ip_priority(self, rate_limiter: RateLimitMiddleware):
        """Test IP extraction priority: X-Forwarded-For > X-Real-IP > client.host."""
        # Test case 1: X-Forwarded-For present
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {
            "X-Forwarded-For": "1.1.1.1, 2.2.2.2",
            "X-Real-IP": "3.3.3.3",
        }
        mock_request.client = MagicMock()
        mock_request.client.host = "4.4.4.4"

        ip = rate_limiter._get_client_ip(mock_request)
        assert ip == "1.1.1.1"

        # Test case 2: Only X-Real-IP present
        mock_request.headers = {"X-Real-IP": "3.3.3.3"}
        ip = rate_limiter._get_client_ip(mock_request)
        assert ip == "3.3.3.3"

        # Test case 3: Only client.host present
        mock_request.headers = {}
        ip = rate_limiter._get_client_ip(mock_request)
        assert ip == "4.4.4.4"


class TestTrustedProxyValidation:
    """Trusted proxy validation 테스트"""

    @pytest.fixture
    def rate_limiter(self):
        """RateLimitMiddleware 인스턴스"""
        return RateLimitMiddleware(app=AsyncMock())

    def test_is_trusted_proxy_private_ipv4(self, rate_limiter):
        """Private IPv4 주소는 trusted"""
        assert rate_limiter._is_trusted_proxy("10.0.0.1") is True
        assert rate_limiter._is_trusted_proxy("172.16.0.1") is True
        assert rate_limiter._is_trusted_proxy("192.168.1.1") is True
        assert rate_limiter._is_trusted_proxy("127.0.0.1") is True

    def test_is_trusted_proxy_public_ipv4(self, rate_limiter):
        """Public IPv4 주소는 untrusted"""
        assert rate_limiter._is_trusted_proxy("8.8.8.8") is False
        assert rate_limiter._is_trusted_proxy("1.1.1.1") is False
        assert rate_limiter._is_trusted_proxy("203.0.113.1") is False

    def test_is_trusted_proxy_invalid_ip(self, rate_limiter):
        """유효하지 않은 IP는 False"""
        assert rate_limiter._is_trusted_proxy("invalid") is False
        assert rate_limiter._is_trusted_proxy("256.256.256.256") is False

    def test_get_client_ip_from_trusted_proxy(self, rate_limiter):
        """Trusted proxy에서는 X-Forwarded-For 신뢰"""
        request = MagicMock()
        request.client.host = "10.0.0.1"  # Trusted proxy
        request.headers.get.return_value = "203.0.113.5"  # Client IP

        ip = rate_limiter._get_client_ip(request)
        assert ip == "203.0.113.5"

    def test_get_client_ip_from_untrusted_proxy(self, rate_limiter):
        """Untrusted proxy에서는 X-Forwarded-For 무시"""
        request = MagicMock()
        request.client.host = "8.8.8.8"  # Untrusted (public IP)
        request.headers.get.return_value = "203.0.113.5"  # Spoofed header

        ip = rate_limiter._get_client_ip(request)
        # X-Forwarded-For를 무시하고 직접 연결 IP 사용
        assert ip == "8.8.8.8"

    def test_get_client_ip_direct_connection(self, rate_limiter):
        """직접 연결 (헤더 없음)"""
        request = MagicMock()
        request.client.host = "203.0.113.10"
        request.headers.get.return_value = None  # No X-Forwarded-For

        ip = rate_limiter._get_client_ip(request)
        assert ip == "203.0.113.10"

    def test_get_client_ip_x_real_ip_from_trusted(self, rate_limiter):
        """Trusted proxy에서 X-Real-IP 헤더 사용"""
        request = MagicMock()
        request.client.host = "192.168.1.1"  # Trusted
        request.headers.get.side_effect = lambda key: {
            "X-Forwarded-For": None,
            "X-Real-IP": "203.0.113.20",
        }.get(key)

        ip = rate_limiter._get_client_ip(request)
        assert ip == "203.0.113.20"

    def test_get_client_ip_multiple_forwarded_ips(self, rate_limiter):
        """여러 IP가 포함된 X-Forwarded-For (첫 번째만 사용)"""
        request = MagicMock()
        request.client.host = "10.0.0.1"  # Trusted
        request.headers.get.return_value = "203.0.113.30, 10.0.0.2, 10.0.0.3"

        ip = rate_limiter._get_client_ip(request)
        # 첫 번째 IP만 추출
        assert ip == "203.0.113.30"
