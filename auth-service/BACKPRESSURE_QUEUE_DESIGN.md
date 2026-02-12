# Backpressure & Queue-based Traffic Control 설계

**목적**: 시스템 수용 한계 초과 시 요청을 대기시켜 순차적으로 처리하여 시스템 안정성 확보

---

## 📊 현재 시스템 한계 분석

### 1. Connection Pool 기반 임계치

#### Phase 1 수정 전 (현재)
```python
# src/shared/database/connection.py
max_pool_size = 50
avg_query_time = 15ms (Permission 쿼리 포함)
bcrypt_blocking_time = 200ms

# 임계치 계산
동시 처리 가능 요청 = 50 connections
안전 임계치 = 50 × 0.8 = 40 connections  # 80% 활용률
```

**현재 한계**: ~200 RPS (bcrypt 병목)

#### Phase 1 수정 후
```python
max_pool_size = 100
avg_query_time = 5ms (캐시 활용)
bcrypt_async_time = 20ms

# 임계치 계산
동시 처리 가능 요청 = 100 connections
안전 임계치 = 100 × 0.8 = 80 connections
```

**개선 후 한계**: ~1,500 RPS

---

### 2. CPU/Memory 기반 임계치

#### CPU 한계
```python
# 단일 인스턴스 (4 vCPU)
workers = 4
max_concurrent_per_worker = 100  # asyncio tasks

# 총 동시 처리 능력
max_concurrent = 4 × 100 = 400 requests

# 안전 임계치 (70% CPU 사용률 유지)
safe_threshold = 400 × 0.7 = 280 requests
```

#### Memory 한계
```python
# 단일 인스턴스 (4GB RAM)
app_base_memory = 500MB
per_request_memory = 1MB  # JWT decode, permission check 등

# 최대 요청 수
max_requests = (4000MB - 500MB) / 1MB = 3,500 requests

# 안전 임계치 (80% 메모리 사용률)
safe_threshold = 3,500 × 0.8 = 2,800 requests
```

**결론**: DB Connection Pool이 가장 제한적인 요소 (100개)

---

### 3. Response Time 기반 임계치 (권장)

#### SLA 기반 임계치 설정
```python
# SLA 목표
target_p95_latency = 100ms  # 95%의 요청이 100ms 이내

# Little's Law: L = λ × W
# L (동시 요청) = λ (RPS) × W (평균 처리 시간)

# Phase 1 수정 후
avg_processing_time = 50ms = 0.05s
target_rps = 1,500

# 필요한 동시 처리 능력
L = 1,500 × 0.05 = 75 concurrent requests

# 안전 임계치 (버퍼 20%)
safe_threshold = 75 × 1.2 = 90 concurrent requests
```

---

## 🎯 권장 임계치 설정 (환경별)

### Development
```python
QUEUE_CONFIG = {
    "max_concurrent": 20,        # 동시 처리 한계
    "queue_capacity": 100,       # 대기열 최대 크기
    "wait_timeout": 10,          # 대기 타임아웃 (초)
    "reject_threshold": 120,     # 초과 시 즉시 거부
}
```

### Staging
```python
QUEUE_CONFIG = {
    "max_concurrent": 80,
    "queue_capacity": 500,
    "wait_timeout": 5,
    "reject_threshold": 580,
}
```

### Production (per instance)
```python
QUEUE_CONFIG = {
    "max_concurrent": 100,       # DB Pool과 동기화
    "queue_capacity": 1000,      # 10초치 버퍼 (100 RPS 가정)
    "wait_timeout": 3,           # 빠른 실패
    "reject_threshold": 1100,
    "priority_lanes": {
        "critical": 0.3,         # 30%는 중요 요청용
        "normal": 0.6,           # 60%는 일반 요청용
        "bulk": 0.1,             # 10%는 배치 작업용
    }
}
```

---

## 🏗️ 구현 아키텍처

### Option 1: Application-Level Semaphore (권장 - 간단함)

**장점**:
- 구현 간단, 외부 의존성 없음
- 메모리 기반, 빠른 응답

**단점**:
- 인스턴스별 독립 (전역 제어 불가)
- 재시작 시 대기열 손실

#### 구현

