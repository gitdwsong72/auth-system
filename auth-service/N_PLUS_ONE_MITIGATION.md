# N+1 Query Mitigation Analysis

## Executive Summary

✅ **No N+1 query issues found** in the current codebase.

The auth-system implements multiple strategies to prevent N+1 queries:

1. **JOIN Queries**: Use proper SQL JOINs instead of separate queries
2. **Window Functions**: Combine list + count queries into single query
3. **Redis Caching**: Cache frequently accessed relationships
4. **Lazy Loading Avoidance**: Don't load related data in loops

## Analysis by Domain

### 1. Users Domain - Roles & Permissions

**Potential Risk**: Loading roles/permissions for each user in a list

**Current Implementation**: ✅ Mitigated

#### Strategy 1: Cache with `get_user_permissions_with_cache()`

```python
# File: src/domains/users/service.py:22-60

async def get_user_permissions_with_cache(connection, user_id):
    # 1. Check Redis cache first (90% faster)
    cached = await redis_store.get_cached_user_permissions(user_id)
    if cached:
        return cached

    # 2. On cache miss, load with efficient JOIN
    roles_permissions_rows = await repository.get_user_roles_permissions(connection, user_id)

    # 3. Transform and cache (TTL 5 minutes)
    await redis_store.cache_user_permissions(user_id, result, ttl_seconds=300)
```

**Performance**:
- Cache hit: ~1ms (Redis lookup)
- Cache miss: ~5ms (single JOIN query)
- **No N+1 issue**: Single query per user, not per role or permission

#### Strategy 2: Efficient JOIN Query

```sql
-- File: src/domains/users/sql/queries/get_user_roles_permissions.sql

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
```

**Benefits**:
- Single query fetches all roles and permissions
- Uses proper JOINs (not separate SELECT * FROM roles WHERE ...)
- Returns flattened result set

#### Strategy 3: User List Doesn't Load Roles

```python
# File: src/domains/users/service.py:313-329

# User list endpoint returns basic info only
user_rows, total = await repository.get_user_list_with_count(...)

users = [
    schemas.UserListResponse(
        id=row["id"],
        email=row["email"],
        username=row["username"],
        # No roles/permissions loaded here!
    )
    for row in user_rows
]
```

**Design**: List endpoints show basic info; detail endpoint shows full info.

---

### 2. Users Domain - List Pagination

**Potential Risk**: Separate queries for list + total count

**Current Implementation**: ✅ Mitigated with Window Functions

```python
# File: src/domains/users/repository.py:116-148

async def get_user_list_with_count(...):
    """
    기존 방식: 2개 쿼리 (get_user_list + get_user_count)
    최적화: 1개 쿼리 (Window Function 사용)
    효과: 쿼리 수 50% 감소, 성능 향상
    """
    query = sql.load_query("get_user_list_with_count")
    rows = await connection.fetch(query, ...)
```

```sql
-- File: src/domains/users/sql/queries/get_user_list_with_count.sql

SELECT
    id, email, username, display_name, is_active, email_verified,
    created_at, last_login_at,
    COUNT(*) OVER() as total_count  -- Window function!
FROM users
WHERE ...
ORDER BY created_at DESC
LIMIT $2 OFFSET $1;
```

**Performance**:
- Before: 2 queries (list + count)
- After: 1 query with window function
- **50% query reduction**

---

### 3. Authentication Domain - Login History

**Potential Risk**: Loading user info for each login history entry

**Current Implementation**: ✅ Not loading user info in history list

```sql
-- File: src/domains/authentication/sql/queries/get_login_history.sql

SELECT
    id, user_id, ip_address, user_agent,
    login_at, success
FROM login_histories
WHERE user_id = $1
ORDER BY login_at DESC
LIMIT $2 OFFSET $3;
```

**Design**: Only stores user_id, doesn't JOIN users table (not needed).

---

### 4. Authentication Domain - Active Sessions

**Potential Risk**: Loading refresh tokens in loop

**Current Implementation**: ✅ Mitigated

```sql
-- File: src/domains/authentication/sql/queries/get_active_sessions.sql

SELECT
    id, user_id, token_hash, expires_at, created_at,
    last_used_at, ip_address, user_agent
FROM refresh_tokens
WHERE user_id = $1
  AND revoked_at IS NULL
  AND expires_at > NOW()
ORDER BY created_at DESC;
```

