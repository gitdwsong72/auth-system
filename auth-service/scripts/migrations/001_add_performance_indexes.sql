-- =============================================================================
-- Performance Index Migration
-- Description: Add performance indexes for common query patterns
-- Date: 2026-02-10
-- =============================================================================

BEGIN;

-- 1. Email search performance (login queries)
CREATE INDEX IF NOT EXISTS idx_users_email_active
    ON users (email)
    WHERE deleted_at IS NULL;

-- 2. Valid user roles filter (permission checks)
CREATE INDEX IF NOT EXISTS idx_user_roles_user_id_valid
    ON user_roles (user_id)
    WHERE expires_at IS NULL OR expires_at > NOW();

-- 3. Login history queries (user activity tracking)
CREATE INDEX IF NOT EXISTS idx_login_histories_user_created
    ON login_histories (user_id, created_at DESC);

COMMIT;

-- Verification queries
-- Run these to verify index usage:
-- EXPLAIN ANALYZE SELECT * FROM users WHERE email = 'test@example.com' AND deleted_at IS NULL;
-- EXPLAIN ANALYZE SELECT * FROM user_roles WHERE user_id = 1 AND (expires_at IS NULL OR expires_at > NOW());
-- EXPLAIN ANALYZE SELECT * FROM login_histories WHERE user_id = 1 ORDER BY created_at DESC LIMIT 10;
