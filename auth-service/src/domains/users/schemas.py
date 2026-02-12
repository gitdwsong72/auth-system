"""Users 도메인 Pydantic 스키마"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    """회원가입 요청"""

    email: EmailStr = Field(..., description="이메일 주소")
    password: str = Field(..., min_length=8, max_length=128, description="비밀번호 (8자 이상)")
    username: str = Field(..., min_length=3, max_length=50, description="사용자명 (3-50자)")
    display_name: str | None = Field(None, max_length=100, description="표시 이름")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """사용자명 검증 (영문, 숫자, 언더스코어, 하이픈만 허용)"""
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("사용자명은 영문, 숫자, 언더스코어, 하이픈만 사용할 수 있습니다")
        return v


class UserRegisterResponse(BaseModel):
    """회원가입 응답"""

    id: int = Field(..., description="사용자 ID")
    email: str = Field(..., description="이메일 주소")
    username: str = Field(..., description="사용자명")
    display_name: str | None = Field(None, description="표시 이름")
    created_at: datetime = Field(..., description="생성 시각")


class UserProfileResponse(BaseModel):
    """사용자 프로필 응답"""

    id: int = Field(..., description="사용자 ID")
    email: str = Field(..., description="이메일 주소")
    username: str = Field(..., description="사용자명")
    display_name: str | None = Field(None, description="표시 이름")
    phone: str | None = Field(None, description="전화번호")
    avatar_url: str | None = Field(None, description="프로필 이미지 URL")
    is_active: bool = Field(..., description="활성화 여부")
    email_verified: bool = Field(..., description="이메일 인증 여부")
    created_at: datetime = Field(..., description="생성 시각")
    last_login_at: datetime | None = Field(None, description="마지막 로그인 시각")
    roles: list[str] = Field(default_factory=list, description="역할 목록")
    permissions: list[str] = Field(default_factory=list, description="권한 목록")


class UserUpdateRequest(BaseModel):
    """사용자 프로필 수정 요청"""

    display_name: str | None = Field(None, max_length=100, description="표시 이름")
    phone: str | None = Field(None, max_length=20, description="전화번호")
    avatar_url: str | None = Field(None, max_length=500, description="프로필 이미지 URL")

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith(("https://", "http://")):
            raise ValueError("avatar_url은 http:// 또는 https:// 프로토콜만 허용됩니다")
        return v


class ChangePasswordRequest(BaseModel):
    """비밀번호 변경 요청"""

    current_password: str = Field(..., description="현재 비밀번호")
    new_password: str = Field(
        ..., min_length=8, max_length=128, description="새 비밀번호 (8자 이상)"
    )


class UserListResponse(BaseModel):
    """사용자 목록 항목"""

    id: int = Field(..., description="사용자 ID")
    email: str = Field(..., description="이메일 주소")
    username: str = Field(..., description="사용자명")
    display_name: str | None = Field(None, description="표시 이름")
    is_active: bool = Field(..., description="활성화 여부")
    email_verified: bool = Field(..., description="이메일 인증 여부")
    created_at: datetime = Field(..., description="생성 시각")
    last_login_at: datetime | None = Field(None, description="마지막 로그인 시각")


class UserDetailResponse(BaseModel):
    """사용자 상세 정보 (관리자용)"""

    id: int = Field(..., description="사용자 ID")
    email: str = Field(..., description="이메일 주소")
    username: str = Field(..., description="사용자명")
    display_name: str | None = Field(None, description="표시 이름")
    phone: str | None = Field(None, description="전화번호")
    avatar_url: str | None = Field(None, description="프로필 이미지 URL")
    is_active: bool = Field(..., description="활성화 여부")
    email_verified: bool = Field(..., description="이메일 인증 여부")
    created_at: datetime = Field(..., description="생성 시각")
    updated_at: datetime | None = Field(None, description="수정 시각")
    last_login_at: datetime | None = Field(None, description="마지막 로그인 시각")
    roles: list[str] = Field(default_factory=list, description="역할 목록")
    permissions: list[str] = Field(default_factory=list, description="권한 목록")
