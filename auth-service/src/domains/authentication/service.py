"""Authentication 도메인 Service

비즈니스 로직을 처리하는 레이어입니다.
"""

import asyncio
import hashlib
import random
from datetime import UTC, datetime, timedelta

import asyncpg

from src.domains.authentication import repository, schemas
from src.domains.users import repository as users_repository
from src.domains.users import service as users_service
from src.shared.constants import TokenSettings
from src.shared.database.transaction import transaction
from src.shared.exceptions import UnauthorizedException
from src.shared.logging import security_logger
from src.shared.security.jwt_handler import InvalidTokenError, TokenExpiredError, jwt_handler
from src.shared.security.password_hasher import password_hasher
from src.shared.security.redis_store import redis_store

# ===== 로그인 헬퍼 함수들 =====


async def _check_account_locked(email: str, ip_address: str | None = None) -> None:
    """계정 잠금 상태 확인.

    보안 참고:
        계정 존재 여부 노출 방지를 위해 일반적인 로그인 실패 메시지를 사용합니다.
        실제 잠금 상태는 보안 로그에만 기록됩니다.

    Args:
        email: 사용자 이메일
        ip_address: IP 주소

    Raises:
        UnauthorizedException: 계정이 잠긴 경우 (일반 메시지)
    """
    is_locked, remaining_time = await redis_store.is_account_locked(email)
    if is_locked:
        # 보안 로그에는 상세 정보 기록 (내부 모니터링용)
        security_logger.log_login_failed(
            email=email,
            ip_address=ip_address,
            reason="account_locked",
        )
        # 사용자에게는 일반 로그인 실패 메시지 (계정 존재 여부 숨김)
        raise UnauthorizedException(
            error_code="AUTH_001",
            message="이메일 또는 비밀번호가 올바르지 않습니다",
        )


async def _authenticate_user(
    connection: asyncpg.Connection,
    email: str,
    password: str,
    ip_address: str | None,
    user_agent: str | None,
) -> asyncpg.Record:
    """사용자 인증 (이메일/비밀번호 검증).

    Args:
        connection: 데이터베이스 연결
        email: 사용자 이메일
        password: 비밀번호
        ip_address: IP 주소
        user_agent: User-Agent

    Returns:
        사용자 레코드

    Raises:
        UnauthorizedException: 인증 실패
    """
    # 사용자 조회
    user_row = await users_repository.get_user_by_email(connection, email)
    if not user_row:
        # 타이밍 공격 방지: 존재하지 않는 이메일 조회 시 무작위 지연 추가
        # 비밀번호 검증 시간과 유사하게 맞춰 사용자 열거 공격 방지
        await asyncio.sleep(random.uniform(0.1, 0.3))  # noqa: S311
        failed_count = await redis_store.increment_failed_login(email)
        security_logger.log_login_failed(
            email=email,
            ip_address=ip_address,
            reason="user_not_found",
            failed_count=failed_count,
        )
        raise UnauthorizedException(
            error_code="AUTH_001",
            message="이메일 또는 비밀번호가 올바르지 않습니다",
        )

    # 비밀번호 검증 (비동기)
    is_valid = await password_hasher.verify_async(password, user_row["password_hash"])
    if not is_valid:
        failed_count = await redis_store.increment_failed_login(email)

        # 로그인 이력 저장 (실패)
        await repository.save_login_history(
            connection,
            user_id=user_row["id"],
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
        )

        # 5회 초과 시 계정 잠금
        if failed_count >= 5:
            # 보안 로그에는 계정 잠금 사실 기록 (내부 모니터링용)
            security_logger.log_account_locked(
                email=email,
                ip_address=ip_address,
                failed_count=failed_count,
            )
            # 사용자에게는 일반 로그인 실패 메시지 (계정 존재 여부 숨김)
            raise UnauthorizedException(
                error_code="AUTH_001",
                message="이메일 또는 비밀번호가 올바르지 않습니다",
            )

        security_logger.log_login_failed(
            email=email,
            ip_address=ip_address,
            reason="invalid_password",
            failed_count=failed_count,
        )
        raise UnauthorizedException(
            error_code="AUTH_001",
            message="이메일 또는 비밀번호가 올바르지 않습니다",
        )

    # 비활성화된 계정 확인
    if not user_row["is_active"]:
        # 보안 로그에는 비활성화 사실 기록 (내부 모니터링용)
        security_logger.log_login_failed(
            email=email,
            ip_address=ip_address,
            reason="account_inactive",
        )
        # 사용자에게는 일반 로그인 실패 메시지 (계정 상태 숨김)
        raise UnauthorizedException(
            error_code="AUTH_001",
            message="이메일 또는 비밀번호가 올바르지 않습니다",
        )

    return user_row


