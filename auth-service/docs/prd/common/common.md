# PRD: 공통 사항 - Auth Service

## 문서 정보
| 항목 | 내용 |
|------|------|
| 작성자 | Auth Team |
| 작성일 | 2026-02-09 |
| 버전 | 1.0 |
| 상태 | Approved |

---

## 1. 프로젝트 개요

### 1.1 배경
MSA(Microservice Architecture) 환경에서 모든 서비스가 공유하는 통합 인증/인가 시스템이 필요합니다. 각 서비스마다 인증 로직을 구현하면 보안 취약점, 일관성 부재, 유지보수 비용 증가 문제가 발생합니다.

### 1.2 목표
- OAuth 2.0 + OIDC 표준 준수의 인증 서비스 구축
- RBAC(역할 기반 접근 제어)으로 세분화된 권한 관리
- auth-sdk를 통해 다른 MSA 서비스에서 쉽게 연동
- API Gateway(Kong)를 통한 중앙화된 토큰 검증
- MFA(2차 인증) 및 API Key 관리 지원

### 1.3 범위

**포함 범위:**
- 회원가입, 로그인, 로그아웃, 토큰 관리
- RBAC 역할/권한 관리
- OAuth 2.0 소셜 로그인 (Google, Kakao)
- OIDC Discovery + JWKS 엔드포인트
- MFA (TOTP, SMS)
- API Key 발급/관리
- 관리자 대시보드
- auth-sdk (Python 패키지)

**제외 범위:**
- 결제/과금 시스템
- 알림 서비스 (이메일/SMS 발송은 외부 서비스 연동)
- 사용자 프로필 이미지 업로드 (파일 서버)

---

## 2. 용어 정의

| 용어 | 정의 |
|------|------|
| Access Token | 단기 인증 토큰 (JWT, 기본 30분) |
| Refresh Token | Access Token 갱신용 장기 토큰 (기본 7일) |
| RBAC | Role-Based Access Control, 역할 기반 접근 제어 |
| OIDC | OpenID Connect, OAuth 2.0 기반 인증 프로토콜 |
| JWKS | JSON Web Key Set, JWT 서명 검증용 공개키 세트 |
| MFA | Multi-Factor Authentication, 다중 인증 |
| TOTP | Time-based One-Time Password, 시간 기반 일회용 비밀번호 |
| Introspection | 토큰의 유효성과 메타데이터를 확인하는 API |
| auth-sdk | 다른 서비스에서 인증 연동을 위한 Python 패키지 |

---

## 3. 기술 스택

### Backend (auth-service)
- FastAPI 0.111+
- PostgreSQL 16
- Redis 7 (토큰 블랙리스트, Rate Limit, 캐시)
- Python 3.11+
- python-jose (JWT RS256)
- passlib + bcrypt (비밀번호 해싱)
- pyotp (TOTP MFA)

### Frontend (auth-admin)
- React 18+
- TypeScript 5+
- AG-Grid (사용자/역할 관리 테이블)
- Zustand (상태 관리)
- Vite

### Infrastructure
- Docker Compose
- Kong API Gateway (DB-less)
- Nginx (Frontend 서빙)

---

## 4. 인증 아키텍처

### 4.1 인증 흐름
```
Client → Kong Gateway → Auth Service → PostgreSQL
                ↕                  ↕
           토큰 검증           Redis (블랙리스트)
```

### 4.2 토큰 구조 (JWT)
```json
{
  "sub": "123",
  "email": "user@example.com",
  "roles": ["user", "manager"],
  "permissions": ["users:read", "orders:write"],
  "type": "access",
  "iss": "auth-service",
  "iat": 1700000000,
  "exp": 1700001800,
  "jti": "uuid"
}
```

### 4.3 다른 MSA 서비스 연동 (auth-sdk)
```python
from auth_sdk import AuthMiddleware, AuthConfig, require_auth, CurrentUser

# 미들웨어 등록
config = AuthConfig(auth_service_url="http://auth-service:8000")
app.add_middleware(AuthMiddleware, config=config)

# 엔드포인트에서 사용
@router.get("/items")
async def get_items(user: CurrentUser = Depends(require_auth)):
    ...
```

---

## 5. API 규약

### 5.1 Base URL
```
Development: http://localhost:8000/api/v1
Gateway:     http://localhost:8080/api/v1
Production:  https://auth.example.com/api/v1
```

### 5.2 인증 헤더
```
Authorization: Bearer {access_token}
Authorization: ApiKey {api_key}
```

### 5.3 Response Format
```json
{
  "success": true,
  "data": {},
  "message": "Success",
  "error": null
}
```

### 5.4 Error Response
```json
{
  "success": false,
  "data": null,
  "message": "Error message",
  "error": {
    "code": "AUTH_001",
    "details": {}
  }
}
```

### 5.5 에러 코드 체계
| 코드 범위 | 도메인 |
|-----------|--------|
| AUTH_001~099 | 인증 (로그인, 토큰) |
| USER_001~099 | 사용자 |
| ROLE_001~099 | 역할/권한 |
| OAUTH_001~099 | OAuth |
| MFA_001~099 | MFA |
| APIKEY_001~099 | API Key |

### 5.6 Pagination
```json
{
  "items": [],
  "total": 100,
  "page": 1,
  "pageSize": 20,
  "totalPages": 5
}
```

---

## 6. 코딩 컨벤션

### 6.1 Backend 폴더 구조
```
src/domains/{domain}/
├── router.py       # FastAPI 라우터 (엔드포인트 정의)
├── service.py      # 비즈니스 로직
├── repository.py   # 데이터 접근 (SQL 실행)
├── schemas.py      # Pydantic v2 스키마
└── sql/
    ├── queries/    # SELECT 쿼리
    └── commands/   # INSERT/UPDATE/DELETE
```

### 6.2 Frontend 폴더 구조
```
src/domains/{domain}/
├── components/     # 도메인 전용 컴포넌트
├── hooks/          # 도메인 전용 훅
├── stores/         # Zustand 스토어
├── pages/          # 페이지 컴포넌트
├── api/            # API 호출 함수
└── types/          # 타입 정의
```

---

## 7. 도메인 목록

| 도메인 | 설명 | 우선순위 |
|--------|------|---------|
| users | 회원가입, 프로필, 비밀번호 | Phase 2 |
| authentication | 로그인, 로그아웃, 토큰 관리 | Phase 2 |
| roles | RBAC 역할/권한 관리 | Phase 3 |
| oauth | OAuth 2.0 + OIDC | Phase 4 |
| mfa | 2차 인증 (TOTP, SMS) | Phase 5 |
| api_keys | API Key 발급/관리 | Phase 5 |

---

## 8. 변경 이력

| 버전 | 일자 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2026-02-09 | Auth Team | 최초 작성 |
