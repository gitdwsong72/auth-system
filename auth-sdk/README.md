# auth-sdk

인증 서비스 연동을 위한 Python SDK입니다. MSA 환경에서 각 서비스가 `pip install`로 설치하여 인증 서비스와 쉽게 연동할 수 있습니다.

## 주요 기능

- **JWT 미들웨어**: FastAPI 미들웨어를 통한 자동 토큰 검증
- **의존성 주입**: `Depends`를 활용한 인증/권한 검증 헬퍼
- **HTTP 클라이언트**: 인증 서비스 API 호출을 위한 비동기 클라이언트
- **JWKS 지원**: 로컬 JWT 검증을 위한 JWKS 키 캐싱

## 설치

```bash
pip install auth-sdk
```

## 빠른 시작

### 환경 변수 설정

```bash
export AUTH_AUTH_SERVICE_URL=http://auth-service:8000
```

### 미들웨어 설정

```python
from fastapi import FastAPI
from auth_sdk import AuthMiddleware, AuthConfig

app = FastAPI()
config = AuthConfig(auth_service_url="http://auth-service:8000")
app.add_middleware(AuthMiddleware, config=config)
```

### 인증 필수 엔드포인트

```python
from fastapi import APIRouter, Depends
from auth_sdk import require_auth, CurrentUser

router = APIRouter()

@router.get("/me")
async def get_me(user: CurrentUser = Depends(require_auth)):
    """현재 로그인한 사용자 정보를 반환합니다."""
    return user
```

### 권한 기반 접근 제어

```python
from auth_sdk import require_permission, require_roles

@router.get("/users")
async def list_users(
    user: CurrentUser = Depends(require_permission("users:read"))
):
    """users:read 권한이 있는 사용자만 접근할 수 있습니다."""
    return {"users": []}

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    user: CurrentUser = Depends(require_roles("admin", "manager"))
):
    """admin 또는 manager 역할을 가진 사용자만 접근할 수 있습니다."""
    return {"deleted": user_id}
```

### 선택적 인증

```python
from auth_sdk.dependencies import get_optional_user

@router.get("/products")
async def list_products(
    user: CurrentUser | None = Depends(get_optional_user)
):
    """인증 여부에 따라 다른 응답을 반환합니다."""
    if user:
        return {"products": [], "personalized": True}
    return {"products": []}
```

### HTTP 클라이언트 직접 사용

```python
from auth_sdk import AuthClient

async def verify_user_token(token: str):
    """인증 서비스를 통해 토큰을 검증합니다."""
    async with AuthClient(base_url="http://auth-service:8000") as client:
        user = await client.verify_token(token)
        has_perm = await client.check_permission(user.id, "admin:write")
        return user, has_perm
```

## 설정 옵션

| 환경 변수 | 설명 | 기본값 |
|-----------|------|--------|
| `AUTH_AUTH_SERVICE_URL` | 인증 서비스 URL | (필수) |
| `AUTH_JWKS_URL` | JWKS 엔드포인트 URL | `{AUTH_SERVICE_URL}/.well-known/jwks.json` |
| `AUTH_JWT_ALGORITHM` | JWT 서명 알고리즘 | `RS256` |
| `AUTH_TOKEN_CACHE_TTL` | 토큰 캐시 TTL (초) | `300` |
| `AUTH_VERIFY_TOKEN_LOCALLY` | 로컬 JWT 검증 사용 여부 | `true` |

## 개발 환경 설정

```bash
# 의존성 설치
pip install -e ".[dev]"

# 테스트 실행
pytest

# 린트 검사
ruff check src/ tests/

# 타입 검사
mypy src/
```
