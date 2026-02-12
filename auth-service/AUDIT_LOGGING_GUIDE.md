# Security Audit Logging Guide

## Overview

The audit logging system provides a comprehensive trail of security-critical events for:
- **Compliance**: Meet regulatory requirements (GDPR, SOX, HIPAA)
- **Incident Response**: Investigate security breaches
- **User Accountability**: Track who did what and when
- **Anomaly Detection**: Identify suspicious patterns

## Architecture

### Components

1. **audit_logs table** (`scripts/migrations/004_add_audit_logs.sql`)
   - Stores all security events
   - Indexed for fast queries
   - Retains data for compliance period

2. **AuditLogger** (`src/shared/security/audit_logger.py`)
   - Core logging functionality
   - Convenience functions for common events
   - Request context extraction

3. **Integration Points** (see below)
   - Authentication flow
   - Authorization changes
   - User management operations

## Usage

### 1. Basic Event Logging

```python
from src.shared.security.audit_logger import (
    AuditLogger,
    AuditEventType,
    AuditAction,
    AuditStatus,
)

# In service layer with database transaction
async def some_security_operation(connection, user_id, request):
    try:
        # Perform operation
        result = await do_something(connection, user_id)

        # Log success
        await AuditLogger.log_event(
            connection,
            event_type=AuditEventType.USER_UPDATED,
            event_action=AuditAction.UPDATE,
            resource_type="user",
            status=AuditStatus.SUCCESS,
            resource_id=user_id,
            actor_id=user_id,
            ip_address=request.client.host if request.client else None,
            metadata={"fields_changed": ["email", "username"]},
        )

        return result
    except Exception as e:
        # Log failure
        await AuditLogger.log_event(
            connection,
            event_type=AuditEventType.USER_UPDATED,
            event_action=AuditAction.UPDATE,
            resource_type="user",
            status=AuditStatus.FAILURE,
            resource_id=user_id,
            actor_id=user_id,
            error_message=str(e),
        )
        raise
```

### 2. Convenience Functions

For common events, use the provided convenience functions:

```python
from src.shared.security.audit_logger import (
    log_login_attempt,
    log_token_refresh_attempt,
    log_role_assignment,
    log_user_deletion,
    log_password_change,
)

# Login attempt
await log_login_attempt(
    connection,
    email="user@example.com",
    success=True,
    request=request,
    user_id=123,
)

# Failed token refresh
await log_token_refresh_attempt(
    connection,
    user_id=123,
    success=False,
    request=request,
    error_message="Token expired",
)

# Role assignment
await log_role_assignment(
    connection,
    actor_id=1,
    target_user_id=123,
    role_id=5,
    role_name="admin",
    action=AuditAction.GRANT,
    request=request,
)
```

## Integration Points

### Priority 1: Authentication Events

**File**: `src/domains/authentication/service.py`

#### Login Success/Failure
```python
# In login() method
async def login(self, connection, credentials, request):
    try:
        # ... existing authentication logic ...

        # Log successful login
        await log_login_attempt(
            connection,
            email=credentials.email,
            success=True,
            request=request,
            user_id=user_row["id"],
        )

        return result
    except UnauthorizedException as e:
        # Log failed login
        await log_login_attempt(
            connection,
            email=credentials.email,
            success=False,
            request=request,
            error_message=str(e),
        )
        raise
```

#### Token Refresh Failure
```python
# In refresh_access_token() method
async def refresh_access_token(self, connection, refresh_token, request):
    try:
        # ... existing refresh logic ...
        return result
    except Exception as e:
        # Extract user_id from token if possible
        user_id = self._extract_user_id_from_token(refresh_token)

        # Log failed refresh
        await log_token_refresh_attempt(
            connection,
            user_id=user_id,
            success=False,
            request=request,
            error_message=str(e),
        )
        raise
```

### Priority 2: Authorization Changes

**File**: `src/domains/users/service.py` (role management methods)

#### Role Assignment
```python
# In assign_role() method (if exists)
async def assign_role(connection, actor_id, user_id, role_id, request):
    # ... assign role logic ...

    # Log role assignment
    await log_role_assignment(
        connection,
        actor_id=actor_id,
        target_user_id=user_id,
        role_id=role_id,
        role_name=role_name,
        action=AuditAction.GRANT,
        request=request,
    )
```

