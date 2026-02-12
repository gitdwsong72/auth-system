# Load Testing Deliverable Summary

## Overview

Complete load testing infrastructure for the auth-system, including test scenarios, documentation, and performance predictions.

## Deliverables

### 1. Load Test Scripts
**File**: `/Users/sktl/WF/WF01/auth-system/auth-service/tests/load/locustfile.py`

**Contents**:
- **4 distinct user scenarios** covering different usage patterns
- **Comprehensive endpoint coverage** (all auth & user endpoints)
- **Realistic user behavior** with weighted tasks and think times
- **Production-ready** with proper error handling and metrics

**Scenarios**:
1. **AuthSystemUser** (Default) - Mixed workload, realistic user journey
2. **LoginHeavyUser** - Authentication stress testing
3. **RegistrationStressUser** - New user registration load
4. **TokenRefreshHeavyUser** - Token refresh operations stress

### 2. Testing Guide
**File**: `/Users/sktl/WF/WF01/auth-system/auth-service/tests/load/README.md`

**Contents**:
- Installation instructions
- Detailed scenario descriptions
- Command-line examples for different test types
- Performance targets and SLAs
- Monitoring guide
- CI/CD integration examples
- Troubleshooting tips

### 3. Performance Analysis
**File**: `/Users/sktl/WF/WF01/auth-system/auth-service/tests/load/PERFORMANCE_ANALYSIS.md`

**Contents**:
- Expected performance for each endpoint
- Identified bottlenecks with mitigation strategies
- Load testing predictions (10/50/100/200+ users)
- Optimization roadmap
- Monitoring checklist

### 4. Quick Test Script
**File**: `/Users/sktl/WF/WF01/auth-system/auth-service/tests/load/quick_test.sh`

**Purpose**: One-command load test execution for quick validation

```bash
./tests/load/quick_test.sh
```

## Key Endpoints Tested

| Endpoint | Method | Test Coverage |
|----------|--------|---------------|
| /api/v1/users/register | POST | ✅ All scenarios |
| /api/v1/auth/login | POST | ✅ All scenarios |
| /api/v1/auth/refresh | POST | ✅ All scenarios |
| /api/v1/users/me | GET | ✅ All scenarios |
| /api/v1/users/me | PUT | ✅ AuthSystemUser |
| /api/v1/auth/logout | POST | ✅ LoginHeavyUser |
| /api/v1/auth/sessions | GET | ✅ AuthSystemUser |
| /api/v1/auth/sessions | DELETE | ✅ (via full flow tests) |

## Performance Targets (95th Percentile)

### Response Times

| Endpoint | Target | Acceptable | Critical |
|----------|--------|------------|----------|
| POST /auth/login | < 200ms | < 500ms | > 1000ms |
| POST /auth/refresh | < 50ms | < 100ms | > 200ms |
| GET /users/me | < 50ms | < 100ms | > 200ms |
| POST /users/register | < 300ms | < 600ms | > 1200ms |

### Throughput

| Scenario | Expected RPS | Target RPS | Max RPS |
|----------|--------------|------------|---------|
| Mixed workload | 50-100 | 200 | 500+ |
| Login-heavy | 20-50 | 100 | 200+ |
| Token refresh | 100-200 | 500 | 1000+ |
| Registration | 5-10 | 20 | 50+ |

## Predicted Bottlenecks

### 1. bcrypt Password Hashing (PRIMARY)
- **Impact**: 100-200ms per login/register request
- **Severity**: Expected, acceptable for security
- **Mitigation**: Horizontal scaling, rate limiting

### 2. Database Connection Pool
- **Impact**: Contention at 50+ concurrent requests
- **Severity**: Tunable, needs load test validation
- **Mitigation**: Increase pool size (default 10 → 30-50)

### 3. Redis Single-Threaded Nature
- **Impact**: Rate limiting, token operations at >1000 RPS
- **Severity**: Low until very high scale
- **Mitigation**: Connection pooling, Redis cluster

### 4. Complex JOIN Queries
- **Impact**: User profile with permissions (~10-20ms)
- **Severity**: Low, reasonable performance
- **Mitigation**: Caching, read replicas

## How to Run Tests

### Quick Test (2 minutes)
```bash
cd /Users/sktl/WF/WF01/auth-system/auth-service
./tests/load/quick_test.sh
```

### Basic Load Test (Web UI)
```bash
# Terminal 1: Start auth service
uvicorn src.main:app --reload --port 8000

# Terminal 2: Run Locust
locust -f tests/load/locustfile.py --host=http://localhost:8000

# Open browser to http://localhost:8089
```

### Stress Test (Headless)
```bash
locust -f tests/load/locustfile.py \
  --host=http://localhost:8000 \
  --users 100 \
  --spawn-rate 10 \
  --run-time 5m \
  --headless \
  --html reports/stress_test.html
```

### Scenario-Specific Tests
```bash
# Test login performance
locust -f tests/load/locustfile.py LoginHeavyUser \
  --host=http://localhost:8000 --users 30 --spawn-rate 5

# Test registration capacity
locust -f tests/load/locustfile.py RegistrationStressUser \
  --host=http://localhost:8000 --users 20 --spawn-rate 2

# Test token refresh
locust -f tests/load/locustfile.py TokenRefreshHeavyUser \
  --host=http://localhost:8000 --users 50 --spawn-rate 5
```

## Recommended Test Sequence

### Phase 1: Baseline (Required)
```bash
# 10 users, 5 minutes - establish baseline
locust -f tests/load/locustfile.py \
  --host=http://localhost:8000 \
  --users 10 --spawn-rate 1 --run-time 5m \
  --headless --html reports/baseline.html
```

