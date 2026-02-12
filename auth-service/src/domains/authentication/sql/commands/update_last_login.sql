-- 마지막 로그인 시각 업데이트
-- $1: user_id
UPDATE users
SET last_login_at = NOW()
WHERE id = $1
RETURNING id;
