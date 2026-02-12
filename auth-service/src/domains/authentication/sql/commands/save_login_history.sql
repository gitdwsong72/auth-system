-- 로그인 이력 저장
-- $1: user_id, $2: ip_address, $3: user_agent, $4: success
INSERT INTO login_histories (user_id, ip_address, user_agent, login_type, success)
VALUES ($1, $2, $3, 'password', $4)
RETURNING id;
