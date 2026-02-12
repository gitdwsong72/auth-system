"""JWT Handler 단위 테스트."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from jose import jwt

from src.shared.security.jwt_handler import (
    InvalidTokenError,
    JWTHandler,
    TokenExpiredError,
)


class TestJWTHandlerTokenCreation:
    """JWT 토큰 생성 테스트."""

    def test_create_access_token_with_all_claims(self, mock_jwt_settings):
        """모든 클레임을 포함한 Access Token 생성."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()

            # Act
            token = handler.create_access_token(
                user_id=1,
                email="test@example.com",
                roles=["admin", "user"],
                permissions=["users:read", "users:write"],
                extra_claims={"custom_field": "custom_value"},
            )

            # Assert
            assert token is not None
            assert isinstance(token, str)
            payload = jwt.decode(
                token,
                mock_jwt_settings.jwt_secret_key,
                algorithms=["HS256"],
            )
            assert payload["sub"] == "1"
            assert payload["email"] == "test@example.com"
            assert payload["roles"] == ["admin", "user"]
            assert payload["permissions"] == ["users:read", "users:write"]
            assert payload["type"] == "access"
            assert payload["iss"] == mock_jwt_settings.jwt_issuer
            assert payload["custom_field"] == "custom_value"
            assert "jti" in payload
            assert "iat" in payload
            assert "exp" in payload

    def test_create_access_token_with_minimal_claims(self, mock_jwt_settings):
        """최소 클레임만 포함한 Access Token 생성."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()

            # Act
            token = handler.create_access_token(
                user_id=1,
                email="test@example.com",
            )

            # Assert
            payload = jwt.decode(
                token,
                mock_jwt_settings.jwt_secret_key,
                algorithms=["HS256"],
            )
            assert payload["sub"] == "1"
            assert payload["email"] == "test@example.com"
            assert payload["roles"] == []
            assert payload["permissions"] == []

    def test_create_access_token_expiration_time(self, mock_jwt_settings):
        """Access Token 만료 시간 확인."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()
            before_creation = datetime.now(UTC)

            # Act
            token = handler.create_access_token(user_id=1, email="test@example.com")

            # Assert
            payload = jwt.decode(
                token,
                mock_jwt_settings.jwt_secret_key,
                algorithms=["HS256"],
            )
            exp_time = datetime.fromtimestamp(payload["exp"], UTC)
            expected_exp = before_creation + timedelta(
                minutes=mock_jwt_settings.jwt_access_token_expire_minutes
            )
            # Allow 2 seconds tolerance
            assert abs((exp_time - expected_exp).total_seconds()) < 2

    def test_create_refresh_token(self, mock_jwt_settings):
        """Refresh Token 생성."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()

            # Act
            token = handler.create_refresh_token(user_id=1)

            # Assert
            payload = jwt.decode(
                token,
                mock_jwt_settings.jwt_secret_key,
                algorithms=["HS256"],
            )
            assert payload["sub"] == "1"
            assert payload["type"] == "refresh"
            assert payload["iss"] == mock_jwt_settings.jwt_issuer
            assert "jti" in payload

    def test_create_refresh_token_expiration_time(self, mock_jwt_settings):
        """Refresh Token 만료 시간 확인."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()
            before_creation = datetime.now(UTC)

            # Act
            token = handler.create_refresh_token(user_id=1)

            # Assert
            payload = jwt.decode(
                token,
                mock_jwt_settings.jwt_secret_key,
                algorithms=["HS256"],
            )
            exp_time = datetime.fromtimestamp(payload["exp"], UTC)
            expected_exp = before_creation + timedelta(
                days=mock_jwt_settings.jwt_refresh_token_expire_days
            )
            # Allow 2 seconds tolerance
            assert abs((exp_time - expected_exp).total_seconds()) < 2

    def test_create_mfa_token(self, mock_jwt_settings):
        """MFA Token 생성."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()

            # Act
            token = handler.create_mfa_token(user_id=1)

            # Assert
            payload = jwt.decode(
                token,
                mock_jwt_settings.jwt_secret_key,
                algorithms=["HS256"],
            )
            assert payload["sub"] == "1"
            assert payload["type"] == "mfa_pending"
            assert payload["iss"] == mock_jwt_settings.jwt_issuer

    def test_create_mfa_token_expiration_time(self, mock_jwt_settings):
        """MFA Token 만료 시간 확인 (5분)."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()
            before_creation = datetime.now(UTC)

            # Act
            token = handler.create_mfa_token(user_id=1)

            # Assert
            payload = jwt.decode(
                token,
                mock_jwt_settings.jwt_secret_key,
                algorithms=["HS256"],
            )
            exp_time = datetime.fromtimestamp(payload["exp"], UTC)
            expected_exp = before_creation + timedelta(minutes=5)
            # Allow 2 seconds tolerance
            assert abs((exp_time - expected_exp).total_seconds()) < 2

    def test_create_password_reset_token(self, mock_jwt_settings):
        """비밀번호 재설정 Token 생성."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()

            # Act
            token = handler.create_password_reset_token(user_id=1)

            # Assert
            payload = jwt.decode(
                token,
                mock_jwt_settings.jwt_secret_key,
                algorithms=["HS256"],
            )
            assert payload["sub"] == "1"
            assert payload["type"] == "password_reset"
            assert payload["iss"] == mock_jwt_settings.jwt_issuer

    def test_create_password_reset_token_expiration_time(self, mock_jwt_settings):
        """비밀번호 재설정 Token 만료 시간 확인 (1시간)."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()
            before_creation = datetime.now(UTC)

            # Act
            token = handler.create_password_reset_token(user_id=1)

            # Assert
            payload = jwt.decode(
                token,
                mock_jwt_settings.jwt_secret_key,
                algorithms=["HS256"],
            )
            exp_time = datetime.fromtimestamp(payload["exp"], UTC)
            expected_exp = before_creation + timedelta(hours=1)
            # Allow 2 seconds tolerance
            assert abs((exp_time - expected_exp).total_seconds()) < 2


