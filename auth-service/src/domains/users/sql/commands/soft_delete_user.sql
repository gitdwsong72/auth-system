-- 사용자 소프트 삭제
-- $1: user_id
UPDATE users
SET deleted_at = NOW(),
    is_active = false
WHERE id = $1 AND deleted_at IS NULL
RETURNING id;
