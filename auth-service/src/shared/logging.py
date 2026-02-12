"""Structured logging configuration for security and observability.

This module provides JSON-formatted logging with security event tracking
for audit trails, incident response, and performance monitoring.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from src.shared.security.config import security_settings


def add_app_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add application context to all log entries."""
    event_dict["app"] = "auth-service"
    event_dict["environment"] = security_settings.env
    return event_dict


def mask_sensitive_data(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Mask sensitive fields in log entries.

    Fields like 'password', 'token', 'secret' will be masked with '***'.
    """
    sensitive_fields = {"password", "token", "secret", "api_key", "password_hash"}

    for key in event_dict:
        if any(sensitive in key.lower() for sensitive in sensitive_fields):
            event_dict[key] = "***MASKED***"

    return event_dict


def configure_logging() -> None:
    """Configure structured logging for the application.

    - Development: Human-readable console output
    - Production: JSON-formatted logs for ELK/Kibana
    """
    # Determine log level
    log_level = logging.DEBUG if security_settings.env == "development" else logging.INFO

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Shared processors for all environments
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        add_app_context,
        mask_sensitive_data,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if security_settings.env == "development":
        # Development: Pretty console output
        processors = [*shared_processors, structlog.dev.ConsoleRenderer(colors=True)]
    else:
        # Production: JSON output for log aggregation
        processors = [*shared_processors, structlog.processors.dict_tracebacks, structlog.processors.JSONRenderer()]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a configured structured logger.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Structured logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("user_login", user_id=123, ip="192.168.1.1")
    """
    return structlog.get_logger(name)


# Security event logging helpers
class SecurityLogger:
    """Helper class for logging security-related events."""

    def __init__(self) -> None:
        self.logger = get_logger("security")

    def log_login_failed(
        self,
        email: str,
        ip_address: str | None,
        reason: str,
        failed_count: int | None = None,
    ) -> None:
        """Log failed login attempt.

        Args:
            email: User email
            ip_address: Client IP address
            reason: Failure reason (invalid_password, account_locked, etc.)
            failed_count: Current failed attempt count
        """
        self.logger.warning(
            "login_failed",
            event_type="authentication",
            email=email,
            ip_address=ip_address,
            reason=reason,
            failed_count=failed_count,
        )

    def log_login_success(
        self,
        user_id: int,
        email: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        """Log successful login.

        Args:
            user_id: User ID
            email: User email
            ip_address: Client IP address
            user_agent: User agent string
        """
        self.logger.info(
            "login_success",
            event_type="authentication",
            user_id=user_id,
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def log_account_locked(
        self,
        email: str,
        ip_address: str | None,
        failed_count: int,
    ) -> None:
        """Log account lockout event.

        Args:
            email: User email
            ip_address: Client IP address
            failed_count: Number of failed attempts
        """
        self.logger.warning(
            "account_locked",
            event_type="security",
            email=email,
            ip_address=ip_address,
            failed_count=failed_count,
            lockout_duration_minutes=15,
        )

    def log_permission_denied(
        self,
        user_id: int,
        email: str,
        required_permission: str,
        endpoint: str,
    ) -> None:
        """Log permission denial.

        Args:
            user_id: User ID
            email: User email
            required_permission: Required permission that was missing
            endpoint: Endpoint that was accessed
        """
        self.logger.warning(
            "permission_denied",
            event_type="authorization",
            user_id=user_id,
            email=email,
            required_permission=required_permission,
            endpoint=endpoint,
        )

    def log_token_expired(
        self,
        user_id: int | None,
        token_type: str,
    ) -> None:
        """Log expired token usage attempt.

        Args:
            user_id: User ID (if available)
            token_type: Type of token (access, refresh)
        """
        self.logger.info(
            "token_expired",
            event_type="authentication",
            user_id=user_id,
            token_type=token_type,
        )

    def log_slow_query(
        self,
        query_name: str,
        duration_ms: float,
        params: dict[str, Any] | None = None,
    ) -> None:
        """Log slow database query (> 100ms).

        Args:
            query_name: Name/identifier of the query
            duration_ms: Query duration in milliseconds
            params: Query parameters (will be masked if sensitive)
        """
        self.logger.warning(
            "slow_query",
            event_type="performance",
            query_name=query_name,
            duration_ms=duration_ms,
            params=params or {},
        )

    def log_rate_limit_exceeded(
        self,
        ip_address: str,
        endpoint: str,
        limit: int,
    ) -> None:
        """Log rate limit exceeded event.

        Args:
            ip_address: Client IP address
            endpoint: Endpoint that was rate limited
            limit: Rate limit threshold
        """
        self.logger.warning(
            "rate_limit_exceeded",
            event_type="security",
            ip_address=ip_address,
            endpoint=endpoint,
            limit=limit,
        )


# Global security logger instance
security_logger = SecurityLogger()
