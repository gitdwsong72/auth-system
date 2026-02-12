-- 리프레시 토큰 조회 (유효한 토큰만)
-- $1: token_hash
SELECT id, user_id, token_hash, device_info, expires_at, created_at
FROM refresh_tokens
WHERE token_hash = $1
  AND revoked_at IS NULL
  AND expires_at > NOW();
