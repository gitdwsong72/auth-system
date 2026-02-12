"""Transaction utilities unit tests"""

import re
from unittest.mock import AsyncMock, call

import pytest

from src.shared.database.transaction import (
    _quote_identifier,
    _validate_identifier,
    savepoint,
    transaction,
)


class TestIdentifierValidation:
    """Identifier validation tests"""

    def test_validate_identifier_valid(self):
        """Valid identifiers should pass validation"""
        assert _validate_identifier("valid_name")
        assert _validate_identifier("ValidName")
        assert _validate_identifier("_private")
        assert _validate_identifier("name123")
        assert _validate_identifier("_123")

    def test_validate_identifier_invalid(self):
        """Invalid identifiers should fail validation"""
        # Starts with number
        assert not _validate_identifier("123name")
        # Contains spaces
        assert not _validate_identifier("invalid name")
        # Contains special characters
        assert not _validate_identifier("name-with-dash")
        assert not _validate_identifier("name.with.dot")
        assert not _validate_identifier("name;drop")
        # SQL injection attempts
        assert not _validate_identifier("name'; DROP TABLE users; --")
        assert not _validate_identifier("name OR 1=1")
        # Empty string
        assert not _validate_identifier("")

    def test_quote_identifier_valid(self):
        """Valid identifiers should be quoted correctly"""
        assert _quote_identifier("valid_name") == '"valid_name"'
        assert _quote_identifier("CamelCase") == '"CamelCase"'
        assert _quote_identifier("_private") == '"_private"'

    def test_quote_identifier_invalid(self):
        """Invalid identifiers should raise ValueError"""
        with pytest.raises(ValueError, match="Invalid savepoint name"):
            _quote_identifier("invalid; DROP TABLE users")

        with pytest.raises(ValueError, match="Invalid savepoint name"):
            _quote_identifier("123invalid")

        with pytest.raises(ValueError, match="Invalid savepoint name"):
            _quote_identifier("invalid name")


@pytest.mark.asyncio
class TestTransaction:
    """Transaction context manager tests"""

    async def test_transaction_success(self):
        """Transaction should commit on success"""
        mock_conn = AsyncMock()
        mock_transaction = AsyncMock()
        mock_conn.transaction.return_value.__aenter__ = AsyncMock()
        mock_conn.transaction.return_value.__aexit__ = AsyncMock()

        async with transaction(mock_conn):
            pass

        mock_conn.transaction.assert_called_once_with(isolation="read_committed")

    async def test_transaction_with_isolation(self):
        """Transaction should use specified isolation level"""
        mock_conn = AsyncMock()
        mock_conn.transaction.return_value.__aenter__ = AsyncMock()
        mock_conn.transaction.return_value.__aexit__ = AsyncMock()

        async with transaction(mock_conn, isolation="serializable"):
            pass

        mock_conn.transaction.assert_called_once_with(isolation="serializable")

    async def test_transaction_rollback_on_error(self):
        """Transaction should rollback on exception"""
        mock_conn = AsyncMock()
        mock_conn.transaction.return_value.__aenter__ = AsyncMock()
        mock_conn.transaction.return_value.__aexit__ = AsyncMock()

        with pytest.raises(ValueError):
            async with transaction(mock_conn):
                raise ValueError("Test error")


@pytest.mark.asyncio
class TestSavepoint:
    """Savepoint context manager tests"""

    async def test_savepoint_with_valid_name(self):
        """Savepoint should work with valid name"""
        mock_conn = AsyncMock()

        async with savepoint(mock_conn, name="valid_savepoint"):
            pass

        # Check SAVEPOINT, RELEASE SAVEPOINT calls
        assert mock_conn.execute.call_count == 2
        calls = mock_conn.execute.call_args_list
        assert calls[0] == call('SAVEPOINT "valid_savepoint"')
        assert calls[1] == call('RELEASE SAVEPOINT "valid_savepoint"')

    async def test_savepoint_with_invalid_name_sql_injection(self):
        """Savepoint should reject SQL injection attempts"""
        mock_conn = AsyncMock()

        with pytest.raises(ValueError, match="Invalid savepoint name"):
            async with savepoint(mock_conn, name="sp'; DROP TABLE users; --"):
                pass

    async def test_savepoint_with_invalid_name_special_chars(self):
        """Savepoint should reject names with special characters"""
        mock_conn = AsyncMock()

        with pytest.raises(ValueError, match="Invalid savepoint name"):
            async with savepoint(mock_conn, name="invalid-name"):
                pass

    async def test_savepoint_without_name(self):
        """Savepoint should auto-generate safe name when None"""
        mock_conn = AsyncMock()

        async with savepoint(mock_conn, name=None):
            pass

        # Check that SAVEPOINT and RELEASE SAVEPOINT were called
        assert mock_conn.execute.call_count == 2
        calls = mock_conn.execute.call_args_list

        # Extract the savepoint name from the first call
        first_call_arg = calls[0][0][0]
        assert first_call_arg.startswith('SAVEPOINT "sp_')
        assert first_call_arg.endswith('"')

        # Verify it's a valid UUID-based name (16 hex chars)
        match = re.search(r'SAVEPOINT "sp_([a-f0-9]{16})"', first_call_arg)
        assert match is not None

    async def test_savepoint_rollback_on_error(self):
        """Savepoint should rollback on exception"""
        mock_conn = AsyncMock()

        with pytest.raises(ValueError):
            async with savepoint(mock_conn, name="test_sp"):
                raise ValueError("Test error")

        # Check SAVEPOINT, ROLLBACK TO SAVEPOINT calls (no RELEASE)
        assert mock_conn.execute.call_count == 2
        calls = mock_conn.execute.call_args_list
        assert calls[0] == call('SAVEPOINT "test_sp"')
        assert calls[1] == call('ROLLBACK TO SAVEPOINT "test_sp"')

    async def test_savepoint_yields_connection(self):
        """Savepoint should yield the connection"""
        mock_conn = AsyncMock()

        async with savepoint(mock_conn, name="test") as conn:
            assert conn is mock_conn
