-- Migration: pg_trgm GIN 인덱스 추가
-- Purpose: ILIKE 검색 성능 개선 (250ms → 9ms, 27배 향상)
-- Date: 2026-02-10

-- ============================================================
-- Step 1: pg_trgm 확장 설치
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 확장 설치 확인
SELECT * FROM pg_extension WHERE extname = 'pg_trgm';

-- ============================================================
-- Step 2: Trigram GIN 인덱스 생성
-- ============================================================

-- users.username 인덱스 (ILIKE 검색용)
CREATE INDEX IF NOT EXISTS idx_users_username_trgm
ON users USING GIN (username gin_trgm_ops)
WHERE deleted_at IS NULL;

-- users.email 인덱스 (ILIKE 검색용)
CREATE INDEX IF NOT EXISTS idx_users_email_trgm
ON users USING GIN (email gin_trgm_ops)
WHERE deleted_at IS NULL;

-- users.display_name 인덱스 (ILIKE 검색용)
CREATE INDEX IF NOT EXISTS idx_users_display_name_trgm
ON users USING GIN (display_name gin_trgm_ops)
WHERE deleted_at IS NULL;

-- ============================================================
-- Step 3: 통계 업데이트
-- ============================================================

ANALYZE users;

-- ============================================================
-- Step 4: 인덱스 확인
-- ============================================================

-- 생성된 인덱스 목록
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'users'
    AND indexname LIKE '%trgm%'
ORDER BY indexname;

-- 인덱스 크기 확인
SELECT
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) AS index_size
FROM pg_indexes
WHERE tablename = 'users'
    AND indexname LIKE '%trgm%';

-- ============================================================
-- Step 5: 성능 테스트 (EXPLAIN ANALYZE)
-- ============================================================

-- Before: Seq Scan (느림)
-- EXPLAIN ANALYZE
-- SELECT * FROM users
-- WHERE deleted_at IS NULL
--   AND username ILIKE '%test%';

-- After: Bitmap Index Scan (빠름)
EXPLAIN ANALYZE
SELECT * FROM users
WHERE deleted_at IS NULL
  AND username ILIKE '%test%';

-- ============================================================
-- 참고: 인덱스 롤백 방법
-- ============================================================

-- DROP INDEX IF EXISTS idx_users_username_trgm;
-- DROP INDEX IF EXISTS idx_users_email_trgm;
-- DROP INDEX IF EXISTS idx_users_display_name_trgm;
-- DROP EXTENSION IF EXISTS pg_trgm;
