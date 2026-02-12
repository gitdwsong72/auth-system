-- 사용자의 활성 세션 목록 조회
-- $1: user_id
SELECT id, device_info, created_at, expires_at
FROM refresh_tokens
WHERE user_id = $1
  AND revoked_at IS NULL
  AND expires_at > NOW()
ORDER BY created_at DESC;
