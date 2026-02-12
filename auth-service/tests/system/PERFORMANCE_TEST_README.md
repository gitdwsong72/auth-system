# Performance Test Suite Documentation

## Overview

이 문서는 auth-service의 성능 및 부하 테스트 스위트에 대한 가이드입니다.

## Test File

- **파일 위치**: `tests/system/test_performance.py`
- **테스트 프레임워크**: pytest + pytest-asyncio
- **필수 패키지**: psutil (메모리 측정용)

## Test Categories

### 1. TestPerformanceBaseline

단일 요청의 베이스라인 성능을 측정합니다.

#### Test Cases

- `test_health_check_baseline`: Health check 엔드포인트 응답 시간
  - 10회 반복 측정
  - 성능 기준: 평균 < 100ms

- `test_login_baseline`: 로그인 엔드포인트 응답 시간
  - bcrypt 해싱 포함
  - 성능 기준: 평균 < 500ms

### 2. TestConcurrentLoad

동시 요청 처리 능력을 테스트합니다.

#### Test Cases

- `test_concurrent_10_health_checks`: 10개 동시 요청
  - 성능 기준: 에러율 < 5%, P95 < 200ms

- `test_concurrent_50_health_checks`: 50개 동시 요청
  - 성능 기준: 에러율 < 10%, P95 < 500ms

- `test_concurrent_10_authenticated_requests`: 10개 동시 인증 요청
  - JWT 검증 포함
  - 성능 기준: 에러율 < 5%, P95 < 300ms

### 3. TestSolidCachePerformance

Solid Cache의 성능 특성을 측정합니다.

#### Test Cases

- `test_cache_hit_vs_miss_performance`: 캐시 히트 vs 미스 비교
  - 캐시 히트가 미스보다 빠르거나 비슷해야 함
  - Speed improvement 측정

- `test_cache_json_performance`: JSON 캐시 성능
  - Set + Get 연속 작업
  - 성능 기준: 평균 < 50ms per operation

### 4. TestMemoryUsage

메모리 사용량을 모니터링합니다.

#### Test Cases

- `test_memory_usage_under_load`: 부하 상황 메모리 사용
  - 100개 동시 요청 실행
  - 성능 기준: 메모리 증가 < 100MB

- `test_cache_memory_growth`: 캐시 메모리 증가량
  - 1000개 캐시 엔트리 생성
  - 성능 기준: 메모리 증가 < 50MB

### 5. TestRateLimiterPerformance

Rate Limiter의 오버헤드를 측정합니다.

#### Test Cases

- `test_rate_limiter_overhead`: Rate Limiter 오버헤드
  - 10회 연속 요청
  - 성능 기준: 평균 < 150ms

## Metrics Collected

각 테스트는 다음 메트릭을 수집합니다:

- **total_requests**: 전체 요청 수
- **successful_requests**: 성공한 요청 수 (2xx)
- **failed_requests**: 실패한 요청 수
- **error_rate**: 에러율 (%)
- **avg_response_time_ms**: 평균 응답 시간 (ms)
- **min_response_time_ms**: 최소 응답 시간 (ms)
- **max_response_time_ms**: 최대 응답 시간 (ms)
- **median_response_time_ms**: 중앙값 응답 시간 (ms)
- **p95_response_time_ms**: 95 percentile 응답 시간 (ms)
- **p99_response_time_ms**: 99 percentile 응답 시간 (ms)
- **requests_per_second**: 초당 요청 수 (RPS)
- **total_duration_s**: 전체 실행 시간 (초)

## Running Tests

### 전체 성능 테스트 실행

```bash
pytest tests/system/test_performance.py -v -s
```

### 특정 테스트 클래스 실행

```bash
# Baseline 테스트만
pytest tests/system/test_performance.py::TestPerformanceBaseline -v -s

# Concurrent load 테스트만
pytest tests/system/test_performance.py::TestConcurrentLoad -v -s

# Cache 성능 테스트만
pytest tests/system/test_performance.py::TestSolidCachePerformance -v -s

# 메모리 테스트만
pytest tests/system/test_performance.py::TestMemoryUsage -v -s
```