### Priority 3: User Management

**File**: `src/domains/users/service.py`

#### Account Deletion
```python
# In delete_user() method
async def delete_user(connection, actor_id, user_id, request):
    user = await repository.get_user_by_id(connection, user_id)

    # Perform soft delete
    await repository.delete_user(connection, user_id)

    # Log deletion
    await log_user_deletion(
        connection,
        actor_id=actor_id,
        target_user_id=user_id,
        target_email=user["email"],
        request=request,
    )
```

#### Password Change
```python
# In change_password() method
async def change_password(connection, user_id, old_password, new_password, request):
    # ... password change logic ...

    # Log password change
    await log_password_change(
        connection,
        user_id=user_id,
        request=request,
    )
```

## Query Examples

### Admin Dashboard Queries

```python
# Failed login attempts in last 24 hours
async def get_recent_failed_logins(connection):
    query = """
        SELECT
            metadata->>'email' AS email,
            ip_address,
            created_at,
            error_message
        FROM audit_logs
        WHERE event_type = 'auth.login'
          AND status = 'failure'
          AND created_at > NOW() - INTERVAL '24 hours'
        ORDER BY created_at DESC
        LIMIT 100
    """
    return await connection.fetch(query)

# User activity history
async def get_user_activity(connection, user_id):
    query = """
        SELECT
            event_type,
            event_action,
            resource_type,
            status,
            ip_address,
            created_at
        FROM audit_logs
        WHERE actor_id = $1
        ORDER BY created_at DESC
        LIMIT 50
    """
    return await connection.fetch(query, user_id)

# Suspicious IP activity
async def get_ip_activity(connection, ip_address):
    query = """
        SELECT
            event_type,
            status,
            COUNT(*) as count
        FROM audit_logs
        WHERE ip_address = $1
          AND created_at > NOW() - INTERVAL '1 hour'
        GROUP BY event_type, status
    """
    return await connection.fetch(query, ip_address)
```

## Best Practices

### 1. Always Log Within Transactions

Audit logs should be part of the same transaction as the operation:

```python
async with transaction(connection):
    # Perform operation
    await do_something(connection)

    # Log it (same transaction)
    await AuditLogger.log_event(...)

    # If operation fails, audit log is also rolled back
```

### 2. Log Both Success and Failure

```python
try:
    result = await risky_operation(connection)
    await log_success(connection, ...)
    return result
except Exception as e:
    await log_failure(connection, error=str(e))
    raise
```

### 3. Include Context in Metadata

```python
metadata = {
    "old_value": old_email,
    "new_value": new_email,
    "reason": "User requested email change",
    "verified": email_verified,
}
```

### 4. Sanitize Sensitive Data

Never log passwords or tokens in metadata:

```python
# ❌ Bad
metadata = {"password": new_password}

# ✅ Good
metadata = {"password_changed": True, "strength": "strong"}
```

## Retention Policy

Configure audit log retention based on compliance requirements:

```sql
-- Delete logs older than 1 year (adjust as needed)
DELETE FROM audit_logs
WHERE created_at < NOW() - INTERVAL '1 year';
```

## Monitoring

Set up alerts for suspicious patterns:

1. **Multiple Failed Logins**: >5 failures from same IP in 5 minutes
2. **Privilege Escalation**: Non-admin user granted admin role
3. **Bulk Deletions**: >10 users deleted in 1 hour
4. **Off-Hours Activity**: Administrative actions at unusual times

## Testing

Run unit tests to verify audit logging:

```bash
pytest tests/unit/test_audit_logger.py -v
```

## Migration

Apply the audit_logs table migration:

```bash
psql -U postgres -d auth_db -f scripts/migrations/004_add_audit_logs.sql
```

## Current Status

- ✅ audit_logs table schema created
- ✅ AuditLogger class implemented
- ✅ Convenience functions for common events
- ✅ Unit tests (11 tests, 100% coverage)
- ⏸️ Integration with authentication/authorization flows (TODO)

## Next Steps

1. Add audit logging to `authentication/service.py` (login, refresh, logout)
2. Add audit logging to user management operations
3. Add audit logging to role/permission changes
4. Create admin dashboard for viewing audit logs
5. Set up monitoring alerts for suspicious patterns
