"""Users 도메인 Repository

데이터베이스 쿼리를 실행하는 레이어입니다.
"""

import asyncpg

from src.shared.utils.query_timing import track_query
from src.shared.utils.sql_loader import create_sql_loader

sql = create_sql_loader("users")


def _sanitize_ilike_pattern(pattern: str | None) -> str | None:
    """Sanitize ILIKE pattern to prevent SQL injection via wildcards.

    Escapes special ILIKE characters (% and _) that could be used for
    unintended wildcard matching or SQL injection.

    Args:
        pattern: User input pattern

    Returns:
        Sanitized pattern with % and _ escaped, or None if input is None
    """
    if pattern is None:
        return None
    # Escape backslash first, then % and _
    return pattern.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def get_user_by_id(connection: asyncpg.Connection, user_id: int) -> asyncpg.Record | None:
    """사용자 ID로 조회

    Args:
        connection: 데이터베이스 연결
        user_id: 사용자 ID

    Returns:
        사용자 레코드 또는 None
    """
    query = sql.load_query("get_user_by_id")
    async with track_query("get_user_by_id"):
        result = await connection.fetchrow(query, user_id)
    return result


async def get_user_by_email(connection: asyncpg.Connection, email: str) -> asyncpg.Record | None:
    """이메일로 사용자 조회 (비밀번호 해시 포함)

    Args:
        connection: 데이터베이스 연결
        email: 이메일 주소

    Returns:
        사용자 레코드 또는 None
    """
    query = sql.load_query("get_user_by_email")
    async with track_query("get_user_by_email"):
        result = await connection.fetchrow(query, email)
    return result


async def get_user_list(
    connection: asyncpg.Connection,
    offset: int,
    limit: int,
    search: str | None = None,
    is_active: bool | None = None,
) -> list[asyncpg.Record]:
    """사용자 목록 조회 (페이징, 검색, 필터)

    Args:
        connection: 데이터베이스 연결
        offset: 페이징 오프셋
        limit: 페이징 제한
        search: 검색어 (email/username) - wildcards are escaped automatically
        is_active: 활성화 필터

    Returns:
        사용자 레코드 리스트
    """
    # Sanitize search input to prevent ILIKE injection
    sanitized_search = _sanitize_ilike_pattern(search)

    query = sql.load_query("get_user_list")
    async with track_query("get_user_list"):
        result = await connection.fetch(query, offset, limit, sanitized_search, is_active)
    return result


async def get_user_count(
    connection: asyncpg.Connection,
    search: str | None = None,
    is_active: bool | None = None,
) -> int:
    """사용자 총 개수 (검색, 필터 적용)

    Args:
        connection: 데이터베이스 연결
        search: 검색어 (email/username) - wildcards are escaped automatically
        is_active: 활성화 필터

    Returns:
        사용자 총 개수
    """
    # Sanitize search input to prevent ILIKE injection
    sanitized_search = _sanitize_ilike_pattern(search)

    query = sql.load_query("get_user_count")
    async with track_query("get_user_count"):
        row = await connection.fetchrow(query, sanitized_search, is_active)
    return row["count"] if row else 0


async def get_user_list_with_count(
    connection: asyncpg.Connection,
    offset: int,
    limit: int,
    search: str | None = None,
    is_active: bool | None = None,
) -> tuple[list[asyncpg.Record], int]:
    """사용자 목록 + 총 개수 조회 (Window Function 최적화)

    기존 방식: 2개 쿼리 (get_user_list + get_user_count)
    최적화: 1개 쿼리 (Window Function 사용)
    효과: 쿼리 수 50% 감소, 성능 향상

    Args:
        connection: 데이터베이스 연결
        offset: 페이징 오프셋
        limit: 페이징 제한
        search: 검색어 (email/username) - wildcards are escaped automatically
        is_active: 활성화 필터

    Returns:
        (사용자 레코드 리스트, 총 개수) 튜플
    """
    # Sanitize search input to prevent ILIKE injection
    sanitized_search = _sanitize_ilike_pattern(search)

    query = sql.load_query("get_user_list_with_count")
    async with track_query("get_user_list_with_count"):
        rows = await connection.fetch(query, offset, limit, sanitized_search, is_active)

    if not rows:
        return ([], 0)

    # total_count는 모든 row에 동일한 값으로 포함됨 (Window Function)
    total_count = rows[0]["total_count"]
    return (rows, total_count)


async def get_user_roles_permissions(
    connection: asyncpg.Connection, user_id: int
) -> list[asyncpg.Record]:
    """사용자의 역할 및 권한 조회

    Args:
        connection: 데이터베이스 연결
        user_id: 사용자 ID

    Returns:
        역할/권한 레코드 리스트
    """
    query = sql.load_query("get_user_roles_permissions")
    async with track_query("get_user_roles_permissions"):
        result = await connection.fetch(query, user_id)
    return result


async def create_user(
    connection: asyncpg.Connection,
    email: str,
    username: str,
    password_hash: str,
    display_name: str | None = None,
) -> asyncpg.Record:
    """사용자 생성

    Args:
        connection: 데이터베이스 연결
        email: 이메일 주소
        username: 사용자명
        password_hash: 비밀번호 해시
        display_name: 표시 이름

    Returns:
        생성된 사용자 레코드
    """
    query = sql.load_command("create_user")
    async with track_query("create_user"):
        result = await connection.fetchrow(query, email, username, password_hash, display_name)
    return result


async def update_user(
    connection: asyncpg.Connection,
    user_id: int,
    display_name: str | None = None,
    phone: str | None = None,
    avatar_url: str | None = None,
) -> asyncpg.Record | None:
    """사용자 프로필 수정

    Args:
        connection: 데이터베이스 연결
        user_id: 사용자 ID
        display_name: 표시 이름
        phone: 전화번호
        avatar_url: 프로필 이미지 URL

    Returns:
        수정된 사용자 레코드 또는 None
    """
    query = sql.load_command("update_user")
    async with track_query("update_user"):
        result = await connection.fetchrow(query, user_id, display_name, phone, avatar_url)
    return result


async def change_password(
    connection: asyncpg.Connection,
    user_id: int,
    new_password_hash: str,
) -> asyncpg.Record | None:
    """비밀번호 변경

    Args:
        connection: 데이터베이스 연결
        user_id: 사용자 ID
        new_password_hash: 새 비밀번호 해시

    Returns:
        수정된 사용자 레코드 또는 None
    """
    query = sql.load_command("change_password")
    async with track_query("change_password"):
        result = await connection.fetchrow(query, user_id, new_password_hash)
    return result


async def assign_default_role(
    connection: asyncpg.Connection,
    user_id: int,
    role_name: str = "user",
) -> asyncpg.Record | None:
    """사용자에게 기본 역할 부여

    Args:
        connection: 데이터베이스 연결
        user_id: 사용자 ID
        role_name: 역할 이름 (기본: 'user')

    Returns:
        생성된 user_role 레코드 또는 None
    """
    query = sql.load_command("assign_default_role")
    async with track_query("assign_default_role"):
        result = await connection.fetchrow(query, user_id, role_name)
    return result
