-- 사용자 목록 조회 + 총 개수 (Window Function 최적화)
-- $1: offset, $2: limit, $3: search (email/username), $4: is_active (nullable)
--
-- 성능 개선:
--   - 기존: 2개 쿼리 (COUNT + SELECT)
--   - 개선: 1개 쿼리 (Window Function)
--   - 효과: 쿼리 수 50% 감소
SELECT
    id,
    email,
    username,
    display_name,
    is_active,
    email_verified,
    created_at,
    last_login_at,
    COUNT(*) OVER() AS total_count  -- Window Function으로 전체 개수 포함
FROM users
WHERE deleted_at IS NULL
  AND ($3::text IS NULL OR email ILIKE '%' || $3 || '%' OR username ILIKE '%' || $3 || '%')
  AND ($4::boolean IS NULL OR is_active = $4)
ORDER BY created_at DESC
LIMIT $2 OFFSET $1;