### Phase 2: Capacity Test (Required)
```bash
# 50 users, 10 minutes - find operating capacity
locust -f tests/load/locustfile.py \
  --host=http://localhost:8000 \
  --users 50 --spawn-rate 5 --run-time 10m \
  --headless --html reports/capacity.html
```

### Phase 3: Stress Test (Recommended)
```bash
# 100+ users, 5 minutes - find limits
locust -f tests/load/locustfile.py \
  --host=http://localhost:8000 \
  --users 100 --spawn-rate 10 --run-time 5m \
  --headless --html reports/stress.html
```

### Phase 4: Scenario Tests (Optional)
```bash
# Test each bottleneck specifically
# See README.md for detailed commands
```

## Success Criteria

### Must Pass (Baseline @ 10 users)
- ✅ 0% error rate
- ✅ Login P95 < 500ms
- ✅ Other endpoints P95 < 100ms
- ✅ No database errors
- ✅ No Redis errors

### Should Pass (Capacity @ 50 users)
- ✅ < 1% error rate
- ✅ Login P95 < 600ms
- ✅ Other endpoints P95 < 150ms
- ✅ CPU < 80%
- ✅ DB connections < pool size

### Nice to Have (Stress @ 100 users)
- ✅ < 5% error rate
- ✅ Login P95 < 1000ms
- ✅ Graceful degradation (no crashes)
- ✅ Recovery after load removal

## Monitoring During Tests

### System Resources
```bash
# CPU and Memory
top -pid $(pgrep -f "uvicorn")

# PostgreSQL connections
psql -h localhost -p 5433 -U postgres -c \
  "SELECT count(*) FROM pg_stat_activity WHERE datname='auth_db';"

# Redis stats
redis-cli -p 6380 INFO stats
redis-cli -p 6380 INFO memory
```

### Key Metrics to Watch
1. **Response Time**: P50, P95, P99
2. **Error Rate**: Target < 1%
3. **Throughput**: RPS (requests per second)
4. **CPU Usage**: Should plateau before memory issues
5. **DB Connections**: Should not exceed pool size

## Next Steps After Testing

### 1. Analyze Results
- Review HTML reports
- Identify actual bottlenecks
- Compare with predictions

### 2. Optimize Based on Findings
- Tune database pool size
- Implement caching where beneficial
- Optimize slow queries

### 3. Establish Baselines
- Document actual performance numbers
- Update PERFORMANCE_ANALYSIS.md with real data
- Set up monitoring alerts based on thresholds

### 4. CI/CD Integration
- Add load tests to deployment pipeline
- Set up performance regression detection
- Automate report generation

### 5. Production Monitoring
- Use similar metrics in production
- Set up alerting for degradation
- Plan capacity based on load test results

## Installation Requirements

```bash
# Install Locust
pip install locust>=2.20.0

# Or add to requirements
echo "locust>=2.20.0" >> requirements-dev.txt
pip install -r requirements-dev.txt
```

## File Structure

```
tests/load/
├── __init__.py                    # Package init
├── locustfile.py                  # Main test scenarios (507 lines)
├── README.md                      # Comprehensive testing guide
├── PERFORMANCE_ANALYSIS.md        # Bottleneck predictions & analysis
├── DELIVERABLE_SUMMARY.md         # This file
├── quick_test.sh                  # Quick test script
└── reports/                       # Generated HTML reports (gitignored)
```

## Known Limitations

### 1. Rate Limiting
Tests will trigger rate limiting intentionally. This is **expected behavior**:
- Login: 5 req/min/IP → 429 errors expected at high load
- Register: 3 req/hour/IP → 429 errors expected quickly
- Other endpoints: 100 req/min/IP

**Solution**: Tests simulate multiple IPs (each Locust user = different context)

### 2. Database State
- Tests create many users (can fill database)
- Consider using test database or cleanup script
- Long-running tests may exhaust rate limits

**Solution**: Clear database between test runs or use time-based cleanup

### 3. bcrypt Performance
- Login performance ceiling is ~200ms due to bcrypt
- This is **intentional** for security
- Cannot optimize without compromising security

**Solution**: Accept this limitation, scale horizontally if needed

### 4. Local Testing Limitations
- Single machine tests don't reflect distributed load
- Network latency not representative of production
- Shared resources (DB, Redis) on same machine

**Solution**: For production planning, run tests in staging environment

## References

### Documentation
- [Locust Documentation](https://docs.locust.io/)
- [FastAPI Performance](https://fastapi.tiangolo.com/deployment/performance/)
- [asyncpg Performance Tips](https://magicstack.github.io/asyncpg/current/usage.html#performance)

### Internal Documentation
- `/tests/load/README.md` - Comprehensive testing guide
- `/tests/load/PERFORMANCE_ANALYSIS.md` - Bottleneck analysis
- `/docs/standards/development-workflow.md` - Development standards

## Support

For questions or issues:
1. Review README.md and PERFORMANCE_ANALYSIS.md
2. Check Locust documentation
3. Consult team lead or infrastructure specialist

## Conclusion

The load testing infrastructure is **complete and ready for use**. All test scenarios are implemented, documented, and ready to execute. The performance analysis provides clear expectations and identifies key bottlenecks.

**Recommended Next Step**: Run the quick test to verify everything works, then proceed with the full test sequence.

```bash
# Quick validation (2 minutes)
./tests/load/quick_test.sh

# Full test sequence (30 minutes)
# See "Recommended Test Sequence" section above
```
