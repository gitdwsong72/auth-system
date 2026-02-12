-- 사용자에게 기본 역할 부여
-- $1: user_id, $2: role_name (e.g., 'user')
INSERT INTO user_roles (user_id, role_id)
SELECT $1, id
FROM roles
WHERE name = $2
ON CONFLICT (user_id, role_id) DO NOTHING
RETURNING id;