```python
# src/shared/middleware/backpressure.py
import asyncio
import time
from typing import Optional
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

class BackpressureMiddleware(BaseHTTPMiddleware):
    """
    시스템 수용 한계를 넘는 요청을 대기열에 추가하고 순차적으로 처리
    """

    def __init__(
        self,
        app,
        max_concurrent: int = 100,
        queue_capacity: int = 1000,
        wait_timeout: int = 3,
        reject_threshold: int = 1100,
    ):
        super().__init__(app)
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.queue_capacity = queue_capacity
        self.wait_timeout = wait_timeout
        self.reject_threshold = reject_threshold

        # 메트릭
        self._current_requests = 0
        self._queued_requests = 0
        self._rejected_requests = 0
        self._total_wait_time = 0.0

    async def dispatch(self, request: Request, call_next):
        # Health check는 bypass
        if request.url.path in ["/health", "/metrics"]:
            return await call_next(request)

        # 즉시 거부 (시스템 완전 과부하)
        total_load = self._current_requests + self._queued_requests
        if total_load >= self.reject_threshold:
            self._rejected_requests += 1
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "success": False,
                    "error": {
                        "code": "SYSTEM_OVERLOAD",
                        "message": "System is overloaded. Please try again later.",
                        "retry_after": 5,  # 5초 후 재시도 권장
                    }
                },
                headers={"Retry-After": "5"},
            )

        # 대기열 초과 (503 반환하되 더 빠른 재시도 권장)
        if self._queued_requests >= self.queue_capacity:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "success": False,
                    "error": {
                        "code": "QUEUE_FULL",
                        "message": "Service is busy. Please retry.",
                        "retry_after": 1,
                    }
                },
                headers={"Retry-After": "1"},
            )

        # 대기열에 추가
        self._queued_requests += 1
        wait_start = time.time()

        try:
            # Semaphore 획득 대기 (timeout 적용)
            async with asyncio.timeout(self.wait_timeout):
                async with self.semaphore:
                    self._queued_requests -= 1
                    self._current_requests += 1

                    wait_time = time.time() - wait_start
                    self._total_wait_time += wait_time

                    # 대기 시간이 길었다면 헤더에 포함
                    response = await call_next(request)
                    if wait_time > 0.1:  # 100ms 이상 대기
                        response.headers["X-Queue-Wait-Time"] = f"{wait_time:.3f}"

                    self._current_requests -= 1
                    return response

        except asyncio.TimeoutError:
            # 대기 타임아웃 - 503 반환
            self._queued_requests -= 1
            self._rejected_requests += 1
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "success": False,
                    "error": {
                        "code": "QUEUE_TIMEOUT",
                        "message": f"Request timed out after {self.wait_timeout}s in queue.",
                        "retry_after": 2,
                    }
                },
                headers={"Retry-After": "2"},
            )

    def get_metrics(self) -> dict:
        """모니터링용 메트릭"""
        return {
            "current_requests": self._current_requests,
            "queued_requests": self._queued_requests,
            "rejected_requests": self._rejected_requests,
            "avg_wait_time": (
                self._total_wait_time / max(1, self._current_requests)
            ),
            "utilization": self._current_requests / self.semaphore._value,
        }
```

#### 적용

```python
# src/main.py
from src.shared.middleware.backpressure import BackpressureMiddleware
from src.shared.config import get_settings

settings = get_settings()

app = FastAPI(title="Auth Service")

# Backpressure Middleware 추가 (가장 먼저)
if settings.enable_backpressure:
    app.add_middleware(
        BackpressureMiddleware,
        max_concurrent=settings.backpressure_max_concurrent,
        queue_capacity=settings.backpressure_queue_capacity,
        wait_timeout=settings.backpressure_wait_timeout,
        reject_threshold=settings.backpressure_reject_threshold,
    )

# 다른 미들웨어들...
app.add_middleware(RateLimiterMiddleware, ...)
```

#### 환경 변수

```bash
# .env.production
ENABLE_BACKPRESSURE=true
BACKPRESSURE_MAX_CONCURRENT=100
BACKPRESSURE_QUEUE_CAPACITY=1000
BACKPRESSURE_WAIT_TIMEOUT=3
BACKPRESSURE_REJECT_THRESHOLD=1100
```

---

### Option 2: Redis-based Queue (권장 - 분산 환경)

**장점**:
- 여러 인스턴스 간 전역 제어
- 재시작 후에도 대기열 유지
- 우선순위 큐 구현 가능

