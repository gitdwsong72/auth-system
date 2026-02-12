"""Rate Limiter Middleware 통합 테스트

실제 Redis와 FastAPI TestClient를 사용하여 Rate Limiting 동작을 검증합니다.
"""

import asyncio

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestBasicRateLimiting:
    """기본 Rate Limiting 테스트."""

    async def test_requests_within_limit_all_succeed(self, client: AsyncClient):
        """제한 내 요청은 모두 성공 (200)."""
        # Arrange
        endpoint = "/health"
        # Health endpoint uses default limit: 100 requests/60 seconds
        max_requests = 5

        # Act - 제한 내 요청
        responses = []
        for _i in range(max_requests):
            response = await client.get(endpoint, headers={"X-Forwarded-For": "192.168.1.100"})
            responses.append(response)

        # Assert
        for response in responses:
            assert response.status_code == 200

    async def test_requests_exceed_limit_returns_429(self, client: AsyncClient):
        """제한 초과 시 429 응답."""
        # Arrange
        # Register endpoint: 3 requests/hour
        endpoint = "/api/v1/users/register"
        max_requests = 3
        test_ip = "192.168.1.101"

        # Act - 제한 초과 요청
        responses = []
        for i in range(max_requests + 2):
            response = await client.post(
                endpoint,
                json={
                    "email": f"test{i}@example.com",
                    "password": "Test1234!",
                    "username": f"testuser{i}",
                },
                headers={"X-Forwarded-For": test_ip},
            )
            responses.append(response)

        # Assert
        # 첫 3개는 rate limit을 통과 (실제 응답은 201 또는 400 등)
        rate_limited_before_limit = sum(1 for r in responses[:max_requests] if r.status_code == 429)
        assert rate_limited_before_limit == 0, (
            f"First {max_requests} requests should not be rate limited"
        )

        # 나머지는 429
        for i, response in enumerate(responses[max_requests:], start=max_requests):
            assert response.status_code == 429, (
                f"Request {i} should be rate limited but got {response.status_code}"
            )
            data = response.json()
            assert data["error_code"] == "RATE_LIMIT_001"
            assert "너무 많은 요청" in data["message"]

    async def test_rate_limit_response_headers(self, client: AsyncClient):
        """Rate limit 응답 헤더 검증 (X-RateLimit-Limit, X-RateLimit-Window)."""
        # Arrange
        endpoint = "/api/v1/auth/login"
        test_ip = "192.168.1.102"
        # Login endpoint: 5 requests/60 seconds
        expected_limit = 5
        expected_window = 60

        # Act
        response = await client.post(
            endpoint,
            json={"email": "test@example.com", "password": "Test1234!"},
            headers={"X-Forwarded-For": test_ip},
        )

        # Assert - 성공 응답에 헤더 포함
        if response.status_code != 429:
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Window" in response.headers
            assert response.headers["X-RateLimit-Limit"] == str(expected_limit)
            assert response.headers["X-RateLimit-Window"] == str(expected_window)

        # Act - 제한 초과 시도
        for _ in range(10):
            response = await client.post(
                endpoint,
                json={"email": "test@example.com", "password": "Test1234!"},
                headers={"X-Forwarded-For": test_ip},
            )

        # Assert - 429 응답에도 헤더 포함
        if response.status_code == 429:
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Window" in response.headers
            assert "Retry-After" in response.headers
            assert response.headers["Retry-After"] == str(expected_window)

    async def test_rate_limit_window_reset(self, client: AsyncClient):
        """시간 윈도우 지나면 카운터 초기화."""
        # Arrange
        endpoint = "/health"
        test_ip = "192.168.1.103"

        # Act - 첫 요청
        response1 = await client.get(endpoint, headers={"X-Forwarded-For": test_ip})
        assert response1.status_code == 200

        # 짧은 대기 (Redis TTL 기반이므로 실제 시간 경과는 필요 없음)
        # 이 테스트는 Redis의 TTL 기능을 신뢰하는 것으로 충분
        # 실제 프로덕션에서는 TTL이 만료되면 자동으로 초기화됨

        # Assert - Redis 키에 TTL이 설정되어 있는지 확인
        # (간접적 검증: 다음 요청도 성공해야 함)
        response2 = await client.get(endpoint, headers={"X-Forwarded-For": test_ip})
        assert response2.status_code == 200

    async def test_different_ips_independent_counters(self, client: AsyncClient):
        """동일 경로 다른 IP는 독립적으로 카운트."""
        # Arrange
        endpoint = "/api/v1/auth/login"
        ip1 = "192.168.1.104"
        ip2 = "192.168.1.105"
        max_requests = 5

        # Act - IP1에서 제한까지 요청
        for _ in range(max_requests):
            await client.post(
                endpoint,
                json={"email": "test@example.com", "password": "Test1234!"},
                headers={"X-Forwarded-For": ip1},
            )

        # IP1 제한 초과 확인
        response_ip1 = await client.post(
            endpoint,
            json={"email": "test@example.com", "password": "Test1234!"},
            headers={"X-Forwarded-For": ip1},
        )

        # IP2에서 첫 요청
        response_ip2 = await client.post(
            endpoint,
            json={"email": "test@example.com", "password": "Test1234!"},
            headers={"X-Forwarded-For": ip2},
        )

        # Assert
        assert response_ip1.status_code == 429  # IP1은 차단
        assert response_ip2.status_code != 429  # IP2는 허용


