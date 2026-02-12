-- 사용자 프로필 수정
-- $1: user_id, $2: display_name, $3: phone, $4: avatar_url
UPDATE users
SET display_name = COALESCE($2, display_name),
    phone = COALESCE($3, phone),
    avatar_url = COALESCE($4, avatar_url),
    updated_at = NOW()
WHERE id = $1 AND deleted_at IS NULL
RETURNING id, email, username, display_name, phone, avatar_url, updated_at;
