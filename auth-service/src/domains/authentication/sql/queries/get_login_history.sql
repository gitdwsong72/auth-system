-- 로그인 이력 조회
-- $1: user_id, $2: limit
SELECT id, user_id, ip_address, user_agent, device_info, login_at, success
FROM login_histories
WHERE user_id = $1
ORDER BY login_at DESC
LIMIT $2;