async def _create_auth_tokens(
    connection: asyncpg.Connection,
    user_id: int,
    email: str,
) -> tuple[str, str]:
    """인증 토큰 생성 (Access + Refresh).

    Args:
        connection: 데이터베이스 연결
        user_id: 사용자 ID
        email: 사용자 이메일

    Returns:
        (access_token, refresh_token) 튜플
    """
    # 역할 및 권한 조회 (캐시 활용)
    permissions_data = await users_service.get_user_permissions_with_cache(connection, user_id)
    roles = permissions_data["roles"]
    permissions = permissions_data["permissions"]

    # 토큰 발급
    access_token = jwt_handler.create_access_token(
        user_id=user_id,
        email=email,
        roles=roles,
        permissions=permissions,
    )
    refresh_token = jwt_handler.create_refresh_token(user_id=user_id)

    # Access Token JTI 등록 (블랙리스트 완전성)
    access_payload = jwt_handler.decode_token(access_token)
    access_jti = access_payload.get("jti")
    if access_jti:
        await redis_store.register_active_token(
            user_id=user_id,
            jti=access_jti,
            ttl_seconds=TokenSettings.ACCESS_TOKEN_TTL_SECONDS,
        )

    return access_token, refresh_token


async def _save_login_success(
    connection: asyncpg.Connection,
    user_id: int,
    refresh_token: str,
    device_info: str | None,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    """로그인 성공 데이터 저장 (트랜잭션).

    Uses PostgreSQL advisory lock to prevent race conditions during concurrent logins
    for the same user.

    Args:
        connection: 데이터베이스 연결
        user_id: 사용자 ID
        refresh_token: Refresh Token
        device_info: 디바이스 정보
        ip_address: IP 주소
        user_agent: User-Agent
    """
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    refresh_token_expires = datetime.now(UTC) + timedelta(days=7)

    async with transaction(connection):
        # Acquire advisory lock for this user to prevent concurrent login race conditions
        # Lock is automatically released when transaction commits or rolls back
        await connection.execute("SELECT pg_advisory_xact_lock($1)", user_id)

        # Refresh Token 저장
        await repository.save_refresh_token(
            connection,
            user_id=user_id,
            token_hash=token_hash,
            device_info=device_info,
            expires_at=refresh_token_expires,
        )

        # 로그인 이력 저장 (성공)
        await repository.save_login_history(
            connection,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
        )

        # 마지막 로그인 시각 업데이트
        await repository.update_last_login(connection, user_id)


async def _validate_refresh_token_and_get_user(
    connection: asyncpg.Connection,
    refresh_token: str,
) -> tuple[asyncpg.Record, asyncpg.Record]:
    """Refresh token 검증 및 사용자 조회.

    Args:
        connection: 데이터베이스 연결
        refresh_token: Refresh token

    Returns:
        (token_row, user_row) 튜플

    Raises:
        UnauthorizedException: 유효하지 않은 토큰 또는 비활성 계정
    """
    # 토큰 디코딩
    try:
        jwt_handler.decode_token(refresh_token)
    except (TokenExpiredError, InvalidTokenError):
        raise UnauthorizedException(
            error_code="AUTH_006",
            message="리프레시 토큰이 유효하지 않습니다",
        )

    # 토큰 해시 계산 및 DB 조회
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    token_row = await repository.get_refresh_token(connection, token_hash)
    if not token_row:
        raise UnauthorizedException(
            error_code="AUTH_006",
            message="리프레시 토큰이 유효하지 않습니다",
        )

    # 사용자 조회
    user_row = await users_repository.get_user_by_id(connection, token_row["user_id"])
    if not user_row or not user_row["is_active"]:
        raise UnauthorizedException(
            error_code="AUTH_005",
            message="비활성화된 계정입니다",
        )

    return token_row, user_row


async def _rotate_refresh_token(
    connection: asyncpg.Connection,
    old_token_hash: str,
    new_refresh_token: str,
    user_id: int,
    device_info: str | None,
) -> None:
    """기존 refresh token 폐기 및 새 토큰 저장 (Token Rotation).

    Args:
        connection: 데이터베이스 연결
        old_token_hash: 기존 토큰 해시
        new_refresh_token: 새 refresh token
        user_id: 사용자 ID
        device_info: 디바이스 정보
    """
    new_token_hash = hashlib.sha256(new_refresh_token.encode()).hexdigest()
    refresh_token_expires = datetime.now(UTC) + timedelta(days=7)

    async with transaction(connection):
        # 기존 토큰 폐기
        await repository.revoke_refresh_token(connection, old_token_hash)

        # 새 토큰 저장
        await repository.save_refresh_token(
            connection,
            user_id=user_id,
            token_hash=new_token_hash,
            device_info=device_info,
            expires_at=refresh_token_expires,
        )


def _build_token_response(access_token: str, refresh_token: str) -> schemas.TokenResponse:
    """토큰 응답 객체를 생성한다.

    Args:
        access_token: 액세스 토큰
        refresh_token: 리프레시 토큰

    Returns:
        토큰 응답 객체
    """
    return schemas.TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=TokenSettings.ACCESS_TOKEN_TTL_SECONDS,
    )


