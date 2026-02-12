# Load Testing Guide for Auth System

## Overview

This directory contains load testing scenarios using Locust to measure performance, identify bottlenecks, and establish capacity limits for the authentication system.

## Installation

```bash
# Install Locust
pip install locust

# Or add to requirements-dev.txt
echo "locust>=2.20.0" >> requirements-dev.txt
pip install -r requirements-dev.txt
```

## Test Scenarios

### 1. AuthSystemUser (Default)
**Purpose**: Realistic user behavior simulation

**User Journey**:
- Register new account
- Login and maintain session
- Regularly check profile (most common)
- Periodically refresh tokens
- Occasionally check sessions
- Rarely update profile

**Task Weights**:
- `get_user_profile`: 10 (most frequent)
- `refresh_access_token`: 5
- `get_sessions`: 2
- `update_profile`: 1

**Use Case**: General capacity planning, mixed workload testing

### 2. LoginHeavyUser
**Purpose**: Authentication-focused stress testing

**User Journey**:
- Frequent login/logout cycles
- Immediate profile checks after login
- Session management operations

**Task Weights**:
- `login`: 10 (CPU-intensive bcrypt operations)
- `logout`: 3
- `get_profile_after_login`: 2

**Use Case**:
- Test bcrypt password hashing performance under load
- Identify authentication bottlenecks
- Redis token blacklist performance

### 3. RegistrationStressUser
**Purpose**: New user registration load

**Behavior**:
- Continuous new user creation
- Unique constraint validation stress
- Database write-heavy operations

**Use Case**:
- Marketing campaign simulations
- Bot registration defense testing
- Database write capacity measurement

### 4. TokenRefreshHeavyUser
**Purpose**: Token refresh operations stress

**Behavior**:
- Aggressive token refresh cycles (0.5-1.5s intervals)
- Continuous JWT generation/validation
- Redis cache stress

**Use Case**:
- Long-running session support testing
- Redis performance under refresh load
- JWT generation bottleneck identification

## Running Tests

### Quick Start
```bash
# Start auth service first
cd /Users/sktl/WF/WF01/auth-system/auth-service
uvicorn src.main:app --reload --port 8000

# In another terminal, run basic load test
locust -f tests/load/locustfile.py --host=http://localhost:8000
```

Then open http://localhost:8089 in your browser to control the test.

### Command Line Examples

#### Light Load (Development Testing)
```bash
locust -f tests/load/locustfile.py \
  --host=http://localhost:8000 \
  --users 10 \
  --spawn-rate 1 \
  --run-time 2m
```

#### Medium Load (Realistic Scenario)
```bash
locust -f tests/load/locustfile.py \
  --host=http://localhost:8000 \
  --users 50 \
  --spawn-rate 5 \
  --run-time 5m \
  --html reports/medium_load.html
```

#### Stress Test (Find Limits)
```bash
locust -f tests/load/locustfile.py \
  --host=http://localhost:8000 \
  --users 200 \
  --spawn-rate 10 \
  --run-time 10m \
  --html reports/stress_test.html
```

#### Spike Test (Sudden Traffic)
```bash
locust -f tests/load/locustfile.py \
  --host=http://localhost:8000 \
  --users 100 \
  --spawn-rate 20 \
  --run-time 3m
```

### Scenario-Specific Tests

#### Test Login Performance
```bash
locust -f tests/load/locustfile.py \
  LoginHeavyUser \
  --host=http://localhost:8000 \
  --users 30 \
  --spawn-rate 5 \
  --run-time 5m
```

#### Test Registration Capacity
```bash
locust -f tests/load/locustfile.py \
  RegistrationStressUser \
  --host=http://localhost:8000 \
  --users 20 \
  --spawn-rate 2 \
  --run-time 3m
```

#### Test Token Refresh Performance
```bash
locust -f tests/load/locustfile.py \
  TokenRefreshHeavyUser \
  --host=http://localhost:8000 \
  --users 50 \
  --spawn-rate 5 \
  --run-time 5m
```

## Performance Targets

### Response Time Targets (95th percentile)

| Endpoint | Target | Acceptable | Critical |
|----------|--------|------------|----------|
| POST /auth/login | < 200ms | < 500ms | > 1000ms |
| POST /auth/refresh | < 50ms | < 100ms | > 200ms |
| GET /users/me | < 50ms | < 100ms | > 200ms |
| POST /users/register | < 300ms | < 600ms | > 1200ms |
| POST /auth/logout | < 100ms | < 200ms | > 400ms |
| GET /auth/sessions | < 100ms | < 200ms | > 400ms |

### Throughput Targets

| Scenario | Expected RPS | Target RPS | Max RPS |
|----------|--------------|------------|---------|
| Mixed workload | 50-100 | 200 | 500+ |
| Login-heavy | 20-50 | 100 | 200+ |
| Token refresh | 100-200 | 500 | 1000+ |
| Registration | 5-10 | 20 | 50+ |

### Resource Limits (Single Instance)

