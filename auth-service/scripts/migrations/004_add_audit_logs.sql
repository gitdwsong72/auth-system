-- =============================================================================
-- Audit Logs Migration
-- Description: Create audit_logs table for security event tracking
-- Date: 2026-02-11
-- Purpose: Track security-critical events for compliance and incident response
-- =============================================================================

BEGIN;

-- =============================================================================
-- audit_logs - Security event audit trail
-- =============================================================================

CREATE TABLE IF NOT EXISTS audit_logs (
    id              BIGSERIAL       PRIMARY KEY,
    event_type      VARCHAR(100)    NOT NULL,           -- Event category (role_assigned, permission_changed, etc.)
    event_action    VARCHAR(50)     NOT NULL,           -- Action taken (create, update, delete, grant, revoke)
    resource_type   VARCHAR(100)    NOT NULL,           -- Resource type (user, role, permission, api_key)
    resource_id     BIGINT,                             -- Resource ID (nullable for failed attempts)
    actor_id        BIGINT          REFERENCES users(id) ON DELETE SET NULL,  -- Who performed the action
    target_id       BIGINT          REFERENCES users(id) ON DELETE SET NULL,  -- Target user (if applicable)
    ip_address      INET,                               -- Client IP address
    user_agent      TEXT,                               -- Client user agent
    metadata        JSONB,                              -- Additional context (old_value, new_value, reason, etc.)
    status          VARCHAR(20)     NOT NULL,           -- success, failure, partial
    error_message   TEXT,                               -- Error message for failed events
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE audit_logs IS 'Security event audit trail for compliance and incident response';
COMMENT ON COLUMN audit_logs.event_type IS 'Event category (auth.login, role.assigned, permission.changed, user.deleted)';
COMMENT ON COLUMN audit_logs.event_action IS 'Action taken (create, update, delete, grant, revoke, login, logout)';
COMMENT ON COLUMN audit_logs.resource_type IS 'Resource type affected (user, role, permission, api_key, session)';
COMMENT ON COLUMN audit_logs.actor_id IS 'User who performed the action (NULL for system actions)';
COMMENT ON COLUMN audit_logs.target_id IS 'Target user affected by action (if applicable)';
COMMENT ON COLUMN audit_logs.metadata IS 'Additional context as JSON (old_value, new_value, reason, etc.)';
COMMENT ON COLUMN audit_logs.status IS 'Event status: success, failure, partial';

-- =============================================================================
-- Performance Indexes
-- =============================================================================

-- 1. Event type queries (admin dashboards)
CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type_created
    ON audit_logs (event_type, created_at DESC);

COMMENT ON INDEX idx_audit_logs_event_type_created IS
    'Index for filtering audit logs by event type with time ordering';

-- 2. Actor activity tracking (user action history)
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_created
    ON audit_logs (actor_id, created_at DESC)
    WHERE actor_id IS NOT NULL;

COMMENT ON INDEX idx_audit_logs_actor_created IS
    'Index for tracking specific user activity history';

-- 3. Target user audit trail (who did what to this user)
CREATE INDEX IF NOT EXISTS idx_audit_logs_target_created
    ON audit_logs (target_id, created_at DESC)
    WHERE target_id IS NOT NULL;

COMMENT ON INDEX idx_audit_logs_target_created IS
    'Index for viewing all actions performed on a specific user';

-- 4. Resource tracking (all events for a resource)
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource
    ON audit_logs (resource_type, resource_id, created_at DESC);

COMMENT ON INDEX idx_audit_logs_resource IS
    'Index for tracking all events related to a specific resource';

-- 5. Failed events monitoring (security incident detection)
CREATE INDEX IF NOT EXISTS idx_audit_logs_failures
    ON audit_logs (status, created_at DESC)
    WHERE status = 'failure';

COMMENT ON INDEX idx_audit_logs_failures IS
    'Index for quickly finding failed security events (potential attacks)';

-- 6. IP-based tracking (suspicious activity from specific IPs)
CREATE INDEX IF NOT EXISTS idx_audit_logs_ip_created
    ON audit_logs (ip_address, created_at DESC)
    WHERE ip_address IS NOT NULL;

COMMENT ON INDEX idx_audit_logs_ip_created IS
    'Index for tracking activity from specific IP addresses';

COMMIT;

-- =============================================================================
-- Example Event Types
-- =============================================================================

-- Authentication Events:
--   - auth.login (success/failure)
--   - auth.logout
--   - auth.token_refresh (success/failure)
--   - auth.token_revoke

-- Authorization Events:
--   - role.assigned
--   - role.revoked
--   - permission.changed
--   - permission.verified (for sensitive operations)

-- User Management Events:
--   - user.created
--   - user.updated
--   - user.deleted
--   - user.activated
--   - user.deactivated
--   - user.password_changed

-- API Key Events:
--   - api_key.created
--   - api_key.revoked
--   - api_key.used

-- =============================================================================
-- Example Usage Queries
-- =============================================================================

-- 1. View all failed login attempts in last 24 hours
-- SELECT *
-- FROM audit_logs
-- WHERE event_type = 'auth.login'
--   AND status = 'failure'
--   AND created_at > NOW() - INTERVAL '24 hours'
-- ORDER BY created_at DESC;

-- 2. View all actions performed by a specific user
-- SELECT event_type, event_action, resource_type, status, created_at
-- FROM audit_logs
-- WHERE actor_id = 123
-- ORDER BY created_at DESC
-- LIMIT 50;

-- 3. View all changes made to a specific user
-- SELECT event_type, event_action, actor_id, metadata, created_at
-- FROM audit_logs
-- WHERE target_id = 456
-- ORDER BY created_at DESC;

-- 4. Find suspicious activity from an IP
-- SELECT event_type, status, COUNT(*)
-- FROM audit_logs
-- WHERE ip_address = '192.168.1.100'
--   AND created_at > NOW() - INTERVAL '1 hour'
-- GROUP BY event_type, status;
