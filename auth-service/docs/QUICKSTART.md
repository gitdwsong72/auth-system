# Solid Cache 빠른 시작 가이드

## 🚀 한 번에 시작하기

```bash
cd /Users/sktl/WF/WF01/auth-system/auth-service

# FastAPI + tmux 모니터링 동시 시작
./scripts/start-with-monitor.sh
```

이 명령어 하나로:
1. ✅ 기존 FastAPI 프로세스 종료
2. ✅ FastAPI 백그라운드 시작
3. ✅ Health Check 대기
4. ✅ tmux 모니터링 자동 시작

---

## 📊 tmux 모니터링 레이아웃

```
┌─────────────────────┬─────────────────────┐
│  FastAPI Logs       │  Solid Cache Stats  │
│  (실시간 로그)       │  (5초 갱신)         │
├─────────────────────┼─────────────────────┤
│  Redis Status       │  Health Check       │
│  (5초 갱신)         │  (10초 갱신)        │
└─────────────────────┴─────────────────────┘
```

### tmux 기본 단축키

| 키 | 기능 |
|---|------|
| `Ctrl+B, D` | Detach (백그라운드로) |
| `Ctrl+B, 화살표` | Pane 이동 |
| `Ctrl+B, [` | 스크롤 모드 (q로 종료) |
| `Ctrl+B, z` | 현재 pane 최대화/복원 |

---

## 📝 개별 실행

### FastAPI만 시작
```bash
.venv/bin/uvicorn src.main:app --port 8001 --reload
```

### 모니터링만 시작 (FastAPI 이미 실행 중)
```bash
./scripts/monitor.sh
```

### 커스텀 세션명
```bash
./scripts/monitor.sh my-custom-session
```

---

## 🔍 수동 확인

### Health Check
```bash
curl http://localhost:8001/health | jq
```

### Solid Cache 통계
```bash
curl http://localhost:8001/metrics/solid-cache | jq
```

### PostgreSQL 직접 확인
```bash
PGPASSWORD=devpassword psql -h localhost -p 5433 -U devuser -d appdb -c \
  "SELECT COUNT(*) as total,
   COUNT(*) FILTER (WHERE expires_at < NOW()) as expired,
   pg_size_pretty(pg_total_relation_size('solid_cache_entries')) as size
   FROM solid_cache_entries;"
```

---

## 🎯 주요 로그 확인

### Solid Cache 초기화 확인
```bash
grep "solid_cache_initialized" /tmp/fastapi.log
```

**기대 출력**:
```
[info] solid_cache_initialized - message='Solid Cache singleton initialized'
```

### Cleanup 실행 확인
```bash
grep "cache_cleanup" /tmp/fastapi.log | tail -5
```

**기대 출력**:
```
[info] cache_cleanup_started - interval_seconds=3600
[info] cache_cleanup_executed - deleted_count=0
```

---

## 🧪 간단한 테스트

### 1. 캐시 저장 테스트
```python
from src.shared.database import get_solid_cache

solid_cache = get_solid_cache()

# 캐시 저장
await solid_cache.set_json("test_key", {"hello": "world"}, ttl_seconds=60)

# 캐시 조회
data = await solid_cache.get_json("test_key")
print(data)  # {"hello": "world"}
```

### 2. 사용자 프로필 캐싱 테스트
```bash
# 1. 사용자 조회 (캐시 미스 → DB 조회)
curl http://localhost:8001/api/v1/users/1

# 2. 다시 조회 (캐시 히트 → 빠름)
curl http://localhost:8001/api/v1/users/1

# 3. PostgreSQL에서 캐시 확인
PGPASSWORD=devpassword psql -h localhost -p 5433 -U devuser -d appdb -c \
  "SELECT key, expires_at FROM solid_cache_entries WHERE key LIKE 'user_profile:%';"
```

---

## 🛠️ 문제 해결

### FastAPI가 시작되지 않음
```bash
# 로그 확인
tail -50 /tmp/fastapi.log

# 포트 충돌 확인
lsof -i:8001

# 강제 종료
lsof -ti:8001 | xargs kill -9
```

### tmux 세션이 이미 존재
```bash
# 기존 세션 종료
tmux kill-session -t auth-monitor

# 또는 attach하여 수동 종료
tmux attach -t auth-monitor
# 그 다음 Ctrl+B, D로 detach 또는 exit로 종료
```

### PostgreSQL 연결 실패
```bash
# PostgreSQL 상태 확인
docker ps | grep postgres

# 연결 테스트
PGPASSWORD=devpassword psql -h localhost -p 5433 -U devuser -d appdb -c "SELECT 1;"
```

---

## 📚 추가 문서

- **전체 가이드**: `docs/solid-cache-guide.md`
- **리팩토링 요약**: `docs/refactoring-summary.md`
- **구현 요약**: `docs/solid-cache-implementation-summary.md`
- **검증 스크립트**: `scripts/verify_solid_cache.py`

---

## 🎉 완료 체크리스트

- [ ] FastAPI 정상 시작 (`http://localhost:8001/health`)
- [ ] tmux 모니터링 실행
- [ ] Solid Cache 초기화 로그 확인
- [ ] Health Check에서 `solid_cache: healthy` 확인
- [ ] Cleanup 백그라운드 태스크 시작 로그 확인

모든 항목이 체크되면 성공! 🚀
