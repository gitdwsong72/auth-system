-- 리프레시 토큰 저장
-- $1: user_id, $2: token_hash, $3: device_info (jsonb), $4: expires_at
INSERT INTO refresh_tokens (user_id, token_hash, device_info, expires_at)
VALUES ($1, $2, $3::jsonb, $4)
RETURNING id, created_at;
