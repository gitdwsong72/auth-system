-- 사용자 ID로 조회
SELECT id, email, username, display_name, phone, avatar_url,
       is_active, email_verified, created_at, updated_at, last_login_at
FROM users
WHERE id = $1 AND deleted_at IS NULL;
