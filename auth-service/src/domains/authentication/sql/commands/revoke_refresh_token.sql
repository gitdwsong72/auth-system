-- 리프레시 토큰 폐기
-- $1: token_hash
UPDATE refresh_tokens
SET revoked_at = NOW()
WHERE token_hash = $1
  AND revoked_at IS NULL
RETURNING id;
