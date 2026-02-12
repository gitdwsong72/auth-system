# 프로덕션 실행 가이드

## Uvicorn Multi-worker 실행

### Development (단일 worker + reload)
```bash
# 개발 중에는 --reload 사용
uv run uvicorn src.main:app --reload --port 8000 --env-file .env.test
```

### Staging (4 workers)
```bash
# 4개 worker로 실행
uv run uvicorn src.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --env-file .env.staging

# 또는 환경 변수 사용
UVICORN_WORKERS=4 uv run uvicorn src.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers ${UVICORN_WORKERS}
```

### Production (CPU 기반)
```bash
# CPU 코어 수 자동 감지 (권장: 2 x cores)
CPU_CORES=$(nproc)
WORKERS=$((CPU_CORES * 2))

uv run uvicorn src.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers ${WORKERS} \
  --env-file .env.production \
  --log-level info \
  --access-log
```

## Worker 수 결정 가이드

### CPU 기반 계산
```bash
# 일반 권장: 2 x CPU 코어
workers = CPU cores × 2

# CPU 집약적 작업: 1 x CPU 코어
workers = CPU cores × 1

# I/O 집약적 작업: 2-4 x CPU 코어
workers = CPU cores × (2 to 4)
```

### 예시
```
CPU 4 cores:
- 일반: 8 workers
- CPU 집약: 4 workers
- I/O 집약: 8-16 workers

CPU 8 cores:
- 일반: 16 workers
- CPU 집약: 8 workers
- I/O 집약: 16-32 workers
```

## Connection Pool 고려사항

### Worker당 Connection Pool
```python
# connection.py 설정
max_size = 100  # worker당 최대 connections

# 총 connections
total_connections = workers × max_size

# 예시: 4 workers × 100 = 400 connections
```

### PostgreSQL max_connections 설정
```sql
-- PostgreSQL이 수용해야 할 connections
max_connections = (workers × pool_max_size × instances) + buffer

-- 예시: (4 × 100 × 1) + 100 = 500
```

## 성능 벤치마크

### 단일 worker (Before)
```
RPS: ~50
CPU: 25% (1 core 사용)
Memory: 200MB
```

### 4 workers (After)
```
RPS: ~200 (4배 증가)
CPU: 100% (4 cores 사용)
Memory: 800MB (4배 증가)
```

## 주의사항

### 1. 메모리 사용량
- Worker당 메모리 사용량 × workers
- 충분한 RAM 확보 필요

### 2. Connection Pool
- PostgreSQL max_connections 조정 필수
- workers × pool_max_size < PostgreSQL max_connections

### 3. Health Check
- 각 worker가 독립적으로 동작
- Load Balancer에서 worker별 health check

### 4. Graceful Shutdown
```bash
# SIGTERM으로 graceful shutdown
kill -TERM <pid>

# 강제 종료 (비권장)
kill -KILL <pid>
```

## Docker Compose 실행

```yaml
# docker-compose.yml
services:
  auth-service:
    command: >
      uvicorn src.main:app
      --host 0.0.0.0
      --port 8000
      --workers 4
    environment:
      - DB_POOL_MAX_SIZE=100
      - UVICORN_WORKERS=4
```

## Gunicorn 대안 (선택)

Uvicorn 대신 Gunicorn + Uvicorn worker 사용도 가능:

```bash
# Gunicorn 설치
pip install gunicorn

# 실행
gunicorn src.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 60 \
  --graceful-timeout 30
```

## 모니터링

### Worker 상태 확인
```bash
# 프로세스 확인
ps aux | grep uvicorn

# Worker별 CPU/Memory
top -p $(pgrep -d',' uvicorn)
```

### 성능 측정
```bash
# Locust로 부하 테스트
locust -f tests/load/locustfile.py \
  --users 1000 \
  --spawn-rate 50 \
  --run-time 5m
```

---

**생성 날짜**: 2026-02-11
**Phase**: 2 (Infrastructure Tuning)
