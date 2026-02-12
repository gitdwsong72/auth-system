"""Users 도메인 Router

사용자 관리 API 엔드포인트를 정의합니다.
"""

import asyncpg
from fastapi import APIRouter, Depends, Query, status

from src.domains.users import schemas, service
from src.shared.database.connection import get_db_connection
from src.shared.dependencies import get_current_active_user, require_permission
from src.shared.schemas import ApiResponse, PaginatedResponse

router = APIRouter()


@router.post(
    "/register",
    response_model=ApiResponse[schemas.UserRegisterResponse],
    status_code=status.HTTP_201_CREATED,
    summary="회원가입",
    description="새로운 사용자를 등록합니다",
)
async def register(
    request: schemas.UserRegisterRequest,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """회원가입"""
    user = await service.register(conn, request)
    return ApiResponse(
        success=True,
        data=user,
        message="회원가입이 완료되었습니다",
    )


@router.get(
    "/me",
    response_model=ApiResponse[schemas.UserProfileResponse],
    summary="내 프로필 조회",
    description="현재 로그인한 사용자의 프로필을 조회합니다",
)
async def get_my_profile(
    current_user: dict = Depends(get_current_active_user),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """내 프로필 조회"""
    profile = await service.get_profile(conn, current_user["id"])
    return ApiResponse(
        success=True,
        data=profile,
    )


@router.put(
    "/me",
    response_model=ApiResponse[schemas.UserProfileResponse],
    summary="프로필 수정",
    description="현재 로그인한 사용자의 프로필을 수정합니다",
)
async def update_my_profile(
    request: schemas.UserUpdateRequest,
    current_user: dict = Depends(get_current_active_user),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """프로필 수정"""
    profile = await service.update_profile(conn, current_user["id"], request)
    return ApiResponse(
        success=True,
        data=profile,
        message="프로필이 수정되었습니다",
    )


@router.put(
    "/me/password",
    response_model=ApiResponse[None],
    summary="비밀번호 변경",
    description="현재 로그인한 사용자의 비밀번호를 변경합니다",
)
async def change_my_password(
    request: schemas.ChangePasswordRequest,
    current_user: dict = Depends(get_current_active_user),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """비밀번호 변경"""
    await service.change_password(conn, current_user["id"], request)
    return ApiResponse(
        success=True,
        data=None,
        message="비밀번호가 변경되었습니다",
    )


@router.get(
    "",
    response_model=ApiResponse[PaginatedResponse[schemas.UserListResponse]],
    summary="사용자 목록 조회 (관리자)",
    description="사용자 목록을 조회합니다 (관리자 전용)",
)
async def list_users(
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    page_size: int = Query(20, ge=1, le=100, description="페이지 크기 (최대 100)"),
    search: str | None = Query(None, description="검색어 (email/username)"),
    is_active: bool | None = Query(None, description="활성화 필터"),
    _: dict = Depends(require_permission("users:read")),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """사용자 목록 조회 (관리자 전용)"""
    users, total = await service.list_users(
        conn,
        page=page,
        page_size=page_size,
        search=search,
        is_active=is_active,
    )

    paginated_data = PaginatedResponse.create(
        items=users,
        total=total,
        page=page,
        page_size=page_size,
    )

    return ApiResponse(
        success=True,
        data=paginated_data,
    )


@router.get(
    "/{user_id}",
    response_model=ApiResponse[schemas.UserDetailResponse],
    summary="사용자 상세 조회 (관리자)",
    description="특정 사용자의 상세 정보를 조회합니다 (관리자 전용)",
)
async def get_user_detail(
    user_id: int,
    _: dict = Depends(require_permission("users:read")),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """사용자 상세 조회 (관리자 전용)"""
    user_detail = await service.get_user_detail(conn, user_id)
    return ApiResponse(
        success=True,
        data=user_detail,
    )
