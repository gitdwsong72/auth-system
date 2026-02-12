-- 사용자 목록 조회 (페이징, 검색, 필터)
-- $1: offset, $2: limit, $3: search (email/username), $4: is_active (nullable)
SELECT id, email, username, display_name, is_active, email_verified,
       created_at, last_login_at
FROM users
WHERE deleted_at IS NULL
  AND ($3::text IS NULL OR email ILIKE '%' || $3 || '%' OR username ILIKE '%' || $3 || '%')
  AND ($4::boolean IS NULL OR is_active = $4)
ORDER BY created_at DESC
LIMIT $2 OFFSET $1;
