"""
Security Headers Middleware

보안 헤더를 모든 응답에 추가하여 XSS, Clickjacking 등 공격 방어
"""

from collections.abc import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.shared.security.config import security_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    보안 헤더 미들웨어

    OWASP 권장 보안 헤더를 모든 응답에 자동 추가
    프로덕션 환경에서만 HSTS 헤더 추가 (localhost HTTPS 오류 방지)
    """

    async def dispatch(self, request: Request, call_next: Callable):
        """
        요청 처리 후 보안 헤더 추가

        Args:
            request: FastAPI Request 객체
            call_next: 다음 미들웨어/핸들러

        Returns:
            보안 헤더가 추가된 Response 객체
        """
        response = await call_next(request)

        # X-Content-Type-Options: MIME 타입 스니핑 방지
        response.headers["X-Content-Type-Options"] = "nosniff"

        # X-Frame-Options: Clickjacking 방어
        response.headers["X-Frame-Options"] = "DENY"

        # X-XSS-Protection: 레거시 브라우저 XSS 필터 활성화
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Strict-Transport-Security: HTTPS 강제 (프로덕션 전용)
        # 개발 환경에서는 localhost HTTPS 오류 방지를 위해 제외
        if security_settings.env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Content-Security-Policy: XSS 및 데이터 주입 공격 방어
        # Swagger UI (/docs, /redoc)는 CDN 스크립트 허용
        if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https:; "
                "font-src 'self' https://cdn.jsdelivr.net; "
                "connect-src 'self'; "
                "frame-ancestors 'none'"
            )
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none'"
            )

        # Referrer-Policy: Referer 헤더 정책
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions-Policy: 브라우저 기능 제어 (구 Feature-Policy)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
        )

        return response