**단점**:
- Redis 의존성 증가
- 약간의 오버헤드

#### 구현

```python
# src/shared/middleware/redis_backpressure.py
import asyncio
import time
import uuid
from typing import Optional
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from redis.asyncio import Redis

class RedisBackpressureMiddleware(BaseHTTPMiddleware):
    """
    Redis 기반 분산 대기열 시스템
    여러 인스턴스가 전역 임계치를 공유
    """

    def __init__(
        self,
        app,
        redis: Redis,
        max_concurrent: int = 300,  # 전체 시스템 기준
        queue_capacity: int = 3000,
        wait_timeout: int = 3,
        instance_id: Optional[str] = None,
    ):
        super().__init__(app)
        self.redis = redis
        self.max_concurrent = max_concurrent
        self.queue_capacity = queue_capacity
        self.wait_timeout = wait_timeout
        self.instance_id = instance_id or str(uuid.uuid4())[:8]

        # Redis 키
        self.active_key = "backpressure:active"
        self.queue_key = "backpressure:queue"
        self.metrics_key = f"backpressure:metrics:{self.instance_id}"

    async def dispatch(self, request: Request, call_next):
        # Health check bypass
        if request.url.path in ["/health", "/metrics"]:
            return await call_next(request)

        request_id = str(uuid.uuid4())
        wait_start = time.time()

        try:
            # 1. 현재 활성 요청 수 확인
            active_count = await self.redis.get(self.active_key)
            active_count = int(active_count) if active_count else 0

            # 2. 대기열 크기 확인
            queue_size = await self.redis.llen(self.queue_key)

            # 3. 즉시 거부 판단
            if active_count + queue_size >= self.max_concurrent + self.queue_capacity:
                await self.redis.hincrby(self.metrics_key, "rejected", 1)
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        "success": False,
                        "error": {
                            "code": "SYSTEM_OVERLOAD",
                            "message": "System capacity exceeded.",
                            "retry_after": 5,
                            "active_requests": active_count,
                            "queue_size": queue_size,
                        }
                    },
                    headers={"Retry-After": "5"},
                )

            # 4. 대기열에 추가
            if active_count >= self.max_concurrent:
                # 대기 필요
                await self.redis.rpush(self.queue_key, request_id)
                await self.redis.hincrby(self.metrics_key, "queued", 1)

                # 폴링으로 순서 대기 (타임아웃 적용)
                timeout_at = time.time() + self.wait_timeout
                while time.time() < timeout_at:
                    # 대기열 선두 확인
                    first_in_queue = await self.redis.lindex(self.queue_key, 0)
                    if first_in_queue == request_id.encode():
                        # 활성 슬롯 확보 시도
                        active = await self.redis.incr(self.active_key)
                        if active <= self.max_concurrent:
                            # 성공 - 대기열에서 제거
                            await self.redis.lpop(self.queue_key)
                            break
                        else:
                            # 실패 - 다시 감소
                            await self.redis.decr(self.active_key)

                    await asyncio.sleep(0.05)  # 50ms 대기
                else:
                    # 타임아웃
                    await self.redis.lrem(self.queue_key, 1, request_id)
                    await self.redis.hincrby(self.metrics_key, "timeout", 1)
                    return JSONResponse(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        content={
                            "success": False,
                            "error": {
                                "code": "QUEUE_TIMEOUT",
                                "message": "Request timed out in queue.",
                                "retry_after": 2,
                            }
                        },
                        headers={"Retry-After": "2"},
                    )
            else:
                # 즉시 처리 가능
                await self.redis.incr(self.active_key)

            # 5. 요청 처리
            wait_time = time.time() - wait_start
            await self.redis.hincrbyfloat(
                self.metrics_key, "total_wait_time", wait_time
            )

            try:
                response = await call_next(request)
                if wait_time > 0.1:
                    response.headers["X-Queue-Wait-Time"] = f"{wait_time:.3f}"
                return response
            finally:
                # 활성 요청 감소
                await self.redis.decr(self.active_key)

        except Exception as e:
            # 오류 발생 시 정리
            await self.redis.lrem(self.queue_key, 1, request_id)
            await self.redis.decr(self.active_key)
            raise

    async def get_metrics(self) -> dict:
        """전역 메트릭 조회"""
        active = await self.redis.get(self.active_key)
        queue_size = await self.redis.llen(self.queue_key)

        metrics = await self.redis.hgetall(self.metrics_key)
        return {
            "active_requests": int(active) if active else 0,
            "queue_size": queue_size,
            "rejected": int(metrics.get(b"rejected", 0)),
            "queued": int(metrics.get(b"queued", 0)),
            "timeout": int(metrics.get(b"timeout", 0)),
            "total_wait_time": float(metrics.get(b"total_wait_time", 0)),
        }
```

