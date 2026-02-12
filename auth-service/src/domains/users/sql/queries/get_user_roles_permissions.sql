-- 사용자의 역할 및 권한 조회
-- $1: user_id
SELECT DISTINCT
    r.name as role_name,
    CASE
        WHEN p.id IS NOT NULL THEN p.resource || ':' || p.action
        ELSE NULL
    END as permission_name
FROM user_roles ur
JOIN roles r ON ur.role_id = r.id
LEFT JOIN role_permissions rp ON r.id = rp.role_id
LEFT JOIN permissions p ON rp.permission_id = p.id
WHERE ur.user_id = $1;
