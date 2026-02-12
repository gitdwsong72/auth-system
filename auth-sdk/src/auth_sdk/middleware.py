"""인증 미들웨어 모듈.

FastAPI 애플리케이션에 JWT 기반 인증을 추가하는 미들웨어를 제공합니다.
공개 경로는 인증을 건너뛰고, 그 외 경로에서는 Bearer 토큰을 검증합니다.
"""

import logging
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from auth_sdk.config import AuthConfig
from auth_sdk.exceptions import AuthSDKError, AuthenticationError, InvalidTokenError
from auth_sdk.jwks import JWKSClient
from auth_sdk.models import CurrentUser, TokenPayload

logger = logging.getLogger(__name__)

# 인증을 건너뛸 기본 공개 경로 목록
DEFAULT_PUBLIC_PATHS: list[str] = [
    "/health",
    "/docs",
    "/openapi.json",
    "/.well-known/",
]


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT 인증 미들웨어.

    모든 요청에서 Authorization 헤더의 Bearer 토큰을 검증하고,
    검증된 사용자 정보를 request.state.user에 설정합니다.

    Args:
        app: FastAPI 애플리케이션 인스턴스
        config: 인증 SDK 설정
        public_paths: 인증을 건너뛸 경로 목록 (기본값 사용 시 None)

    Example:
        >>> from fastapi import FastAPI
        >>> from auth_sdk import AuthMiddleware, AuthConfig
        >>>
        >>> app = FastAPI()
        >>> config = AuthConfig(auth_service_url="http://auth-service:8000")
        >>> app.add_middleware(AuthMiddleware, config=config)
    """

    def __init__(
        self,
        app: Any,
        config: AuthConfig,
        public_paths: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.config = config
        self.public_paths = public_paths or DEFAULT_PUBLIC_PATHS
        self.jwks_client = JWKSClient(
            jwks_url=config.jwks_url or "",
            cache_ttl=config.token_cache_ttl,
        )

    def _is_public_path(self, path: str) -> bool:
        """요청 경로가 공개 경로인지 확인합니다.

        Args:
            path: 요청 경로

        Returns:
            공개 경로 여부
        """
        return any(path.startswith(public) for public in self.public_paths)

    def _extract_token(self, request: Request) -> str:
        """Authorization 헤더에서 Bearer 토큰을 추출합니다.

        Args:
            request: FastAPI 요청 객체

        Returns:
            추출된 JWT 토큰 문자열

        Raises:
            AuthenticationError: Authorization 헤더가 없거나 형식이 잘못된 경우
        """
        authorization = request.headers.get("Authorization")
        if not authorization:
            raise AuthenticationError("Authorization 헤더가 없습니다")

        parts = authorization.split(" ")
        if len(parts) != 2 or parts[0].lower() != "bearer":  # noqa: PLR2004
            raise AuthenticationError("Authorization 헤더 형식이 잘못되었습니다. 'Bearer <token>' 형식을 사용하세요")

        return parts[1]

    def _token_payload_to_user(self, payload: TokenPayload) -> CurrentUser:
        """토큰 페이로드를 CurrentUser 모델로 변환합니다.

        Args:
            payload: JWT 토큰 페이로드

        Returns:
            변환된 CurrentUser 인스턴스
        """
        return CurrentUser(
            id=payload.sub,
            email=payload.email,
            username=payload.email,
            roles=payload.roles,
            permissions=payload.permissions,
        )

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """미들웨어 요청 처리 로직.

        공개 경로는 인증을 건너뛰고, 그 외 경로에서는
        Bearer 토큰을 검증하여 사용자 정보를 request.state에 설정합니다.

        Args:
            request: FastAPI 요청 객체
            call_next: 다음 미들웨어/핸들러 호출 함수

        Returns:
            HTTP 응답 객체
        """
        # 공개 경로는 인증 건너뛰기
        if self._is_public_path(request.url.path):
            return await call_next(request)

        try:
            token = self._extract_token(request)

            if self.config.verify_token_locally:
                # 로컬 JWT 검증 (JWKS 사용)
                payload = await self.jwks_client.verify_token(
                    token, algorithm=self.config.jwt_algorithm
                )
                request.state.user = self._token_payload_to_user(payload)
            else:
                # 인증 서비스를 통한 토큰 인트로스펙션 (폴백)
                from auth_sdk.client import AuthClient

                async with AuthClient(base_url=self.config.auth_service_url) as client:
                    user = await client.verify_token(token)
                    request.state.user = user

        except AuthSDKError as e:
            logger.warning("인증 실패: %s", e.message)
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.message},
            )
        except Exception as e:
            logger.exception("인증 처리 중 예기치 않은 오류 발생")
            return JSONResponse(
                status_code=401,
                content={"detail": "인증 처리 중 오류가 발생했습니다"},
            )

        return await call_next(request)
