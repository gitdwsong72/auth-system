"""Constants 모듈 단위 테스트"""

from src.shared.constants import (
    CacheSettings,
    ErrorCode,
    ErrorMessage,
    Pagination,
    PasswordPolicy,
    TokenSettings,
)


class TestPasswordPolicy:
    """비밀번호 정책 상수 테스트"""

    def test_min_length(self):
        """최소 비밀번호 길이"""
        assert PasswordPolicy.MIN_LENGTH == 8

    def test_max_failed_attempts(self):
        """최대 실패 시도 횟수"""
        assert PasswordPolicy.MAX_FAILED_ATTEMPTS == 5

    def test_lockout_minutes(self):
        """계정 잠금 시간"""
        assert PasswordPolicy.LOCKOUT_MINUTES == 15


class TestTokenSettings:
    """토큰 설정 상수 테스트"""

    def test_access_token_ttl(self):
        """액세스 토큰 TTL"""
        assert TokenSettings.ACCESS_TOKEN_TTL_SECONDS == 1800

    def test_access_token_expires_in(self):
        """액세스 토큰 만료 시간"""
        assert TokenSettings.ACCESS_TOKEN_EXPIRES_IN == 900

    def test_refresh_token_expires_days(self):
        """리프레시 토큰 만료 일수"""
        assert TokenSettings.REFRESH_TOKEN_EXPIRES_DAYS == 7

    def test_blacklist_ttl(self):
        """블랙리스트 TTL"""
        assert TokenSettings.BLACKLIST_TTL_SECONDS == 1800


class TestCacheSettings:
    """캐시 설정 상수 테스트"""

    def test_permissions_cache_ttl(self):
        """권한 캐시 TTL"""
        assert CacheSettings.PERMISSIONS_CACHE_TTL_SECONDS == 300


class TestPagination:
    """페이징 상수 테스트"""

    def test_default_page_size(self):
        """기본 페이지 크기"""
        assert Pagination.DEFAULT_PAGE_SIZE == 20

    def test_max_page_size(self):
        """최대 페이지 크기"""
        assert Pagination.MAX_PAGE_SIZE == 100


class TestErrorCode:
    """에러 코드 상수 테스트"""

    def test_user_error_codes(self):
        """사용자 관리 에러 코드"""
        assert ErrorCode.USER_001 == "USER_001"
        assert ErrorCode.USER_002 == "USER_002"
        assert ErrorCode.USER_003 == "USER_003"
        assert ErrorCode.USER_004 == "USER_004"

    def test_auth_error_codes(self):
        """인증 에러 코드"""
        assert ErrorCode.AUTH_001 == "AUTH_001"
        assert ErrorCode.AUTH_002 == "AUTH_002"
        assert ErrorCode.AUTH_003 == "AUTH_003"
        assert ErrorCode.AUTH_004 == "AUTH_004"
        assert ErrorCode.AUTH_005 == "AUTH_005"
        assert ErrorCode.AUTH_006 == "AUTH_006"

    def test_authz_error_codes(self):
        """인가 에러 코드"""
        assert ErrorCode.AUTHZ_001 == "AUTHZ_001"
        assert ErrorCode.AUTHZ_002 == "AUTHZ_002"

    def test_internal_error_code(self):
        """내부 에러 코드"""
        assert ErrorCode.INTERNAL_ERROR == "INTERNAL_ERROR"

    def test_error_code_is_string_enum(self):
        """ErrorCode는 StrEnum 타입"""
        # StrEnum은 str로 직접 비교 가능
        assert str(ErrorCode.USER_001) == "USER_001"
        assert isinstance(ErrorCode.USER_001, str)


