"""CSRF Protection for state-changing operations

Double Submit Cookie 패턴을 사용한 CSRF 방어
JWT 기반 API에서 추가 보호 계층 제공
"""

import secrets
from typing import Optional

from fastapi import Header, HTTPException, status


class CSRFProtection:
    """CSRF 토큰 생성 및 검증"""

    @staticmethod
    def generate_token() -> str:
        """CSRF 토큰 생성

        Returns:
            32바이트 hex 형식의 안전한 랜덤 토큰
        """
        return secrets.token_hex(32)

    @staticmethod
    def validate_token(
        token_from_header: Optional[str],
        token_from_cookie: Optional[str],
    ) -> None:
        """CSRF 토큰 검증 (Double Submit Cookie 패턴)

        Args:
            token_from_header: X-CSRF-Token 헤더 값
            token_from_cookie: CSRF-Token 쿠키 값

        Raises:
            HTTPException: 토큰이 없거나 일치하지 않는 경우
        """
        # 토큰이 없는 경우
        if not token_from_header or not token_from_cookie:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": "CSRF_001",
                    "message": "CSRF 토큰이 필요합니다",
                },
            )

        # 토큰이 일치하지 않는 경우
        if not secrets.compare_digest(token_from_header, token_from_cookie):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": "CSRF_002",
                    "message": "유효하지 않은 CSRF 토큰입니다",
                },
            )


def require_csrf_token(
    x_csrf_token: Optional[str] = Header(None, alias="X-CSRF-Token"),
    csrf_token_cookie: Optional[str] = Header(None, alias="Cookie"),
) -> None:
    """CSRF 토큰 필수 의존성

    POST/PUT/DELETE/PATCH 엔드포인트에서 사용

    Args:
        x_csrf_token: X-CSRF-Token 헤더
        csrf_token_cookie: Cookie 헤더 (CSRF-Token 추출)

    Raises:
        HTTPException: CSRF 검증 실패
    """
    # Cookie 헤더에서 CSRF-Token 추출
    cookie_token = None
    if csrf_token_cookie:
        for cookie in csrf_token_cookie.split(";"):
            cookie = cookie.strip()
            if cookie.startswith("CSRF-Token="):
                cookie_token = cookie.split("=", 1)[1]
                break

    CSRFProtection.validate_token(x_csrf_token, cookie_token)


# 사용 예시:
# @app.post("/api/v1/users", dependencies=[Depends(require_csrf_token)])
# async def create_user(...):
#     pass
