# Solid Cache 사용 가이드

## 개요

**Solid Cache**는 37signals가 만든 PostgreSQL 기반 key-value 캐시 스토어입니다. Redis의 단순 캐싱 기능을 Aurora PostgreSQL로 대체하여 인프라를 단순화합니다.

## 아키텍처

```
┌─────────────────────────────────────┐
│     Application Layer               │
└─────────────┬───────────────────────┘
              │
      ┌───────┴────────┐
      │                │
┌─────▼─────┐   ┌─────▼──────────┐
│   Redis   │   │ Solid Cache    │
│           │   │ (Aurora Table) │
├───────────┤   ├────────────────┤
│ • Tokens  │   │ • Query cache  │
│ • Sessions│   │ • Static data  │
│ • Rate    │   │ • User profile │
│   limit   │   │   (optional)   │
│ • Counters│   │                │
└───────────┘   └────────────────┘
```

## 권장 사용 케이스

### ✅ Solid Cache 사용 권장

- **쿼리 결과 캐싱**: 복잡한 JOIN 쿼리 결과 (변경 빈도 낮음)
- **정적 설정 데이터**: 시스템 설정, 국가 코드, 카테고리 목록 등
- **사용자 프로필 캐시**: 자주 조회되지만 덜 변경되는 데이터
- **권한 캐시** (선택사항): Redis에서 마이그레이션 가능

### ❌ Solid Cache 사용 비권장

- **Rate Limiting**: Redis의 `INCR` 필요 (원자적 카운터)
- **Active Token Registry**: Redis의 Set 자료구조 필요
- **Real-time Counters**: 높은 쓰기 빈도
- **세션 저장소**: 빠른 읽기/쓰기 필요

## 설정

### 1. 마이그레이션 실행

```bash
# PostgreSQL에 연결
psql -h localhost -p 5433 -U auth_user -d auth_db

# 마이그레이션 실행
\i scripts/migrations/005_add_solid_cache.sql
```

### 2. Cleanup Job 설정 (선택사항)

#### Option A: pg_cron (권장)

```sql
-- pg_cron extension 활성화 (슈퍼유저 권한 필요)
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- 매 1시간마다 만료된 캐시 삭제
SELECT cron.schedule(
    'cleanup-solid-cache',
    '0 * * * *',
    'SELECT cleanup_expired_cache();'
);
```

#### Option B: AWS Lambda + EventBridge

```python
# lambda_function.py
import asyncpg
import os

async def handler(event, context):
    """만료된 Solid Cache 엔트리를 삭제하는 Lambda 핸들러."""
    db_url = os.environ['DB_URL']

    conn = await asyncpg.connect(db_url)
    try:
        deleted_count = await conn.fetchval('SELECT cleanup_expired_cache()')
        return {
            'statusCode': 200,
            'body': f'Deleted {deleted_count} expired cache entries'
        }
    finally:
        await conn.close()
```

**EventBridge Rule:**
- Schedule: `rate(1 hour)`
- Target: Lambda function

#### Option C: Kubernetes CronJob

```yaml
# k8s/cronjob-solid-cache-cleanup.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: solid-cache-cleanup
spec:
  schedule: "0 * * * *"  # 매 1시간
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: cleanup
            image: postgres:15
            env:
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: password
            command:
            - psql
            - -h
            - $(DB_HOST)
            - -U
            - $(DB_USER)
            - -d
            - $(DB_NAME)
            - -c
            - SELECT cleanup_expired_cache();
          restartPolicy: OnFailure
```

## 사용 방법

### 기본 사용법

```python
from src.shared.database import db_pool
from src.shared.database.solid_cache import SolidCache

# Solid Cache 인스턴스 생성
solid_cache = SolidCache(db_pool._primary_pool)

# 1. 문자열 저장/조회
await solid_cache.set("my_key", "my_value", ttl_seconds=300)
value = await solid_cache.get("my_key")

# 2. JSON 저장/조회
data = {"user_id": 123, "name": "John"}
await solid_cache.set_json("user:123", data, ttl_seconds=600)
cached_data = await solid_cache.get_json("user:123")

# 3. 삭제
await solid_cache.delete("my_key")

# 4. 패턴 매칭 삭제
deleted_count = await solid_cache.delete_pattern("user:%")

# 5. 존재 확인
exists = await solid_cache.exists("my_key")

# 6. TTL 확인
remaining_seconds = await solid_cache.ttl("my_key")
```

