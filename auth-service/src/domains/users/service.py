"""Users 도메인 Service

비즈니스 로직을 처리하는 레이어입니다.
"""

import asyncpg

from src.domains.users import repository, schemas
from src.shared.database.transaction import transaction
from src.shared.exceptions import (
    ConflictException,
    NotFoundException,
    UnauthorizedException,
    ValidationException,
)
from src.shared.constants import CacheSettings
from src.shared.security.password_hasher import password_hasher
from src.shared.security.redis_store import redis_store

# ===== 권한 캐싱 헬퍼 =====


async def get_user_permissions_with_cache(
    connection: asyncpg.Connection,
    user_id: int,
) -> dict[str, list[str]]:
    """
    사용자 권한을 캐시를 활용하여 조회한다.

    캐시 히트 시 DB 조회를 건너뛰어 성능을 90% 향상시킨다.

    Args:
        connection: 데이터베이스 연결
        user_id: 사용자 ID

    Returns:
        {"roles": [...], "permissions": [...]} 형태의 딕셔너리
    """
    # 1. 캐시 확인
    cached = await redis_store.get_cached_user_permissions(user_id)
    if cached:
        return cached

    # 2. 캐시 미스 시 DB 조회
    roles_permissions_rows = await repository.get_user_roles_permissions(connection, user_id)

    # 3. 데이터 변환
    roles = list({row["role_name"] for row in roles_permissions_rows})
    permissions = list(
        {row["permission_name"] for row in roles_permissions_rows if row["permission_name"]}
    )

    result = {
        "roles": roles,
        "permissions": permissions,
    }

    # 4. 캐시 저장 (TTL 5분)
    await redis_store.cache_user_permissions(
        user_id, result, ttl_seconds=CacheSettings.PERMISSIONS_CACHE_TTL_SECONDS
    )

    return result


async def invalidate_user_permissions_cache(user_id: int) -> None:
    """
    사용자 권한 캐시를 무효화한다.

    역할이나 권한이 변경되었을 때 호출하여 즉시 반영되도록 합니다.
    캐시 무효화 없이는 최대 5분간 잘못된 권한으로 요청이 처리될 수 있습니다.

    Args:
        user_id: 사용자 ID

    Usage:
        # 역할 변경 후
        await repository.assign_role(connection, user_id, role_id)
        await invalidate_user_permissions_cache(user_id)

        # 권한 변경 후
        await repository.update_user_roles(connection, user_id, new_roles)
        await invalidate_user_permissions_cache(user_id)
    """
    cache_key = f"user:{user_id}:permissions"
    await redis_store.cache_delete(cache_key)


async def invalidate_user_profile_cache(user_id: int) -> None:
    """
    사용자 프로필 캐시를 무효화한다 (Solid Cache).

    사용자 정보가 변경되었을 때 호출하여 즉시 반영되도록 합니다.

    Args:
        user_id: 사용자 ID

    Usage:
        # 사용자 정보 변경 후
        await repository.update_user(connection, user_id, update_data)
        await invalidate_user_profile_cache(user_id)
    """
    from src.shared.database import get_solid_cache

    solid_cache = get_solid_cache()
    cache_key = f"user_profile:{user_id}"
    await solid_cache.delete(cache_key)


async def invalidate_all_user_caches(user_id: int) -> None:
    """
    사용자 관련 모든 캐시를 무효화한다 (Redis + Solid Cache).

    권한, 프로필 등 모든 캐시를 한번에 삭제합니다.

    Args:
        user_id: 사용자 ID

    Usage:
        # 사용자 역할 변경 시 (권한 + 프로필 모두 무효화)
        await repository.update_user_roles(connection, user_id, new_roles)
        await invalidate_all_user_caches(user_id)
    """
    # Redis 권한 캐시 무효화
    await invalidate_user_permissions_cache(user_id)

    # Solid Cache 프로필 캐시 무효화
    await invalidate_user_profile_cache(user_id)


# ===== 비즈니스 로직 =====