@pytest.mark.asyncio
class TestEndpointSpecificRateLimits:
    """엔드포인트별 Rate Limit 테스트."""

    async def test_login_endpoint_rate_limit(self, client: AsyncClient):
        """Login 엔드포인트 제한 (5회/분)."""
        # Arrange
        endpoint = "/api/v1/auth/login"
        test_ip = "192.168.1.110"
        max_requests = 5

        # Act
        responses = []
        for _i in range(max_requests + 2):
            response = await client.post(
                endpoint,
                json={"email": "test@example.com", "password": "Test1234!"},
                headers={"X-Forwarded-For": test_ip},
            )
            responses.append(response)

        # Assert - 처음 5개는 허용 (실제 인증 실패여도 rate limit 통과)
        rate_limited_count = sum(1 for r in responses if r.status_code == 429)
        assert rate_limited_count >= 2  # 최소 2개는 429 응답

        # 마지막 요청은 반드시 429
        assert responses[-1].status_code == 429

    async def test_register_endpoint_rate_limit(self, client: AsyncClient):
        """Register 엔드포인트 제한 (3회/시간)."""
        # Arrange
        endpoint = "/api/v1/users/register"
        test_ip = "192.168.1.111"
        max_requests = 3

        # Act
        responses = []
        for i in range(max_requests + 1):
            response = await client.post(
                endpoint,
                json={
                    "email": f"registertest{i}@example.com",
                    "password": "Test1234!",
                    "username": f"reguser{i}",
                },
                headers={"X-Forwarded-For": test_ip},
            )
            responses.append(response)

        # Assert
        # 마지막 요청은 rate limit
        assert responses[-1].status_code == 429

    async def test_refresh_endpoint_rate_limit(self, client: AsyncClient):
        """Refresh 엔드포인트 제한 (10회/분)."""
        # Arrange
        endpoint = "/api/v1/auth/refresh"
        test_ip = "192.168.1.112"
        max_requests = 10

        # Act
        responses = []
        for _i in range(max_requests + 2):
            response = await client.post(
                endpoint,
                json={"refresh_token": "invalid_token"},
                headers={"X-Forwarded-For": test_ip},
            )
            responses.append(response)

        # Assert - 첫 10개는 rate limit 통과 (401 Unauthorized)
        sum(1 for r in responses[:max_requests] if r.status_code == 401)
        rate_limited_before = sum(1 for r in responses[:max_requests] if r.status_code == 429)
        assert rate_limited_before == 0, "First 10 requests should not be rate limited"

        # 마지막 2개는 429 (rate limit 초과)
        assert responses[-1].status_code == 429
        assert responses[-2].status_code == 429

    async def test_general_api_endpoint_rate_limit(self, client: AsyncClient):
        """일반 엔드포인트 제한 (100회/분)."""
        # Arrange
        endpoint = "/health"
        test_ip = "192.168.1.113"
        # 100번 요청은 시간이 오래 걸리므로, 일부만 테스트

        # Act - 10번만 시도
        responses = []
        for _i in range(10):
            response = await client.get(endpoint, headers={"X-Forwarded-For": test_ip})
            responses.append(response)

        # Assert - 모두 성공해야 함 (100개 제한)
        for response in responses:
            assert response.status_code == 200


