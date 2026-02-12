"""Transaction management utilities."""

import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg


def _validate_identifier(identifier: str) -> bool:
    """Validate that an identifier is safe for SQL.

    Only allows alphanumeric characters and underscores.
    Must start with a letter or underscore.

    Args:
        identifier: The identifier to validate

    Returns:
        True if valid, False otherwise
    """
    return bool(re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", identifier))


def _quote_identifier(identifier: str) -> str:
    """Quote an identifier for safe use in SQL.

    Args:
        identifier: The identifier to quote

    Returns:
        Quoted identifier

    Raises:
        ValueError: If identifier contains invalid characters
    """
    if not _validate_identifier(identifier):
        raise ValueError(
            f"Invalid savepoint name: {identifier!r}. "
            "Only alphanumeric characters and underscores are allowed."
        )
    return f'"{identifier}"'


@asynccontextmanager
async def transaction(
    connection: asyncpg.Connection,
    isolation: str = "read_committed",
) -> AsyncIterator[asyncpg.Connection]:
    """Context manager for database transactions."""
    async with connection.transaction(isolation=isolation):
        yield connection


@asynccontextmanager
async def savepoint(
    connection: asyncpg.Connection,
    name: str | None = None,
) -> AsyncIterator[asyncpg.Connection]:
    """Context manager for savepoints within a transaction.

    Args:
        connection: Database connection
        name: Optional savepoint name. If None, uses a generated UUID-based name.
              Name must be alphanumeric with underscores only.

    Yields:
        Database connection

    Raises:
        ValueError: If name contains invalid characters
    """
    if name:
        # Validate and quote the identifier to prevent SQL injection
        quoted_name = _quote_identifier(name)
    else:
        # Generate a safe UUID-based name if not provided
        safe_name = f"sp_{uuid.uuid4().hex[:16]}"
        quoted_name = f'"{safe_name}"'

    await connection.execute(f"SAVEPOINT {quoted_name}")
    try:
        yield connection
        await connection.execute(f"RELEASE SAVEPOINT {quoted_name}")
    except Exception:
        await connection.execute(f"ROLLBACK TO SAVEPOINT {quoted_name}")
        raise
