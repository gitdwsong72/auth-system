"""Application-wide constants and configuration values.

This module centralizes all magic numbers, error codes, and configuration constants
to improve maintainability and prevent hardcoded values scattered throughout the codebase.
"""

from enum import StrEnum

# ===== Password Policy =====


class PasswordPolicy:
    """Password security policy constants."""

    MIN_LENGTH = 8
    """Minimum password length"""

    MAX_FAILED_ATTEMPTS = 5
    """Maximum failed login attempts before account lockout"""

    LOCKOUT_MINUTES = 15
    """Account lockout duration in minutes"""


# ===== Token Settings =====


class TokenSettings:
    """Authentication token configuration."""

    ACCESS_TOKEN_TTL_SECONDS = 1800  # 30 minutes
    """Access token time-to-live in seconds"""

    ACCESS_TOKEN_EXPIRES_IN = 900  # 15 minutes
    """Access token expiration returned to client (in seconds)"""

    REFRESH_TOKEN_EXPIRES_DAYS = 7
    """Refresh token expiration in days"""

    BLACKLIST_TTL_SECONDS = 1800  # 30 minutes
    """Token blacklist TTL (should match or exceed access token TTL)"""


# ===== Cache Settings =====


class CacheSettings:
    """Redis cache configuration."""

    PERMISSIONS_CACHE_TTL_SECONDS = 300  # 5 minutes
    """User permissions cache TTL in seconds"""


# ===== Pagination =====


class Pagination:
    """Pagination limits for list APIs."""

    DEFAULT_PAGE_SIZE = 20
    """Default number of items per page"""

    MAX_PAGE_SIZE = 100
    """Maximum allowed page size"""


# ===== Error Codes =====


class ErrorCode(StrEnum):
    """Standardized error codes for the entire application.

    Error code naming convention:
    - USER_XXX: User management errors
    - AUTH_XXX: Authentication errors
    - AUTHZ_XXX: Authorization errors
    - INTERNAL_XXX: Internal server errors
    """

    # User Management (USER_XXX)
    USER_001 = "USER_001"  # Email already exists
    USER_002 = "USER_002"  # User not found
    USER_003 = "USER_003"  # Password strength insufficient
    USER_004 = "USER_004"  # Current password mismatch

    # Authentication (AUTH_XXX)
    AUTH_001 = "AUTH_001"  # Invalid email or password
    AUTH_002 = "AUTH_002"  # Token expired
    AUTH_003 = "AUTH_003"  # Invalid token
    AUTH_004 = "AUTH_004"  # Account locked
    AUTH_005 = "AUTH_005"  # Account inactive
    AUTH_006 = "AUTH_006"  # Invalid refresh token

    # Authorization (AUTHZ_XXX)
    AUTHZ_001 = "AUTHZ_001"  # Insufficient permissions
    AUTHZ_002 = "AUTHZ_002"  # Invalid scope

    # Internal Errors
    INTERNAL_ERROR = "INTERNAL_ERROR"  # Generic internal server error


# ===== Error Messages =====


class ErrorMessage:
    """User-facing error messages (Korean).

    These messages provide clear, user-friendly explanations for error conditions.
    Note: S105 warnings suppressed - these are error messages, not passwords.
    """

    # User Management
    EMAIL_ALREADY_EXISTS = "이미 사용 중인 이메일입니다"
    USER_NOT_FOUND = "사용자를 찾을 수 없습니다"
    PASSWORD_STRENGTH_INSUFFICIENT = "비밀번호 강도가 부족합니다"  # noqa: S105
    CURRENT_PASSWORD_MISMATCH = "현재 비밀번호가 일치하지 않습니다"  # noqa: S105

    # Authentication
    INVALID_CREDENTIALS = "이메일 또는 비밀번호가 올바르지 않습니다"
    TOKEN_EXPIRED = "토큰이 만료되었습니다"
    INVALID_TOKEN = "유효하지 않은 토큰입니다"
    ACCOUNT_LOCKED = "계정이 잠겨있습니다 ({minutes}분 후 재시도)"
    ACCOUNT_INACTIVE = "비활성화된 계정입니다"
    INVALID_REFRESH_TOKEN = "리프레시 토큰이 유효하지 않습니다"

    # Authorization
    INSUFFICIENT_PERMISSIONS = "권한이 부족합니다"
    INVALID_SCOPE = "유효하지 않은 권한 범위입니다"

    # Internal
    INTERNAL_SERVER_ERROR = "서버 내부 오류가 발생했습니다"
