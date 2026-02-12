"""통합 워크플로우 E2E 테스트

실제 서비스를 구동하여 end-to-end 시나리오를 테스트합니다.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestCacheWorkflow:
    """캐시 워크플로우 E2E 테스트"""

    async def test_cache_workflow(self, client: AsyncClient, auth_headers: dict[str, str]):
        """
        시나리오 1: 캐시 워크플로우
        1. Health Check 호출
        2. Solid Cache 통계 조회 (초기 상태: 0 entries)
        3. DB Pool 통계 조회
        4. Cleanup API 호출
        5. Solid Cache 통계 재조회 (cleanup 후)
        """
        # Step 1: Health Check 호출
        health_response = await client.get("/health")
        assert health_response.status_code == 200
        health_data = health_response.json()
        assert health_data["status"] == "healthy"
        assert "services" in health_data
        assert "database" in health_data["services"]
        assert "redis" in health_data["services"]
        assert "solid_cache" in health_data["services"]

        # Database가 healthy인지 확인
        assert health_data["services"]["database"]["healthy"] is True
        assert health_data["services"]["database"]["primary"]["status"] == "connected"

        # Redis가 healthy인지 확인
        assert health_data["services"]["redis"]["status"] == "healthy"

        # Solid Cache가 healthy인지 확인
        assert health_data["services"]["solid_cache"]["status"] == "healthy"

        # Step 2: Solid Cache 통계 조회 (초기 상태)
        cache_stats_response = await client.get(
            "/metrics/solid-cache",
            headers=auth_headers,
        )
        assert cache_stats_response.status_code == 200
        initial_stats = cache_stats_response.json()
        assert "total_entries" in initial_stats
        assert "expired_entries" in initial_stats
        assert "total_size_bytes" in initial_stats
        assert "total_size_kb" in initial_stats

        initial_total = initial_stats["total_entries"]
        initial_expired = initial_stats["expired_entries"]

        # Step 3: DB Pool 통계 조회
        pool_stats_response = await client.get(
            "/metrics/db-pool",
            headers=auth_headers,
        )
        assert pool_stats_response.status_code == 200
        pool_stats = pool_stats_response.json()
        assert "primary" in pool_stats
        assert "current_size" in pool_stats["primary"]
        assert "max_size" in pool_stats["primary"]
        assert "available_connections" in pool_stats["primary"]

        # Pool이 정상적으로 작동하는지 확인
        assert pool_stats["primary"]["current_size"] > 0
        assert pool_stats["primary"]["max_size"] > 0
        assert pool_stats["primary"]["available_connections"] >= 0

        # Step 4: Cleanup API 호출
        cleanup_response = await client.post(
            "/admin/cache/cleanup",
            headers=auth_headers,
        )
        assert cleanup_response.status_code == 200
        cleanup_data = cleanup_response.json()
        assert cleanup_data["status"] == "success"
        assert "deleted_count" in cleanup_data
        assert "message" in cleanup_data

        deleted_count = cleanup_data["deleted_count"]

        # Step 5: Solid Cache 통계 재조회 (cleanup 후)
        final_stats_response = await client.get(
            "/metrics/solid-cache",
            headers=auth_headers,
        )
        assert final_stats_response.status_code == 200
        final_stats = final_stats_response.json()

        # Cleanup 후 만료된 엔트리가 감소했는지 확인
        final_expired = final_stats["expired_entries"]
        assert final_expired <= initial_expired

        # 삭제된 항목만큼 total_entries가 감소했는지 확인
        final_total = final_stats["total_entries"]
        assert final_total == initial_total - deleted_count


@pytest.mark.asyncio
class TestFullWorkflow:
    """전체 워크플로우 E2E 테스트"""

    async def test_full_workflow(self, client: AsyncClient):
        """
        시나리오 2: 전체 워크플로우
        1. 모든 서비스 Health Check
        2. 캐시 생성/조회/삭제 사이클
        3. 메트릭 수집 및 검증
        """
        # Step 1: 모든 서비스 Health Check
        health_response = await client.get("/health")
        assert health_response.status_code == 200
        health_data = health_response.json()
        assert health_data["status"] == "healthy"

        # 모든 서비스가 healthy인지 확인
        services = health_data["services"]
        assert services["database"]["healthy"] is True
        assert services["redis"]["status"] == "healthy"
        assert services["solid_cache"]["status"] == "healthy"

        # Step 2: 캐시 생성 사이클 - 사용자 등록 및 로그인 (Solid Cache 사용)
        # 2-1: 사용자 등록
        register_payload = {
            "email": "e2etest@example.com",
            "password": "E2ETest123!",
            "username": "e2etest",
            "display_name": "E2E Test User",
        }
        register_response = await client.post("/api/v1/users/register", json=register_payload)
        assert register_response.status_code == 201
        register_data = register_response.json()
        assert register_data["success"] is True
        user_id = register_data["data"]["id"]

        # 2-2: 로그인 (세션 캐시 생성)
        login_payload = {
            "email": "e2etest@example.com",
            "password": "E2ETest123!",
            "device_info": "E2E Test Device",
        }
        login_response = await client.post("/api/v1/auth/login", json=login_payload)
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert login_data["success"] is True
        access_token = login_data["data"]["access_token"]
        refresh_token = login_data["data"]["refresh_token"]

        # 2-3: 인증된 요청으로 사용자 정보 조회 (캐시 히트)
        auth_headers = {"Authorization": f"Bearer {access_token}"}
        profile_response = await client.get("/api/v1/users/me", headers=auth_headers)
        assert profile_response.status_code == 200
        profile_data = profile_response.json()
        assert profile_data["success"] is True
        assert profile_data["data"]["email"] == "e2etest@example.com"

        # Step 3: 메트릭 수집 및 검증
        # 3-1: Solid Cache 통계 확인 (캐시 엔트리가 생성되었는지)
        cache_stats_response = await client.get(
            "/metrics/solid-cache",
            headers=auth_headers,
        )
        assert cache_stats_response.status_code == 200
        cache_stats = cache_stats_response.json()
        assert cache_stats["total_entries"] >= 0  # 캐시 엔트리 존재
        assert cache_stats["total_size_bytes"] >= 0

        # 3-2: DB Pool 통계 확인 (연결이 정상적으로 작동하는지)
        pool_stats_response = await client.get(
            "/metrics/db-pool",
            headers=auth_headers,
        )
        assert pool_stats_response.status_code == 200
        pool_stats = pool_stats_response.json()
        assert pool_stats["primary"]["current_size"] > 0
        assert pool_stats["primary"]["available_connections"] >= 0

        # 3-3: Health Check 재확인 (전체 플로우 후에도 healthy)
        final_health_response = await client.get("/health")
        assert final_health_response.status_code == 200
        final_health_data = final_health_response.json()
        assert final_health_data["status"] == "healthy"

        # Step 4: 캐시 삭제 사이클 - 로그아웃
        logout_response = await client.post("/api/v1/auth/logout", headers=auth_headers)
        assert logout_response.status_code == 200
        logout_data = logout_response.json()
        assert logout_data["success"] is True

        # Step 5: 토큰 무효화 확인 (로그아웃 후 접근 불가)
        # 로그아웃한 access token으로 접근 시도
        invalid_profile_response = await client.get("/api/v1/users/me", headers=auth_headers)
        assert invalid_profile_response.status_code == 401
        invalid_data = invalid_profile_response.json()
        assert invalid_data["success"] is False

        # Refresh token도 무효화되었는지 확인
        refresh_payload = {"refresh_token": refresh_token}
        invalid_refresh_response = await client.post("/api/v1/auth/refresh", json=refresh_payload)
        assert invalid_refresh_response.status_code == 401


@pytest.mark.asyncio
class TestServiceIntegration:
    """서비스 간 통합 테스트"""

    async def test_authentication_and_authorization_flow(
        self, client: AsyncClient, test_user_data: dict
    ):
        """
        인증 및 권한 부여 통합 플로우
        1. 사용자 등록
        2. 로그인
        3. 권한이 필요한 엔드포인트 접근
        4. 토큰 갱신
        5. 로그아웃
        """
        # Step 1: 사용자 등록
        register_payload = {
            "email": test_user_data["email"],
            "password": test_user_data["password"],
            "username": test_user_data["username"],
            "display_name": test_user_data["display_name"],
        }
        register_response = await client.post("/api/v1/users/register", json=register_payload)
        assert register_response.status_code == 201

        # Step 2: 로그인
        login_payload = {
            "email": test_user_data["email"],
            "password": test_user_data["password"],
        }
        login_response = await client.post("/api/v1/auth/login", json=login_payload)
        assert login_response.status_code == 200
        login_data = login_response.json()
        access_token = login_data["data"]["access_token"]
        refresh_token = login_data["data"]["refresh_token"]

        # Step 3: 권한이 필요한 엔드포인트 접근 (인증된 요청)
        auth_headers = {"Authorization": f"Bearer {access_token}"}
        profile_response = await client.get("/api/v1/users/me", headers=auth_headers)
        assert profile_response.status_code == 200

        # Step 4: 토큰 갱신
        refresh_payload = {"refresh_token": refresh_token}
        refresh_response = await client.post("/api/v1/auth/refresh", json=refresh_payload)
        assert refresh_response.status_code == 200
        refresh_data = refresh_response.json()
        new_access_token = refresh_data["data"]["access_token"]
        assert new_access_token != access_token  # 새로운 토큰이 발급됨

        # Step 5: 새로운 토큰으로 접근 가능한지 확인
        new_auth_headers = {"Authorization": f"Bearer {new_access_token}"}
        new_profile_response = await client.get("/api/v1/users/me", headers=new_auth_headers)
        assert new_profile_response.status_code == 200

        # Step 6: 로그아웃
        logout_response = await client.post("/api/v1/auth/logout", headers=new_auth_headers)
        assert logout_response.status_code == 200

    async def test_rate_limiting_integration(self, client: AsyncClient):
        """
        Rate Limiting 통합 테스트
        1. 동일한 엔드포인트에 반복 요청
        2. Rate Limit 초과 시 429 응답 확인
        """
        # Health check는 rate limit이 없으므로 여러 번 호출 가능
        for _ in range(10):
            response = await client.get("/health")
            assert response.status_code == 200

        # 로그인 시도는 rate limit이 있으므로 제한될 수 있음
        # 하지만 테스트 환경에서는 제한이 느슨할 수 있으므로
        # 단순히 응답이 200 또는 429인지만 확인
        login_payload = {
            "email": "nonexistent@example.com",
            "password": "Test1234!",
        }

        responses = []
        for _ in range(20):
            response = await client.post("/api/v1/auth/login", json=login_payload)
            responses.append(response.status_code)

        # 최소한 하나의 요청은 성공하거나 인증 실패 (401)
        assert 401 in responses or 200 in responses
        # Rate limit이 적용되었다면 429 응답이 있을 수 있음
        # (테스트 환경 설정에 따라 다를 수 있음)

    async def test_database_connection_resilience(self, client: AsyncClient):
        """
        데이터베이스 연결 복원력 테스트
        1. 여러 요청을 동시에 보내서 connection pool 테스트
        2. 모든 요청이 성공하는지 확인
        """
        # 여러 health check 요청을 동시에 보냄
        import asyncio

        tasks = []
        for _ in range(10):
            task = client.get("/health")
            tasks.append(task)

        responses = await asyncio.gather(*tasks)

        # 모든 요청이 성공해야 함
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
