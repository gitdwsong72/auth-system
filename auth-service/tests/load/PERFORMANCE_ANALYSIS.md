# Performance Analysis & Bottleneck Predictions

## Executive Summary

Based on code analysis of the auth-system, this document identifies expected performance characteristics, potential bottlenecks, and optimization recommendations.

## Architecture Overview

```
Client Request
    ↓
Rate Limiter Middleware (Redis check)
    ↓
Security Headers Middleware
    ↓
FastAPI Router
    ↓
Authentication Layer (JWT validation, Redis)
    ↓
Service Layer (Business Logic)
    ↓
Repository Layer (asyncpg)
    ↓
PostgreSQL Database
```

## Expected Performance Characteristics

### 1. POST /api/v1/auth/login

**Expected Performance**: 150-300ms (P95)

**Breakdown**:
- Database query (find user by email): ~5-10ms
- bcrypt password verification: **100-200ms** (bcrypt cost factor)
- JWT token generation (RS256): ~5-10ms
- Database insert (login_history): ~5ms
- Database insert (refresh_token): ~5ms
- Redis SET (token metadata): ~1-2ms
- Total: ~116-232ms + overhead

**Primary Bottleneck**: **bcrypt password hashing**
- Intentionally slow for security (protects against brute force)
- CPU-intensive operation
- Cannot be easily optimized without compromising security

**Rate Limit**: 5 requests/minute/IP

**Scaling Considerations**:
- Horizontal scaling required (CPU-bound)
- Consider dedicated auth worker processes
- Connection pooling to handle concurrent requests

### 2. POST /api/v1/auth/refresh

**Expected Performance**: 30-80ms (P95)

**Breakdown**:
- JWT validation: ~5-10ms
- Redis GET (token blacklist check): ~1-2ms
- Database query (find refresh token): ~5-10ms
- JWT token generation (new access + refresh): ~10-15ms
- Database update (refresh token): ~5-10ms
- Redis SET operations (2x): ~2-4ms
- Total: ~28-51ms + overhead

**Primary Bottleneck**: Database query + update
- Less severe than login (no bcrypt)
- Can handle higher throughput

**Rate Limit**: 10 requests/minute/IP

**Scaling Considerations**:
- Mostly I/O bound (DB + Redis)
- Database connection pool size critical
- Redis performance crucial for token validation

### 3. GET /api/v1/users/me

**Expected Performance**: 20-50ms (P95)

**Breakdown**:
- JWT validation: ~5-10ms
- Redis GET (token blacklist check): ~1-2ms
- Database query (user + roles + permissions): ~10-20ms
- Response serialization: ~5ms
- Total: ~21-37ms + overhead

**Primary Bottleneck**: Database JOIN query
- 3-table JOIN (users, roles, permissions)
- Reasonable performance with proper indexes

**Rate Limit**: 100 requests/minute/IP (default)

**Scaling Considerations**:
- Can leverage database read replicas
- Consider caching user profile + permissions in Redis
- Good candidate for HTTP caching headers

### 4. POST /api/v1/users/register

**Expected Performance**: 200-400ms (P95)

**Breakdown**:
- Input validation: ~1-2ms
- Database query (check email uniqueness): ~5-10ms
- bcrypt password hashing: **100-200ms** (same as login)
- Database insert (user): ~5-10ms
- Database query (get default role): ~5ms
- Database insert (user_role): ~5ms
- Response serialization: ~5ms
- Total: ~126-237ms + overhead

**Primary Bottleneck**: **bcrypt password hashing**
- Same issue as login endpoint
- Security requirement, cannot optimize away

**Rate Limit**: 3 requests/hour/IP (aggressive protection)

**Scaling Considerations**:
- Lower expected throughput (rate limited)
- Database write capacity important
- Consider background job for email verification

### 5. POST /api/v1/auth/logout

**Expected Performance**: 40-80ms (P95)

**Breakdown**:
- JWT validation: ~5-10ms
- Redis GET (blacklist check): ~1-2ms
- JWT decode: ~5ms
- Redis SET (blacklist token): ~2-5ms
- Database delete (refresh token): ~10-20ms
- Redis DEL (token metadata): ~2-5ms
- Total: ~25-47ms + overhead

**Primary Bottleneck**: Database delete operation
- Multiple index updates
- Redis operations are fast

**Rate Limit**: 10 requests/minute/IP

**Scaling Considerations**:
- I/O bound operation
- Redis connection pooling helps
- Consider async token cleanup

### 6. GET /api/v1/auth/sessions

**Expected Performance**: 30-70ms (P95)

