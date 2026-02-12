"""auth-sdk: 인증 서비스 연동을 위한 Python SDK.

MSA 서비스에서 인증 서비스와 연동하기 위한 SDK입니다.
FastAPI 미들웨어, 의존성 주입 헬퍼, HTTP 클라이언트를 제공합니다.

주요 구성 요소:
    - AuthMiddleware: JWT 인증 미들웨어
    - AuthConfig: 인증 설정 관리
    - require_auth, require_permission, require_roles: FastAPI 의존성 주입 헬퍼
    - CurrentUser: 현재 사용자 모델
    - AuthClient: 인증 서비스 HTTP 클라이언트

Example:
    >>> from fastapi import FastAPI, Depends
    >>> from auth_sdk import AuthMiddleware, AuthConfig, require_auth, CurrentUser
    >>>
    >>> app = FastAPI()
    >>> config = AuthConfig(auth_service_url="http://auth-service:8000")
    >>> app.add_middleware(AuthMiddleware, config=config)
    >>>
    >>> @app.get("/me")
    >>> async def get_me(user: CurrentUser = Depends(require_auth)):
    ...     return user
"""

from auth_sdk.client import AuthClient
from auth_sdk.config import AuthConfig
from auth_sdk.dependencies import require_auth, require_permission, require_roles
from auth_sdk.exceptions import AuthenticationError, PermissionDeniedError
from auth_sdk.middleware import AuthMiddleware
from auth_sdk.models import CurrentUser

__all__ = [
    "AuthMiddleware",
    "AuthConfig",
    "require_auth",
    "require_permission",
    "require_roles",
    "CurrentUser",
    "AuthClient",
    "AuthenticationError",
    "PermissionDeniedError",
]
