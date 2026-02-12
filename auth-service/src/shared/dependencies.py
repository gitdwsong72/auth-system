"""FastAPI 의존성 주입

인증/인가를 위한 FastAPI Depends 함수들을 정의합니다.
"""

import asyncpg
from fastapi import Depends, Header

from src.domains.users import repository as users_repository
from src.domains.users import service as users_service
from src.shared.database.connection import get_db_connection
from src.shared.exceptions import ForbiddenException, UnauthorizedException
from src.shared.security.jwt_handler import InvalidTokenError, TokenExpiredError, jwt_handler
from src.shared.security.redis_store import redis_store


def extract_bearer_token(authorization: str) -> str:
    """Authorization 헤더에서 Bearer 토큰을 추출한다.

    Args:
        authorization: Authorization 헤더 값

    Returns:
        토큰 문자열

    Raises:
        UnauthorizedException: 올바르지 않은 Authorization 헤더
    """
    if not authorization.startswith("Bearer "):
        raise UnauthorizedException(
            error_code="AUTH_007",
            message="인증이 필요합니다",
            details={"reason": "invalid_authorization_header"},
        )
    return authorization[7:].strip()


async def get_current_user(
    authorization: str = Header(..., description="Bearer 토큰"),
    conn: asyncpg.Connection = Depends(get_db_connection),
) -> dict:
    """현재 인증된 사용자 정보 조회

    Args:
        authorization: Authorization 헤더 (Bearer {token})
        conn: 데이터베이스 연결

    Returns:
        사용자 정보 딕셔너리 (id, email, is_active, roles, permissions)

    Raises:
        UnauthorizedException: 토큰이 유효하지 않거나 사용자를 찾을 수 없는 경우
    """
    # Bearer 토큰 추출
    token = extract_bearer_token(authorization)

    # 토큰 디코딩
    try:
        payload = jwt_handler.decode_token(token)
    except TokenExpiredError:
        raise UnauthorizedException(
            error_code="AUTH_002",
            message="토큰이 만료되었습니다",
        )
    except (InvalidTokenError, Exception):
        raise UnauthorizedException(
            error_code="AUTH_003",
            message="유효하지 않은 토큰입니다",
        )

    # Redis 블랙리스트 확인
    jti = payload.get("jti")
    if jti and await redis_store.is_blacklisted(jti):
        raise UnauthorizedException(
            error_code="AUTH_003",
            message="유효하지 않은 토큰입니다",
            details={"reason": "token_blacklisted"},
        )

    # 사용자 ID 추출
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedException(
            error_code="AUTH_003",
            message="유효하지 않은 토큰입니다",
            details={"reason": "missing_subject"},
        )

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise UnauthorizedException(
            error_code="AUTH_003",
            message="유효하지 않은 토큰입니다",
            details={"reason": "invalid_user_id"},
        )

    # Active token registry 확인 (revoke된 토큰 감지)
    if jti:
        is_active = await redis_store.is_token_active(user_id, jti)
        if not is_active:
            raise UnauthorizedException(
                error_code="AUTH_008",
                message="토큰이 취소되었습니다",
                details={"reason": "token_revoked"},
            )

    # users 테이블에서 사용자 조회
    user_row = await users_repository.get_user_by_id(conn, user_id)

    if not user_row:
        raise UnauthorizedException(
            error_code="USER_002",
            message="사용자를 찾을 수 없습니다",
        )

    # 역할 및 권한 조회 (캐시 활용)
    permissions_data = await users_service.get_user_permissions_with_cache(conn, user_id)
    roles = permissions_data["roles"]
    permissions = permissions_data["permissions"]

    return {
        "id": user_row["id"],
        "email": user_row["email"],
        "username": user_row["username"],
        "is_active": user_row["is_active"],
        "roles": roles,
        "permissions": permissions,
    }


async def get_current_active_user(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """활성화된 사용자만 허용

    Args:
        current_user: 현재 사용자 정보

    Returns:
        사용자 정보 딕셔너리

    Raises:
        UnauthorizedException: 비활성화된 계정인 경우
    """
    if not current_user["is_active"]:
        raise UnauthorizedException(
            error_code="AUTH_005",
            message="비활성화된 계정입니다",
        )
    return current_user


def require_permission(permission: str):
    """특정 권한을 요구하는 의존성 생성

    Args:
        permission: 필요한 권한 이름

    Returns:
        FastAPI 의존성 함수
    """

    async def permission_checker(
        current_user: dict = Depends(get_current_active_user),
    ) -> dict:
        """권한 확인"""
        if permission not in current_user["permissions"]:
            raise ForbiddenException(
                error_code="AUTH_008",
                message="권한이 부족합니다",
                details={"required_permission": permission},
            )
        return current_user

    return permission_checker
