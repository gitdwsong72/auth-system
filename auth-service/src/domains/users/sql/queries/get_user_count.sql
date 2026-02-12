-- 사용자 총 개수 (검색, 필터 적용)
-- $1: search (email/username), $2: is_active (nullable)
SELECT COUNT(*) as count
FROM users
WHERE deleted_at IS NULL
  AND ($1::text IS NULL OR email ILIKE '%' || $1 || '%' OR username ILIKE '%' || $1 || '%')
  AND ($2::boolean IS NULL OR is_active = $2);
