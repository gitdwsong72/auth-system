"""System Performance and Load Tests

이 모듈은 auth-service의 성능 및 부하 테스트를 수행합니다.

테스트 항목:
1. 단일 요청 응답 시간 (baseline)
2. 10 concurrent 요청 처리
3. 50 concurrent 요청 처리
4. Solid Cache 히트/미스 응답 시간 비교
5. 메모리 사용량 확인

각 테스트에서 측정 항목:
- 평균 응답 시간
- 최대/최소 응답 시간
- 에러율
- 초당 요청 수 (RPS)
"""

import asyncio
import statistics
import time
from collections.abc import AsyncGenerator
from typing import Any

import psutil
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app


class PerformanceMetrics:
    """성능 메트릭 측정 및 계산 클래스"""

    def __init__(self):
        self.response_times: list[float] = []
        self.status_codes: list[int] = []
        self.errors: list[str] = []
        self.start_time: float = 0
        self.end_time: float = 0

    def record_request(self, duration: float, status_code: int, error: str | None = None):
        """요청 결과를 기록"""
        self.response_times.append(duration)
        self.status_codes.append(status_code)
        if error:
            self.errors.append(error)

    def start_timer(self):
        """타이머 시작"""
        self.start_time = time.time()

    def stop_timer(self):
        """타이머 종료"""
        self.end_time = time.time()

    def calculate_stats(self) -> dict[str, Any]:
        """통계 계산"""
        if not self.response_times:
            return {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "error_rate": 0.0,
                "avg_response_time_ms": 0.0,
                "min_response_time_ms": 0.0,
                "max_response_time_ms": 0.0,
                "median_response_time_ms": 0.0,
                "p95_response_time_ms": 0.0,
                "p99_response_time_ms": 0.0,
                "requests_per_second": 0.0,
                "total_duration_s": 0.0,
            }

        total_requests = len(self.response_times)
        successful_requests = sum(1 for code in self.status_codes if 200 <= code < 300)
        failed_requests = total_requests - successful_requests
        error_rate = (failed_requests / total_requests) * 100 if total_requests > 0 else 0.0

        response_times_ms = [rt * 1000 for rt in self.response_times]
        sorted_times = sorted(response_times_ms)

        total_duration = self.end_time - self.start_time
        rps = total_requests / total_duration if total_duration > 0 else 0.0

        # Percentile 계산
        p95_index = int(len(sorted_times) * 0.95)
        p99_index = int(len(sorted_times) * 0.99)

        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "error_rate": round(error_rate, 2),
            "avg_response_time_ms": round(statistics.mean(response_times_ms), 2),
            "min_response_time_ms": round(min(response_times_ms), 2),
            "max_response_time_ms": round(max(response_times_ms), 2),
            "median_response_time_ms": round(statistics.median(response_times_ms), 2),
            "p95_response_time_ms": round(sorted_times[p95_index], 2),
            "p99_response_time_ms": round(sorted_times[p99_index], 2),
            "requests_per_second": round(rps, 2),
            "total_duration_s": round(total_duration, 2),
        }