| Resource | Development | Production |
|----------|-------------|------------|
| CPU Cores | 2-4 | 4-8 |
| RAM | 2GB | 4-8GB |
| Concurrent Users | 100 | 500-1000 |
| DB Connections | 10-20 | 50-100 |
| Redis Memory | 256MB | 1-2GB |

## Monitoring During Tests

### Key Metrics to Watch

1. **Response Times**
   - Median (P50)
   - 95th percentile (P95)
   - 99th percentile (P99)

2. **Error Rate**
   - Target: < 0.1%
   - Acceptable: < 1%
   - Critical: > 5%

3. **System Resources**
   - CPU utilization
   - Memory usage
   - Database connection pool
   - Redis memory/connections

4. **Rate Limiting**
   - 429 error rate
   - Expected for excessive load scenarios

### Check System Resources During Test

```bash
# CPU and Memory
top -pid $(pgrep -f "uvicorn")

# PostgreSQL connections
psql -h localhost -p 5433 -U postgres -c "SELECT count(*) FROM pg_stat_activity WHERE datname='auth_db';"

# Redis memory
redis-cli -p 6380 INFO memory
redis-cli -p 6380 INFO stats
```

## Known Bottlenecks

### 1. Password Hashing (bcrypt)
- **Impact**: Login endpoint, 100-200ms per request
- **Mitigation**: Accept slower login for security, consider rate limiting
- **Scale Strategy**: Horizontal scaling, dedicated auth workers

### 2. Database Connection Pool
- **Impact**: All endpoints under heavy load
- **Current Limit**: Default asyncpg pool (10 connections)
- **Mitigation**: Tune pool size based on load test results

### 3. Redis Operations
- **Impact**: Token refresh, logout, session management
- **Single-threaded nature**: Can become bottleneck at high RPS
- **Mitigation**: Connection pooling, Redis clustering for scale

### 4. Rate Limiting
- **By Design**: Intentional throttling
- **Login**: 5 requests/minute/IP
- **Register**: 3 requests/hour/IP
- **Refresh**: 10 requests/minute/IP

## Test Reports

Reports are saved to `tests/load/reports/` directory with timestamps.

### Analyzing Results

1. **Response Time Distribution**: Should be tight, minimal variance
2. **Failure Rate**: Should be < 1% under normal load
3. **RPS Growth**: Should scale linearly with user count until bottleneck
4. **Resource Usage**: CPU should plateau before memory issues

### Red Flags

- P95 response time > 1s for read operations
- Error rate > 1% under target load
- CPU at 100% with low RPS (inefficient code)
- Memory leaks (gradual increase without plateau)
- Connection pool exhaustion

## Interpreting Rate Limit Errors

429 errors are **expected** under these conditions:
- Login: > 5 requests/minute from same IP
- Register: > 3 requests/hour from same IP
- Default APIs: > 100 requests/minute from same IP

If you see 429s:
1. Check if it's from rate limiting (expected) or overload (problem)
2. Review X-RateLimit-* headers in responses
3. Adjust Locust wait_time if testing legitimate load

## Continuous Load Testing

### Pre-Deployment Checklist

```bash
# 1. Run baseline test
locust -f tests/load/locustfile.py \
  --host=http://localhost:8000 \
  --users 50 \
  --spawn-rate 5 \
  --run-time 5m \
  --html reports/baseline_$(date +%Y%m%d_%H%M%S).html \
  --headless

# 2. Run stress test
locust -f tests/load/locustfile.py \
  --host=http://localhost:8000 \
  --users 200 \
  --spawn-rate 10 \
  --run-time 3m \
  --html reports/stress_$(date +%Y%m%d_%H%M%S).html \
  --headless

# 3. Compare with previous results
# Ensure no regression in P95 response times
```

## CI/CD Integration

Example GitHub Actions workflow:

```yaml
name: Load Test

on:
  push:
    branches: [develop]

jobs:
  load-test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: auth_db
          POSTGRES_PASSWORD: postgres
        ports:
          - 5433:5432

      redis:
        image: redis:7-alpine
        ports:
          - 6380:6379

    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install locust

      - name: Start auth service
        run: uvicorn src.main:app --host 0.0.0.0 --port 8000 &

      - name: Wait for service
        run: sleep 10

      - name: Run load test
        run: |
          locust -f tests/load/locustfile.py \
            --host=http://localhost:8000 \
            --users 20 \
            --spawn-rate 2 \
            --run-time 2m \
            --headless \
            --html load_test_report.html

      - name: Upload report
        uses: actions/upload-artifact@v3
        with:
          name: load-test-report
          path: load_test_report.html
```

## Next Steps

1. **Establish Baseline**: Run initial tests to establish current performance
2. **Identify Bottlenecks**: Use profiling tools (py-spy, cProfile) during load tests
3. **Optimize**: Address identified bottlenecks
4. **Re-test**: Verify improvements with load tests
5. **Document**: Update this README with actual performance data
6. **Monitor Production**: Use similar metrics in production monitoring