---

### Option 3: Priority Queue (VIP 우선 처리)

```python
# src/shared/middleware/priority_backpressure.py
from enum import IntEnum

class RequestPriority(IntEnum):
    CRITICAL = 0   # Health check, 관리자 요청
    HIGH = 1       # 로그인, 토큰 갱신
    NORMAL = 2     # 일반 API
    LOW = 3        # 배치 작업

class PriorityBackpressureMiddleware(BaseHTTPMiddleware):
    """
    우선순위 기반 대기열
    """

    def __init__(self, app, redis: Redis, **config):
        super().__init__(app)
        self.redis = redis
        self.config = config

        # 우선순위별 큐
        self.queue_keys = {
            RequestPriority.CRITICAL: "backpressure:queue:critical",
            RequestPriority.HIGH: "backpressure:queue:high",
            RequestPriority.NORMAL: "backpressure:queue:normal",
            RequestPriority.LOW: "backpressure:queue:low",
        }

    def get_priority(self, request: Request) -> RequestPriority:
        """요청 우선순위 결정"""
        path = request.url.path

        # Critical (항상 처리)
        if path in ["/health", "/metrics"]:
            return RequestPriority.CRITICAL

        # High (인증 관련)
        if path in ["/api/v1/auth/login", "/api/v1/auth/refresh"]:
            return RequestPriority.HIGH

        # Normal (일반 API)
        if request.method in ["GET", "POST", "PUT", "DELETE"]:
            # 관리자는 High로 승격
            if request.headers.get("X-User-Role") == "admin":
                return RequestPriority.HIGH
            return RequestPriority.NORMAL

        # Low (배치, 대량 작업)
        return RequestPriority.LOW

    async def dispatch(self, request: Request, call_next):
        priority = self.get_priority(request)

        # Critical은 bypass
        if priority == RequestPriority.CRITICAL:
            return await call_next(request)

        # 우선순위 큐에 추가 및 처리
        # (구현 로직은 RedisBackpressureMiddleware와 유사하되,
        #  우선순위별로 별도 큐 사용)
        ...
```

#### 우선순위별 할당

```python
PRIORITY_ALLOCATION = {
    "critical": 0.1,   # 10% 슬롯 예약
    "high": 0.4,       # 40% 슬롯
    "normal": 0.4,     # 40% 슬롯
    "low": 0.1,        # 10% 슬롯
}

# 100 슬롯 기준
# Critical: 10개 (항상 사용 가능)
# High: 40개
# Normal: 40개
# Low: 10개 (여유 있을 때만)
```

---

## 📊 모니터링 & 메트릭

### Metrics Endpoint

```python
# src/api/routes/metrics.py
from fastapi import APIRouter, Depends
from src.shared.middleware.backpressure import BackpressureMiddleware

router = APIRouter(prefix="/metrics", tags=["monitoring"])

@router.get("/backpressure")
async def get_backpressure_metrics(
    middleware: BackpressureMiddleware = Depends(get_backpressure_middleware)
):
    """
    Backpressure 시스템 메트릭 조회
    """
    metrics = middleware.get_metrics()
    return {
        "success": True,
        "data": {
            "current_requests": metrics["current_requests"],
            "queued_requests": metrics["queued_requests"],
            "rejected_requests": metrics["rejected_requests"],
            "avg_wait_time_ms": metrics["avg_wait_time"] * 1000,
            "utilization_percent": metrics["utilization"] * 100,
            "status": (
                "healthy" if metrics["utilization"] < 0.7
                else "warning" if metrics["utilization"] < 0.9
                else "critical"
            )
        }
    }
```

### Prometheus 통합