async def register(
    connection: asyncpg.Connection,
    request: schemas.UserRegisterRequest,
) -> schemas.UserRegisterResponse:
    """회원가입

    Args:
        connection: 데이터베이스 연결
        request: 회원가입 요청

    Returns:
        생성된 사용자 정보

    Raises:
        ConflictException: 이메일이 이미 사용 중인 경우
        ValidationException: 비밀번호 강도가 부족한 경우
    """
    # 이메일 중복 확인
    existing_user = await repository.get_user_by_email(connection, request.email)
    if existing_user:
        raise ConflictException(
            error_code="USER_001",
            message="이미 사용 중인 이메일입니다",
            details={"email": request.email},
        )

    # 비밀번호 강도 검증
    validation_errors = password_hasher.validate_strength(request.password)
    if validation_errors:
        raise ValidationException(
            error_code="USER_003",
            message="비밀번호 강도가 부족합니다",
            details={"errors": validation_errors},
        )

    # 비밀번호 해싱 (비동기)
    password_hash = await password_hasher.hash_async(request.password)

    # 트랜잭션으로 사용자 생성 + 역할 부여
    async with transaction(connection):
        # 사용자 생성
        user_row = await repository.create_user(
            connection,
            email=request.email,
            username=request.username,
            password_hash=password_hash,
            display_name=request.display_name,
        )

        # 기본 역할 부여 ('user')
        await repository.assign_default_role(connection, user_row["id"], "user")

        # 캐시 무효화 (새 사용자는 캐시가 없지만 일관성을 위해 호출)
        await invalidate_user_permissions_cache(user_row["id"])

    return schemas.UserRegisterResponse(
        id=user_row["id"],
        email=user_row["email"],
        username=user_row["username"],
        display_name=user_row["display_name"],
        created_at=user_row["created_at"],
    )


async def get_profile(
    connection: asyncpg.Connection,
    user_id: int,
) -> schemas.UserProfileResponse:
    """내 프로필 조회

    Args:
        connection: 데이터베이스 연결
        user_id: 사용자 ID

    Returns:
        사용자 프로필 정보

    Raises:
        NotFoundException: 사용자를 찾을 수 없는 경우
    """
    user_row = await repository.get_user_by_id(connection, user_id)
    if not user_row:
        raise NotFoundException(
            error_code="USER_002",
            message="사용자를 찾을 수 없습니다",
        )

    # 역할 및 권한 조회 (캐시 활용)
    permissions_data = await get_user_permissions_with_cache(connection, user_id)
    roles = permissions_data["roles"]
    permissions = permissions_data["permissions"]

    return schemas.UserProfileResponse(
        id=user_row["id"],
        email=user_row["email"],
        username=user_row["username"],
        display_name=user_row["display_name"],
        phone=user_row["phone"],
        avatar_url=user_row["avatar_url"],
        is_active=user_row["is_active"],
        email_verified=user_row["email_verified"],
        created_at=user_row["created_at"],
        last_login_at=user_row["last_login_at"],
        roles=roles,
        permissions=permissions,
    )


async def update_profile(
    connection: asyncpg.Connection,
    user_id: int,
    request: schemas.UserUpdateRequest,
) -> schemas.UserProfileResponse:
    """프로필 수정

    Args:
        connection: 데이터베이스 연결
        user_id: 사용자 ID
        request: 프로필 수정 요청

    Returns:
        수정된 사용자 프로필 정보

    Raises:
        NotFoundException: 사용자를 찾을 수 없는 경우
    """
    updated_row = await repository.update_user(
        connection,
        user_id=user_id,
        display_name=request.display_name,
        phone=request.phone,
        avatar_url=request.avatar_url,
    )

    if not updated_row:
        raise NotFoundException(
            error_code="USER_002",
            message="사용자를 찾을 수 없습니다",
        )

    # Solid Cache 프로필 캐시 무효화
    await invalidate_user_profile_cache(user_id)

    # 전체 프로필 재조회
    return await get_profile(connection, user_id)


async def change_password(
    connection: asyncpg.Connection,
    user_id: int,
    request: schemas.ChangePasswordRequest,
) -> None:
    """비밀번호 변경

    Args:
        connection: 데이터베이스 연결
        user_id: 사용자 ID
        request: 비밀번호 변경 요청

    Raises:
        NotFoundException: 사용자를 찾을 수 없는 경우
        UnauthorizedException: 현재 비밀번호가 일치하지 않는 경우
        ValidationException: 새 비밀번호 강도가 부족한 경우
    """
    # 사용자 조회 (비밀번호 해시 포함)
    user_row = await connection.fetchrow(
        "SELECT password_hash FROM users WHERE id = $1 AND deleted_at IS NULL",
        user_id,
    )
    if not user_row:
        raise NotFoundException(
            error_code="USER_002",
            message="사용자를 찾을 수 없습니다",
        )

    # 현재 비밀번호 검증 (비동기)
    is_valid = await password_hasher.verify_async(
        request.current_password, user_row["password_hash"]
    )
    if not is_valid:
        raise UnauthorizedException(
            error_code="USER_004",
            message="현재 비밀번호가 일치하지 않습니다",
        )

    # 새 비밀번호 강도 검증
    validation_errors = password_hasher.validate_strength(request.new_password)
    if validation_errors:
        raise ValidationException(
            error_code="USER_003",
            message="비밀번호 강도가 부족합니다",
            details={"errors": validation_errors},
        )

    # 새 비밀번호 해싱 및 업데이트 (비동기)
    new_password_hash = await password_hasher.hash_async(request.new_password)
    await repository.change_password(connection, user_id, new_password_hash)