**Breakdown**:
- JWT validation: ~5-10ms
- Redis GET (blacklist check): ~1-2ms
- Database query (refresh_tokens by user_id): ~15-30ms
- Response serialization: ~5-10ms
- Total: ~26-52ms + overhead

**Primary Bottleneck**: Database query
- Can return multiple rows (multiple sessions)
- Reasonable performance with index on user_id

**Rate Limit**: 100 requests/minute/IP (default)

**Scaling Considerations**:
- Read-heavy operation
- Good candidate for read replicas
- Consider caching in Redis with TTL

## System-Wide Bottlenecks

### 1. Database Connection Pool

**Current Configuration**: Default asyncpg pool (~10-20 connections)

**Impact**: All endpoints under concurrent load

**Symptoms**:
- Increased latency at 50+ concurrent requests
- TimeoutError exceptions
- Response time variance increases

**Recommendations**:
```python
# src/shared/database/connection.py
pool = await asyncpg.create_pool(
    dsn=db_url,
    min_size=10,      # Minimum connections
    max_size=50,      # Maximum connections (tune based on load test)
    command_timeout=5.0,  # Query timeout
    max_inactive_connection_lifetime=300  # Close idle connections
)
```

**Load Test Target**: Find optimal pool size (likely 30-50 for moderate load)

### 2. Redis Single-Threaded Nature

**Impact**: Token operations under very high load (>1000 RPS)

**Operations Affected**:
- Rate limiting checks (every request)
- Token blacklist operations (login/logout)
- Token metadata storage

**Symptoms**:
- Redis becomes CPU bottleneck at high RPS
- Increased latency across all endpoints
- Queueing on Redis connection

**Recommendations**:
- Use Redis connection pooling (already in redis-py)
- Consider Redis cluster for horizontal scaling
- Pipeline multiple Redis operations where possible
- Monitor Redis CPU usage during tests

### 3. bcrypt CPU Consumption

**Impact**: Authentication endpoints (login, register)

**Current Configuration**: bcrypt default rounds (~12)

**CPU Profile Expectation**:
```
Top CPU Consumers:
1. bcrypt (60-80% of request time)
2. PostgreSQL queries (10-15%)
3. JWT operations (5-10%)
4. FastAPI/Pydantic (5-10%)
```

**Recommendations**:
- **DO NOT reduce bcrypt rounds** (security risk)
- Accept 100-200ms login latency as security tradeoff
- Scale horizontally for more bcrypt capacity
- Consider rate limiting as primary defense
- Monitor CPU usage: should be high during login-heavy tests

### 4. JWT Token Validation (RS256)

**Impact**: All authenticated endpoints

**Performance**: ~5-10ms per request (acceptable)

**Optimization Potential**:
- Current RS256 provides security + stateless verification
- Could cache public key parsing (likely already done by library)
- NOT a major bottleneck unless RPS > 5000

### 5. Database Query Performance

**Critical Queries**:

1. **User lookup by email** (login):
```sql
-- INDEX EXISTS: users_email_idx
-- Expected: ~5ms
SELECT * FROM users WHERE email = $1
```

2. **User profile with permissions** (get_profile):
```sql
-- Multiple JOINs, needs analysis
-- Expected: ~10-20ms
SELECT u.*, r.name, p.resource, p.action
FROM users u
JOIN user_roles ur ON ...
JOIN roles r ON ...
JOIN role_permissions rp ON ...
JOIN permissions p ON ...
```

3. **Refresh token lookup** (refresh):
```sql
-- INDEX EXISTS: refresh_tokens_token_hash_idx
-- Expected: ~5-10ms
SELECT * FROM refresh_tokens WHERE token_hash = $1
```

**Recommendations**:
- Verify all indexes exist (especially foreign keys)
- Use EXPLAIN ANALYZE during load tests
- Monitor slow query log
- Consider materialized views for complex permission checks

## Load Testing Predictions

### Light Load (10 concurrent users)
- **Expected**: All endpoints < 100ms (P95)
- **Bottleneck**: None, comfortable capacity
- **Resources**: CPU < 20%, DB connections < 10

### Medium Load (50 concurrent users)
- **Expected**:
  - Login: ~200ms (P95)
  - Other endpoints: < 100ms (P95)
- **Bottleneck**: bcrypt on login endpoints
- **Resources**: CPU 40-60% (during login spikes), DB connections ~20-30

### Heavy Load (100 concurrent users)
- **Expected**:
  - Login: ~300-500ms (P95), possible queueing
  - Read endpoints: ~100-150ms (P95)
