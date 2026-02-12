-- 비밀번호 변경
-- $1: user_id, $2: new_password_hash
UPDATE users
SET password_hash = $2,
    updated_at = NOW()
WHERE id = $1 AND deleted_at IS NULL
RETURNING id;
