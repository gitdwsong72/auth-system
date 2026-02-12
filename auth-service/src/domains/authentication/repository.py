"""Authentication 도메인 Repository

데이터베이스 쿼리를 실행하는 레이어입니다.
"""

import json
from datetime import datetime

import asyncpg

from src.shared.utils.query_timing import track_query
from src.shared.utils.sql_loader import create_sql_loader

sql = create_sql_loader("authentication")


async def get_refresh_token(
    connection: asyncpg.Connection, token_hash: str
) -> asyncpg.Record | None:
    """리프레시 토큰 조회 (유효한 토큰만)

    Args:
        connection: 데이터베이스 연결
        token_hash: 토큰 해시

    Returns:
        리프레시 토큰 레코드 또는 None
    """
    query = sql.load_query("get_refresh_token")
    async with track_query("get_refresh_token"):
        result = await connection.fetchrow(query, token_hash)
    return result


async def get_active_sessions(connection: asyncpg.Connection, user_id: int) -> list[asyncpg.Record]:
    """사용자의 활성 세션 목록 조회

    Args:
        connection: 데이터베이스 연결
        user_id: 사용자 ID

    Returns:
        세션 레코드 리스트
    """
    query = sql.load_query("get_active_sessions")
    async with track_query("get_active_sessions"):
        result = await connection.fetch(query, user_id)
    return result


async def save_refresh_token(
    connection: asyncpg.Connection,
    user_id: int,
    token_hash: str,
    device_info: str | None,
    expires_at: datetime,
) -> asyncpg.Record:
    """리프레시 토큰 저장

    Args:
        connection: 데이터베이스 연결
        user_id: 사용자 ID
        token_hash: 토큰 해시
        device_info: 디바이스 정보 (string, DB에 JSON으로 저장)
        expires_at: 만료 시각

    Returns:
        생성된 리프레시 토큰 레코드
    """
    # device_info를 JSON 문자열로 변환 (DB 컬럼이 jsonb 타입)
    device_info_json = json.dumps(device_info) if device_info is not None else None

    query = sql.load_command("save_refresh_token")
    async with track_query("save_refresh_token"):
        result = await connection.fetchrow(query, user_id, token_hash, device_info_json, expires_at)
    return result


async def revoke_refresh_token(
    connection: asyncpg.Connection, token_hash: str
) -> asyncpg.Record | None:
    """리프레시 토큰 폐기

    Args:
        connection: 데이터베이스 연결
        token_hash: 토큰 해시

    Returns:
        폐기된 토큰 레코드 또는 None
    """
    query = sql.load_command("revoke_refresh_token")
    async with track_query("revoke_refresh_token"):
        result = await connection.fetchrow(query, token_hash)
    return result


async def revoke_all_user_tokens(
    connection: asyncpg.Connection, user_id: int
) -> list[asyncpg.Record]:
    """사용자의 모든 리프레시 토큰 폐기

    Args:
        connection: 데이터베이스 연결
        user_id: 사용자 ID

    Returns:
        폐기된 토큰 레코드 리스트
    """
    query = sql.load_command("revoke_all_user_tokens")
    async with track_query("revoke_all_user_tokens"):
        result = await connection.fetch(query, user_id)
    return result


async def save_login_history(
    connection: asyncpg.Connection,
    user_id: int,
    ip_address: str | None,
    user_agent: str | None,
    success: bool,
) -> asyncpg.Record:
    """로그인 이력 저장

    Args:
        connection: 데이터베이스 연결
        user_id: 사용자 ID
        ip_address: IP 주소
        user_agent: User-Agent
        success: 성공 여부

    Returns:
        생성된 로그인 이력 레코드
    """
    query = sql.load_command("save_login_history")
    async with track_query("save_login_history"):
        result = await connection.fetchrow(query, user_id, ip_address, user_agent, success)
    return result


async def update_last_login(connection: asyncpg.Connection, user_id: int) -> asyncpg.Record | None:
    """마지막 로그인 시각 업데이트

    Args:
        connection: 데이터베이스 연결
        user_id: 사용자 ID

    Returns:
        업데이트된 사용자 레코드 또는 None
    """
    query = sql.load_command("update_last_login")
    async with track_query("update_last_login"):
        result = await connection.fetchrow(query, user_id)
    return result
