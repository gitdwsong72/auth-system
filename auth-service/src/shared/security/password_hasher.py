"""비밀번호 해싱 모듈."""

from __future__ import annotations

import asyncio
import re
from functools import partial

from passlib.context import CryptContext

from src.shared.security.config import security_settings


class PasswordHasher:
    """비밀번호 해싱 및 검증을 담당하는 클래스."""

    def __init__(self) -> None:
        self._context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=12,
        )
        self._settings = security_settings

    def hash(self, password: str) -> str:
        """비밀번호를 bcrypt로 해싱한다."""
        return self._context.hash(password)

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        """평문 비밀번호와 해시를 비교 검증한다."""
        return self._context.verify(plain_password, hashed_password)

    def needs_rehash(self, hashed_password: str) -> bool:
        """해시 알고리즘 업그레이드가 필요한지 확인한다."""
        return self._context.needs_update(hashed_password)

    async def hash_async(self, password: str) -> str:
        """
        비밀번호를 bcrypt로 해싱한다 (비동기).

        Event Loop 블로킹을 방지하기 위해 별도 스레드에서 실행합니다.
        bcrypt는 CPU 집약적 작업(100-300ms)이므로 asyncio.to_thread()로
        처리하여 다른 요청의 응답성을 보장합니다.

        Args:
            password: 평문 비밀번호

        Returns:
            bcrypt 해시 문자열
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,  # Default ThreadPoolExecutor
            partial(self._context.hash, password),
        )

    async def verify_async(self, plain_password: str, hashed_password: str) -> bool:
        """
        평문 비밀번호와 해시를 비교 검증한다 (비동기).

        Event Loop 블로킹을 방지하기 위해 별도 스레드에서 실행합니다.

        Args:
            plain_password: 평문 비밀번호
            hashed_password: bcrypt 해시

        Returns:
            검증 성공 여부
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, partial(self._context.verify, plain_password, hashed_password)
        )

    def validate_strength(self, password: str) -> list[str]:
        """비밀번호 강도를 검증하고 위반 사항 목록을 반환한다.

        Returns:
            위반 사항 메시지 리스트. 비어있으면 유효한 비밀번호.
        """
        errors: list[str] = []
        min_length = self._settings.password_min_length

        if len(password) < min_length:
            errors.append(f"비밀번호는 최소 {min_length}자 이상이어야 합니다")

        if not re.search(r"[A-Z]", password):
            errors.append("대문자를 최소 1개 포함해야 합니다")

        if not re.search(r"[a-z]", password):
            errors.append("소문자를 최소 1개 포함해야 합니다")

        if not re.search(r"\d", password):
            errors.append("숫자를 최소 1개 포함해야 합니다")

        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", password):
            errors.append("특수문자를 최소 1개 포함해야 합니다")

        return errors


password_hasher = PasswordHasher()