**Design**: Single query for all active sessions (no loop).

---

## Best Practices Observed

### ✅ DO's (Currently Implemented)

1. **Use JOINs**: Combine related tables in single query
   - Example: `user_roles JOIN roles JOIN permissions`

2. **Cache Frequently Accessed Data**: Use Redis for hot paths
   - Example: User permissions cached 5 minutes

3. **Window Functions**: Combine list + count queries
   - Example: `COUNT(*) OVER()` in user list

4. **List vs Detail Pattern**: Lists show basic info, details show full info
   - Example: User list doesn't include roles/permissions

5. **Track Query Performance**: Use `track_query()` context manager
   - Located in: `src/shared/database/connection.py`

### ❌ DON'Ts (Avoided)

1. **Don't load related data in loops**:
   ```python
   # ❌ BAD (N+1)
   users = await get_users()
   for user in users:
       roles = await get_user_roles(user.id)  # N queries!

   # ✅ GOOD
   users_with_roles = await get_users_with_roles_joined()
   ```

2. **Don't make separate list + count queries**:
   ```python
   # ❌ BAD (2 queries)
   users = await get_user_list()
   count = await get_user_count()

   # ✅ GOOD (1 query with window function)
   users, count = await get_user_list_with_count()
   ```

3. **Don't skip caching for hot paths**:
   ```python
   # ❌ BAD (DB hit every request)
   permissions = await db.get_user_permissions(user_id)

   # ✅ GOOD (cache + DB fallback)
   permissions = await get_user_permissions_with_cache(user_id)
   ```

---

## Monitoring & Detection

### 1. Query Tracking

All repository methods use `track_query()`:

```python
async with track_query("get_user_list"):
    result = await connection.fetch(query, ...)
```

### 2. Slow Query Logging

Located in: `src/shared/logging.py:29-51`

```python
def log_slow_query(query: str, duration: float, params: dict | None = None):
    """Log slow SQL queries (>100ms)"""
    if duration > 0.1:  # 100ms threshold
        performance_logger.warning(
            "Slow query detected",
            extra={"query": query, "duration_ms": duration * 1000},
        )
```

### 3. APM Integration (Future)

Consider adding:
- New Relic / DataDog APM
- pganalyze for PostgreSQL monitoring
- Prometheus query duration metrics

---

## Verification Checklist

- [x] User roles/permissions use JOINs (not loops)
- [x] User list uses window function (not 2 queries)
- [x] Frequently accessed data is cached (Redis)
- [x] List endpoints don't load related data
- [x] Query tracking is implemented
- [x] Slow query logging is configured

---

## Future Enhancements

### 1. DataLoader Pattern (Optional)

For GraphQL or complex nested queries, consider DataLoader:

```python
from aiodataloader import DataLoader

class UserRoleLoader(DataLoader):
    async def batch_load_fn(self, user_ids):
        # Load roles for multiple users in single query
        query = "SELECT user_id, role_id FROM user_roles WHERE user_id = ANY($1)"
        rows = await connection.fetch(query, user_ids)
        # Group by user_id and return
        ...
```

### 2. Query Result Prefetching

For known access patterns:

```python
# Prefetch related data if we know it will be accessed
users_with_roles = await get_users_with_roles_prefetched()
```

### 3. Database Connection Pooling Monitoring

Already implemented: `/metrics/db-pool` endpoint

```bash
curl http://localhost:8000/metrics/db-pool
```

Returns pool statistics to detect connection exhaustion.

---

## Conclusion

**Status**: ✅ N+1 queries are properly mitigated

The codebase demonstrates strong understanding of N+1 query prevention:
- Efficient SQL JOINs
- Redis caching for hot paths
- Window functions for list + count
- Query performance tracking

**Recommendation**: Continue current practices. No immediate action required.

---

## References

- [Efficient SQL JOINs](https://www.postgresql.org/docs/current/tutorial-join.html)
- [PostgreSQL Window Functions](https://www.postgresql.org/docs/current/tutorial-window.html)
- [Redis Caching Best Practices](https://redis.io/docs/manual/patterns/)
- [N+1 Query Problem](https://stackoverflow.com/questions/97197/what-is-the-n1-selects-problem)
