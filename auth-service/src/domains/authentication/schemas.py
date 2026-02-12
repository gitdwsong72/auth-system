"""Authentication 도메인 Pydantic 스키마"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """로그인 요청"""

    email: EmailStr = Field(..., description="이메일 주소")
    password: str = Field(..., description="비밀번호")
    device_info: str | None = Field(None, max_length=500, description="디바이스 정보")


class TokenResponse(BaseModel):
    """토큰 응답"""

    access_token: str = Field(..., description="액세스 토큰")
    refresh_token: str = Field(..., description="리프레시 토큰")
    token_type: str = Field(default="bearer", description="토큰 타입")
    expires_in: int = Field(..., description="액세스 토큰 만료 시간 (초)")


class LogoutRequest(BaseModel):
    """로그아웃 요청"""

    refresh_token: str | None = Field(None, description="리프레시 토큰 (전달 시 해당 토큰도 폐기)")


class RefreshTokenRequest(BaseModel):
    """토큰 갱신 요청"""

    refresh_token: str = Field(..., description="리프레시 토큰")


class SessionResponse(BaseModel):
    """세션 정보 응답"""

    id: int = Field(..., description="세션 ID")
    device_info: str | None = Field(None, description="디바이스 정보")
    created_at: datetime = Field(..., description="생성 시각")
    expires_at: datetime = Field(..., description="만료 시각")
    is_current: bool = Field(default=False, description="현재 세션 여부")