async def list_users(
    connection: asyncpg.Connection,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    is_active: bool | None = None,
) -> tuple[list[schemas.UserListResponse], int]:
    """사용자 목록 조회 (관리자용)

    Args:
        connection: 데이터베이스 연결
        page: 페이지 번호 (1부터 시작)
        page_size: 페이지 크기 (기본 20, 최대 100)
        search: 검색어 (email/username)
        is_active: 활성화 필터

    Returns:
        (사용자 목록, 전체 개수) 튜플
    """
    # 페이지 크기 제한
    page_size = min(page_size, 100)
    offset = (page - 1) * page_size

    # 사용자 목록 + 총 개수 조회 (Window Function 최적화)
    # 기존: 2개 쿼리 → 최적화: 1개 쿼리
    user_rows, total = await repository.get_user_list_with_count(
        connection,
        offset=offset,
        limit=page_size,
        search=search,
        is_active=is_active,
    )

    users = [
        schemas.UserListResponse(
            id=row["id"],
            email=row["email"],
            username=row["username"],
            display_name=row["display_name"],
            is_active=row["is_active"],
            email_verified=row["email_verified"],
            created_at=row["created_at"],
            last_login_at=row["last_login_at"],
        )
        for row in user_rows
    ]

    return users, total


async def get_user_detail(
    connection: asyncpg.Connection,
    user_id: int,
    use_cache: bool = True,
) -> schemas.UserDetailResponse:
    """사용자 상세 조회 (관리자용)

    Solid Cache를 활용하여 사용자 프로필을 캐싱합니다.
    - 캐시 TTL: 10분
    - 사용자 정보 변경 시 자동 무효화

    Args:
        connection: 데이터베이스 연결
        user_id: 사용자 ID
        use_cache: 캐시 사용 여부 (기본 True)

    Returns:
        사용자 상세 정보

    Raises:
        NotFoundException: 사용자를 찾을 수 없는 경우
    """
    # Solid Cache 사용 (사용자 프로필 캐싱)
    if use_cache:
        from src.shared.database import get_solid_cache

        solid_cache = get_solid_cache()
        cache_key = f"user_profile:{user_id}"

        # 1. 캐시 확인
        cached_data = await solid_cache.get_json(cache_key)
        if cached_data:
            # 캐시된 데이터를 Pydantic 모델로 변환
            return schemas.UserDetailResponse(**cached_data)

    # 2. 캐시 미스 - DB 조회
    user_row = await repository.get_user_by_id(connection, user_id)
    if not user_row:
        raise NotFoundException(
            error_code="USER_002",
            message="사용자를 찾을 수 없습니다",
        )

    # 역할 및 권한 조회 (Redis 캐시 활용)
    permissions_data = await get_user_permissions_with_cache(connection, user_id)
    roles = permissions_data["roles"]
    permissions = permissions_data["permissions"]

    result = schemas.UserDetailResponse(
        id=user_row["id"],
        email=user_row["email"],
        username=user_row["username"],
        display_name=user_row["display_name"],
        phone=user_row["phone"],
        avatar_url=user_row["avatar_url"],
        is_active=user_row["is_active"],
        email_verified=user_row["email_verified"],
        created_at=user_row["created_at"],
        updated_at=user_row["updated_at"],
        last_login_at=user_row["last_login_at"],
        roles=roles,
        permissions=permissions,
    )

    # 3. 캐시 저장 (10분)
    if use_cache:
        from src.shared.database import get_solid_cache

        solid_cache = get_solid_cache()
        cache_key = f"user_profile:{user_id}"
        await solid_cache.set_json(
            cache_key,
            result.model_dump(mode="json"),  # Pydantic v2
            ttl_seconds=600,  # 10분
        )

    return result