```python
from prometheus_client import Counter, Histogram, Gauge

# 메트릭 정의
backpressure_active_requests = Gauge(
    "backpressure_active_requests",
    "Current number of active requests"
)

backpressure_queued_requests = Gauge(
    "backpressure_queued_requests",
    "Current number of queued requests"
)

backpressure_rejected_total = Counter(
    "backpressure_rejected_total",
    "Total number of rejected requests"
)

backpressure_wait_time = Histogram(
    "backpressure_wait_time_seconds",
    "Time spent waiting in queue",
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 3.0, 5.0]
)

# Middleware에서 업데이트
class BackpressureMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        backpressure_active_requests.set(self._current_requests)
        backpressure_queued_requests.set(self._queued_requests)

        # ... 처리 ...

        backpressure_wait_time.observe(wait_time)
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Backpressure Monitoring",
    "panels": [
      {
        "title": "Active vs Queued Requests",
        "targets": [
          {
            "expr": "backpressure_active_requests",
            "legendFormat": "Active"
          },
          {
            "expr": "backpressure_queued_requests",
            "legendFormat": "Queued"
          }
        ]
      },
      {
        "title": "Queue Wait Time (P95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, backpressure_wait_time_seconds)"
          }
        ]
      },
      {
        "title": "Rejection Rate",
        "targets": [
          {
            "expr": "rate(backpressure_rejected_total[5m])"
          }
        ]
      }
    ]
  }
}
```

---

## 🔔 알림 규칙

```yaml
# alerts/backpressure.yml
groups:
  - name: backpressure
    interval: 30s
    rules:
      # Critical: 거부율 높음
      - alert: HighRejectionRate
        expr: rate(backpressure_rejected_total[5m]) > 10
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High request rejection rate"
          description: "{{ $value }} requests/sec are being rejected"

      # Warning: 대기열 증가
      - alert: QueueBuildup
        expr: backpressure_queued_requests > 500
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Queue is building up"
          description: "{{ $value }} requests waiting in queue"

      # Critical: 대기 시간 초과
      - alert: HighQueueWaitTime
        expr: histogram_quantile(0.95, backpressure_wait_time_seconds) > 1
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "Queue wait time exceeds 1s"
          description: "P95 wait time is {{ $value }}s"

      # Warning: 높은 활용률
      - alert: HighUtilization
        expr: (backpressure_active_requests / 100) > 0.85
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "System utilization above 85%"
          description: "Consider scaling out"
```

---

## 🧪 테스트 시나리오

### Test 1: 정상 부하 (Utilization < 70%)

```python
# tests/load/test_backpressure_normal.py
import asyncio
from locust import HttpUser, task, between

class NormalLoadUser(HttpUser):
    wait_time = between(0.5, 1.5)

    @task
    def login(self):
        self.client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "pass"
        })
```

**실행**:
```bash
locust -f test_backpressure_normal.py \
  --users 70 \
  --spawn-rate 10 \
  --run-time 5m
```

**예상 결과**:
- ✅ 모든 요청 성공 (0% 거부)
- ✅ Queue Wait Time < 10ms
- ✅ Response Time P95 < 100ms

---

### Test 2: 임계치 도달 (Utilization 80-100%)

```bash
locust -f test_backpressure_normal.py \
  --users 120 \
  --spawn-rate 20 \
  --run-time 5m
```

**예상 결과**:
- ✅ 대부분 성공 (< 5% 거부)
- ⚠️ Queue Wait Time 100-500ms
- ⚠️ Response Time P95 200-300ms
- ✅ 시스템 안정 (크래시 없음)

---

### Test 3: 과부하 (Utilization > 150%)

```bash
locust -f test_backpressure_normal.py \
  --users 200 \
  --spawn-rate 50 \
  --run-time 5m
```

**예상 결과**:
- ⚠️ 30-50% 거부 (503 응답)
- ⚠️ Queue Wait Time > 1s (timeout)
- ✅ 시스템 보호 (크래시 없음)
- ✅ 처리된 요청은 정상 응답

---

### Test 4: Spike (급증 트래픽)

```python
# tests/load/test_spike.py
from locust import HttpUser, task, between, events

class SpikeUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def stress(self):
        self.client.get("/api/v1/users/me")

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    # 0 → 500 users in 10 seconds
    pass
```

**예상 결과**:
- ⚠️ 처음 10초: 거부율 증가
- ✅ 10초 이후: 안정화 (큐가 소화)
- ✅ 시스템 복구 (자동 조절)

---

## 💡 Best Practices

### 1. 적절한 임계치 설정

