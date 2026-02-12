"""FastAPI 의존성 주입 헬퍼 모듈.

인증 및 권한 검증을 위한 FastAPI Depends 함수를 제공합니다.
미들웨어에서 설정한 request.state.user를 기반으로 동작합니다.

Example:
    >>> from fastapi import APIRouter, Depends
    >>> from auth_sdk import require_auth, require_permission, CurrentUser
    >>>
    >>> router = APIRouter()
    >>>
    >>> @router.get("/me")
    >>> async def get_me(user: CurrentUser = Depends(require_auth)):
    ...     return user
    >>>
    >>> @router.get("/admin")
    >>> async def admin_only(user: CurrentUser = Depends(require_permission("admin:read"))):
    ...     return user
"""

from collections.abc import Callable

from fastapi import Depends, Request

from auth_sdk.exceptions import AuthenticationError, PermissionDeniedError
from auth_sdk.models import CurrentUser


async def require_auth(request: Request) -> CurrentUser:
    """인증된 사용자를 요구하는 의존성 함수.

    미들웨어에서 설정한 request.state.user를 반환합니다.
    인증되지 않은 경우 AuthenticationError를 발생시킵니다.

    Args:
        request: FastAPI 요청 객체

    Returns:
        현재 인증된 사용자 정보

    Raises:
        AuthenticationError: 인증되지 않은 요청인 경우
    """
    user: CurrentUser | None = getattr(request.state, "user", None)
    if user is None:
        raise AuthenticationError("인증이 필요합니다")
    return user


def require_permission(permission: str) -> Callable[..., CurrentUser]:
    """특정 권한을 요구하는 의존성 함수 팩토리.

    사용자가 지정된 권한을 보유하고 있는지 확인합니다.
    슈퍼유저는 모든 권한을 자동으로 보유합니다.

    Args:
        permission: 필요한 권한 문자열 (예: "users:read", "admin:write")

    Returns:
        FastAPI Depends에서 사용할 의존성 함수

    Example:
        >>> @router.get("/users")
        >>> async def list_users(
        ...     user: CurrentUser = Depends(require_permission("users:read"))
        ... ):
        ...     return {"users": []}
    """

    async def _check_permission(
        user: CurrentUser = Depends(require_auth),
    ) -> CurrentUser:
        """권한을 확인하는 내부 의존성 함수."""
        if user.is_superuser:
            return user
        if permission not in user.permissions:
            raise PermissionDeniedError(f"'{permission}' 권한이 필요합니다")
        return user

    return _check_permission


def require_roles(*roles: str) -> Callable[..., CurrentUser]:
    """특정 역할을 요구하는 의존성 함수 팩토리.

    사용자가 지정된 역할 중 하나 이상을 보유하고 있는지 확인합니다.
    슈퍼유저는 모든 역할 검증을 자동으로 통과합니다.

    Args:
        *roles: 필요한 역할 문자열 (하나 이상 보유 시 통과)

    Returns:
        FastAPI Depends에서 사용할 의존성 함수

    Example:
        >>> @router.delete("/users/{user_id}")
        >>> async def delete_user(
        ...     user_id: int,
        ...     user: CurrentUser = Depends(require_roles("admin", "manager"))
        ... ):
        ...     return {"deleted": user_id}
    """

    async def _check_roles(
        user: CurrentUser = Depends(require_auth),
    ) -> CurrentUser:
        """역할을 확인하는 내부 의존성 함수."""
        if user.is_superuser:
            return user
        if not any(role in user.roles for role in roles):
            roles_str = ", ".join(roles)
            raise PermissionDeniedError(f"다음 역할 중 하나가 필요합니다: {roles_str}")
        return user

    return _check_roles


async def get_optional_user(request: Request) -> CurrentUser | None:
    """선택적 사용자 정보를 반환하는 의존성 함수.

    인증되지 않은 요청에서도 예외를 발생시키지 않고 None을 반환합니다.
    인증 여부에 따라 다른 응답을 제공해야 하는 엔드포인트에 사용합니다.

    Args:
        request: FastAPI 요청 객체

    Returns:
        인증된 사용자 정보 또는 None

    Example:
        >>> @router.get("/products")
        >>> async def list_products(
        ...     user: CurrentUser | None = Depends(get_optional_user)
        ... ):
        ...     if user:
        ...         return {"products": [], "personalized": True}
        ...     return {"products": []}
    """
    return getattr(request.state, "user", None)
