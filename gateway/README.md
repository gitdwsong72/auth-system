# API Gateway (Kong)

auth-system의 API Gateway 설정입니다. Kong DB-less 모드를 사용하여 선언적 구성 파일로 관리합니다.

## 아키텍처

```
Client Request
    │
    ▼
┌─────────────────────────────┐
│  Kong Gateway (:8080)       │
│  ┌───────────────────────┐  │
│  │ Global Plugins        │  │
│  │ - rate-limiting       │  │
│  │ - cors                │  │
│  │ - file-log            │  │
│  └───────────────────────┘  │
│                             │
│  ┌───────────────────────┐  │
│  │ Routes                │  │
│  │ /api/v1/* → auth-svc  │  │
│  │ /.well-known → auth   │  │
│  │ /health → auth-svc    │  │
│  │ /admin → auth-admin   │  │
│  └───────────────────────┘  │
└─────────────────────────────┘
    │                    │
    ▼                    ▼
┌──────────┐     ┌─────────────┐
│auth-service│   │ auth-admin  │
│  (:8000)  │    │   (:5173)   │
└──────────┘     └─────────────┘
```

## DB-less 모드

Kong을 데이터베이스 없이 선언적 YAML 설정 파일(`kong/kong.yml`)로 운영합니다.

**장점:**
- 설정을 Git으로 버전 관리 가능
- 별도의 PostgreSQL/Cassandra 불필요
- 컨테이너 재시작만으로 설정 반영
- 구성이 단순하고 재현 가능

**제약사항:**
- Admin API를 통한 런타임 설정 변경 불가
- 설정 변경 시 컨테이너 재배포 필요

## 라우팅 구조

| 경로 | 대상 서비스 | 설명 |
|------|-----------|------|
| `/api/v1/auth/*` | auth-service:8000 | 인증 (로그인, 토큰 등) |
| `/api/v1/users/*` | auth-service:8000 | 사용자 관리 |
| `/api/v1/roles/*` | auth-service:8000 | 역할 관리 |
| `/api/v1/permissions/*` | auth-service:8000 | 권한 관리 |
| `/api/v1/oauth/*` | auth-service:8000 | OAuth 2.0 |
| `/api/v1/mfa/*` | auth-service:8000 | 다중 인증 (MFA) |
| `/api/v1/api-keys/*` | auth-service:8000 | API 키 관리 |
| `/.well-known/*` | auth-service:8000 | OpenID Connect Discovery |
| `/health` | auth-service:8000 | 헬스체크 |
| `/admin/*` | auth-admin:5173 | 관리자 대시보드 |

모든 라우트는 `strip_path: false`로 설정되어 원래 경로가 그대로 백엔드 서비스에 전달됩니다.

## 플러그인

### Rate Limiting

분당 요청 수를 제한하여 과도한 트래픽으로부터 서비스를 보호합니다.

```yaml
- name: rate-limiting
  config:
    minute: 60
    policy: local
```

- `minute: 60` - 클라이언트당 분당 60회 요청 허용
- `policy: local` - 각 Kong 인스턴스에서 로컬로 카운트 (Redis 불필요)

> **참고:** 프로덕션 환경에서는 `policy: redis`로 변경하여 여러 Kong 인스턴스 간 카운터를 공유하는 것을 권장합니다.

### CORS

Cross-Origin Resource Sharing 설정으로 허용된 출처의 브라우저 요청만 허용합니다.

```yaml
- name: cors
  config:
    origins:
      - "http://localhost:5173"
      - "http://localhost:3000"
    methods:
      - GET
      - POST
      - PUT
      - DELETE
      - OPTIONS
    headers:
      - Authorization
      - Content-Type
    credentials: true
```

- `origins` - 허용할 출처 도메인 목록
- `credentials: true` - 쿠키/인증 헤더 포함 요청 허용

### File Log

모든 요청/응답을 stdout으로 출력하여 Docker 로그로 수집합니다.

```yaml
- name: file-log
  config:
    path: /dev/stdout
    reopen: true
```