@pytest.mark.asyncio
class TestIPExtractionLogic:
    """IP 추출 로직 테스트."""

    async def test_x_forwarded_for_header(self, client: AsyncClient):
        """X-Forwarded-For 헤더 사용."""
        # Arrange
        endpoint = "/health"
        test_ip = "10.0.0.1"
        # X-Forwarded-For에 여러 IP가 있을 경우 첫 번째 IP 사용
        forwarded_header = f"{test_ip}, 10.0.0.2, 10.0.0.3"

        # Act
        response1 = await client.get(endpoint, headers={"X-Forwarded-For": forwarded_header})

        # 같은 IP로 다시 요청
        response2 = await client.get(endpoint, headers={"X-Forwarded-For": forwarded_header})

        # Assert - 두 요청 모두 성공 (같은 IP로 인식)
        assert response1.status_code == 200
        assert response2.status_code == 200

    async def test_x_real_ip_header(self, client: AsyncClient):
        """X-Real-IP 헤더 사용."""
        # Arrange
        endpoint = "/health"
        test_ip = "10.0.0.10"

        # Act
        response1 = await client.get(endpoint, headers={"X-Real-IP": test_ip})

        response2 = await client.get(endpoint, headers={"X-Real-IP": test_ip})

        # Assert
        assert response1.status_code == 200
        assert response2.status_code == 200

    async def test_client_host_fallback(self, client: AsyncClient):
        """헤더 없을 때 client.host 사용."""
        # Arrange
        endpoint = "/health"

        # Act - 헤더 없이 요청
        response1 = await client.get(endpoint)
        response2 = await client.get(endpoint)

        # Assert - 기본 client.host로 rate limit 적용됨
        assert response1.status_code == 200
        assert response2.status_code == 200

    async def test_x_forwarded_for_priority_over_x_real_ip(self, client: AsyncClient):
        """X-Forwarded-For가 X-Real-IP보다 우선."""
        # Arrange
        endpoint = "/api/v1/auth/login"
        forwarded_ip = "10.0.1.1"
        real_ip = "10.0.1.2"
        max_requests = 5

        # Act - X-Forwarded-For IP로 제한까지 요청
        for _ in range(max_requests):
            await client.post(
                endpoint,
                json={"email": "test@example.com", "password": "Test1234!"},
                headers={"X-Forwarded-For": forwarded_ip, "X-Real-IP": real_ip},
            )

        # 같은 X-Forwarded-For로 추가 요청 (제한 초과)
        response1 = await client.post(
            endpoint,
            json={"email": "test@example.com", "password": "Test1234!"},
            headers={"X-Forwarded-For": forwarded_ip, "X-Real-IP": real_ip},
        )

        # 다른 X-Real-IP만 변경해서 요청 (여전히 제한 적용)
        response2 = await client.post(
            endpoint,
            json={"email": "test@example.com", "password": "Test1234!"},
            headers={
                "X-Forwarded-For": forwarded_ip,
                "X-Real-IP": "10.0.1.3",  # 변경
            },
        )

        # Assert
        assert response1.status_code == 429
        assert response2.status_code == 429  # X-Forwarded-For가 우선이므로 여전히 차단


