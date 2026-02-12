"""JWT 토큰 생성 및 검증 모듈."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from src.shared.security.config import security_settings


class JWTHandler:
    """JWT 토큰 생성 및 검증을 담당하는 클래스."""

    def __init__(self) -> None:
        self._settings = security_settings
        self._private_key: str | None = None
        self._public_key: str | None = None
        self._load_keys()

    def _load_keys(self) -> None:
        """RSA 키 파일을 로드한다.

        프로덕션 환경에서는 RSA 키 로드 실패 시 예외를 발생시킨다.
        개발 환경에서는 키가 없으면 HMAC 시크릿을 사용한다.

        Raises:
            RuntimeError: 프로덕션 환경에서 RSA 키 로드 실패 시
        """
        is_production = self._settings.env == "production"

        # RSA Private Key 로드
        if self._settings.jwt_private_key_path:
            key_path = Path(self._settings.jwt_private_key_path)
            if key_path.exists():
                try:
                    self._private_key = key_path.read_text()
                except Exception as e:
                    if is_production:
                        raise RuntimeError(
                            f"Failed to load RSA private key in production: {e}"
                        ) from e
                    # 개발 환경에서는 경고만 출력
                    import logging

                    logging.warning(f"Failed to load RSA private key: {e}. Falling back to HS256")
            elif is_production:
                # 프로덕션에서는 파일 없으면 즉시 실패 (config 검증을 통과했다면 이 코드는 실행되지 않아야 함)
                raise RuntimeError(
                    f"RSA private key file not found in production: {self._settings.jwt_private_key_path}"
                )

        # RSA Public Key 로드
        if self._settings.jwt_public_key_path:
            key_path = Path(self._settings.jwt_public_key_path)
            if key_path.exists():
                try:
                    self._public_key = key_path.read_text()
                except Exception as e:
                    if is_production:
                        raise RuntimeError(
                            f"Failed to load RSA public key in production: {e}"
                        ) from e
                    # 개발 환경에서는 경고만 출력
                    import logging

                    logging.warning(f"Failed to load RSA public key: {e}. Falling back to HS256")
            elif is_production:
                # 프로덕션에서는 파일 없으면 즉시 실패
                raise RuntimeError(
                    f"RSA public key file not found in production: {self._settings.jwt_public_key_path}"
                )

        # 프로덕션에서 RS256 알고리즘인데 키가 로드되지 않았으면 실패
        if is_production and self._settings.jwt_algorithm.startswith("RS"):
            if not self._private_key or not self._public_key:
                raise RuntimeError(
                    f"Production environment requires RSA keys for {self._settings.jwt_algorithm} algorithm, "
                    "but keys were not loaded. This is a critical security issue."
                )

    @property
    def _signing_key(self) -> str:
        """서명에 사용할 키를 반환한다."""
        if self._settings.jwt_algorithm.startswith("RS") and self._private_key:
            return self._private_key
        return self._settings.jwt_secret_key

    @property
    def _verification_key(self) -> str:
        """검증에 사용할 키를 반환한다."""
        if self._settings.jwt_algorithm.startswith("RS") and self._public_key:
            return self._public_key
        return self._settings.jwt_secret_key

    @property
    def algorithm(self) -> str:
        """사용 중인 알고리즘을 반환한다."""
        if self._settings.jwt_algorithm.startswith("RS") and self._private_key:
            return self._settings.jwt_algorithm
        return "HS256"

    def create_access_token(
        self,
        user_id: int,
        email: str,
        roles: list[str] | None = None,
        permissions: list[str] | None = None,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        """Access Token을 생성한다."""
        now = datetime.now(UTC)
        expire = now + timedelta(minutes=self._settings.jwt_access_token_expire_minutes)

        payload: dict[str, Any] = {
            "sub": str(user_id),
            "email": email,
            "roles": roles or [],
            "permissions": permissions or [],
            "type": "access",
            "iss": self._settings.jwt_issuer,
            "iat": now,
            "exp": expire,
            "jti": str(uuid.uuid4()),
        }

        if extra_claims:
            payload.update(extra_claims)

        return jwt.encode(payload, self._signing_key, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: int) -> str:
        """Refresh Token을 생성한다."""
        now = datetime.now(UTC)
        expire = now + timedelta(days=self._settings.jwt_refresh_token_expire_days)

        payload: dict[str, Any] = {
            "sub": str(user_id),
            "type": "refresh",
            "iss": self._settings.jwt_issuer,
            "iat": now,
            "exp": expire,
            "jti": str(uuid.uuid4()),
        }

        return jwt.encode(payload, self._signing_key, algorithm=self.algorithm)

    def create_mfa_token(self, user_id: int) -> str:
        """MFA 인증 대기 토큰을 생성한다 (유효기간 5분)."""
        now = datetime.now(UTC)
        expire = now + timedelta(minutes=5)

        payload: dict[str, Any] = {
            "sub": str(user_id),
            "type": "mfa_pending",
            "iss": self._settings.jwt_issuer,
            "iat": now,
            "exp": expire,
            "jti": str(uuid.uuid4()),
        }

        return jwt.encode(payload, self._signing_key, algorithm=self.algorithm)

    def create_password_reset_token(self, user_id: int) -> str:
        """비밀번호 재설정 토큰을 생성한다 (유효기간 1시간)."""
        now = datetime.now(UTC)
        expire = now + timedelta(hours=1)

        payload: dict[str, Any] = {
            "sub": str(user_id),
            "type": "password_reset",
            "iss": self._settings.jwt_issuer,
            "iat": now,
            "exp": expire,
            "jti": str(uuid.uuid4()),
        }

        return jwt.encode(payload, self._signing_key, algorithm=self.algorithm)

    def decode_token(self, token: str) -> dict[str, Any]:
        """토큰을 디코딩하고 검증한다.

        Raises:
            TokenExpiredError: 토큰이 만료된 경우
            InvalidTokenError: 토큰이 유효하지 않은 경우
        """
        try:
            payload = jwt.decode(
                token,
                self._verification_key,
                algorithms=[self.algorithm],
                issuer=self._settings.jwt_issuer,
            )
            return payload  # type: ignore[no-any-return]
        except ExpiredSignatureError:
            raise TokenExpiredError("토큰이 만료되었습니다")
        except JWTError as e:
            raise InvalidTokenError(f"유효하지 않은 토큰입니다: {e}")

    def get_jwks(self) -> dict[str, Any]:
        """JWKS (JSON Web Key Set) 공개키 정보를 반환한다."""
        if not self._public_key:
            return {"keys": []}

        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from jose.backends import RSAKey

        public_key = load_pem_public_key(self._public_key.encode())
        rsa_key = RSAKey(public_key, self.algorithm)
        jwk = rsa_key.to_dict()
        jwk["kid"] = "auth-service-key-1"
        jwk["use"] = "sig"
        jwk["alg"] = self.algorithm

        return {"keys": [jwk]}


class TokenExpiredError(Exception):
    """토큰 만료 예외."""


class InvalidTokenError(Exception):
    """유효하지 않은 토큰 예외."""


jwt_handler = JWTHandler()
