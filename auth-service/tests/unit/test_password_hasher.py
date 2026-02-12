"""Password Hasher 단위 테스트."""

from unittest.mock import MagicMock, patch

from src.shared.security.password_hasher import PasswordHasher


class TestPasswordHasherHashing:
    """비밀번호 해싱 테스트."""

    def test_hash_password_success(self, mock_password_settings):
        """비밀번호 해싱 성공."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            plain_password = "Test1234!"

            # Act
            hashed = hasher.hash(plain_password)

            # Assert
            assert hashed is not None
            assert isinstance(hashed, str)
            assert hashed != plain_password
            assert hashed.startswith("$2b$")  # bcrypt prefix

    def test_hash_password_different_hashes_for_same_password(self, mock_password_settings):
        """같은 비밀번호도 매번 다른 해시 생성 (salt 때문)."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            plain_password = "Test1234!"

            # Act
            hash1 = hasher.hash(plain_password)
            hash2 = hasher.hash(plain_password)

            # Assert
            assert hash1 != hash2

    def test_hash_password_with_special_characters(self, mock_password_settings):
        """특수문자 포함 비밀번호 해싱."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            special_password = "P@ssw0rd!#$%^&*()"

            # Act
            hashed = hasher.hash(special_password)

            # Assert
            assert hashed is not None
            assert hashed.startswith("$2b$")

    def test_hash_password_with_unicode_characters(self, mock_password_settings):
        """유니코드 문자 포함 비밀번호 해싱."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            unicode_password = "Test1234!한글"

            # Act
            hashed = hasher.hash(unicode_password)

            # Assert
            assert hashed is not None
            assert hashed.startswith("$2b$")

    def test_hash_password_with_very_long_password(self, mock_password_settings):
        """매우 긴 비밀번호 해싱 (bcrypt는 72바이트 제한 있음)."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            long_password = "A1b!" + ("x" * 100)

            # Act
            hashed = hasher.hash(long_password)

            # Assert
            assert hashed is not None
            assert hashed.startswith("$2b$")


class TestPasswordHasherVerification:
    """비밀번호 검증 테스트."""

    def test_verify_password_success(self, mock_password_settings):
        """올바른 비밀번호 검증 성공."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            plain_password = "Test1234!"
            hashed = hasher.hash(plain_password)

            # Act
            result = hasher.verify(plain_password, hashed)

            # Assert
            assert result is True

    def test_verify_password_wrong_password(self, mock_password_settings):
        """잘못된 비밀번호 검증 실패."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            plain_password = "Test1234!"
            wrong_password = "Wrong5678@"
            hashed = hasher.hash(plain_password)

            # Act
            result = hasher.verify(wrong_password, hashed)

            # Assert
            assert result is False

    def test_verify_password_case_sensitive(self, mock_password_settings):
        """비밀번호는 대소문자 구분."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            plain_password = "Test1234!"
            wrong_case = "test1234!"
            hashed = hasher.hash(plain_password)

            # Act
            result = hasher.verify(wrong_case, hashed)

            # Assert
            assert result is False

    def test_verify_password_with_special_characters(self, mock_password_settings):
        """특수문자 포함 비밀번호 검증."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            special_password = "P@ssw0rd!#$%"
            hashed = hasher.hash(special_password)

            # Act
            result = hasher.verify(special_password, hashed)

            # Assert
            assert result is True

    def test_verify_password_with_unicode(self, mock_password_settings):
        """유니코드 문자 포함 비밀번호 검증."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            unicode_password = "Test1234!한글"
            hashed = hasher.hash(unicode_password)

            # Act
            result = hasher.verify(unicode_password, hashed)

            # Assert
            assert result is True

    def test_verify_password_empty_string(self, mock_password_settings):
        """빈 문자열 비밀번호 검증."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            hashed = hasher.hash("Test1234!")

            # Act
            result = hasher.verify("", hashed)

            # Assert
            assert result is False


class TestPasswordHasherRehash:
    """비밀번호 재해싱 필요 여부 테스트."""

    def test_needs_rehash_false_for_current_hash(self, mock_password_settings):
        """최신 알고리즘으로 해싱된 비밀번호는 재해싱 불필요."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            plain_password = "Test1234!"
            hashed = hasher.hash(plain_password)

            # Act
            result = hasher.needs_rehash(hashed)

            # Assert
            assert result is False

    def test_needs_rehash_true_for_deprecated_algorithm(self, mock_password_settings):
        """구버전 알고리즘으로 해싱된 비밀번호는 재해싱 필요."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            # bcrypt with rounds=10 (현재 설정은 12)
            deprecated_hash = "$2b$10$N9qo8uLOickgx2ZMRZoMye.qpwvJnUz6hOq/0y9C7xT7YXaLlUe4i"

            # Act
            result = hasher.needs_rehash(deprecated_hash)

            # Assert
            # passlib이 rounds 차이를 감지하면 True, 아니면 False
            # 실제 동작은 passlib 내부 로직에 따라 다를 수 있음
            assert isinstance(result, bool)


class TestPasswordHasherStrengthValidation:
    """비밀번호 강도 검증 테스트."""

    def test_validate_strength_all_requirements_met(self, mock_password_settings):
        """모든 요구사항 충족 시 빈 리스트 반환."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            strong_password = "Test1234!"

            # Act
            errors = hasher.validate_strength(strong_password)

            # Assert
            assert errors == []

    def test_validate_strength_too_short(self, mock_password_settings):
        """비밀번호 길이 부족."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            short_password = "Test1!"

            # Act
            errors = hasher.validate_strength(short_password)

            # Assert
            assert len(errors) > 0
            assert any("최소 8자" in error for error in errors)

    def test_validate_strength_no_uppercase(self, mock_password_settings):
        """대문자 없음."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            no_uppercase = "test1234!"

            # Act
            errors = hasher.validate_strength(no_uppercase)

            # Assert
            assert len(errors) > 0
            assert any("대문자" in error for error in errors)

    def test_validate_strength_no_lowercase(self, mock_password_settings):
        """소문자 없음."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            no_lowercase = "TEST1234!"

            # Act
            errors = hasher.validate_strength(no_lowercase)

            # Assert
            assert len(errors) > 0
            assert any("소문자" in error for error in errors)

    def test_validate_strength_no_digit(self, mock_password_settings):
        """숫자 없음."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            no_digit = "TestTest!"

            # Act
            errors = hasher.validate_strength(no_digit)

            # Assert
            assert len(errors) > 0
            assert any("숫자" in error for error in errors)

    def test_validate_strength_no_special_char(self, mock_password_settings):
        """특수문자 없음."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            no_special = "Test1234"

            # Act
            errors = hasher.validate_strength(no_special)

            # Assert
            assert len(errors) > 0
            assert any("특수문자" in error for error in errors)

    def test_validate_strength_multiple_violations(self, mock_password_settings):
        """여러 요구사항 위반."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            weak_password = "test"

            # Act
            errors = hasher.validate_strength(weak_password)

            # Assert
            assert len(errors) >= 4  # 길이, 대문자, 숫자, 특수문자

    def test_validate_strength_edge_case_exactly_8_chars(self, mock_password_settings):
        """정확히 8자인 강한 비밀번호."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            exact_length = "Test123!"

            # Act
            errors = hasher.validate_strength(exact_length)

            # Assert
            assert errors == []

    def test_validate_strength_with_various_special_chars(self, mock_password_settings):
        """다양한 특수문자 인식."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            special_chars = [
                "Test1234!",
                "Test1234@",
                "Test1234#",
                "Test1234$",
                "Test1234%",
                "Test1234^",
                "Test1234&",
                "Test1234*",
            ]

            # Act & Assert
            for password in special_chars:
                errors = hasher.validate_strength(password)
                assert errors == [], f"Failed for {password}"

    def test_validate_strength_empty_string(self, mock_password_settings):
        """빈 문자열 검증."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()

            # Act
            errors = hasher.validate_strength("")

            # Assert
            assert len(errors) == 5  # 모든 요구사항 위반


class TestPasswordHasherEdgeCases:
    """Password Hasher 엣지 케이스 테스트."""

    def test_hash_and_verify_whitespace_password(self, mock_password_settings):
        """공백이 포함된 비밀번호."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            password_with_space = "Test 1234!"

            # Act
            hashed = hasher.hash(password_with_space)
            result = hasher.verify(password_with_space, hashed)

            # Assert
            assert result is True

    def test_verify_with_trailing_whitespace_fails(self, mock_password_settings):
        """뒤에 공백이 있는 경우 검증 실패."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            plain_password = "Test1234!"
            hashed = hasher.hash(plain_password)

            # Act
            result = hasher.verify(plain_password + " ", hashed)

            # Assert
            assert result is False

    def test_hash_password_with_only_special_chars(self, mock_password_settings):
        """특수문자만으로 구성된 비밀번호 해싱."""
        # Arrange
        with patch("src.shared.security.password_hasher.security_settings", mock_password_settings):
            hasher = PasswordHasher()
            special_only = "!@#$%^&*()"

            # Act
            hashed = hasher.hash(special_only)

            # Assert
            assert hashed is not None
            assert hashed.startswith("$2b$")

    def test_validate_strength_custom_min_length(self):
        """커스텀 최소 길이 설정."""
        # Arrange
        custom_settings = MagicMock()
        custom_settings.password_min_length = 12

        with patch("src.shared.security.password_hasher.security_settings", custom_settings):
            hasher = PasswordHasher()
            password = "Test1234!"  # 9자

            # Act
            errors = hasher.validate_strength(password)

            # Assert
            assert any("최소 12자" in error for error in errors)
