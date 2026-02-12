-- 사용자 생성
-- $1: email, $2: username, $3: password_hash, $4: display_name (nullable)
INSERT INTO users (email, username, password_hash, display_name, is_active, email_verified)
VALUES ($1, $2, $3, $4, true, false)
RETURNING id, email, username, display_name, created_at;