class TestJWTHandlerTokenDecoding:
    """JWT 토큰 디코딩 및 검증 테스트."""

    def test_decode_token_valid(self, mock_jwt_settings):
        """유효한 토큰 디코딩."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()
            token = handler.create_access_token(user_id=1, email="test@example.com")

            # Act
            payload = handler.decode_token(token)

            # Assert
            assert payload["sub"] == "1"
            assert payload["email"] == "test@example.com"
            assert payload["type"] == "access"

    def test_decode_token_expired(self, mock_jwt_settings):
        """만료된 토큰 디코딩 시 TokenExpiredError 발생."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()
            now = datetime.now(UTC)
            expired_payload = {
                "sub": "1",
                "type": "access",
                "iss": mock_jwt_settings.jwt_issuer,
                "iat": now - timedelta(hours=2),
                "exp": now - timedelta(hours=1),
                "jti": "expired-jti",
            }
            token = jwt.encode(
                expired_payload,
                mock_jwt_settings.jwt_secret_key,
                algorithm="HS256",
            )

            # Act & Assert
            with pytest.raises(TokenExpiredError) as exc_info:
                handler.decode_token(token)
            assert "만료" in str(exc_info.value)

    def test_decode_token_invalid_signature(self, mock_jwt_settings):
        """잘못된 서명의 토큰 디코딩 시 InvalidTokenError 발생."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()
            now = datetime.now(UTC)
            payload = {
                "sub": "1",
                "type": "access",
                "iss": mock_jwt_settings.jwt_issuer,
                "iat": now,
                "exp": now + timedelta(minutes=30),
                "jti": "test-jti",
            }
            # 다른 키로 서명
            token = jwt.encode(payload, "wrong-secret-key", algorithm="HS256")

            # Act & Assert
            with pytest.raises(InvalidTokenError) as exc_info:
                handler.decode_token(token)
            assert "유효하지 않은" in str(exc_info.value)

    def test_decode_token_wrong_issuer(self, mock_jwt_settings):
        """잘못된 발행자의 토큰 디코딩 시 InvalidTokenError 발생."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()
            now = datetime.now(UTC)
            payload = {
                "sub": "1",
                "type": "access",
                "iss": "wrong-issuer",
                "iat": now,
                "exp": now + timedelta(minutes=30),
                "jti": "test-jti",
            }
            token = jwt.encode(
                payload,
                mock_jwt_settings.jwt_secret_key,
                algorithm="HS256",
            )

            # Act & Assert
            with pytest.raises(InvalidTokenError):
                handler.decode_token(token)

    def test_decode_token_malformed(self, mock_jwt_settings):
        """잘못된 형식의 토큰 디코딩 시 InvalidTokenError 발생."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()
            malformed_token = "not.a.valid.jwt.token"

            # Act & Assert
            with pytest.raises(InvalidTokenError):
                handler.decode_token(malformed_token)

    def test_decode_token_empty_string(self, mock_jwt_settings):
        """빈 문자열 토큰 디코딩 시 InvalidTokenError 발생."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()

            # Act & Assert
            with pytest.raises(InvalidTokenError):
                handler.decode_token("")