```python
# ❌ 너무 낮음 - 리소스 낭비
max_concurrent = 20  # DB Pool 100인데?

# ❌ 너무 높음 - 보호 효과 없음
max_concurrent = 500  # DB Pool 100인데?

# ✅ 적절 - 가장 제한적인 리소스 기준
max_concurrent = DB_POOL_SIZE × 0.8 = 80
```

### 2. Timeout 설정

```python
# ❌ 너무 길면 - 사용자 경험 나쁨
wait_timeout = 30

# ❌ 너무 짧으면 - 불필요한 거부
wait_timeout = 0.5

# ✅ 적절 - 사용자 인내심 고려
wait_timeout = 3  # 3초면 충분
```

### 3. Graceful Degradation

```python
# 부하에 따라 기능 제한
async def dispatch(self, request: Request, call_next):
    utilization = self._current_requests / self.max_concurrent

    if utilization > 0.9:
        # 90% 이상: 읽기 전용 모드
        if request.method not in ["GET", "HEAD"]:
            return JSONResponse(
                status_code=503,
                content={"error": "Read-only mode due to high load"}
            )

    if utilization > 0.95:
        # 95% 이상: 캐시된 응답만
        cached = await self.get_cached_response(request)
        if cached:
            return cached

    # 정상 처리
    return await call_next(request)
```

### 4. Circuit Breaker 통합

```python
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=60)
async def process_request(request):
    # 연속 5번 실패 시 60초간 차단
    return await call_next(request)
```

---

## 📋 구현 우선순위

### Phase 1: 기본 Semaphore (즉시)

```bash
# 1일 작업
✅ Application-level Semaphore
✅ 503 응답 + Retry-After
✅ 기본 메트릭
```

### Phase 2: Redis Queue (1주일 내)

```bash
# 3일 작업
✅ Redis 기반 분산 대기열
✅ 전역 임계치 제어
✅ Prometheus 메트릭
```

### Phase 3: Priority Queue (1개월 내)

```bash
# 5일 작업
✅ 우선순위 기반 처리
✅ VIP 레인
✅ Graceful Degradation
```

---

## 🎯 기대 효과

### Before (Backpressure 없음)

```
# 과부하 시
├─ RPS: 불안정 (50 ~ 500 fluctuation)
├─ Response Time: 10초+ (timeout)
├─ Error Rate: 80%+ (connection refused)
└─ System: 크래시 위험
```

### After (Backpressure 적용)

```
# 과부하 시
├─ RPS: 안정적 (max 100, 나머지는 503)
├─ Response Time: 100ms (처리된 요청)
├─ Rejection Rate: 50% (503 with Retry-After)
└─ System: 안정 (보호됨)
```

**결론**: 일부 요청은 거부되지만, **시스템은 항상 안정적으로 유지**

---

## 📚 참고 자료

### 유사 사례

1. **AWS API Gateway Throttling**
   - Burst: 5,000 RPS
   - Steady: 10,000 RPS
   - 초과 시: 429 Too Many Requests

2. **Google Cloud Load Balancer**
   - Connection Limits
   - Queue Depth: 1,000
   - Timeout: 30s

3. **Nginx Connection Limiting**
   ```nginx
   limit_conn_zone $binary_remote_addr zone=addr:10m;
   limit_conn addr 10;  # IP당 10 연결
   ```

### Little's Law 활용

```
L = λ × W

L: 평균 동시 요청 수
λ: 평균 RPS
W: 평균 처리 시간 (초)

예시:
1000 RPS × 0.05s = 50 concurrent requests
```

---

## ✅ Checklist

### 구현 전

- [ ] 현재 시스템 한계 측정 (Load Test)
- [ ] DB Connection Pool 크기 확인
- [ ] Redis 용량 계획
- [ ] 모니터링 대시보드 준비

### 구현 중

- [ ] Semaphore 또는 Redis Queue 선택
- [ ] 임계치 설정 (max_concurrent)
- [ ] Timeout 설정 (wait_timeout)
- [ ] 503 응답 포맷 정의
- [ ] 메트릭 수집 구현

### 구현 후

- [ ] Load Test로 검증
- [ ] 알림 규칙 설정
- [ ] 문서화 (Retry 정책)
- [ ] 운영 가이드 작성

---

**작성 날짜**: 2026-02-11
**문서 버전**: 1.0
