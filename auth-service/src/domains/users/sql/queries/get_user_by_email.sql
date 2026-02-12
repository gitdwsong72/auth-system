-- 이메일로 사용자 조회 (비밀번호 해시 포함)
SELECT id, email, username, password_hash, display_name, phone, avatar_url,
       is_active, email_verified, created_at, updated_at, last_login_at
FROM users
WHERE email = $1 AND deleted_at IS NULL;