### 특정 테스트 케이스 실행

```bash
pytest tests/system/test_performance.py::TestPerformanceBaseline::test_health_check_baseline -v -s
```

### 출력 형식

각 테스트는 상세한 성능 메트릭을 출력합니다:

```
=== Health Check Baseline ===
Total Requests: 10
Success Rate: 100.0%
Avg Response Time: 23.45 ms
Min/Max: 18.23/31.56 ms
Median: 22.89 ms
```

## Performance Baselines

### Expected Performance Thresholds

| Endpoint | Metric | Threshold |
|----------|--------|-----------|
| Health Check | Avg Response | < 100ms |
| Login | Avg Response | < 500ms |
| Authenticated API | P95 Response | < 300ms |
| Concurrent 10 | Error Rate | < 5% |
| Concurrent 50 | Error Rate | < 10% |
| Cache Hit/Miss | Hit <= Miss * 1.5 | - |
| JSON Cache | Avg per Operation | < 50ms |
| Memory (100 req) | Memory Increase | < 100MB |
| Memory (1000 cache) | Memory Increase | < 50MB |
| Rate Limiter | Avg Response | < 150ms |

## Dependencies

### Required Packages

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "psutil>=5.9.0",  # For memory monitoring
    "httpx>=0.27.0",
]
```

### Installation

```bash
pip install -e ".[dev]"
```

## Test Environment

- **Database**: PostgreSQL (localhost:5433)
- **Redis**: Redis (localhost:6380)
- **Environment**: development (ENV=development)
- **Config**: `.env.test`

## Implementation Details

### PerformanceMetrics Class

성능 메트릭 수집 및 계산을 담당하는 유틸리티 클래스:

```python
metrics = PerformanceMetrics()
metrics.start_timer()

# Record requests
metrics.record_request(duration, status_code, error)

metrics.stop_timer()
stats = metrics.calculate_stats()
```

### Concurrent Test Pattern

```python
async def make_request():
    start = time.time()
    try:
        response = await client.get("/endpoint")
        duration = time.time() - start
        metrics.record_request(duration, response.status_code)
    except Exception as e:
        metrics.record_request(duration, 500, str(e))

# Run concurrent requests
tasks = [make_request() for _ in range(N)]
await asyncio.gather(*tasks)
```

### Memory Monitoring

```python
import psutil

process = psutil.Process()
initial_memory = process.memory_info().rss / 1024 / 1024  # MB

# ... run operations ...

final_memory = process.memory_info().rss / 1024 / 1024
memory_increase = final_memory - initial_memory
```

## Troubleshooting

### Test Timeout

일부 성능 테스트는 오래 걸릴 수 있습니다. 타임아웃을 늘리려면:

```bash
pytest tests/system/test_performance.py --timeout=300
```

### Database Connection Issues

테스트 실행 전 데이터베이스와 Redis가 실행 중인지 확인:

```bash
docker-compose up -d postgres redis
```

### Memory Test Failures

시스템 메모리가 부족하면 메모리 테스트가 실패할 수 있습니다.
다른 프로세스를 종료하거나 임계값을 조정하세요.

## Best Practices

1. **테스트 격리**: 각 테스트는 독립적으로 실행 가능해야 함
2. **캐시 정리**: 캐시 테스트 후 정리 코드 실행
3. **타임아웃 설정**: 긴 실행 시간 고려
4. **통계 수집**: 평균뿐만 아니라 P95, P99도 확인
5. **에러 처리**: Exception을 catch하여 메트릭에 기록

## Future Enhancements

- [ ] Locust를 활용한 실제 부하 테스트 스크립트
- [ ] 시계열 성능 데이터 수집 및 시각화
- [ ] CI/CD 파이프라인 통합 (성능 회귀 감지)
- [ ] 다양한 부하 패턴 (spike, ramp-up, sustained)
- [ ] Database connection pool 메트릭 모니터링
- [ ] 네트워크 레이턴시 시뮬레이션

## References

- [Solid Cache by 37signals](https://github.com/rails/solid_cache)
- [psutil Documentation](https://psutil.readthedocs.io/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
