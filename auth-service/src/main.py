"""FastAPI 애플리케이션 진입점 - MSA 인증/인가 서비스."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from src.shared.database import db_pool
from src.shared.logging import configure_logging, get_logger
from src.shared.middleware.backpressure import BackpressureMiddleware
from src.shared.middleware.rate_limiter import RateLimitMiddleware
from src.shared.middleware.security_headers import SecurityHeadersMiddleware
from src.shared.security import redis_store
from src.shared.security.config import backpressure_settings, cors_settings, security_settings

# Configure structured logging
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """애플리케이션 생명주기 관리."""
    from src.shared.database import SolidCacheManager
    from src.shared.tasks import cache_cleanup_task

    logger.info("application_startup", environment=security_settings.env)
    await db_pool.initialize()
    await redis_store.initialize()

    # Solid Cache 싱글톤 초기화
    SolidCacheManager.initialize(db_pool._primary_pool)
    logger.info("solid_cache_initialized", message="Solid Cache singleton initialized")

    # Solid Cache cleanup 백그라운드 태스크 시작
    await cache_cleanup_task.start()

    logger.info("application_ready", message="All services initialized")
    yield
    logger.info("application_shutdown", message="Shutting down gracefully")

    # Solid Cache cleanup 백그라운드 태스크 중지
    await cache_cleanup_task.stop()

    await redis_store.close()
    await db_pool.close()
    logger.info("application_stopped")


app = FastAPI(
    title="Auth Service API",
    description="MSA 인증/인가 서비스 - OAuth 2.0 + OIDC",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 설정 (최소 권한 원칙)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_settings.allowed_origins,
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "PATCH",
    ],  # 필요한 메서드만 허용
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "X-Request-ID",
        "X-CSRF-Token",
    ],  # 필요한 헤더만 허용
    expose_headers=["X-Request-ID"],
    max_age=600,  # Preflight 캐시 10분
)

# Backpressure 미들웨어 (시스템 과부하 방지) - 가장 먼저 적용
if backpressure_settings.enable_backpressure:
    logger.info(
        "backpressure_enabled",
        max_concurrent=backpressure_settings.max_concurrent,
        queue_capacity=backpressure_settings.queue_capacity,
    )
    app.add_middleware(
        BackpressureMiddleware,
        max_concurrent=backpressure_settings.max_concurrent,
        queue_capacity=backpressure_settings.queue_capacity,
        wait_timeout=backpressure_settings.wait_timeout,
        reject_threshold=backpressure_settings.reject_threshold,
    )

# Rate Limiting 미들웨어 추가 (브루트포스/DDoS 방어)
app.add_middleware(RateLimitMiddleware)

# 보안 헤더 미들웨어 (XSS, Clickjacking 방어)
app.add_middleware(SecurityHeadersMiddleware)

# 프로덕션 환경 보안 미들웨어
if security_settings.env == "production":
    # HTTPS 강제 리다이렉트
    app.add_middleware(HTTPSRedirectMiddleware)

    # 신뢰할 수 있는 호스트만 허용
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=security_settings.allowed_hosts)

# 도메인 라우터 등록
from src.domains.authentication.router import router as auth_router
from src.domains.users.router import router as users_router

# from src.domains.roles.router import router as roles_router
# from src.domains.oauth.router import router as oauth_router
# from src.domains.mfa.router import router as mfa_router
# from src.domains.api_keys.router import router as api_keys_router
from src.shared.dependencies import require_permission
from src.shared.exceptions import register_exception_handlers

# 예외 핸들러 등록
register_exception_handlers(app)

# 라우터 등록
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users_router, prefix="/api/v1/users", tags=["Users"])

# app.include_router(roles_router, prefix="/api/v1/roles", tags=["Roles"])
# app.include_router(oauth_router, prefix="/api/v1/oauth", tags=["OAuth"])
# app.include_router(mfa_router, prefix="/api/v1/mfa", tags=["MFA"])
# app.include_router(api_keys_router, prefix="/api/v1/api-keys", tags=["API Keys"])


@app.get("/health")
async def health_check() -> dict:
    """
    헬스 체크 엔드포인트.

    데이터베이스, Redis, Solid Cache 연결 상태를 확인한다.

    Returns:
        상태 정보 딕셔너리
    """
    result = {
        "status": "healthy",
        "services": {},
    }

    # Database Health Check
    db_health = await db_pool.health_check()
    result["services"]["database"] = db_health

    if not db_health.get("healthy"):
        result["status"] = "unhealthy"

    # Redis Health Check
    try:
        await redis_store.client.ping()
        result["services"]["redis"] = {
            "status": "healthy",
        }
    except Exception as e:
        result["status"] = "unhealthy"
        result["services"]["redis"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # Solid Cache Health Check
    try:
        from src.shared.database import get_solid_cache

        solid_cache = get_solid_cache()
        stats = await solid_cache.get_stats()

        result["services"]["solid_cache"] = {
            "status": "healthy",
            "total_entries": stats["total_entries"],
            "expired_entries": stats["expired_entries"],
            "total_size_kb": round(stats["total_size_bytes"] / 1024, 2),
        }
    except Exception as e:
        result["status"] = "unhealthy"
        result["services"]["solid_cache"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    return result


@app.get("/metrics/db-pool")
async def get_db_pool_metrics(
    _: dict = Depends(require_permission("system:metrics")),
) -> dict:
    """
    Connection Pool 통계 엔드포인트.

    현재 Connection Pool의 사용 현황을 반환한다.

    Returns:
        Connection Pool 통계 딕셔너리
    """
    return db_pool.get_pool_stats()


@app.get("/metrics/solid-cache")
async def get_solid_cache_metrics(
    _: dict = Depends(require_permission("system:metrics")),
) -> dict:
    """
    Solid Cache 통계 엔드포인트.

    현재 Solid Cache의 사용 현황을 반환한다.

    Returns:
        Solid Cache 통계 딕셔너리
    """
    from src.shared.database import get_solid_cache

    solid_cache = get_solid_cache()
    stats = await solid_cache.get_stats()

    return {
        "total_entries": stats["total_entries"],
        "expired_entries": stats["expired_entries"],
        "total_size_bytes": stats["total_size_bytes"],
        "total_size_kb": round(stats["total_size_bytes"] / 1024, 2),
    }


@app.post("/admin/cache/cleanup")
async def manual_cache_cleanup(
    _: dict = Depends(require_permission("system:admin")),
) -> dict:
    """
    Solid Cache 수동 정리 엔드포인트.

    만료된 캐시 엔트리를 즉시 삭제한다.

    Returns:
        삭제된 엔트리 수
    """
    from src.shared.tasks import cache_cleanup_task

    deleted_count = await cache_cleanup_task.manual_cleanup()

    return {
        "status": "success",
        "deleted_count": deleted_count,
        "message": f"Deleted {deleted_count} expired cache entries",
    }
