"""인증 서비스 HTTP 클라이언트 모듈.

인증 서비스 API와 통신하기 위한 비동기 HTTP 클라이언트를 제공합니다.
토큰 검증, 사용자 정보 조회, 권한 확인 등의 기능을 제공합니다.
"""

import logging
from types import TracebackType

import httpx

from auth_sdk.exceptions import (
    AuthenticationError,
    AuthServiceUnavailableError,
    InvalidTokenError,
)
from auth_sdk.models import CurrentUser, TokenIntrospectionResponse

logger = logging.getLogger(__name__)


class AuthClient:
    """인증 서비스 비동기 HTTP 클라이언트.

    인증 서비스의 REST API를 호출하여 토큰 검증, 사용자 조회,
    권한 확인 등의 기능을 제공합니다.

    Args:
        base_url: 인증 서비스 기본 URL
        timeout: HTTP 요청 타임아웃 (초 단위, 기본값: 5.0)

    Example:
        >>> async with AuthClient(base_url="http://auth-service:8000") as client:
        ...     user = await client.verify_token("eyJ...")
        ...     print(user.email)
    """

    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """내부 httpx.AsyncClient 인스턴스를 반환합니다.

        클라이언트가 아직 생성되지 않은 경우 자동으로 생성합니다.

        Returns:
            httpx.AsyncClient 인스턴스
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def __aenter__(self) -> "AuthClient":
        """비동기 컨텍스트 매니저 진입."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """비동기 컨텍스트 매니저 종료 시 HTTP 클라이언트를 닫습니다."""
        await self.close()

    async def close(self) -> None:
        """HTTP 클라이언트 연결을 닫습니다."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def verify_token(self, token: str) -> CurrentUser:
        """토큰을 검증하고 사용자 정보를 반환합니다.

        인증 서비스의 토큰 검증 엔드포인트를 호출하여
        토큰의 유효성을 확인하고 사용자 정보를 반환합니다.

        Args:
            token: 검증할 JWT 토큰

        Returns:
            검증된 사용자 정보

        Raises:
            InvalidTokenError: 토큰이 유효하지 않은 경우
            AuthServiceUnavailableError: 인증 서비스에 연결할 수 없는 경우
        """
        try:
            response = await self.client.post(
                "/api/v1/auth/verify",
                json={"token": token},
            )
        except httpx.ConnectError as e:
            raise AuthServiceUnavailableError(
                "인증 서비스에 연결할 수 없습니다"
            ) from e
        except httpx.TimeoutException as e:
            raise AuthServiceUnavailableError(
                "인증 서비스 요청 시간이 초과되었습니다"
            ) from e

        if response.status_code == 401:  # noqa: PLR2004
            raise InvalidTokenError("유효하지 않은 토큰입니다")

        response.raise_for_status()
        return CurrentUser.model_validate(response.json())

    async def check_permission(self, user_id: int, permission: str) -> bool:
        """사용자의 특정 권한 보유 여부를 확인합니다.

        인증 서비스에 사용자의 권한을 조회하여 지정된 권한을
        보유하고 있는지 확인합니다.

        Args:
            user_id: 사용자 ID
            permission: 확인할 권한 문자열

        Returns:
            권한 보유 여부

        Raises:
            AuthServiceUnavailableError: 인증 서비스에 연결할 수 없는 경우
        """
        try:
            response = await self.client.get(
                f"/api/v1/users/{user_id}/permissions/{permission}",
            )
        except httpx.ConnectError as e:
            raise AuthServiceUnavailableError(
                "인증 서비스에 연결할 수 없습니다"
            ) from e
        except httpx.TimeoutException as e:
            raise AuthServiceUnavailableError(
                "인증 서비스 요청 시간이 초과되었습니다"
            ) from e

        if response.status_code == 404:  # noqa: PLR2004
            return False

        response.raise_for_status()
        data: dict[str, bool] = response.json()
        return data.get("has_permission", False)

    async def get_user(self, user_id: int) -> CurrentUser:
        """사용자 ID로 사용자 정보를 조회합니다.

        Args:
            user_id: 조회할 사용자 ID

        Returns:
            사용자 정보

        Raises:
            AuthenticationError: 사용자를 찾을 수 없는 경우
            AuthServiceUnavailableError: 인증 서비스에 연결할 수 없는 경우
        """
        try:
            response = await self.client.get(
                f"/api/v1/users/{user_id}",
            )
        except httpx.ConnectError as e:
            raise AuthServiceUnavailableError(
                "인증 서비스에 연결할 수 없습니다"
            ) from e
        except httpx.TimeoutException as e:
            raise AuthServiceUnavailableError(
                "인증 서비스 요청 시간이 초과되었습니다"
            ) from e

        if response.status_code == 404:  # noqa: PLR2004
            raise AuthenticationError(f"사용자를 찾을 수 없습니다: {user_id}")

        response.raise_for_status()
        return CurrentUser.model_validate(response.json())

    async def introspect_token(self, token: str) -> TokenIntrospectionResponse:
        """토큰 인트로스펙션을 수행합니다.

        인증 서비스의 인트로스펙션 엔드포인트를 호출하여
        토큰의 상세 정보를 반환합니다.

        Args:
            token: 인트로스펙션할 JWT 토큰

        Returns:
            토큰 인트로스펙션 응답

        Raises:
            AuthServiceUnavailableError: 인증 서비스에 연결할 수 없는 경우
        """
        try:
            response = await self.client.post(
                "/api/v1/auth/introspect",
                json={"token": token},
            )
        except httpx.ConnectError as e:
            raise AuthServiceUnavailableError(
                "인증 서비스에 연결할 수 없습니다"
            ) from e
        except httpx.TimeoutException as e:
            raise AuthServiceUnavailableError(
                "인증 서비스 요청 시간이 초과되었습니다"
            ) from e

        response.raise_for_status()
        return TokenIntrospectionResponse.model_validate(response.json())