# ===== 메인 로그인 함수 =====


async def login(
    connection: asyncpg.Connection,
    request: schemas.LoginRequest,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> schemas.TokenResponse:
    """로그인 (리팩토링: 작은 함수들로 분해).

    Args:
        connection: 데이터베이스 연결
        request: 로그인 요청
        ip_address: IP 주소
        user_agent: User-Agent

    Returns:
        토큰 정보

    Raises:
        UnauthorizedException: 로그인 실패
    """
    # 1. 계정 잠금 확인
    await _check_account_locked(request.email, ip_address)

    # 2. 사용자 인증
    user_row = await _authenticate_user(
        connection,
        request.email,
        request.password,
        ip_address,
        user_agent,
    )

    # 3. 토큰 생성
    access_token, refresh_token = await _create_auth_tokens(
        connection,
        user_row["id"],
        user_row["email"],
    )

    # 4. 로그인 성공 데이터 저장
    await _save_login_success(
        connection,
        user_row["id"],
        refresh_token,
        request.device_info,
        ip_address,
        user_agent,
    )

    # 5. 실패 횟수 초기화
    await redis_store.reset_failed_login(request.email)

    # 6. 로그인 성공 로깅
    security_logger.log_login_success(
        user_id=user_row["id"],
        email=user_row["email"],
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return _build_token_response(access_token, refresh_token)


async def logout(
    connection: asyncpg.Connection,
    access_token: str,
    refresh_token: str | None = None,
) -> None:
    """로그아웃

    Args:
        connection: 데이터베이스 연결
        access_token: 액세스 토큰

    Raises:
        UnauthorizedException: 유효하지 않은 토큰
    """
    # 토큰 디코딩
    try:
        payload = jwt_handler.decode_token(access_token)
    except (TokenExpiredError, InvalidTokenError):
        raise UnauthorizedException(
            error_code="AUTH_003",
            message="유효하지 않은 토큰입니다",
        )

    # JTI 추출
    jti = payload.get("jti")
    if not jti:
        raise UnauthorizedException(
            error_code="AUTH_003",
            message="유효하지 않은 토큰입니다",
        )

    # 액세스 토큰 블랙리스트 추가 (TTL: 만료 시간까지)
    exp = payload.get("exp")
    if exp:
        ttl = max(0, exp - int(datetime.now(UTC).timestamp()))
        await redis_store.blacklist_token(jti, ttl)

    # Active Token 목록에서 제거
    user_id = payload.get("sub")
    if user_id:
        await redis_store.remove_active_token(int(user_id), jti)

    # 리프레시 토큰이 전달된 경우 해당 토큰도 폐기
    if refresh_token:
        refresh_token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        await repository.revoke_refresh_token(connection, refresh_token_hash)


async def refresh_access_token(
    connection: asyncpg.Connection,
    request: schemas.RefreshTokenRequest,
) -> schemas.TokenResponse:
    """토큰 갱신 (리팩토링: 검증 및 교체 로직 분리).

    Args:
        connection: 데이터베이스 연결
        request: 토큰 갱신 요청

    Returns:
        새로운 토큰 정보

    Raises:
        UnauthorizedException: 유효하지 않은 리프레시 토큰
    """
    # 1. 토큰 검증 및 사용자 조회
    token_row, user_row = await _validate_refresh_token_and_get_user(
        connection, request.refresh_token
    )

    # 2. 새 토큰 생성
    new_access_token, new_refresh_token = await _create_auth_tokens(
        connection, token_row["user_id"], user_row["email"]
    )

    # 3. 토큰 교체 (Refresh Token Rotation)
    old_token_hash = hashlib.sha256(request.refresh_token.encode()).hexdigest()
    await _rotate_refresh_token(
        connection,
        old_token_hash,
        new_refresh_token,
        token_row["user_id"],
        token_row["device_info"],
    )

    return _build_token_response(new_access_token, new_refresh_token)


async def get_sessions(
    connection: asyncpg.Connection,
    user_id: int,
    current_token: str | None = None,
) -> list[schemas.SessionResponse]:
    """활성 세션 목록 조회

    Args:
        connection: 데이터베이스 연결
        user_id: 사용자 ID
        current_token: 현재 액세스 토큰 (현재 세션 표시용)

    Returns:
        세션 목록
    """
    session_rows = await repository.get_active_sessions(connection, user_id)

    # 현재 토큰의 JTI 추출 (있는 경우)
    if current_token:
        try:
            payload = jwt_handler.decode_token(current_token)
            payload.get("jti")
        except ValueError:
            pass

    sessions = [
        schemas.SessionResponse(
            id=row["id"],
            device_info=row["device_info"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            is_current=False,  # 정확한 매칭은 어려움 (refresh_token과 access_token이 별도)
        )
        for row in session_rows
    ]

    return sessions


async def revoke_all_sessions(
    connection: asyncpg.Connection,
    user_id: int,
) -> None:
    """모든 세션 완전히 종료 (Access Token + Refresh Token)

    계정 탈취나 보안 위협 시 사용자의 모든 활성 토큰을 즉시 무효화합니다.

    Args:
        connection: 데이터베이스 연결
        user_id: 사용자 ID
    """
    # 1. 모든 Refresh Token 폐기 (DB)
    await repository.revoke_all_user_tokens(connection, user_id)

    # 2. 모든 활성 Access Token JTI 조회 (Redis)
    active_jtis = await redis_store.get_user_active_tokens(user_id)

    # 3. 모든 Access Token을 블랙리스트에 추가
    for jti in active_jtis:
        # 블랙리스트 TTL은 Access Token 만료 시간보다 길게 (여유)
        await redis_store.blacklist_token(jti, ttl_seconds=1800)  # 30분

    # 4. Active Token 목록 삭제
    await redis_store.clear_user_active_tokens(user_id)

    # 이제 해당 사용자의 모든 토큰이 완전히 무효화됨
    # - Refresh Token: DB에서 폐기됨
    # - Access Token: Redis 블랙리스트에 추가되어 즉시 차단됨
