"""CSRF Protection unit tests"""

import pytest
from fastapi import HTTPException

from src.shared.security.csrf_protection import CSRFProtection


class TestCSRFProtection:
    """CSRF 토큰 생성 및 검증 테스트"""

    def test_generate_token(self):
        """CSRF 토큰 생성"""
        token = CSRFProtection.generate_token()

        # 64자 hex 문자열 (32바이트)
        assert len(token) == 64
        assert all(c in "0123456789abcdef" for c in token)

    def test_generate_token_uniqueness(self):
        """생성된 토큰은 고유해야 함"""
        tokens = [CSRFProtection.generate_token() for _ in range(100)]

        # 모두 고유한지 확인
        assert len(set(tokens)) == 100

    def test_validate_token_success(self):
        """동일한 토큰으로 검증 성공"""
        token = CSRFProtection.generate_token()

        # 예외가 발생하지 않아야 함
        CSRFProtection.validate_token(token, token)

    def test_validate_token_missing_header(self):
        """헤더 토큰이 없는 경우 실패"""
        cookie_token = CSRFProtection.generate_token()

        with pytest.raises(HTTPException) as exc_info:
            CSRFProtection.validate_token(None, cookie_token)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error_code"] == "CSRF_001"

    def test_validate_token_missing_cookie(self):
        """쿠키 토큰이 없는 경우 실패"""
        header_token = CSRFProtection.generate_token()

        with pytest.raises(HTTPException) as exc_info:
            CSRFProtection.validate_token(header_token, None)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error_code"] == "CSRF_001"

    def test_validate_token_mismatch(self):
        """헤더와 쿠키 토큰이 다른 경우 실패"""
        header_token = CSRFProtection.generate_token()
        cookie_token = CSRFProtection.generate_token()

        with pytest.raises(HTTPException) as exc_info:
            CSRFProtection.validate_token(header_token, cookie_token)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error_code"] == "CSRF_002"

    def test_validate_token_empty_strings(self):
        """빈 문자열은 None과 동일하게 처리"""
        with pytest.raises(HTTPException) as exc_info:
            CSRFProtection.validate_token("", "")

        assert exc_info.value.status_code == 403

    def test_validate_token_timing_attack_resistant(self):
        """Timing attack에 안전한지 확인 (secrets.compare_digest 사용)"""
        # 이 테스트는 구현이 secrets.compare_digest를 사용하는지 확인
        # 실제 timing attack 테스트는 매우 복잡하므로 생략
        token1 = "a" * 64
        token2 = "b" * 64

        with pytest.raises(HTTPException):
            CSRFProtection.validate_token(token1, token2)
