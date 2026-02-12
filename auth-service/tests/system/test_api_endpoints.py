"""API 엔드포인트 시스템 테스트.

이 모듈은 모든 공개 API 엔드포인트의 기본 동작을 검증합니다:
- HTTP 상태 코드
- 응답 JSON 스키마
- 응답 시간
"""

import time
from typing import Any

import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    """Health Check 엔드포인트 테스트."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, client: AsyncClient) -> None:
        """GET /health - 정상 응답 테스트."""
        # Arrange
        start_time = time.time()

        # Act
        response = await client.get("/health")
        response_time = time.time() - start_time

        # Assert - HTTP 상태 코드
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        # Assert - JSON 응답
        data = response.json()
        assert isinstance(data, dict), "Response should be a JSON object"

        # Assert - 응답 스키마
        assert "status" in data, "Response should contain 'status'"
        assert "services" in data, "Response should contain 'services'"

        # Assert - 상태 값
        assert data["status"] in ["healthy", "unhealthy"], f"Invalid status: {data['status']}"

        # Assert - 서비스 체크
        services = data["services"]
        assert isinstance(services, dict), "Services should be a dictionary"
        assert "database" in services, "Services should contain 'database'"
        assert "redis" in services, "Services should contain 'redis'"
        assert "solid_cache" in services, "Services should contain 'solid_cache'"

        # Assert - Database 상태
        db_status = services["database"]
        assert "healthy" in db_status, "Database status should contain 'healthy'"
        assert isinstance(db_status["healthy"], bool), "Database healthy should be boolean"

        # Assert - Redis 상태
        redis_status = services["redis"]
        assert "status" in redis_status, "Redis status should contain 'status'"

        # Assert - Solid Cache 상태
        cache_status = services["solid_cache"]
        assert "status" in cache_status, "Solid Cache status should contain 'status'"

        # Assert - 응답 시간 (1초 이내)
        assert response_time < 1.0, f"Response time too slow: {response_time:.3f}s"

        print(f"✓ Health check responded in {response_time:.3f}s")
        print(f"✓ Overall status: {data['status']}")
        print(f"✓ Services checked: {len(services)}")

    @pytest.mark.asyncio
    async def test_health_check_response_structure(self, client: AsyncClient) -> None:
        """GET /health - 응답 구조 상세 검증."""
        # Act
        response = await client.get("/health")
        data = response.json()

        # Assert - 전체 구조
        required_top_level_keys = {"status", "services"}
        actual_keys = set(data.keys())
        assert required_top_level_keys.issubset(
            actual_keys
        ), f"Missing keys: {required_top_level_keys - actual_keys}"

        # Assert - Services 구조
        services = data["services"]
        required_services = {"database", "redis", "solid_cache"}
        actual_services = set(services.keys())
        assert required_services.issubset(
            actual_services
        ), f"Missing services: {required_services - actual_services}"

        print("✓ Response structure validated")
        print(f"✓ All required services present: {', '.join(required_services)}")


class TestSolidCacheMetricsEndpoint:
    """Solid Cache 메트릭 엔드포인트 테스트."""

    @pytest.mark.asyncio
    async def test_solid_cache_metrics_without_auth(self, client: AsyncClient) -> None:
        """GET /metrics/solid-cache - 인증 없이 접근 시 422."""
        # Act
        response = await client.get("/metrics/solid-cache")

        # Assert
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"

        data = response.json()
        assert (
            "error" in data or "detail" in data
        ), "Error response should contain 'error' or 'detail'"

        print("✓ Unauthorized access properly rejected")

    @pytest.mark.asyncio
    async def test_solid_cache_metrics_with_auth(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """GET /metrics/solid-cache - 인증된 사용자 접근 테스트."""
        # Arrange
        start_time = time.time()

        # Act
        response = await client.get("/metrics/solid-cache", headers=auth_headers)
        response_time = time.time() - start_time

        # Assert - HTTP 상태 코드 (권한 부족 또는 성공)
        assert response.status_code in [
            200,
            403,
        ], f"Expected 200 or 403, got {response.status_code}"

        if response.status_code == 403:
            # 권한 부족 - 정상 동작
            data = response.json()
            assert (
                "error" in data or "detail" in data
            ), "Error response should contain 'error' or 'detail'"
            print("✓ Forbidden access (insufficient permissions)")
            return

        # Assert - 성공 응답 (system:metrics 권한 보유 시)
        data = response.json()
        assert isinstance(data, dict), "Response should be a JSON object"

        # Assert - 응답 스키마
        required_keys = {"total_entries", "expired_entries", "total_size_bytes", "total_size_kb"}
        actual_keys = set(data.keys())
        assert required_keys.issubset(actual_keys), f"Missing keys: {required_keys - actual_keys}"

        # Assert - 데이터 타입
        assert isinstance(data["total_entries"], int), "total_entries should be integer"
        assert isinstance(data["expired_entries"], int), "expired_entries should be integer"
        assert isinstance(data["total_size_bytes"], int), "total_size_bytes should be integer"
        assert isinstance(data["total_size_kb"], (int, float)), "total_size_kb should be number"

        # Assert - 값 범위
        assert data["total_entries"] >= 0, "total_entries should be non-negative"
        assert data["expired_entries"] >= 0, "expired_entries should be non-negative"
        assert data["total_size_bytes"] >= 0, "total_size_bytes should be non-negative"

        # Assert - 응답 시간 (500ms 이내)
        assert response_time < 0.5, f"Response time too slow: {response_time:.3f}s"

        print(f"✓ Solid Cache metrics responded in {response_time:.3f}s")
        print(f"✓ Total entries: {data['total_entries']}")
        print(f"✓ Expired entries: {data['expired_entries']}")
        print(f"✓ Cache size: {data['total_size_kb']:.2f} KB")


class TestDBPoolMetricsEndpoint:
    """DB Pool 메트릭 엔드포인트 테스트."""

    @pytest.mark.asyncio
    async def test_db_pool_metrics_without_auth(self, client: AsyncClient) -> None:
        """GET /metrics/db-pool - 인증 없이 접근 시 422."""
        # Act
        response = await client.get("/metrics/db-pool")

        # Assert
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"

        data = response.json()
        assert (
            "error" in data or "detail" in data
        ), "Error response should contain 'error' or 'detail'"

        print("✓ Unauthorized access properly rejected")

    @pytest.mark.asyncio
    async def test_db_pool_metrics_with_auth(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """GET /metrics/db-pool - 인증된 사용자 접근 테스트."""
        # Arrange
        start_time = time.time()

        # Act
        response = await client.get("/metrics/db-pool", headers=auth_headers)
        response_time = time.time() - start_time

        # Assert - HTTP 상태 코드 (권한 부족 또는 성공)
        assert response.status_code in [
            200,
            403,
        ], f"Expected 200 or 403, got {response.status_code}"

        if response.status_code == 403:
            # 권한 부족 - 정상 동작
            data = response.json()
            assert (
                "error" in data or "detail" in data
            ), "Error response should contain 'error' or 'detail'"
            print("✓ Forbidden access (insufficient permissions)")
            return

        # Assert - 성공 응답 (system:metrics 권한 보유 시)
        data = response.json()
        assert isinstance(data, dict), "Response should be a JSON object"

        # Assert - Primary Pool 통계
        assert "primary" in data, "Response should contain 'primary' pool stats"
        primary = data["primary"]

        required_keys = {
            "size",
            "min_size",
            "max_size",
            "free_connections",
            "active_connections",
        }
        actual_keys = set(primary.keys())
        assert required_keys.issubset(actual_keys), f"Missing keys: {required_keys - actual_keys}"

        # Assert - 데이터 타입
        assert isinstance(primary["size"], int), "size should be integer"
        assert isinstance(primary["min_size"], int), "min_size should be integer"
        assert isinstance(primary["max_size"], int), "max_size should be integer"
        assert isinstance(primary["free_connections"], int), "free_connections should be integer"
        assert isinstance(
            primary["active_connections"], int
        ), "active_connections should be integer"

        # Assert - 값 범위
        assert primary["size"] >= 0, "size should be non-negative"
        assert primary["min_size"] >= 0, "min_size should be non-negative"
        assert primary["max_size"] > 0, "max_size should be positive"
        assert primary["free_connections"] >= 0, "free_connections should be non-negative"
        assert primary["active_connections"] >= 0, "active_connections should be non-negative"

        # Assert - 논리적 관계
        assert primary["size"] <= primary["max_size"], "size should not exceed max_size"
        assert (
            primary["free_connections"] + primary["active_connections"] == primary["size"]
        ), "free + active should equal total size"

        # Assert - 응답 시간 (500ms 이내)
        assert response_time < 0.5, f"Response time too slow: {response_time:.3f}s"

        print(f"✓ DB Pool metrics responded in {response_time:.3f}s")
        print(f"✓ Pool size: {primary['size']}/{primary['max_size']}")
        print(f"✓ Free connections: {primary['free_connections']}")
        print(f"✓ Active connections: {primary['active_connections']}")

    @pytest.mark.asyncio
    async def test_db_pool_metrics_replica_optional(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """GET /metrics/db-pool - Replica Pool은 선택적."""
        # Act
        response = await client.get("/metrics/db-pool", headers=auth_headers)

        if response.status_code == 403:
            # 권한 부족 - 테스트 스킵
            pytest.skip("Insufficient permissions for metrics endpoint")

        # Assert
        data = response.json()

        # Replica는 선택적이지만, 존재하면 구조 검증
        if "replica" in data:
            replica = data["replica"]
            assert isinstance(replica, dict), "replica should be a dictionary"

            required_keys = {
                "size",
                "min_size",
                "max_size",
                "free_connections",
                "active_connections",
            }
            actual_keys = set(replica.keys())
            assert required_keys.issubset(
                actual_keys
            ), f"Missing replica keys: {required_keys - actual_keys}"

            print("✓ Replica pool configured")
            print(f"✓ Replica size: {replica['size']}/{replica['max_size']}")
        else:
            print("✓ No replica pool configured (single DB mode)")


class TestEndpointPerformance:
    """엔드포인트 성능 통합 테스트."""

    @pytest.mark.asyncio
    async def test_all_endpoints_response_time(self, client: AsyncClient) -> None:
        """모든 공개 엔드포인트의 응답 시간 테스트."""
        endpoints = [
            ("/health", "GET", None),
        ]

        results: list[dict[str, Any]] = []

        for url, method, headers in endpoints:
            start_time = time.time()

            if method == "GET":
                response = await client.get(url, headers=headers)
            else:
                response = await client.post(url, headers=headers)

            response_time = time.time() - start_time

            results.append(
                {
                    "endpoint": url,
                    "method": method,
                    "status_code": response.status_code,
                    "response_time": response_time,
                }
            )

            # 모든 엔드포인트는 2초 이내에 응답해야 함
            assert response_time < 2.0, f"{url} too slow: {response_time:.3f}s"

        # 결과 출력
        print("\n=== Endpoint Performance Summary ===")
        for result in results:
            print(
                f"  {result['method']} {result['endpoint']}: "
                f"{result['response_time']:.3f}s (HTTP {result['status_code']})"
            )

        avg_time = sum(r["response_time"] for r in results) / len(results)
        print(f"\n  Average response time: {avg_time:.3f}s")
        print("=" * 40)
