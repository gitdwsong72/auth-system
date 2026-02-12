"""보안 관련 설정."""

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecuritySettings(BaseSettings):
    """JWT 및 보안 관련 설정."""

    # 환경 설정
    env: str = Field(default="development", description="Environment (development/production)")

    # Trusted Host 설정
    allowed_hosts: list[str] = Field(
        default=["localhost", "127.0.0.1"],
        description="Allowed hosts for TrustedHostMiddleware (production only)",
    )

    # JWT 설정
    jwt_algorithm: str = "RS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    jwt_issuer: str = "auth-service"

    # RSA 키 경로 (RS256용) - 프로덕션 필수
    jwt_private_key_path: str = Field(
        default="", description="RSA private key file path (required for production)"
    )
    jwt_public_key_path: str = Field(
        default="", description="RSA public key file path (required for production)"
    )

    # HMAC 시크릿 (HS256 폴백용) - 개발 환경 전용
    jwt_secret_key: str = Field(
        description="JWT secret key for HS256 (required - set JWT_SECRET_KEY environment variable)"
    )

    # Redis 설정
    redis_url: str = "redis://localhost:6380/0"

    # 비밀번호 정책
    password_min_length: int = 8
    password_max_failed_attempts: int = 5
    password_lockout_minutes: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_security(self):
        """
        프로덕션 환경 보안 설정 검증

        프로덕션에서는:
        1. RSA 키 필수 (경로 + 파일 존재 여부)
        2. JWT secret이 최소 32바이트 이상, 약한 기본값 사용 금지
        3. localhost Redis 사용 금지
        """
        if self.env == "production":
            # RSA 키 파일 경로 필수
            if not self.jwt_private_key_path or not self.jwt_public_key_path:
                raise ValueError(
                    "Production environment requires RSA keys. "
                    "Set JWT_PRIVATE_KEY_PATH and JWT_PUBLIC_KEY_PATH"
                )

            # RSA 키 파일 실제 존재 여부 검증
            from pathlib import Path

            private_key_path = Path(self.jwt_private_key_path)
            if not private_key_path.exists():
                raise ValueError(
                    f"Production RSA private key file not found: {self.jwt_private_key_path}. "
                    "Ensure the file exists and path is correct"
                )

            public_key_path = Path(self.jwt_public_key_path)
            if not public_key_path.exists():
                raise ValueError(
                    f"Production RSA public key file not found: {self.jwt_public_key_path}. "
                    "Ensure the file exists and path is correct"
                )

            # RSA 키 파일 읽기 가능 여부 및 형식 검증
            try:
                private_key_content = private_key_path.read_text()
                if not private_key_content.strip():
                    raise ValueError("RSA private key file is empty")
                if "BEGIN" not in private_key_content or "PRIVATE KEY" not in private_key_content:
                    raise ValueError(
                        "RSA private key file format invalid. Expected PEM format "
                        "(-----BEGIN PRIVATE KEY-----)"
                    )
            except Exception as e:
                if isinstance(e, ValueError):
                    raise
                raise ValueError(f"Failed to read RSA private key file: {e}")

            try:
                public_key_content = public_key_path.read_text()
                if not public_key_content.strip():
                    raise ValueError("RSA public key file is empty")
                if "BEGIN" not in public_key_content or "PUBLIC KEY" not in public_key_content:
                    raise ValueError(
                        "RSA public key file format invalid. Expected PEM format "
                        "(-----BEGIN PUBLIC KEY-----)"
                    )
            except Exception as e:
                if isinstance(e, ValueError):
                    raise
                raise ValueError(f"Failed to read RSA public key file: {e}")

            # JWT secret 길이 및 강도 검증
            if len(self.jwt_secret_key) < 32:
                raise ValueError(
                    "Production JWT secret must be at least 32 bytes. "
                    f"Current length: {len(self.jwt_secret_key)} bytes. Generate a strong random secret."
                )

            # 약한 기본값 또는 개발용 시크릿 사용 금지
            weak_patterns = ["dev-", "dev_", "test", "change", "secret", "password", "default"]
            if any(pattern in self.jwt_secret_key.lower() for pattern in weak_patterns):
                raise ValueError(
                    "Production JWT secret contains weak patterns (dev-, test, change, etc.). "
                    "Use a cryptographically secure random string"
                )

            # localhost Redis 사용 금지
            if "localhost" in self.redis_url or "127.0.0.1" in self.redis_url:
                raise ValueError(
                    "Production cannot use localhost Redis. "
                    "Set REDIS_URL to production Redis server"
                )

            # Redis TLS 필수
            if not self.redis_url.startswith("rediss://"):
                raise ValueError(
                    "Production Redis must use TLS (rediss://). Current URL scheme does not use TLS"
                )

        return self


class CORSSettings(BaseSettings):
    """CORS 관련 설정."""

    allowed_origins: list[str] = Field(
        default=[
            "http://localhost:5173",
            "http://localhost:3000",
            "http://localhost:8080",
        ],
        description="Allowed CORS origins",
    )

    model_config = SettingsConfigDict(
        env_prefix="CORS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class BackpressureSettings(BaseSettings):
    """
    Backpressure (과부하 방지) 설정

    시스템 수용 한계를 넘는 요청을 대기시켜 순차 처리
    """

    # Backpressure 활성화 여부
    enable_backpressure: bool = Field(
        default=False, description="Enable backpressure middleware (recommended for production)"
    )

    # 동시 처리 한계 (DB Connection Pool과 동기화 권장)
    max_concurrent: int = Field(
        default=100, description="Maximum concurrent requests (align with DB pool size)"
    )

    # 대기열 크기
    queue_capacity: int = Field(
        default=1000, description="Maximum queue size (10s buffer at 100 RPS)"
    )

    # 대기 타임아웃 (초)
    wait_timeout: float = Field(default=3.0, description="Maximum wait time in queue (seconds)")

    # 즉시 거부 임계치 (None이면 max_concurrent + queue_capacity)
    reject_threshold: int | None = Field(
        default=None,
        description="Immediate rejection threshold (default: max_concurrent + queue_capacity)",
    )

    model_config = SettingsConfigDict(
        env_prefix="BACKPRESSURE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


security_settings = SecuritySettings()
cors_settings = CORSSettings()
backpressure_settings = BackpressureSettings()
