-- 사용자의 모든 리프레시 토큰 폐기
-- $1: user_id
UPDATE refresh_tokens
SET revoked_at = NOW()
WHERE user_id = $1
  AND revoked_at IS NULL
RETURNING id;
