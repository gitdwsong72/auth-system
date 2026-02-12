# 🚀 CI/CD 자동화 설정 가이드

이 문서는 Auth System의 CI/CD 파이프라인 설정 방법을 설명합니다.

## 📋 목차

1. [Pre-commit Hooks 설정](#1-pre-commit-hooks-설정)
2. [GitHub Actions 설정](#2-github-actions-설정)
3. [보안 스캔](#3-보안-스캔)
4. [커버리지 목표](#4-커버리지-목표)
5. [배포 전략](#5-배포-전략)
6. [성능 테스트](#6-성능-테스트)
7. [모니터링](#7-모니터링)

---

## 1. Pre-commit Hooks 설정

### 설치

```bash
cd auth-service

# Pre-commit 설치
pip install pre-commit

# Hooks 활성화
pre-commit install

# 수동 실행 (모든 파일)
pre-commit run --all-files
```

### 실행 단계

Pre-commit은 커밋 전에 자동으로 다음을 실행합니다:

1. **Ruff Linting** - 코드 스타일 검사 및 자동 수정
2. **Ruff Formatting** - 코드 포맷팅
3. **MyPy** - 타입 체킹
4. **Bandit** - 보안 취약점 스캔
5. **Trailing Whitespace** - 공백 제거
6. **Fast Unit Tests** - 빠른 단위 테스트 (선택)

### 성능 최적화

테스트가 느리면 `.pre-commit-config.yaml`에서 `pytest-fast` 훅을 주석 처리:

```yaml
# - repo: local
#   hooks:
#     - id: pytest-fast
#       ...
```

---

## 2. GitHub Actions 설정

### 필요한 Secrets

GitHub 저장소 Settings → Secrets and variables → Actions에서 설정:

```
# 필수
GITHUB_TOKEN (자동 제공)

# 배포용 (선택)
KUBE_CONFIG          # Kubernetes 설정
DOCKER_REGISTRY_USER # Docker 레지스트리 사용자
DOCKER_REGISTRY_PASS # Docker 레지스트리 비밀번호
SLACK_WEBHOOK_URL    # 알림용
```

### 워크플로우 구조

```
.github/workflows/
├── ci.yml           # PR & Push 자동 실행
│   ├── 1. Lint & Format Check
│   ├── 2. Type Check (MyPy)
│   ├── 3. Security Scan (Bandit + Trivy)
│   ├── 4. Unit Tests (80%+ coverage)
│   ├── 5. Integration Tests (PostgreSQL + Redis)
│   ├── 6. Build Docker Image
│   └── 7. CI Success Check
│
├── cd.yml           # 배포 (main/tags)
│   ├── 1. Build & Push Image
│   ├── 2. Deploy to Staging
│   ├── 3. Deploy to Production (Manual Approval)
│   └── 4. Rollback (on failure)
│
└── performance.yml  # 성능 테스트 (스케줄)
    ├── Load Testing (Locust)
    └── System Performance Tests
```

### Branch Protection Rules

GitHub 저장소 Settings → Branches에서 설정:

**main/master 브랜치 보호:**
- ✅ Require status checks before merging
  - ✅ `CI Pipeline Success` (필수)
- ✅ Require pull request reviews (1명 이상)
- ✅ Require conversation resolution before merging
- ✅ Do not allow bypassing the above settings

---

## 3. 보안 스캔

### 3.1 Bandit (SAST - Static Application Security Testing)

**검사 항목:**
- SQL Injection
- XSS (Cross-Site Scripting)
- 하드코딩된 비밀번호
- 약한 암호화
- 안전하지 않은 함수 사용

**로컬 실행:**
```bash
cd auth-service
pip install bandit[toml]
bandit -c pyproject.toml -r src/ -f screen
```

### 3.2 Trivy (Container Security)

**검사 항목:**
- OS 패키지 취약점 (CVE)
- Python 패키지 취약점
- 설정 오류
- 비밀 누출

**로컬 실행:**
```bash
# Docker 이미지 빌드
docker build -t auth-service:test ./auth-service

# Trivy 스캔
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image auth-service:test
```

### 3.3 Dependency Scanning

GitHub의 Dependabot이 자동으로 취약한 의존성을 감지하고 PR을 생성합니다.

**활성화:**
- GitHub Settings → Security → Dependabot alerts ✅
- GitHub Settings → Security → Dependabot security updates ✅

---

## 4. 커버리지 목표

### 목표: **80%+**

**현재 커버리지:**
- 핵심 모듈 (JWT, Password, Redis): **90%+** ✅
- 도메인 서비스: **70-90%** ⚠️
- OAuth/MFA/API Keys: **0%** ❌ (미구현 기능)

### 커버리지 확인

```bash
cd auth-service

# Unit tests with coverage
pytest tests/unit/ --cov=src --cov-report=html --cov-report=term-missing

# Integration tests (append to coverage)
pytest tests/integration/ --cov=src --cov-append --cov-report=html

# Open HTML report
open htmlcov/index.html
```

### 커버리지 실패 시

CI가 실패하면 다음을 확인:

```bash
# 커버리지가 낮은 파일 확인
coverage report --show-missing --skip-covered

# 특정 파일만 커버리지 확인
pytest tests/ --cov=src/domains/authentication --cov-report=term-missing
```

---

## 5. 배포 전략

### 5.1 Git 브랜치 전략

```
main/master (프로덕션)
  ↑
  PR + Review + CI Pass
  ↑
develop (스테이징)
  ↑
  PR + CI Pass
  ↑
feature/SKTL-XXXX (개발)
```

### 5.2 환경별 배포

| 환경 | 트리거 | 승인 | URL |
|------|--------|------|-----|
| **Staging** | Push to `develop` | 자동 | staging-auth.your-domain.com |
| **Production** | Tag `v*.*.*` | 수동 승인 필요 | auth.your-domain.com |

### 5.3 배포 프로세스

**스테이징 배포 (자동):**
```bash
git checkout develop
git merge feature/SKTL-1234
git push origin develop
# GitHub Actions가 자동으로 staging에 배포
```

**프로덕션 배포 (수동 승인):**
```bash
# 1. 버전 태그 생성
git tag v1.2.3
git push origin v1.2.3

# 2. GitHub Actions에서 승인 대기
#    (Settings → Environments → production → Required reviewers)

# 3. 승인 후 자동 배포
```

### 5.4 롤백

**자동 롤백:**
- Health check 실패 시 자동 롤백

**수동 롤백:**
```bash
# Kubernetes (예시)
kubectl rollout undo deployment/auth-service -n production

# 또는 이전 태그로 재배포
git tag v1.2.2  # 이전 버전
git push origin v1.2.2 --force
```

---

## 6. 성능 테스트

### 6.1 자동 성능 테스트

**스케줄:** 매일 오전 2시 (UTC)

**성능 기준:**
- Login: P95 < 200ms
- Token Refresh: P95 < 50ms
- Profile API: P95 < 50ms
- RPS: 100+ req/sec

### 6.2 수동 성능 테스트

```bash
cd auth-service/tests/load

# Locust UI 실행
locust --host http://localhost:8000

# 브라우저에서 http://localhost:8089 열기
# Users: 100, Spawn rate: 10

# 또는 Headless 모드
locust \
  --host http://localhost:8000 \
  --users 100 \
  --spawn-rate 10 \
  --run-time 60s \
  --headless \
  --html=report.html
```

### 6.3 성능 회귀 감지

**Baseline 저장:**
```bash
# 현재 성능을 baseline으로 저장
pytest tests/system/test_performance.py \
  --benchmark-save=baseline

# 새 성능과 비교
pytest tests/system/test_performance.py \
  --benchmark-compare=baseline \
  --benchmark-compare-fail=mean:10%  # 10% 이상 느려지면 실패
```

---

## 7. 모니터링

### 7.1 GitHub Actions 모니터링

**체크리스트:**
- ✅ CI 파이프라인 성공률 > 95%
- ✅ 평균 CI 실행 시간 < 10분
- ✅ 커버리지 추세 (80%+ 유지)
- ✅ 보안 취약점 0건

**확인 방법:**
```
GitHub → Actions → 성공/실패 통계 확인
```

### 7.2 Codecov (Coverage Tracking)

**설정:**
1. https://codecov.io 가입
2. GitHub 저장소 연결
3. `CODECOV_TOKEN` Secret 추가 (private repo만)

**기능:**
- PR마다 커버리지 변화 표시
- 커버리지 감소 시 경고
- 커버리지 배지 생성

### 7.3 알림 설정

**Slack 알림 (선택):**
```yaml
# .github/workflows/ci.yml에 추가
- name: Notify Slack
  if: failure()
  uses: slackapi/slack-github-action@v1
  with:
    webhook: ${{ secrets.SLACK_WEBHOOK_URL }}
    payload: |
      {
        "text": "❌ CI Pipeline failed for ${{ github.repository }}"
      }
```

---

## 🚦 체크리스트

### 초기 설정 (1회)

- [ ] Pre-commit hooks 설치 (`pre-commit install`)
- [ ] GitHub Secrets 설정 (필요시)
- [ ] Branch protection rules 설정
- [ ] Dependabot 활성화
- [ ] Codecov 연결 (선택)

### PR 생성 시

- [ ] Pre-commit hooks 통과
- [ ] 로컬 테스트 통과 (`pytest`)
- [ ] CI 파이프라인 통과 (자동)
- [ ] 커버리지 80%+ 유지
- [ ] 리뷰어 승인

### 프로덕션 배포 시

- [ ] 스테이징 테스트 완료
- [ ] 성능 테스트 통과
- [ ] 보안 스캔 통과
- [ ] 버전 태그 생성
- [ ] 수동 승인 (production)
- [ ] 배포 후 Health check

---

## 📚 참고 자료

- [GitHub Actions 문서](https://docs.github.com/en/actions)
- [Pre-commit 문서](https://pre-commit.com/)
- [Bandit 문서](https://bandit.readthedocs.io/)
- [Trivy 문서](https://aquasecurity.github.io/trivy/)
- [Locust 문서](https://docs.locust.io/)
- [Codecov 문서](https://docs.codecov.com/)

---

## 🆘 문제 해결

### CI가 느려요

1. **병렬 실행 활성화:**
   ```bash
   pytest -n auto  # pytest-xdist 사용
   ```

2. **캐싱 확인:**
   - GitHub Actions는 자동으로 pip, Docker 캐싱

3. **불필요한 테스트 제외:**
   ```bash
   pytest --ignore=tests/load/  # 부하 테스트 제외
   ```

### 커버리지가 떨어져요

1. **커버리지 낮은 파일 확인:**
   ```bash
   coverage report --show-missing
   ```

2. **테스트 추가:**
   - OAuth/MFA/API Keys 우선
   - Edge cases 추가

### 보안 스캔 실패

1. **False positive 확인:**
   ```bash
   bandit -c pyproject.toml -r src/ -ll  # Medium/High만
   ```

2. **예외 추가 (신중히):**
   ```toml
   [tool.bandit]
   skips = ["B101"]  # assert_used
   ```

---

**작성일:** 2026-02-12
**버전:** 1.0
