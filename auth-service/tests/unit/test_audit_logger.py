"""Unit tests for security audit logger."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.shared.security.audit_logger import (
    AuditAction,
    AuditEventType,
    AuditLogger,
    AuditStatus,
    log_login_attempt,
    log_password_change,
    log_role_assignment,
    log_token_refresh_attempt,
    log_user_deletion,
)


class TestAuditLogger:
    """Test suite for AuditLogger class."""

    @pytest.mark.asyncio
    async def test_log_event_success(self):
        """Test logging a successful security event."""
        connection = AsyncMock()
        connection.fetchval = AsyncMock(return_value=1)

        audit_id = await AuditLogger.log_event(
            connection,
            event_type=AuditEventType.AUTH_LOGIN,
            event_action=AuditAction.LOGIN,
            resource_type="session",
            status=AuditStatus.SUCCESS,
            actor_id=123,
            ip_address="192.168.1.100",
            metadata={"email": "test@example.com"},
        )

        assert audit_id == 1
        connection.fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_event_failure(self):
        """Test logging a failed security event."""
        connection = AsyncMock()
        connection.fetchval = AsyncMock(return_value=2)

        audit_id = await AuditLogger.log_event(
            connection,
            event_type=AuditEventType.AUTH_LOGIN,
            event_action=AuditAction.LOGIN,
            resource_type="session",
            status=AuditStatus.FAILURE,
            ip_address="192.168.1.100",
            error_message="Invalid credentials",
            metadata={"email": "test@example.com"},
        )

        assert audit_id == 2
        connection.fetchval.assert_called_once()

    def test_extract_client_info(self):
        """Test extracting client IP and user agent from request."""
        request = MagicMock()
        request.client.host = "192.168.1.100"
        request.headers.get = MagicMock(side_effect=lambda key: {
            "X-Forwarded-For": "203.0.113.1, 192.168.1.1",
            "User-Agent": "Mozilla/5.0",
        }.get(key))

        ip_address, user_agent = AuditLogger.extract_client_info(request)

        assert ip_address == "203.0.113.1"  # First IP in X-Forwarded-For
        assert user_agent == "Mozilla/5.0"

    def test_extract_client_info_no_forwarded_for(self):
        """Test extracting client info without X-Forwarded-For header."""
        request = MagicMock()
        request.client.host = "192.168.1.100"
        request.headers.get = MagicMock(side_effect=lambda key: {
            "User-Agent": "curl/7.68.0",
        }.get(key))

        ip_address, user_agent = AuditLogger.extract_client_info(request)

        assert ip_address == "192.168.1.100"  # Direct client IP
        assert user_agent == "curl/7.68.0"


class TestConvenienceFunctions:
    """Test convenience functions for common audit events."""

    @pytest.mark.asyncio
    async def test_log_login_attempt_success(self):
        """Test logging successful login attempt."""
        connection = AsyncMock()
        connection.fetchval = AsyncMock(return_value=1)

        request = MagicMock()
        request.client.host = "192.168.1.100"
        request.headers.get = MagicMock(return_value="Mozilla/5.0")

        audit_id = await log_login_attempt(
            connection,
            email="test@example.com",
            success=True,
            request=request,
            user_id=123,
        )

        assert audit_id == 1
        connection.fetchval.assert_called_once()

        # Verify correct event type and status
        call_args = connection.fetchval.call_args[0]
        assert call_args[1] == AuditEventType.AUTH_LOGIN
        assert call_args[10] == AuditStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_log_login_attempt_failure(self):
        """Test logging failed login attempt."""
        connection = AsyncMock()
        connection.fetchval = AsyncMock(return_value=2)

        request = MagicMock()
        request.client.host = "192.168.1.100"
        request.headers.get = MagicMock(return_value=None)

        audit_id = await log_login_attempt(
            connection,
            email="test@example.com",
            success=False,
            request=request,
            error_message="Invalid credentials",
        )

        assert audit_id == 2

        # Verify failure status
        call_args = connection.fetchval.call_args[0]
        assert call_args[10] == AuditStatus.FAILURE
        assert call_args[11] == "Invalid credentials"

    @pytest.mark.asyncio
    async def test_log_token_refresh_attempt(self):
        """Test logging token refresh attempt."""
        connection = AsyncMock()
        connection.fetchval = AsyncMock(return_value=3)

        request = MagicMock()
        request.client.host = "192.168.1.100"
        request.headers.get = MagicMock(return_value=None)

        audit_id = await log_token_refresh_attempt(
            connection,
            user_id=123,
            success=False,
            request=request,
            error_message="Token expired",
        )

        assert audit_id == 3

        # Verify event type
        call_args = connection.fetchval.call_args[0]
        assert call_args[1] == AuditEventType.AUTH_TOKEN_REFRESH

    @pytest.mark.asyncio
    async def test_log_role_assignment(self):
        """Test logging role assignment."""
        connection = AsyncMock()
        connection.fetchval = AsyncMock(return_value=4)

        request = MagicMock()
        request.client.host = "192.168.1.100"
        request.headers.get = MagicMock(return_value=None)

        audit_id = await log_role_assignment(
            connection,
            actor_id=1,
            target_user_id=123,
            role_id=5,
            role_name="admin",
            action=AuditAction.GRANT,
            request=request,
        )

        assert audit_id == 4

        # Verify event type and metadata
        call_args = connection.fetchval.call_args[0]
        assert call_args[1] == AuditEventType.ROLE_ASSIGNED
        assert call_args[9] == {"role_name": "admin"}

    @pytest.mark.asyncio
    async def test_log_user_deletion(self):
        """Test logging user deletion."""
        connection = AsyncMock()
        connection.fetchval = AsyncMock(return_value=5)

        request = MagicMock()
        request.client.host = "192.168.1.100"
        request.headers.get = MagicMock(return_value=None)

        audit_id = await log_user_deletion(
            connection,
            actor_id=1,
            target_user_id=123,
            target_email="deleted@example.com",
            request=request,
        )

        assert audit_id == 5

        # Verify event type
        call_args = connection.fetchval.call_args[0]
        assert call_args[1] == AuditEventType.USER_DELETED

    @pytest.mark.asyncio
    async def test_log_password_change(self):
        """Test logging password change."""
        connection = AsyncMock()
        connection.fetchval = AsyncMock(return_value=6)

        request = MagicMock()
        request.client.host = "192.168.1.100"
        request.headers.get = MagicMock(return_value=None)

        audit_id = await log_password_change(
            connection,
            user_id=123,
            request=request,
        )

        assert audit_id == 6

        # Verify event type
        call_args = connection.fetchval.call_args[0]
        assert call_args[1] == AuditEventType.USER_PASSWORD_CHANGED