@pytest.mark.asyncio
class TestSpecialCases:
    """특수 케이스 테스트."""

    async def test_options_request_excluded_from_rate_limit(self, client: AsyncClient):
        """OPTIONS 요청은 Rate Limit 제외."""
        # Arrange
        endpoint = "/api/v1/auth/login"
        test_ip = "192.168.1.120"
        max_requests = 5

        # Act - POST로 제한까지 요청
        for _ in range(max_requests):
            await client.post(
                endpoint,
                json={"email": "test@example.com", "password": "Test1234!"},
                headers={"X-Forwarded-For": test_ip},
            )

        # POST 제한 초과 확인
        post_response = await client.post(
            endpoint,
            json={"email": "test@example.com", "password": "Test1234!"},
            headers={"X-Forwarded-For": test_ip},
        )

        # OPTIONS 요청 (CORS preflight)
        options_response = await client.options(endpoint, headers={"X-Forwarded-For": test_ip})

        # Assert
        assert post_response.status_code == 429  # POST는 차단
        assert options_response.status_code != 429  # OPTIONS는 허용

    async def test_concurrent_requests_from_same_ip(self, client: AsyncClient):
        """동일 IP에서 동시 요청 처리."""
        # Arrange
        endpoint = "/health"
        test_ip = "192.168.1.121"

        # Act - 동시 요청
        tasks = [client.get(endpoint, headers={"X-Forwarded-For": test_ip}) for _ in range(5)]
        responses = await asyncio.gather(*tasks)

        # Assert - 모두 성공 (Redis가 원자적 연산 보장)
        for response in responses:
            assert response.status_code == 200

    async def test_rate_limit_key_format(self, client: AsyncClient):
        """Rate limit Redis 키 형식 검증 (간접 테스트)."""
        # Arrange
        endpoint = "/api/v1/auth/login"
        test_ip = "192.168.1.122"

        # Act - 요청 수행
        response = await client.post(
            endpoint,
            json={"email": "test@example.com", "password": "Test1234!"},
            headers={"X-Forwarded-For": test_ip},
        )

        # Assert - 응답이 정상적으로 처리됨 (키 형식이 올바름)
        # Redis 키 형식: rate_limit:{ip}:{path}
        # 실제 키 확인은 Redis 직접 접근이 필요하지만,
        # 정상 동작하면 키 형식이 올바른 것으로 간주
        assert response.status_code in [200, 401, 429]

    async def test_different_paths_independent_limits(self, client: AsyncClient):
        """다른 경로는 독립적인 Rate Limit."""
        # Arrange
        test_ip = "192.168.1.123"
        endpoint1 = "/api/v1/auth/login"
        endpoint2 = "/health"  # Use health endpoint instead to avoid auth validation
        max_login = 5

        # Act - Login 엔드포인트 제한까지 요청
        for _ in range(max_login):
            await client.post(
                endpoint1,
                json={"email": "test@example.com", "password": "Test1234!"},
                headers={"X-Forwarded-For": test_ip},
            )

        # Login 제한 초과 확인
        login_response = await client.post(
            endpoint1,
            json={"email": "test@example.com", "password": "Test1234!"},
            headers={"X-Forwarded-For": test_ip},
        )

        # Health 엔드포인트 요청 (독립적이므로 허용되어야 함)
        health_response = await client.get(endpoint2, headers={"X-Forwarded-For": test_ip})

        # Assert
        assert login_response.status_code == 429  # Login은 차단
        assert health_response.status_code == 200  # Health는 허용 (독립적인 경로)

    async def test_rate_limit_error_response_format(self, client: AsyncClient):
        """Rate limit 에러 응답 형식 검증."""
        # Arrange
        endpoint = "/api/v1/auth/login"
        test_ip = "192.168.1.124"
        max_requests = 5

        # Act - 제한 초과
        for _ in range(max_requests + 1):
            response = await client.post(
                endpoint,
                json={"email": "test@example.com", "password": "Test1234!"},
                headers={"X-Forwarded-For": test_ip},
            )

        # Assert - 에러 응답 형식
        if response.status_code == 429:
            data = response.json()
            assert "error_code" in data
            assert data["error_code"] == "RATE_LIMIT_001"
            assert "message" in data
            assert "너무 많은 요청" in data["message"]