- **Bottleneck**:
  - bcrypt CPU saturation
  - Database connection pool contention
- **Resources**: CPU 80-100% (login-heavy), DB connections approaching pool limit

### Stress Test (200+ concurrent users)
- **Expected**: System degradation
- **Bottlenecks**:
  - bcrypt queueing (login endpoints)
  - Database pool exhaustion (all endpoints)
  - Possible Redis contention (rate limiting)
- **Symptoms**:
  - 429 rate limit errors (expected)
  - 500 errors (database timeouts)
  - Response time variance increases significantly

## Recommended Test Sequence

### Phase 1: Baseline (30 minutes)
```bash
# 10 users, 5 minutes per scenario
1. AuthSystemUser (mixed workload)
2. LoginHeavyUser (auth stress)
3. TokenRefreshHeavyUser (Redis/JWT stress)
```

**Goal**: Establish baseline performance, verify no errors under light load

### Phase 2: Capacity Testing (1 hour)
```bash
# Gradually increase load
1. 25 users (10 min)
2. 50 users (15 min)
3. 75 users (15 min)
4. 100 users (15 min)
5. Monitor for degradation point
```

**Goal**: Find comfortable operating capacity (< 1% error rate, P95 < target)

### Phase 3: Stress Testing (30 minutes)
```bash
# Push beyond capacity
1. 150 users (10 min)
2. 200 users (10 min)
3. 300 users (spike test, 5 min)
```

**Goal**: Find absolute limits, observe failure modes

### Phase 4: Scenario-Specific (1 hour)
```bash
# Deep dive into specific concerns
1. LoginHeavyUser @ 50 users (bcrypt capacity)
2. RegistrationStressUser @ 20 users (write capacity)
3. TokenRefreshHeavyUser @ 100 users (Redis capacity)
```

**Goal**: Stress individual components to failure

## Monitoring Checklist

### Before Test
- [ ] Clear Redis cache: `redis-cli -p 6380 FLUSHDB`
- [ ] Restart PostgreSQL to clear connection state
- [ ] Restart auth service
- [ ] Verify test database is empty (or use test data)
- [ ] Start monitoring tools

### During Test
- [ ] Watch CPU usage: `top -pid $(pgrep uvicorn)`
- [ ] Monitor database connections: `SELECT count(*) FROM pg_stat_activity`
- [ ] Check Redis stats: `redis-cli INFO stats`
- [ ] Observe Locust web UI for errors
- [ ] Note when performance degradation begins

### After Test
- [ ] Save Locust HTML report
- [ ] Export PostgreSQL slow query log
- [ ] Review Redis command stats
- [ ] Document error rates and types
- [ ] Compare against previous test results

## Expected Results Summary

| Metric | Light (10u) | Medium (50u) | Heavy (100u) | Stress (200u+) |
|--------|-------------|--------------|--------------|----------------|
| Login P95 | ~150ms | ~200ms | ~350ms | ~600ms+ |
| Refresh P95 | ~30ms | ~50ms | ~80ms | ~150ms+ |
| Profile P95 | ~25ms | ~40ms | ~70ms | ~120ms+ |
| Error Rate | 0% | <0.5% | <2% | >5% |
| CPU Usage | 15-25% | 40-60% | 80-95% | 100% |
| DB Connections | 5-8 | 15-25 | 30-45 | Pool exhaustion |

## Optimization Roadmap

### Quick Wins (< 1 week)
1. ✅ Verify all database indexes exist
2. ✅ Tune connection pool size based on load tests
3. ✅ Add response caching headers for read endpoints
4. ✅ Implement Redis connection pooling (if not already)

### Medium Term (1-2 weeks)
1. Cache user permissions in Redis (reduce DB queries)
2. Implement database read replicas for read-heavy endpoints
3. Add request/response compression
4. Optimize SQL queries based on EXPLAIN ANALYZE

### Long Term (1+ months)
1. Horizontal scaling (multiple auth service instances)
2. Redis cluster for high availability
3. Dedicated auth worker processes
4. Database sharding if scale requires

## Conclusion

The auth-system is well-architected with clear separation of concerns and proper security measures. The primary performance constraint is **intentional** (bcrypt for security), and the system should handle moderate load (50-100 concurrent users) comfortably.

Key findings:
- bcrypt is the bottleneck (expected, acceptable)
- Database connection pool tuning is critical
- Redis performs well, unlikely bottleneck until very high scale
- Read endpoints have good optimization potential via caching

Load testing will validate these predictions and guide optimization priorities.
