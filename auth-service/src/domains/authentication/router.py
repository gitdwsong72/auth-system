"""Authentication 도메인 Router

인증 및 세션 관리 API 엔드포인트를 정의합니다.
"""

import asyncpg
from fastapi import APIRouter, Depends, Header, Request, status

from src.domains.authentication import schemas, service
from src.shared.database.connection import get_db_connection
from src.shared.dependencies import extract_bearer_token, get_current_active_user
from src.shared.schemas import ApiResponse

router = APIRouter()


@router.post(
    "/login",
    response_model=ApiResponse[schemas.TokenResponse],
    summary="로그인",
    description="이메일과 비밀번호로 로그인하고 토큰을 발급받습니다",
)
async def login(
    request: schemas.LoginRequest,
    http_request: Request,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """로그인"""
    # IP 주소 및 User-Agent 추출
    ip_address = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")

    tokens = await service.login(
        conn,
        request,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return ApiResponse(
        success=True,
        data=tokens,
        message="로그인에 성공했습니다",
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="로그아웃",
    description="현재 세션을 종료합니다",
)
async def logout(
    authorization: str = Header(...),
    body: schemas.LogoutRequest | None = None,
    _: dict = Depends(get_current_active_user),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """로그아웃"""
    # Bearer 토큰 추출
    access_token = extract_bearer_token(authorization)

    refresh_token = body.refresh_token if body else None
    await service.logout(conn, access_token, refresh_token=refresh_token)

    # 204 No Content - no response body


@router.post(
    "/refresh",
    response_model=ApiResponse[schemas.TokenResponse],
    summary="토큰 갱신",
    description="리프레시 토큰으로 새로운 액세스 토큰을 발급받습니다",
)
async def refresh_token(
    request: schemas.RefreshTokenRequest,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """토큰 갱신"""
    tokens = await service.refresh_access_token(conn, request)

    return ApiResponse(
        success=True,
        data=tokens,
        message="토큰이 갱신되었습니다",
    )


@router.get(
    "/sessions",
    response_model=ApiResponse[list[schemas.SessionResponse]],
    summary="활성 세션 목록",
    description="현재 사용자의 활성 세션 목록을 조회합니다",
)
async def get_sessions(
    current_user: dict = Depends(get_current_active_user),
    authorization: str = Header(None),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """활성 세션 목록 조회"""
    # 현재 토큰 추출
    current_token = None
    if authorization and authorization.startswith("Bearer "):
        current_token = extract_bearer_token(authorization)

    sessions = await service.get_sessions(conn, current_user["id"], current_token)

    return ApiResponse(
        success=True,
        data=sessions,
    )


@router.delete(
    "/sessions",
    response_model=ApiResponse[None],
    summary="전체 세션 종료",
    description="현재 사용자의 모든 세션을 종료합니다",
)
async def revoke_all_sessions(
    current_user: dict = Depends(get_current_active_user),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """전체 세션 종료"""
    await service.revoke_all_sessions(conn, current_user["id"])

    return ApiResponse(
        success=True,
        data=None,
        message="모든 세션이 종료되었습니다",
    )
