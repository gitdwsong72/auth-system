-- Migration: Add Solid Cache infrastructure
-- Description: Solid Cache는 PostgreSQL 기반 key-value 캐시 스토어입니다.
-- Date: 2026-02-12
-- Author: Claude Code

-- ===== 테이블 생성 =====

CREATE TABLE IF NOT EXISTS solid_cache_entries (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

-- ===== 인덱스 생성 =====

-- expires_at 인덱스: 만료된 엔트리 조회 및 cleanup에 사용
CREATE INDEX IF NOT EXISTS idx_solid_cache_expires
    ON solid_cache_entries(expires_at);

-- 패턴 매칭 검색용 인덱스 (예: 'permissions:user:%' 패턴)
-- GIN 인덱스 + pg_trgm extension 활용 (LIKE 쿼리 최적화)
CREATE INDEX IF NOT EXISTS idx_solid_cache_key_pattern
    ON solid_cache_entries USING gin(key gin_trgm_ops);

-- ===== Cleanup 함수 =====

CREATE OR REPLACE FUNCTION cleanup_expired_cache()
RETURNS TABLE(deleted_count INTEGER) AS $$
DECLARE
    rows_deleted INTEGER;
BEGIN
    -- 만료된 캐시 엔트리 삭제
    DELETE FROM solid_cache_entries WHERE expires_at < NOW();

    -- 삭제된 행 수 반환
    GET DIAGNOSTICS rows_deleted = ROW_COUNT;

    RETURN QUERY SELECT rows_deleted;
END;
$$ LANGUAGE plpgsql;

-- ===== 주석 =====

COMMENT ON TABLE solid_cache_entries IS
'Solid Cache: PostgreSQL 기반 key-value 캐시 스토어. Redis의 단순 캐싱 기능을 대체.';

COMMENT ON COLUMN solid_cache_entries.key IS
'캐시 키 (예: "permissions:user:123", "query_result:hash")';

COMMENT ON COLUMN solid_cache_entries.value IS
'캐시 값 (문자열 또는 JSON)';

COMMENT ON COLUMN solid_cache_entries.expires_at IS
'만료 시각 (UTC). cleanup_expired_cache() 함수로 주기적 삭제.';

COMMENT ON FUNCTION cleanup_expired_cache IS
'만료된 캐시 엔트리를 삭제하는 함수. Cron job이나 pg_cron으로 주기적 실행 권장.';

-- ===== 사용 예시 (주석) =====

/*
-- 1. 캐시 저장
INSERT INTO solid_cache_entries (key, value, expires_at)
VALUES ('permissions:user:1', '{"roles": ["admin"]}', NOW() + INTERVAL '5 minutes')
ON CONFLICT (key) DO UPDATE SET
    value = EXCLUDED.value,
    expires_at = EXCLUDED.expires_at;

-- 2. 캐시 조회
SELECT value FROM solid_cache_entries
WHERE key = 'permissions:user:1' AND expires_at > NOW();

-- 3. 수동 cleanup (테스트용)
SELECT * FROM cleanup_expired_cache();

-- 4. 패턴 매칭 삭제
DELETE FROM solid_cache_entries WHERE key LIKE 'permissions:user:%';

-- 5. 캐시 통계
SELECT
    COUNT(*) as total_entries,
    COUNT(*) FILTER (WHERE expires_at < NOW()) as expired_entries,
    pg_total_relation_size('solid_cache_entries') as total_size_bytes
FROM solid_cache_entries;
*/

-- ===== 주기적 Cleanup 설정 (pg_cron 사용 시) =====

/*
-- pg_cron extension이 설치되어 있다면 아래 주석을 해제하여 자동 cleanup 설정
-- 매 1시간마다 만료된 캐시 삭제

-- 1. pg_cron extension 활성화 (슈퍼유저 권한 필요)
-- CREATE EXTENSION IF NOT EXISTS pg_cron;

-- 2. Cleanup job 등록
-- SELECT cron.schedule(
--     'cleanup-solid-cache',              -- job 이름
--     '0 * * * *',                         -- 매 시간 0분에 실행
--     'SELECT cleanup_expired_cache();'
-- );

-- 3. Cleanup job 확인
-- SELECT * FROM cron.job WHERE jobname = 'cleanup-solid-cache';

-- 4. Cleanup job 삭제 (필요시)
-- SELECT cron.unschedule('cleanup-solid-cache');
*/

-- ===== Lambda/ECS Scheduled Task 대안 =====

/*
-- pg_cron을 사용할 수 없는 환경 (Amazon Aurora Serverless v2 등)에서는
-- 다음 방법으로 주기적 cleanup 구현:

-- 1. AWS Lambda + EventBridge (CloudWatch Events)
--    - EventBridge: 매 1시간마다 트리거
--    - Lambda 함수: PostgreSQL 연결 후 cleanup_expired_cache() 호출

-- 2. ECS Scheduled Task
--    - ECS Task Definition: cleanup 스크립트 컨테이너
--    - EventBridge: 스케줄링

-- 3. Kubernetes CronJob
--    - CronJob: 매 1시간마다 실행
--    - Job: psql 또는 Python 스크립트로 cleanup_expired_cache() 호출

-- Python 예시 (Lambda/ECS):
import asyncpg

async def cleanup_handler(event, context):
    conn = await asyncpg.connect('postgresql://...')
    result = await conn.fetchval('SELECT cleanup_expired_cache()')
    await conn.close()
    return {'deleted_count': result}
*/