@pytest_asyncio.fixture(scope="function")
async def perf_client(setup_app_dependencies) -> AsyncGenerator[AsyncClient, None]:
    """성능 테스트용 HTTP 클라이언트 - 긴 타임아웃 설정"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=60.0,  # 성능 테스트는 더 긴 타임아웃 필요
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def test_user_token(perf_client: AsyncClient) -> str:
    """테스트용 사용자 생성 및 토큰 반환"""
    # 사용자 등록
    register_payload = {
        "email": "perftest@example.com",
        "password": "PerfTest123!",
        "username": "perftest",
        "display_name": "Perf Test User",
    }
    await perf_client.post("/api/v1/users/register", json=register_payload)

    # 로그인
    login_payload = {
        "email": "perftest@example.com",
        "password": "PerfTest123!",
    }
    response = await perf_client.post("/api/v1/auth/login", json=login_payload)
    data = response.json()
    return data["data"]["access_token"]


@pytest.mark.asyncio
class TestPerformanceBaseline:
    """단일 요청 성능 베이스라인 테스트"""

    async def test_health_check_baseline(self, perf_client: AsyncClient):
        """헬스 체크 엔드포인트 단일 요청 응답 시간"""
        metrics = PerformanceMetrics()
        metrics.start_timer()

        # 10회 반복 측정하여 평균 계산
        for _ in range(10):
            start = time.time()
            response = await perf_client.get("/health")
            duration = time.time() - start
            metrics.record_request(duration, response.status_code)

        metrics.stop_timer()
        stats = metrics.calculate_stats()

        # 결과 출력
        print("\n=== Health Check Baseline ===")
        print(f"Total Requests: {stats['total_requests']}")
        print(f"Success Rate: {100 - stats['error_rate']}%")
        print(f"Avg Response Time: {stats['avg_response_time_ms']} ms")
        print(f"Min/Max: {stats['min_response_time_ms']}/{stats['max_response_time_ms']} ms")
        print(f"Median: {stats['median_response_time_ms']} ms")

        # 성능 기준: 평균 응답 시간 < 100ms
        assert stats["avg_response_time_ms"] < 100, "Health check should respond within 100ms"
        assert stats["error_rate"] == 0, "No errors should occur"

    async def test_login_baseline(self, perf_client: AsyncClient):
        """로그인 엔드포인트 단일 요청 응답 시간"""
        # 테스트 사용자 생성
        register_payload = {
            "email": "loginbaseline@example.com",
            "password": "LoginTest123!",
            "username": "loginbaseline",
        }
        await perf_client.post("/api/v1/users/register", json=register_payload)

        metrics = PerformanceMetrics()
        metrics.start_timer()

        # 10회 로그인 테스트
        login_payload = {
            "email": "loginbaseline@example.com",
            "password": "LoginTest123!",
        }
        for _ in range(10):
            start = time.time()
            response = await perf_client.post("/api/v1/auth/login", json=login_payload)
            duration = time.time() - start
            metrics.record_request(duration, response.status_code)

        metrics.stop_timer()
        stats = metrics.calculate_stats()

        # 결과 출력
        print("\n=== Login Baseline ===")
        print(f"Total Requests: {stats['total_requests']}")
        print(f"Success Rate: {100 - stats['error_rate']}%")
        print(f"Avg Response Time: {stats['avg_response_time_ms']} ms")
        print(f"Min/Max: {stats['min_response_time_ms']}/{stats['max_response_time_ms']} ms")
        print(f"Median: {stats['median_response_time_ms']} ms")

        # 성능 기준: 평균 응답 시간 < 500ms (bcrypt 해싱 시간 포함)
        assert stats["avg_response_time_ms"] < 500, "Login should respond within 500ms"
        assert stats["error_rate"] == 0, "No errors should occur"


@pytest.mark.asyncio
class TestConcurrentLoad:
    """동시 요청 부하 테스트"""

    async def test_concurrent_10_health_checks(self, perf_client: AsyncClient):
        """10개 동시 헬스 체크 요청 처리"""
        metrics = PerformanceMetrics()
        metrics.start_timer()

        async def make_request():
            start = time.time()
            try:
                response = await perf_client.get("/health")
                duration = time.time() - start
                metrics.record_request(duration, response.status_code)
            except Exception as e:
                duration = time.time() - start
                metrics.record_request(duration, 500, str(e))

        # 10개 동시 요청
        tasks = [make_request() for _ in range(10)]
        await asyncio.gather(*tasks)

        metrics.stop_timer()
        stats = metrics.calculate_stats()

        # 결과 출력
        print("\n=== 10 Concurrent Health Checks ===")
        print(f"Total Requests: {stats['total_requests']}")
        print(f"Success Rate: {100 - stats['error_rate']}%")
        print(f"Avg Response Time: {stats['avg_response_time_ms']} ms")
        print(f"P95 Response Time: {stats['p95_response_time_ms']} ms")
        print(f"P99 Response Time: {stats['p99_response_time_ms']} ms")
        print(f"RPS: {stats['requests_per_second']}")

        # 성능 기준
        assert stats["error_rate"] < 5, "Error rate should be less than 5%"
        assert stats["p95_response_time_ms"] < 200, "P95 should be under 200ms"

    async def test_concurrent_50_health_checks(self, perf_client: AsyncClient):
        """50개 동시 헬스 체크 요청 처리"""
        metrics = PerformanceMetrics()
        metrics.start_timer()

        async def make_request():
            start = time.time()
            try:
                response = await perf_client.get("/health")
                duration = time.time() - start
                metrics.record_request(duration, response.status_code)
            except Exception as e:
                duration = time.time() - start
                metrics.record_request(duration, 500, str(e))

        # 50개 동시 요청
        tasks = [make_request() for _ in range(50)]
        await asyncio.gather(*tasks)

        metrics.stop_timer()
        stats = metrics.calculate_stats()

        # 결과 출력
        print("\n=== 50 Concurrent Health Checks ===")
        print(f"Total Requests: {stats['total_requests']}")
        print(f"Success Rate: {100 - stats['error_rate']}%")
        print(f"Avg Response Time: {stats['avg_response_time_ms']} ms")
        print(f"P95 Response Time: {stats['p95_response_time_ms']} ms")
        print(f"P99 Response Time: {stats['p99_response_time_ms']} ms")
        print(f"RPS: {stats['requests_per_second']}")

        # 성능 기준 - 더 관대하게 설정
        assert stats["error_rate"] < 10, "Error rate should be less than 10%"
        assert stats["p95_response_time_ms"] < 500, "P95 should be under 500ms"

    async def test_concurrent_10_authenticated_requests(
        self, perf_client: AsyncClient, test_user_token: str
    ):
        """10개 동시 인증 요청 처리"""
        metrics = PerformanceMetrics()
        metrics.start_timer()

        async def make_request():
            start = time.time()
            try:
                headers = {"Authorization": f"Bearer {test_user_token}"}
                response = await perf_client.get("/api/v1/users/me", headers=headers)
                duration = time.time() - start
                metrics.record_request(duration, response.status_code)
            except Exception as e:
                duration = time.time() - start
                metrics.record_request(duration, 500, str(e))

        # 10개 동시 요청
        tasks = [make_request() for _ in range(10)]
        await asyncio.gather(*tasks)

        metrics.stop_timer()
        stats = metrics.calculate_stats()

        # 결과 출력
        print("\n=== 10 Concurrent Authenticated Requests ===")
        print(f"Total Requests: {stats['total_requests']}")
        print(f"Success Rate: {100 - stats['error_rate']}%")
        print(f"Avg Response Time: {stats['avg_response_time_ms']} ms")
        print(f"P95 Response Time: {stats['p95_response_time_ms']} ms")
        print(f"RPS: {stats['requests_per_second']}")

        # 성능 기준
        assert stats["error_rate"] < 5, "Error rate should be less than 5%"
        assert stats["p95_response_time_ms"] < 300, "P95 should be under 300ms"


@pytest.mark.asyncio
class TestSolidCachePerformance:
    """Solid Cache 히트/미스 응답 시간 비교"""

    async def test_cache_hit_vs_miss_performance(self, perf_client: AsyncClient):
        """캐시 히트 vs 미스 응답 시간 비교"""
        from src.shared.database import get_solid_cache

        cache = get_solid_cache()

        # 캐시 클리어
        await cache.delete("test:perf:*")

        # 1. 캐시 미스 성능 측정
        miss_metrics = PerformanceMetrics()
        miss_metrics.start_timer()

        for i in range(10):
            key = f"test:perf:miss:{i}"
            start = time.time()
            result = await cache.get(key)
            duration = time.time() - start
            miss_metrics.record_request(duration, 200 if result is None else 500)

        miss_metrics.stop_timer()
        miss_stats = miss_metrics.calculate_stats()

        # 2. 캐시 데이터 생성
        for i in range(10):
            key = f"test:perf:hit:{i}"
            await cache.set(key, f"value_{i}", ttl_seconds=60)

        # 3. 캐시 히트 성능 측정
        hit_metrics = PerformanceMetrics()
        hit_metrics.start_timer()

        for i in range(10):
            key = f"test:perf:hit:{i}"
            start = time.time()
            result = await cache.get(key)
            duration = time.time() - start
            hit_metrics.record_request(duration, 200 if result is not None else 404)

        hit_metrics.stop_timer()
        hit_stats = hit_metrics.calculate_stats()

        # 결과 출력
        print("\n=== Solid Cache Performance ===")
        print(f"Cache MISS - Avg: {miss_stats['avg_response_time_ms']} ms")
        print(f"Cache HIT  - Avg: {hit_stats['avg_response_time_ms']} ms")
        print(
            f"Speed Improvement: {round(miss_stats['avg_response_time_ms'] / hit_stats['avg_response_time_ms'], 2)}x"
        )

        # 캐시 히트가 미스보다 빠르거나 비슷해야 함
        assert hit_stats["avg_response_time_ms"] <= miss_stats["avg_response_time_ms"] * 1.5
        assert hit_stats["error_rate"] == 0

        # 정리
        await cache.delete("test:perf:*")

    async def test_cache_json_performance(self, perf_client: AsyncClient):
        """JSON 캐시 성능 테스트"""
        from src.shared.database import get_solid_cache

        cache = get_solid_cache()

        # 테스트 데이터
        test_data = {
            "user_id": 12345,
            "username": "perftest",
            "email": "perf@example.com",
            "roles": ["user", "admin"],
            "permissions": ["read", "write", "delete"],
        }

        metrics = PerformanceMetrics()
        metrics.start_timer()

        # 10회 set + get 반복
        for i in range(10):
            key = f"test:json:perf:{i}"

            # Set
            start = time.time()
            await cache.set_json(key, test_data, ttl_seconds=60)
            set_duration = time.time() - start
            metrics.record_request(set_duration, 200)

            # Get
            start = time.time()
            result = await cache.get_json(key)
            get_duration = time.time() - start
            metrics.record_request(get_duration, 200 if result else 404)

        metrics.stop_timer()
        stats = metrics.calculate_stats()

        # 결과 출력
        print("\n=== JSON Cache Performance ===")
        print(f"Total Operations: {stats['total_requests']} (set + get)")
        print(f"Avg Time per Operation: {stats['avg_response_time_ms']} ms")
        print(f"P95: {stats['p95_response_time_ms']} ms")

        # 성능 기준
        assert stats["error_rate"] == 0
        assert stats["avg_response_time_ms"] < 50, "JSON operations should be fast"

        # 정리
        await cache.delete("test:json:perf:*")


@pytest.mark.asyncio
class TestMemoryUsage:
    """메모리 사용량 테스트"""

    async def test_memory_usage_under_load(self, perf_client: AsyncClient, test_user_token: str):
        """부하 상황에서 메모리 사용량 확인"""
        process = psutil.Process()

        # 초기 메모리 사용량
        initial_memory_mb = process.memory_info().rss / 1024 / 1024

        # 100개 동시 요청 실행
        async def make_request():
            headers = {"Authorization": f"Bearer {test_user_token}"}
            await perf_client.get("/api/v1/users/me", headers=headers)

        tasks = [make_request() for _ in range(100)]
        await asyncio.gather(*tasks, return_exceptions=True)

        # 최종 메모리 사용량
        final_memory_mb = process.memory_info().rss / 1024 / 1024
        memory_increase_mb = final_memory_mb - initial_memory_mb

        # 결과 출력
        print("\n=== Memory Usage Under Load ===")
        print(f"Initial Memory: {round(initial_memory_mb, 2)} MB")
        print(f"Final Memory: {round(final_memory_mb, 2)} MB")
        print(f"Memory Increase: {round(memory_increase_mb, 2)} MB")

        # 메모리 증가가 과도하지 않아야 함 (100MB 이하)
        assert memory_increase_mb < 100, "Memory increase should be less than 100MB"

    async def test_cache_memory_growth(self, perf_client: AsyncClient):
        """캐시 사용 시 메모리 증가량 확인"""
        from src.shared.database import get_solid_cache

        cache = get_solid_cache()
        process = psutil.Process()

        # 초기 메모리
        initial_memory_mb = process.memory_info().rss / 1024 / 1024

        # 1000개 캐시 엔트리 생성
        for i in range(1000):
            key = f"test:memory:entry:{i}"
            value = f"value_{i}" * 100  # 약 600 bytes per entry
            await cache.set(key, value, ttl_seconds=60)

        # 캐시 통계 조회
        stats = await cache.get_stats()
        final_memory_mb = process.memory_info().rss / 1024 / 1024
        memory_increase_mb = final_memory_mb - initial_memory_mb

        # 결과 출력
        print("\n=== Cache Memory Growth ===")
        print(f"Total Cache Entries: {stats['total_entries']}")
        print(f"Cache Size: {round(stats['total_size_bytes'] / 1024, 2)} KB")
        print(f"Process Memory Increase: {round(memory_increase_mb, 2)} MB")

        # 정리
        await cache.delete("test:memory:entry:*")

        # 메모리 증가가 합리적인 범위 내
        assert stats["total_entries"] >= 1000
        assert memory_increase_mb < 50, "Memory increase should be reasonable"


@pytest.mark.asyncio
class TestRateLimiterPerformance:
    """Rate Limiter 성능 테스트"""

    async def test_rate_limiter_overhead(self, perf_client: AsyncClient):
        """Rate Limiter 오버헤드 측정"""
        metrics = PerformanceMetrics()
        metrics.start_timer()

        # 동일 IP에서 연속 요청 (Rate Limiter 동작)
        for _ in range(10):
            start = time.time()
            response = await perf_client.get("/health")
            duration = time.time() - start
            metrics.record_request(duration, response.status_code)

        metrics.stop_timer()
        stats = metrics.calculate_stats()

        # 결과 출력
        print("\n=== Rate Limiter Overhead ===")
        print(f"Total Requests: {stats['total_requests']}")
        print(f"Avg Response Time: {stats['avg_response_time_ms']} ms")
        print(f"P95: {stats['p95_response_time_ms']} ms")

        # Rate Limiter가 있어도 응답 시간이 합리적이어야 함
        assert stats["avg_response_time_ms"] < 150, "Rate limiter overhead should be minimal"