class TestJWTHandlerAlgorithms:
    """JWT 알고리즘 및 키 관리 테스트."""

    def test_algorithm_defaults_to_hs256_without_rsa_keys(self, mock_jwt_settings):
        """RSA 키가 없으면 HS256으로 폴백."""
        # Arrange
        mock_jwt_settings.jwt_algorithm = "RS256"
        mock_jwt_settings.jwt_private_key_path = ""
        mock_jwt_settings.jwt_public_key_path = ""

        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()

            # Act
            algorithm = handler.algorithm

            # Assert
            assert algorithm == "HS256"

    def test_signing_key_uses_secret_for_hs256(self, mock_jwt_settings):
        """HS256 사용 시 signing_key는 secret_key."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()

            # Act
            signing_key = handler._signing_key

            # Assert
            assert signing_key == mock_jwt_settings.jwt_secret_key

    def test_verification_key_uses_secret_for_hs256(self, mock_jwt_settings):
        """HS256 사용 시 verification_key는 secret_key."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()

            # Act
            verification_key = handler._verification_key

            # Assert
            assert verification_key == mock_jwt_settings.jwt_secret_key

    def test_get_jwks_empty_without_public_key(self, mock_jwt_settings):
        """공개키가 없으면 JWKS는 빈 keys 배열 반환."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()
            # Force _public_key to None to test the empty keys scenario
            handler._public_key = None

            # Act
            jwks = handler.get_jwks()

            # Assert
            assert jwks == {"keys": []}


class TestJWTHandlerEdgeCases:
    """JWT Handler 엣지 케이스 테스트."""

    def test_create_access_token_with_none_roles(self, mock_jwt_settings):
        """None roles는 빈 리스트로 변환."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()

            # Act
            token = handler.create_access_token(
                user_id=1,
                email="test@example.com",
                roles=None,
            )

            # Assert
            payload = jwt.decode(
                token,
                mock_jwt_settings.jwt_secret_key,
                algorithms=["HS256"],
            )
            assert payload["roles"] == []

    def test_create_access_token_with_none_permissions(self, mock_jwt_settings):
        """None permissions는 빈 리스트로 변환."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()

            # Act
            token = handler.create_access_token(
                user_id=1,
                email="test@example.com",
                permissions=None,
            )

            # Assert
            payload = jwt.decode(
                token,
                mock_jwt_settings.jwt_secret_key,
                algorithms=["HS256"],
            )
            assert payload["permissions"] == []

    def test_create_access_token_with_large_user_id(self, mock_jwt_settings):
        """매우 큰 user_id 처리."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()
            large_user_id = 9999999999

            # Act
            token = handler.create_access_token(
                user_id=large_user_id,
                email="test@example.com",
            )

            # Assert
            payload = jwt.decode(
                token,
                mock_jwt_settings.jwt_secret_key,
                algorithms=["HS256"],
            )
            assert payload["sub"] == str(large_user_id)

    def test_create_access_token_with_special_characters_in_email(self, mock_jwt_settings):
        """이메일에 특수문자 포함."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()
            special_email = "test+tag@example.com"

            # Act
            token = handler.create_access_token(
                user_id=1,
                email=special_email,
            )

            # Assert
            payload = jwt.decode(
                token,
                mock_jwt_settings.jwt_secret_key,
                algorithms=["HS256"],
            )
            assert payload["email"] == special_email

    def test_jti_uniqueness(self, mock_jwt_settings):
        """각 토큰마다 고유한 JTI 생성."""
        # Arrange
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()

            # Act
            token1 = handler.create_access_token(user_id=1, email="test@example.com")
            token2 = handler.create_access_token(user_id=1, email="test@example.com")

            # Assert
            payload1 = jwt.decode(
                token1,
                mock_jwt_settings.jwt_secret_key,
                algorithms=["HS256"],
            )
            payload2 = jwt.decode(
                token2,
                mock_jwt_settings.jwt_secret_key,
                algorithms=["HS256"],
            )
            assert payload1["jti"] != payload2["jti"]


class TestJWTHandlerRSAKeyValidation:
    """RSA 키 검증 테스트 (프로덕션 환경)."""

    def test_production_fails_without_rsa_private_key_file(self, tmp_path):
        """프로덕션 환경에서 RSA private key 파일이 없으면 실패."""
        # Arrange
        from src.shared.security.config import SecuritySettings

        public_key_file = tmp_path / "public.pem"
        public_key_file.write_text(
            "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----"
        )

        # Act & Assert
        with pytest.raises(RuntimeError, match="RSA private key file not found in production"):
            with patch("src.shared.security.config.SecuritySettings") as mock_settings_class:
                mock_settings = SecuritySettings(
                    env="production",
                    jwt_secret_key="a" * 32,
                    jwt_private_key_path=str(tmp_path / "nonexistent.pem"),
                    jwt_public_key_path=str(public_key_file),
                    redis_url="rediss://prod-redis:6379/0",
                )
                mock_settings_class.return_value = mock_settings

                with patch("src.shared.security.jwt_handler.security_settings", mock_settings):
                    JWTHandler()

    def test_production_fails_without_rsa_public_key_file(self, tmp_path):
        """프로덕션 환경에서 RSA public key 파일이 없으면 실패."""
        # Arrange
        from src.shared.security.config import SecuritySettings

        private_key_file = tmp_path / "private.pem"
        private_key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"
        )

        # Act & Assert
        with pytest.raises(RuntimeError, match="RSA public key file not found in production"):
            with patch("src.shared.security.config.SecuritySettings") as mock_settings_class:
                mock_settings = SecuritySettings(
                    env="production",
                    jwt_secret_key="a" * 32,
                    jwt_private_key_path=str(private_key_file),
                    jwt_public_key_path=str(tmp_path / "nonexistent.pem"),
                    redis_url="rediss://prod-redis:6379/0",
                )
                mock_settings_class.return_value = mock_settings

                with patch("src.shared.security.jwt_handler.security_settings", mock_settings):
                    JWTHandler()

    def test_production_fails_when_rsa_keys_not_loaded(self, tmp_path):
        """프로덕션 환경에서 RS256 알고리즘인데 키가 로드되지 않으면 실패."""
        # Arrange
        from src.shared.security.config import SecuritySettings

        # 파일은 존재하지만 읽기 실패하는 상황 시뮬레이션
        private_key_file = tmp_path / "private.pem"
        private_key_file.write_text("")  # 빈 파일

        public_key_file = tmp_path / "public.pem"
        public_key_file.write_text("")  # 빈 파일

        # Act & Assert
        with pytest.raises(RuntimeError, match="Production environment requires RSA keys"):
            mock_settings = SecuritySettings(
                env="production",
                jwt_secret_key="a" * 32,
                jwt_algorithm="RS256",
                jwt_private_key_path=str(private_key_file),
                jwt_public_key_path=str(public_key_file),
                redis_url="rediss://prod-redis:6379/0",
            )

            with patch("src.shared.security.jwt_handler.security_settings", mock_settings):
                # _load_keys가 빈 파일로 인해 키를 로드하지 못하도록 설정
                with patch.object(
                    JWTHandler,
                    "_load_keys",
                    side_effect=lambda self: setattr(self, "_private_key", None)
                    or setattr(self, "_public_key", None),
                ):
                    JWTHandler()

    def test_development_allows_missing_rsa_keys(self, mock_jwt_settings):
        """개발 환경에서는 RSA 키가 없어도 HS256으로 fallback."""
        # Arrange
        mock_jwt_settings.env = "development"
        mock_jwt_settings.jwt_private_key_path = "/nonexistent/private.pem"
        mock_jwt_settings.jwt_public_key_path = "/nonexistent/public.pem"
        mock_jwt_settings.jwt_algorithm = "RS256"

        # Act
        with patch("src.shared.security.jwt_handler.security_settings", mock_jwt_settings):
            handler = JWTHandler()

            # Assert - HS256으로 fallback되어야 함
            assert handler.algorithm == "HS256"
            assert handler._signing_key == mock_jwt_settings.jwt_secret_key

    def test_rsa_keys_loaded_successfully_in_production(self, tmp_path):
        """프로덕션 환경에서 RSA 키가 정상적으로 로드되는 경우."""
        # Arrange
        from src.shared.security.config import SecuritySettings

        private_key_content = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7VJTUt9Us8cKj
MzEfYyjiWA4R4/M2bS1+fWIcPm15A8se0P7JH43sekq5AihQLe9VLcCco0mKWH0X
-----END PRIVATE KEY-----"""

        public_key_content = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAu1SU1LfVLPHCozMxH2Mo
4lgOEePzNm0tfn1iHD5teQPLHtD+yR+N7HpKuQIoUC3vVS3AnKNJilh9Fw==
-----END PUBLIC KEY-----"""

        private_key_file = tmp_path / "private.pem"
        private_key_file.write_text(private_key_content)

        public_key_file = tmp_path / "public.pem"
        public_key_file.write_text(public_key_content)

        # Act
        mock_settings = SecuritySettings(
            env="production",
            jwt_secret_key="a" * 32,
            jwt_algorithm="RS256",
            jwt_private_key_path=str(private_key_file),
            jwt_public_key_path=str(public_key_file),
            redis_url="rediss://prod-redis:6379/0",
        )

        with patch("src.shared.security.jwt_handler.security_settings", mock_settings):
            handler = JWTHandler()

            # Assert
            assert handler._private_key == private_key_content
            assert handler._public_key == public_key_content
            assert handler.algorithm == "RS256"
