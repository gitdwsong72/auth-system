"""Security audit logging for compliance and incident response.

This module provides centralized security event logging to the audit_logs table.
All security-critical events (authentication, authorization, user management) should be logged.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import asyncpg
from fastapi import Request

from src.shared.utils.client_ip import get_client_info


class AuditEventType(StrEnum):
    """Security event types for audit logging."""

    # Authentication events
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_TOKEN_REFRESH = "auth.token_refresh"
    AUTH_TOKEN_REVOKE = "auth.token_revoke"

    # Authorization events
    ROLE_ASSIGNED = "role.assigned"
    ROLE_REVOKED = "role.revoked"
    PERMISSION_CHANGED = "permission.changed"

    # User management events
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_PASSWORD_CHANGED = "user.password_changed"
    USER_ACTIVATED = "user.activated"
    USER_DEACTIVATED = "user.deactivated"

    # API key events
    API_KEY_CREATED = "api_key.created"
    API_KEY_REVOKED = "api_key.revoked"


class AuditAction(StrEnum):
    """Security event actions."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    GRANT = "grant"
    REVOKE = "revoke"
    LOGIN = "login"
    LOGOUT = "logout"
    REFRESH = "refresh"
    VERIFY = "verify"


class AuditStatus(StrEnum):
    """Security event status."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


class AuditLogger:
    """Security audit logger for tracking critical events."""

    @staticmethod
    async def log_event(
        connection: asyncpg.Connection,
        event_type: AuditEventType,
        event_action: AuditAction,
        resource_type: str,
        status: AuditStatus,
        *,
        resource_id: int | None = None,
        actor_id: int | None = None,
        target_id: int | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> int:
        """Log a security audit event.

        Args:
            connection: Database connection
            event_type: Type of event (auth.login, role.assigned, etc.)
            event_action: Action taken (create, update, delete, grant, revoke)
            resource_type: Resource type (user, role, permission, api_key)
            status: Event status (success, failure, partial)
            resource_id: Resource ID (optional)
            actor_id: User who performed the action (optional)
            target_id: Target user affected (optional)
            ip_address: Client IP address (optional)
            user_agent: Client user agent (optional)
            metadata: Additional context as dict (optional)
            error_message: Error message for failed events (optional)

        Returns:
            ID of created audit log entry
        """
        query = """
            INSERT INTO audit_logs (
                event_type,
                event_action,
                resource_type,
                resource_id,
                actor_id,
                target_id,
                ip_address,
                user_agent,
                metadata,
                status,
                error_message,
                created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING id
        """

        result = await connection.fetchval(
            query,
            event_type,
            event_action,
            resource_type,
            resource_id,
            actor_id,
            target_id,
            ip_address,
            user_agent,
            metadata,
            status,
            error_message,
            datetime.now(UTC),
        )

        return result

    @staticmethod
    def extract_client_info(request: Request) -> tuple[str, str | None]:
        """Extract client IP and user agent from request with trusted proxy validation.

        IMPORTANT: This method validates X-Forwarded-For headers to prevent IP spoofing.
        Only headers from trusted proxies (RFC1918 + localhost) are accepted.

        This prevents attackers from:
        - Bypassing audit logs by faking their IP
        - Evading account lockout by appearing as different IPs
        - Obscuring their identity in security investigations

        Args:
            request: FastAPI request object

        Returns:
            Tuple of (ip_address, user_agent)
            - ip_address: Validated client IP (never None, returns "unknown" if unavailable)
            - user_agent: User-Agent header value (can be None)

        Security Note:
            Uses src.shared.utils.client_ip.get_client_info() which implements
            trusted proxy validation. See that module for security details.
        """
        return get_client_info(request)


# Convenience functions for common audit events


async def log_login_attempt(
    connection: asyncpg.Connection,
    email: str,
    success: bool,
    request: Request,
    *,
    user_id: int | None = None,
    error_message: str | None = None,
) -> int:
    """Log a login attempt (success or failure).

    Args:
        connection: Database connection
        email: Email used for login
        success: Whether login was successful
        request: FastAPI request object
        user_id: User ID (only for successful logins)
        error_message: Error message (only for failed logins)

    Returns:
        Audit log ID
    """
    ip_address, user_agent = AuditLogger.extract_client_info(request)

    return await AuditLogger.log_event(
        connection,
        event_type=AuditEventType.AUTH_LOGIN,
        event_action=AuditAction.LOGIN,
        resource_type="session",
        status=AuditStatus.SUCCESS if success else AuditStatus.FAILURE,
        resource_id=user_id,
        actor_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"email": email},
        error_message=error_message,
    )


async def log_token_refresh_attempt(
    connection: asyncpg.Connection,
    user_id: int,
    success: bool,
    request: Request,
    *,
    error_message: str | None = None,
) -> int:
    """Log a token refresh attempt (success or failure).

    Args:
        connection: Database connection
        user_id: User ID
        success: Whether refresh was successful
        request: FastAPI request object
        error_message: Error message (only for failed refreshes)

    Returns:
        Audit log ID
    """
    ip_address, user_agent = AuditLogger.extract_client_info(request)

    return await AuditLogger.log_event(
        connection,
        event_type=AuditEventType.AUTH_TOKEN_REFRESH,
        event_action=AuditAction.REFRESH,
        resource_type="token",
        status=AuditStatus.SUCCESS if success else AuditStatus.FAILURE,
        actor_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        error_message=error_message,
    )


async def log_role_assignment(
    connection: asyncpg.Connection,
    actor_id: int,
    target_user_id: int,
    role_id: int,
    role_name: str,
    action: AuditAction,  # GRANT or REVOKE
    request: Request | None = None,
) -> int:
    """Log a role assignment or revocation.

    Args:
        connection: Database connection
        actor_id: User who granted/revoked the role
        target_user_id: User receiving/losing the role
        role_id: Role ID
        role_name: Role name for context
        action: GRANT or REVOKE
        request: FastAPI request object (optional)

    Returns:
        Audit log ID
    """
    ip_address, user_agent = None, None
    if request:
        ip_address, user_agent = AuditLogger.extract_client_info(request)

    event_type = (
        AuditEventType.ROLE_ASSIGNED if action == AuditAction.GRANT else AuditEventType.ROLE_REVOKED
    )

    return await AuditLogger.log_event(
        connection,
        event_type=event_type,
        event_action=action,
        resource_type="role",
        status=AuditStatus.SUCCESS,
        resource_id=role_id,
        actor_id=actor_id,
        target_id=target_user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"role_name": role_name},
    )


async def log_user_deletion(
    connection: asyncpg.Connection,
    actor_id: int,
    target_user_id: int,
    target_email: str,
    request: Request | None = None,
) -> int:
    """Log a user account deletion (soft delete).

    Args:
        connection: Database connection
        actor_id: User who performed the deletion
        target_user_id: User being deleted
        target_email: Email of deleted user
        request: FastAPI request object (optional)

    Returns:
        Audit log ID
    """
    ip_address, user_agent = None, None
    if request:
        ip_address, user_agent = AuditLogger.extract_client_info(request)

    return await AuditLogger.log_event(
        connection,
        event_type=AuditEventType.USER_DELETED,
        event_action=AuditAction.DELETE,
        resource_type="user",
        status=AuditStatus.SUCCESS,
        resource_id=target_user_id,
        actor_id=actor_id,
        target_id=target_user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"email": target_email},
    )


async def log_password_change(
    connection: asyncpg.Connection,
    user_id: int,
    request: Request,
) -> int:
    """Log a password change event.

    Args:
        connection: Database connection
        user_id: User who changed their password
        request: FastAPI request object

    Returns:
        Audit log ID
    """
    ip_address, user_agent = AuditLogger.extract_client_info(request)

    return await AuditLogger.log_event(
        connection,
        event_type=AuditEventType.USER_PASSWORD_CHANGED,
        event_action=AuditAction.UPDATE,
        resource_type="user",
        status=AuditStatus.SUCCESS,
        resource_id=user_id,
        actor_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
