"""인증 SDK 데이터 모델 모듈.

JWT 토큰 페이로드, 현재 사용자 정보, 토큰 검증 응답 등의
Pydantic 모델을 정의합니다.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class TokenType(StrEnum):
    """토큰 유형 열거형."""

    ACCESS = "access"
    REFRESH = "refresh"


class CurrentUser(BaseModel):
    """현재 인증된 사용자 정보 모델.

    미들웨어에서 JWT 토큰을 검증한 후 request.state.user에 설정되는 모델입니다.

    Attributes:
        id: 사용자 고유 식별자
        email: 사용자 이메일 주소
        username: 사용자명
        display_name: 표시 이름
        roles: 사용자에게 부여된 역할 목록
        permissions: 사용자에게 부여된 권한 목록
        is_active: 계정 활성 상태
        is_superuser: 슈퍼유저 여부
    """

    id: int
    email: str
    username: str
    display_name: str = ""
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    is_active: bool = True
    is_superuser: bool = False


class TokenPayload(BaseModel):
    """JWT 토큰 페이로드 모델.

    JWT 토큰 디코딩 후 페이로드 데이터를 구조화하는 모델입니다.

    Attributes:
        sub: 사용자 ID (subject)
        email: 사용자 이메일 주소
        roles: 역할 목록
        permissions: 권한 목록
        exp: 토큰 만료 시간 (Unix timestamp)
        iat: 토큰 발행 시간 (Unix timestamp)
        jti: 토큰 고유 식별자
        type: 토큰 유형 (access 또는 refresh)
    """

    sub: int
    email: str
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    exp: int
    iat: int
    jti: str
    type: TokenType = TokenType.ACCESS


class TokenIntrospectionResponse(BaseModel):
    """토큰 인트로스펙션 응답 모델.

    인증 서비스의 토큰 검증 API 응답을 나타냅니다.

    Attributes:
        active: 토큰 유효 여부
        user_id: 사용자 ID
        email: 사용자 이메일 주소
        roles: 역할 목록
        permissions: 권한 목록
        exp: 토큰 만료 시간 (Unix timestamp)
    """

    active: bool
    user_id: int | None = None
    email: str | None = None
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    exp: int | None = None