## 새 서비스 추가 방법

`kong/kong.yml`의 `services` 섹션에 새 서비스를 추가합니다.

```yaml
services:
  # ... 기존 서비스 ...

  # 새 서비스 추가 예시
  - name: notification-service
    url: http://notification-service:8001
    routes:
      - name: notification-routes
        paths:
          - /api/v1/notifications
        strip_path: false
```

추가 후 Kong 컨테이너를 재시작합니다:

```bash
docker compose restart gateway
```

## JWT 검증 플러그인 (Phase 2)

Phase 2에서 Kong의 JWT 플러그인을 활성화하여 Gateway 레벨에서 토큰 검증을 수행할 예정입니다.

### 활성화 방법

`kong/kong.yml`에 JWT 플러그인을 추가합니다:

```yaml
plugins:
  # ... 기존 플러그인 ...

  # JWT 검증 (Phase 2에서 활성화)
  - name: jwt
    config:
      uri_param_names:
        - jwt
      header_names:
        - Authorization
      claims_to_verify:
        - exp
      secret_is_base64: false
```

### 특정 라우트에만 적용

공개 엔드포인트(로그인, 회원가입 등)는 JWT 검증을 제외해야 합니다:

```yaml
services:
  - name: auth-service
    url: http://auth-service:8000
    routes:
      # 인증이 필요한 라우트
      - name: protected-routes
        paths:
          - /api/v1/users
          - /api/v1/roles
          - /api/v1/permissions
        strip_path: false
        plugins:
          - name: jwt

      # 공개 라우트 (JWT 검증 없음)
      - name: public-routes
        paths:
          - /api/v1/auth/login
          - /api/v1/auth/register
          - /api/v1/auth/refresh
        strip_path: false
```

### Consumer 등록

JWT 검증을 위해 Consumer와 JWT credential을 등록합니다:

```yaml
consumers:
  - username: auth-system
    jwt_secrets:
      - key: auth-system-issuer
        algorithm: RS256
        rsa_public_key: |
          -----BEGIN PUBLIC KEY-----
          (공개 키 내용)
          -----END PUBLIC KEY-----
```

## 환경별 설정

### Development (기본값)

현재 `kong/kong.yml`이 개발 환경 기본 설정입니다.

```yaml
# 개발 환경 특징
- rate-limiting: 60 req/min (넉넉하게)
- CORS origins: localhost 허용
- file-log: stdout 출력
```

### Staging

```yaml
# 변경 사항
plugins:
  - name: rate-limiting
    config:
      minute: 30
      policy: redis
      redis:
        host: redis
        port: 6379

  - name: cors
    config:
      origins:
        - "https://staging.example.com"
      credentials: true
```

### Production

```yaml
# 변경 사항
plugins:
  - name: rate-limiting
    config:
      minute: 20
      policy: redis
      redis:
        host: redis-cluster
        port: 6379

  - name: cors
    config:
      origins:
        - "https://app.example.com"
        - "https://admin.example.com"
      credentials: true

  # IP 제한 (관리자 대시보드)
  - name: ip-restriction
    service: auth-admin
    config:
      allow:
        - 10.0.0.0/8

  # 요청 크기 제한
  - name: request-size-limiting
    config:
      allowed_payload_size: 10
      size_unit: megabytes

  # JWT 검증 활성화
  - name: jwt
    config:
      claims_to_verify:
        - exp
```

### 환경별 설정 전환

`docker-compose.yml`에서 환경 변수로 설정 파일을 지정합니다:

```yaml
gateway:
  build: ./gateway
  environment:
    KONG_DATABASE: "off"
    KONG_DECLARATIVE_CONFIG: /kong/kong.yml
    KONG_PROXY_LISTEN: "0.0.0.0:8080"
    KONG_LOG_LEVEL: info
  ports:
    - "8080:8080"
```

프로덕션에서는 별도의 설정 파일을 마운트할 수 있습니다:

```yaml
gateway:
  volumes:
    - ./gateway/kong/kong.prod.yml:/kong/kong.yml:ro
```
