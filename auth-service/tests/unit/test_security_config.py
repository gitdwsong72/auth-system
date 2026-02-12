"""보안 설정 검증 테스트."""

from pathlib import Path

import pytest

from src.shared.security.config import SecuritySettings


class TestSecuritySettingsProductionValidation:
    """프로덕션 환경 보안 설정 검증 테스트."""

    def test_production_requires_rsa_key_paths(self):
        """프로덕션 환경에서 RSA 키 경로가 필수."""
        # Act & Assert
        with pytest.raises(ValueError, match="Production environment requires RSA keys"):
            SecuritySettings(
                env="production",
                jwt_secret_key="a" * 32,
                jwt_private_key_path="",
                jwt_public_key_path="",
                redis_url="rediss://prod-redis:6379/0",
            )

    def test_production_requires_rsa_private_key_file_exists(self, tmp_path):
        """프로덕션 환경에서 RSA private key 파일이 존재해야 함."""
        # Arrange
        public_key_file = tmp_path / "public.pem"
        public_key_file.write_text(
            "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----"
        )

        # Act & Assert
        with pytest.raises(ValueError, match="RSA private key file not found"):
            SecuritySettings(
                env="production",
                jwt_secret_key="a" * 32,
                jwt_private_key_path=str(tmp_path / "nonexistent_private.pem"),
                jwt_public_key_path=str(public_key_file),
                redis_url="rediss://prod-redis:6379/0",
            )

    def test_production_requires_rsa_public_key_file_exists(self, tmp_path):
        """프로덕션 환경에서 RSA public key 파일이 존재해야 함."""
        # Arrange
        private_key_file = tmp_path / "private.pem"
        private_key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"
        )

        # Act & Assert
        with pytest.raises(ValueError, match="RSA public key file not found"):
            SecuritySettings(
                env="production",
                jwt_secret_key="a" * 32,
                jwt_private_key_path=str(private_key_file),
                jwt_public_key_path=str(tmp_path / "nonexistent_public.pem"),
                redis_url="rediss://prod-redis:6379/0",
            )

    def test_production_requires_valid_private_key_format(self, tmp_path):
        """프로덕션 환경에서 RSA private key가 PEM 형식이어야 함."""
        # Arrange
        private_key_file = tmp_path / "private.pem"
        private_key_file.write_text("invalid key format")

        public_key_file = tmp_path / "public.pem"
        public_key_file.write_text(
            "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----"
        )

        # Act & Assert
        with pytest.raises(ValueError, match="RSA private key file format invalid"):
            SecuritySettings(
                env="production",
                jwt_secret_key="a" * 32,
                jwt_private_key_path=str(private_key_file),
                jwt_public_key_path=str(public_key_file),
                redis_url="rediss://prod-redis:6379/0",
            )

    def test_production_requires_valid_public_key_format(self, tmp_path):
        """프로덕션 환경에서 RSA public key가 PEM 형식이어야 함."""
        # Arrange
        private_key_file = tmp_path / "private.pem"
        private_key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"
        )

        public_key_file = tmp_path / "public.pem"
        public_key_file.write_text("invalid key format")

        # Act & Assert
        with pytest.raises(ValueError, match="RSA public key file format invalid"):
            SecuritySettings(
                env="production",
                jwt_secret_key="a" * 32,
                jwt_private_key_path=str(private_key_file),
                jwt_public_key_path=str(public_key_file),
                redis_url="rediss://prod-redis:6379/0",
            )

    def test_production_rejects_empty_private_key_file(self, tmp_path):
        """프로덕션 환경에서 빈 RSA private key 파일 거부."""
        # Arrange
        private_key_file = tmp_path / "private.pem"
        private_key_file.write_text("")  # 빈 파일

        public_key_file = tmp_path / "public.pem"
        public_key_file.write_text(
            "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----"
        )

        # Act & Assert
        with pytest.raises(ValueError, match="RSA private key file is empty"):
            SecuritySettings(
                env="production",
                jwt_secret_key="a" * 32,
                jwt_private_key_path=str(private_key_file),
                jwt_public_key_path=str(public_key_file),
                redis_url="rediss://prod-redis:6379/0",
            )

    def test_production_rejects_empty_public_key_file(self, tmp_path):
        """프로덕션 환경에서 빈 RSA public key 파일 거부."""
        # Arrange
        private_key_file = tmp_path / "private.pem"
        private_key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"
        )

        public_key_file = tmp_path / "public.pem"
        public_key_file.write_text("")  # 빈 파일

        # Act & Assert
        with pytest.raises(ValueError, match="RSA public key file is empty"):
            SecuritySettings(
                env="production",
                jwt_secret_key="a" * 32,
                jwt_private_key_path=str(private_key_file),
                jwt_public_key_path=str(public_key_file),
                redis_url="rediss://prod-redis:6379/0",
            )

    def test_production_requires_strong_jwt_secret(self, tmp_path):
        """프로덕션 환경에서 강력한 JWT secret 필요 (32바이트 이상)."""
        # Arrange - RSA 키 파일 생성
        private_key_file = tmp_path / "private.pem"
        private_key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"
        )
        public_key_file = tmp_path / "public.pem"
        public_key_file.write_text(
            "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----"
        )

        # Act & Assert
        with pytest.raises(ValueError, match="at least 32 bytes"):
            SecuritySettings(
                env="production",
                jwt_secret_key="short",
                jwt_private_key_path=str(private_key_file),
                jwt_public_key_path=str(public_key_file),
                redis_url="rediss://prod-redis:6379/0",
            )

    def test_production_rejects_weak_jwt_secret_patterns(self, tmp_path):
        """프로덕션 환경에서 약한 JWT secret 패턴 거부."""
        # Arrange - RSA 키 파일 생성
        private_key_file = tmp_path / "private.pem"
        private_key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"
        )
        public_key_file = tmp_path / "public.pem"
        public_key_file.write_text(
            "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----"
        )

        weak_secrets = [
            "dev-secret-key-that-is-long-enough-32bytes",
            "test_secret_key_that_is_long_enough_32bytes",
            "change_me_secret_key_that_is_32bytes_long",
            "default_secret_key_that_is_32bytes_long",
        ]

        # Act & Assert
        for weak_secret in weak_secrets:
            with pytest.raises(ValueError, match="weak patterns"):
                SecuritySettings(
                    env="production",
                    jwt_secret_key=weak_secret,
                    jwt_private_key_path=str(private_key_file),
                    jwt_public_key_path=str(public_key_file),
                    redis_url="rediss://prod-redis:6379/0",
                )

    def test_production_requires_non_localhost_redis(self, tmp_path):
        """프로덕션 환경에서 localhost Redis 사용 금지."""
        # Arrange - RSA 키 파일 생성
        private_key_file = tmp_path / "private.pem"
        private_key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"
        )
        public_key_file = tmp_path / "public.pem"
        public_key_file.write_text(
            "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----"
        )

        # Act & Assert
        with pytest.raises(ValueError, match="cannot use localhost Redis"):
            SecuritySettings(
                env="production",
                jwt_secret_key="a" * 32,
                jwt_private_key_path=str(private_key_file),
                jwt_public_key_path=str(public_key_file),
                redis_url="redis://localhost:6379/0",
            )

    def test_production_requires_redis_tls(self, tmp_path):
        """프로덕션 환경에서 Redis TLS 필수."""
        # Arrange - RSA 키 파일 생성
        private_key_file = tmp_path / "private.pem"
        private_key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"
        )
        public_key_file = tmp_path / "public.pem"
        public_key_file.write_text(
            "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----"
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Redis must use TLS"):
            SecuritySettings(
                env="production",
                jwt_secret_key="a" * 32,
                jwt_private_key_path=str(private_key_file),
                jwt_public_key_path=str(public_key_file),
                redis_url="redis://prod-redis.example.com:6379/0",  # redis:// (TLS 없음)
            )

    def test_production_valid_configuration(self, tmp_path):
        """프로덕션 환경에서 유효한 설정이 통과하는지 확인."""
        # Arrange
        private_key_file = tmp_path / "private.pem"
        private_key_file.write_text(
            "-----BEGIN PRIVATE KEY-----\nvalid_key_content\n-----END PRIVATE KEY-----"
        )

        public_key_file = tmp_path / "public.pem"
        public_key_file.write_text(
            "-----BEGIN PUBLIC KEY-----\nvalid_key_content\n-----END PUBLIC KEY-----"
        )

        # Act - 예외가 발생하지 않아야 함
        settings = SecuritySettings(
            env="production",
            jwt_secret_key="a" * 32,
            jwt_private_key_path=str(private_key_file),
            jwt_public_key_path=str(public_key_file),
            redis_url="rediss://prod-redis.example.com:6379/0",
        )

        # Assert
        assert settings.env == "production"
        assert len(settings.jwt_secret_key) >= 32


class TestSecuritySettingsDevelopmentMode:
    """개발 환경 설정 테스트."""

    def test_development_allows_missing_rsa_keys(self):
        """개발 환경에서는 RSA 키가 없어도 허용."""
        # Act - 예외가 발생하지 않아야 함
        settings = SecuritySettings(
            env="development",
            jwt_secret_key="dev-secret-key",
            jwt_private_key_path="",
            jwt_public_key_path="",
            redis_url="redis://localhost:6379/0",
        )

        # Assert
        assert settings.env == "development"

    def test_development_allows_localhost_redis(self):
        """개발 환경에서는 localhost Redis 허용."""
        # Act
        settings = SecuritySettings(
            env="development",
            jwt_secret_key="dev-secret-key",
            redis_url="redis://localhost:6379/0",
        )

        # Assert
        assert "localhost" in settings.redis_url

    def test_development_allows_weak_jwt_secret(self):
        """개발 환경에서는 약한 JWT secret도 허용."""
        # Act
        settings = SecuritySettings(
            env="development",
            jwt_secret_key="dev",
            redis_url="redis://localhost:6379/0",
        )

        # Assert
        assert len(settings.jwt_secret_key) < 32