class TestErrorMessage:
    """에러 메시지 상수 테스트"""

    def test_user_error_messages(self):
        """사용자 관리 에러 메시지"""
        assert ErrorMessage.EMAIL_ALREADY_EXISTS == "이미 사용 중인 이메일입니다"
        assert ErrorMessage.USER_NOT_FOUND == "사용자를 찾을 수 없습니다"
        assert ErrorMessage.PASSWORD_STRENGTH_INSUFFICIENT == "비밀번호 강도가 부족합니다"
        assert ErrorMessage.CURRENT_PASSWORD_MISMATCH == "현재 비밀번호가 일치하지 않습니다"

    def test_auth_error_messages(self):
        """인증 에러 메시지"""
        assert ErrorMessage.INVALID_CREDENTIALS == "이메일 또는 비밀번호가 올바르지 않습니다"
        assert ErrorMessage.TOKEN_EXPIRED == "토큰이 만료되었습니다"
        assert ErrorMessage.INVALID_TOKEN == "유효하지 않은 토큰입니다"
        assert ErrorMessage.ACCOUNT_LOCKED == "계정이 잠겨있습니다 ({minutes}분 후 재시도)"
        assert ErrorMessage.ACCOUNT_INACTIVE == "비활성화된 계정입니다"
        assert ErrorMessage.INVALID_REFRESH_TOKEN == "리프레시 토큰이 유효하지 않습니다"

    def test_authz_error_messages(self):
        """인가 에러 메시지"""
        assert ErrorMessage.INSUFFICIENT_PERMISSIONS == "권한이 부족합니다"
        assert ErrorMessage.INVALID_SCOPE == "유효하지 않은 권한 범위입니다"

    def test_internal_error_message(self):
        """내부 에러 메시지"""
        assert ErrorMessage.INTERNAL_SERVER_ERROR == "서버 내부 오류가 발생했습니다"

    def test_account_locked_message_formatting(self):
        """계정 잠금 메시지 포맷팅"""
        # 메시지는 format string이므로 {minutes} placeholder 확인
        message = ErrorMessage.ACCOUNT_LOCKED
        assert "{minutes}" in message
        formatted = message.format(minutes=15)
        assert "15분" in formatted


class TestConstantsConsistency:
    """상수 간 일관성 테스트"""

    def test_token_ttl_consistency(self):
        """액세스 토큰 TTL과 블랙리스트 TTL 일관성"""
        # 블랙리스트 TTL은 액세스 토큰 TTL 이상이어야 함
        assert TokenSettings.BLACKLIST_TTL_SECONDS >= TokenSettings.ACCESS_TOKEN_TTL_SECONDS

    def test_pagination_limits(self):
        """페이징 제한 일관성"""
        # 최대 페이지 크기가 기본 크기보다 커야 함
        assert Pagination.MAX_PAGE_SIZE >= Pagination.DEFAULT_PAGE_SIZE

    def test_error_code_uniqueness(self):
        """에러 코드 중복 검사"""
        # 모든 에러 코드가 고유한지 확인
        codes = [
            ErrorCode.USER_001,
            ErrorCode.USER_002,
            ErrorCode.USER_003,
            ErrorCode.USER_004,
            ErrorCode.AUTH_001,
            ErrorCode.AUTH_002,
            ErrorCode.AUTH_003,
            ErrorCode.AUTH_004,
            ErrorCode.AUTH_005,
            ErrorCode.AUTH_006,
            ErrorCode.AUTHZ_001,
            ErrorCode.AUTHZ_002,
            ErrorCode.INTERNAL_ERROR,
        ]
        assert len(codes) == len(set(codes))

    def test_password_policy_values_positive(self):
        """비밀번호 정책 값이 양수"""
        assert PasswordPolicy.MIN_LENGTH > 0
        assert PasswordPolicy.MAX_FAILED_ATTEMPTS > 0
        assert PasswordPolicy.LOCKOUT_MINUTES > 0

    def test_token_values_positive(self):
        """토큰 설정 값이 양수"""
        assert TokenSettings.ACCESS_TOKEN_TTL_SECONDS > 0
        assert TokenSettings.ACCESS_TOKEN_EXPIRES_IN > 0
        assert TokenSettings.REFRESH_TOKEN_EXPIRES_DAYS > 0
        assert TokenSettings.BLACKLIST_TTL_SECONDS > 0

    def test_cache_values_positive(self):
        """캐시 설정 값이 양수"""
        assert CacheSettings.PERMISSIONS_CACHE_TTL_SECONDS > 0