### 쿼리 결과 캐싱 예시

```python
async def get_user_summary_with_cache(conn: asyncpg.Connection, user_id: int) -> dict:
    """사용자 요약 정보를 캐시와 함께 조회한다."""
    from src.shared.database import db_pool
    from src.shared.database.solid_cache import SolidCache

    solid_cache = SolidCache(db_pool._primary_pool)
    cache_key = f"user_summary:{user_id}"

    # 1. 캐시 확인
    cached = await solid_cache.get_json(cache_key)
    if cached:
        return cached

    # 2. DB 조회
    query = """
        SELECT
            u.id,
            u.username,
            u.email,
            COUNT(DISTINCT ul.id) as login_count,
            MAX(ul.created_at) as last_login
        FROM users u
        LEFT JOIN login_histories ul ON u.id = ul.user_id
        WHERE u.id = $1
        GROUP BY u.id, u.username, u.email
    """
    row = await conn.fetchrow(query, user_id)

    if not row:
        return None

    result = dict(row)

    # 3. 캐시 저장 (5분)
    await solid_cache.set_json(cache_key, result, ttl_seconds=300)

    return result
```

### 권한 캐시 마이그레이션 예시 (Redis → Solid Cache)

```python
# Before (Redis)
from src.shared.security.redis_store import redis_store

cached = await redis_store.get_cached_user_permissions(user_id)
if not cached:
    permissions = await fetch_permissions_from_db(conn, user_id)
    await redis_store.cache_user_permissions(user_id, permissions, ttl_seconds=300)

# After (Solid Cache)
from src.shared.database import db_pool
from src.shared.database.solid_cache import SolidCache

solid_cache = SolidCache(db_pool._primary_pool)
cache_key = f"permissions:user:{user_id}"

cached = await solid_cache.get_json(cache_key)
if not cached:
    permissions = await fetch_permissions_from_db(conn, user_id)
    await solid_cache.set_json(cache_key, permissions, ttl_seconds=300)
```

## 모니터링

### 캐시 통계 조회

```python
# Python 코드
stats = await solid_cache.get_stats()
print(stats)
# {
#     'total_entries': 1234,
#     'expired_entries': 56,
#     'total_size_bytes': 102400
# }
```

```sql
-- SQL 쿼리
SELECT
    COUNT(*) as total_entries,
    COUNT(*) FILTER (WHERE expires_at < NOW()) as expired_entries,
    pg_total_relation_size('solid_cache_entries') as total_size_bytes,
    pg_size_pretty(pg_total_relation_size('solid_cache_entries')) as total_size
FROM solid_cache_entries;
```

### Health Check 엔드포인트 추가

```python
# src/main.py
@app.get("/health")
async def health_check() -> dict:
    result = {
        "status": "healthy",
        "services": {},
    }

    # ... 기존 DB, Redis 체크 ...

    # Solid Cache Health Check
    try:
        from src.shared.database import db_pool
        from src.shared.database.solid_cache import SolidCache

        solid_cache = SolidCache(db_pool._primary_pool)
        stats = await solid_cache.get_stats()

        result["services"]["solid_cache"] = {
            "status": "healthy",
            "total_entries": stats["total_entries"],
            "total_size_bytes": stats["total_size_bytes"],
        }
    except Exception as e:
        result["status"] = "unhealthy"
        result["services"]["solid_cache"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    return result
```

## 성능 고려사항

### Redis vs Solid Cache 응답 시간

| 작업 | Redis | Solid Cache (Aurora) |
|------|-------|----------------------|
| 단순 GET | ~0.1ms | ~1-5ms |
| JSON GET | ~0.2ms | ~2-8ms |
| SET | ~0.1ms | ~3-10ms |
| Pattern DELETE | ~1-10ms | ~10-50ms |

### 최적화 팁

1. **적절한 TTL 설정**: 불필요하게 긴 TTL은 스토리지 낭비
   ```python
   # 자주 변경되는 데이터: 짧은 TTL
   await solid_cache.set_json(key, data, ttl_seconds=60)

   # 정적 데이터: 긴 TTL
   await solid_cache.set_json(key, data, ttl_seconds=3600)
   ```

