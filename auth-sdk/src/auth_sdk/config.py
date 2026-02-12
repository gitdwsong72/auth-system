"""인증 SDK 설정 모듈.

환경 변수를 통해 인증 서비스 연동에 필요한 설정값을 관리합니다.
모든 환경 변수는 AUTH_ 접두사를 사용합니다.
"""

from pydantic import model_validator
from pydantic_settings import BaseSettings


class AuthConfig(BaseSettings):
    """인증 SDK 설정 클래스.

    환경 변수에서 인증 서비스 연동 설정을 로드합니다.

    Attributes:
        auth_service_url: 인증 서비스 기본 URL (예: http://auth-service:8000)
        jwks_url: JWKS 엔드포인트 URL. 미설정 시 auth_service_url에서 자동 파생
        jwt_algorithm: JWT 서명 알고리즘 (기본값: RS256)
        token_cache_ttl: 토큰 캐시 TTL (초 단위, 기본값: 300)
        verify_token_locally: 로컬 JWT 검증 사용 여부 (기본값: True)

    Example:
        >>> config = AuthConfig(auth_service_url="http://auth-service:8000")
        >>> config.jwks_url
        'http://auth-service:8000/.well-known/jwks.json'
    """

    auth_service_url: str
    jwks_url: str | None = None
    jwt_algorithm: str = "RS256"
    token_cache_ttl: int = 300
    verify_token_locally: bool = True

    model_config = {"env_prefix": "AUTH_"}

    @model_validator(mode="after")
    def _derive_jwks_url(self) -> "AuthConfig":
        """jwks_url이 설정되지 않은 경우 auth_service_url에서 자동 파생합니다."""
        if self.jwks_url is None:
            base = self.auth_service_url.rstrip("/")
            self.jwks_url = f"{base}/.well-known/jwks.json"
        return self
