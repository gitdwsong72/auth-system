# CSRF Protection 사용 가이드

## 개요

Double Submit Cookie 패턴을 사용한 CSRF 방어 구현
- JWT 기반 API에서 추가 보호 계층 제공
- 외부 의존성 없음
- 간단한 통합

## 사용 방법

### 1. 엔드포인트에 CSRF 보호 적용

```python
from fastapi import Depends
from src.shared.security.csrf_protection import require_csrf_token

@app.post("/api/v1/users", dependencies=[Depends(require_csrf_token)])
async def create_user(user: UserCreate):
    # CSRF 검증이 자동으로 수행됨
    pass

@app.put("/api/v1/users/{user_id}", dependencies=[Depends(require_csrf_token)])
async def update_user(user_id: int, user: UserUpdate):
    pass

@app.delete("/api/v1/users/{user_id}", dependencies=[Depends(require_csrf_token)])
async def delete_user(user_id: int):
    pass
```

### 2. CSRF 토큰 발급 엔드포인트 (선택사항)

```python
from fastapi import Response
from src.shared.security.csrf_protection import CSRFProtection

@app.get("/api/v1/auth/csrf-token")
async def get_csrf_token(response: Response):
    """CSRF 토큰 발급"""
    token = CSRFProtection.generate_token()

    # 쿠키에 설정
    response.set_cookie(
        key="CSRF-Token",
        value=token,
        httponly=True,
        secure=True,  # HTTPS only
        samesite="strict",
    )

    return {"csrf_token": token}
```

### 3. 클라이언트 사용법

```typescript
// 1. 토큰 받기
const response = await fetch('/api/v1/auth/csrf-token');
const { csrf_token } = await response.json();

// 2. 요청 시 헤더에 포함
await fetch('/api/v1/users', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRF-Token': csrf_token,  // 헤더에 토큰 포함
  },
  credentials: 'include',  // 쿠키 포함
  body: JSON.stringify(userData),
});
```

## 적용 범위

### 필수 적용 대상
- ✅ POST 엔드포인트 (생성)
- ✅ PUT/PATCH 엔드포인트 (수정)
- ✅ DELETE 엔드포인트 (삭제)

### 적용 제외 대상
- ❌ GET 엔드포인트 (읽기 - Idempotent)
- ❌ HEAD/OPTIONS 엔드포인트
- ❌ 공개 API (인증 불필요)

## 보안 고려사항

### 장점
1. **Double Submit Cookie 패턴**: 헤더와 쿠키 일치 확인
2. **Timing Attack 방지**: `secrets.compare_digest` 사용
3. **외부 의존성 없음**: 자체 구현으로 커스터마이즈 가능

### 제한사항
1. **JWT 기반 API**: 이미 CSRF 공격에 어느 정도 보호됨
2. **쿠키 사용 시 필수**: JWT를 로컬스토리지에 저장하는 경우 CSRF 불필요
3. **프론트엔드 통합 필요**: 클라이언트가 토큰을 관리해야 함

## 현재 상태

- ✅ CSRF 보호 모듈 구현 완료
- ✅ 단위 테스트 8개 작성 (100% 통과)
- ⏸️ 실제 엔드포인트 적용은 선택사항 (필요 시 적용)

## 추후 개선사항

1. **미들웨어로 전환**: 특정 경로에 자동 적용
2. **토큰 만료 시간**: 시간 제한 토큰으로 강화
3. **SameSite Cookie**: Strict 모드 강제