2. **인덱스 활용**: 패턴 매칭은 GIN 인덱스 활용
   ```sql
   -- 이미 생성됨 (005_add_solid_cache.sql)
   CREATE INDEX idx_solid_cache_key_pattern
       ON solid_cache_entries USING gin(key gin_trgm_ops);
   ```

3. **배치 삭제**: 대량 삭제 시 트랜잭션 사용
   ```python
   async with db_pool.acquire_primary() as conn:
       async with conn.transaction():
           await conn.execute("DELETE FROM solid_cache_entries WHERE key LIKE 'old_data:%'")
   ```

4. **주기적 Cleanup**: 만료된 엔트리 정리로 성능 유지
   ```python
   deleted_count = await solid_cache.cleanup_expired()
   ```

## 비용 분석

### Aurora 스토리지 증가 예상

| 캐시 엔트리 수 | 평균 값 크기 | 예상 스토리지 | 월간 비용 (us-east-1) |
|---------------|------------|--------------|---------------------|
| 1,000 | 1 KB | ~1 MB | < $0.01 |
| 10,000 | 1 KB | ~10 MB | < $0.01 |
| 100,000 | 1 KB | ~100 MB | ~$0.10 |
| 1,000,000 | 1 KB | ~1 GB | ~$1.00 |

**Aurora 스토리지 비용**: $0.10/GB/월 (us-east-1 기준)

### Redis vs Solid Cache 비용 비교

**ElastiCache Redis (cache.t3.micro):**
- 월간 비용: ~$12 (온디맨드)
- 메모리: 512MB
- 적합: 고빈도 읽기/쓰기

**Solid Cache (Aurora에 통합):**
- 추가 비용: ~$0.10-$1.00/월 (스토리지만)
- 메모리: Aurora 기존 메모리 사용
- 적합: 저빈도 읽기, 정적 데이터

## FAQ

### Q1. Redis를 완전히 대체할 수 있나요?

**A:** 아니요. Solid Cache는 **단순 key-value 캐싱**만 대체 가능합니다.

- ✅ 대체 가능: Token blacklist, Query cache, Static data
- ❌ 대체 불가: Rate limiting (INCR), Active tokens (Set), Counters

권장: **하이브리드 접근** - Redis는 세션/토큰 전용, Solid Cache는 쿼리 캐싱 전용

### Q2. 성능이 Redis보다 느린데 괜찮나요?

**A:** 사용 케이스에 따라 다릅니다.

- **실시간 세션/토큰**: Redis 필수 (~0.1ms)
- **쿼리 결과 캐싱**: Solid Cache 충분 (~2-5ms)
  - 원본 쿼리: 50-200ms
  - Solid Cache: 2-5ms (40-100배 빠름)

### Q3. Aurora 부하가 증가하지 않나요?

**A:** 적절히 사용하면 오히려 **부하 감소**:

- **Before**: 매번 복잡한 JOIN 쿼리 실행
- **After**: Solid Cache에서 간단한 SELECT (인덱스 활용)

주의: Rate limiting처럼 초당 수백 건의 쓰기는 Solid Cache에 부적합 (Redis 유지)

### Q4. Cleanup job을 설정하지 않으면 어떻게 되나요?

**A:** 만료된 엔트리가 삭제되지 않아 스토리지가 증가합니다.

- **영향**: Aurora 스토리지 비용 증가
- **해결**: 주기적 cleanup (pg_cron, Lambda, Kubernetes CronJob)
- **수동 실행**: `SELECT cleanup_expired_cache();`

### Q5. 어떤 데이터를 Solid Cache로 옮겨야 하나요?

**A:** 다음 조건을 만족하는 데이터:

1. **읽기 빈도**: 높음 (초당 10+ 요청)
2. **쓰기 빈도**: 낮음 (분당 1-10회)
3. **데이터 크기**: 작음 (< 10KB)
4. **TTL**: 1분 이상

**예시:**
- ✅ 사용자 프로필 (읽기 많음, 쓰기 적음)
- ✅ 권한 정보 (읽기 많음, 변경 드뭄)
- ❌ 실시간 카운터 (쓰기 많음)
- ❌ 세션 토큰 (빠른 응답 필수)

## 참고 자료

- [Solid Cache GitHub](https://github.com/rails/solid_cache)
- [37signals 발표](https://dev.37signals.com/solid-cache/)
- [Aurora Performance Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.BestPractices.html)
- [PostgreSQL pg_trgm](https://www.postgresql.org/docs/current/pgtrgm.html)
