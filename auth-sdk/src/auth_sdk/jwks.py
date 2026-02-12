"""JWKS (JSON Web Key Set) 키 관리 모듈.

인증 서비스의 JWKS 엔드포인트에서 공개키를 가져와 캐싱하고,
JWT 토큰의 서명을 로컬에서 검증하는 기능을 제공합니다.
"""

import logging
import time
from typing import Any

import httpx
from cachetools import TTLCache
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from auth_sdk.exceptions import (
    AuthServiceUnavailableError,
    InvalidTokenError,
    TokenExpiredError,
)
from auth_sdk.models import TokenPayload

logger = logging.getLogger(__name__)


class JWKSClient:
    """JWKS 기반 JWT 토큰 검증 클라이언트.

    인증 서비스의 JWKS 엔드포인트에서 공개키를 가져와 캐싱하고,
    JWT 토큰의 서명을 로컬에서 검증합니다.

    Args:
        jwks_url: JWKS 엔드포인트 URL
        cache_ttl: JWKS 캐시 TTL (초 단위, 기본값: 300)
        http_timeout: JWKS 요청 타임아웃 (초 단위, 기본값: 5.0)

    Example:
        >>> client = JWKSClient(
        ...     jwks_url="http://auth-service:8000/.well-known/jwks.json",
        ...     cache_ttl=300,
        ... )
        >>> payload = await client.verify_token("eyJ...")
    """

    def __init__(
        self,
        jwks_url: str,
        cache_ttl: int = 300,
        http_timeout: float = 5.0,
    ) -> None:
        self.jwks_url = jwks_url
        self.http_timeout = http_timeout
        self._cache: TTLCache[str, dict[str, Any]] = TTLCache(
            maxsize=1, ttl=cache_ttl
        )

    async def fetch_jwks(self) -> dict[str, Any]:
        """JWKS 엔드포인트에서 키 세트를 가져옵니다.

        캐시에 유효한 키가 있으면 캐시된 값을 반환하고,
        그렇지 않으면 JWKS 엔드포인트에서 새로 가져옵니다.

        Returns:
            JWKS 키 세트 딕셔너리

        Raises:
            AuthServiceUnavailableError: JWKS 엔드포인트에 연결할 수 없는 경우
        """
        # 캐시에서 조회
        cached = self._cache.get("jwks")
        if cached is not None:
            return cached

        # JWKS 엔드포인트에서 가져오기
        try:
            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                response = await client.get(self.jwks_url)
                response.raise_for_status()
                jwks_data: dict[str, Any] = response.json()
        except httpx.ConnectError as e:
            raise AuthServiceUnavailableError(
                "JWKS 엔드포인트에 연결할 수 없습니다"
            ) from e
        except httpx.TimeoutException as e:
            raise AuthServiceUnavailableError(
                "JWKS 요청 시간이 초과되었습니다"
            ) from e
        except httpx.HTTPStatusError as e:
            raise AuthServiceUnavailableError(
                f"JWKS 요청 실패: HTTP {e.response.status_code}"
            ) from e

        # 캐시에 저장
        self._cache["jwks"] = jwks_data
        logger.debug("JWKS 키 세트를 캐시에 저장했습니다")

        return jwks_data

    def _get_signing_key(
        self, token: str, jwks: dict[str, Any]
    ) -> dict[str, Any]:
        """JWT 토큰의 헤더에서 kid를 추출하여 대응하는 서명 키를 찾습니다.

        Args:
            token: JWT 토큰 문자열
            jwks: JWKS 키 세트

        Returns:
            서명에 사용된 JWK 딕셔너리

        Raises:
            InvalidTokenError: 토큰 헤더를 파싱할 수 없거나 대응하는 키가 없는 경우
        """
        try:
            unverified_header = jwt.get_unverified_header(token)
        except JWTError as e:
            raise InvalidTokenError("토큰 헤더를 파싱할 수 없습니다") from e

        kid = unverified_header.get("kid")
        if not kid:
            raise InvalidTokenError("토큰 헤더에 kid가 없습니다")

        keys: list[dict[str, Any]] = jwks.get("keys", [])
        for key in keys:
            if key.get("kid") == kid:
                return key

        raise InvalidTokenError(
            f"토큰의 kid '{kid}'에 대응하는 키를 찾을 수 없습니다"
        )

    async def verify_token(
        self, token: str, algorithm: str = "RS256"
    ) -> TokenPayload:
        """JWT 토큰을 로컬에서 검증하고 페이로드를 반환합니다.

        JWKS에서 공개키를 가져와 토큰의 서명을 검증하고,
        만료 시간 등을 확인한 후 페이로드를 반환합니다.

        Args:
            token: 검증할 JWT 토큰
            algorithm: JWT 서명 알고리즘 (기본값: RS256)

        Returns:
            검증된 토큰 페이로드

        Raises:
            TokenExpiredError: 토큰이 만료된 경우
            InvalidTokenError: 토큰이 유효하지 않은 경우
            AuthServiceUnavailableError: JWKS를 가져올 수 없는 경우
        """
        jwks = await self.fetch_jwks()
        signing_key = self._get_signing_key(token, jwks)

        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                signing_key,
                algorithms=[algorithm],
                options={"verify_exp": True},
            )
        except ExpiredSignatureError as e:
            raise TokenExpiredError("토큰이 만료되었습니다") from e
        except JWTError as e:
            raise InvalidTokenError(
                f"토큰 검증에 실패했습니다: {e}"
            ) from e

        return TokenPayload.model_validate(payload)
