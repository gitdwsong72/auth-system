# Error Handling Guide

## Overview

This guide documents the standardized error handling patterns used throughout the auth-system codebase.

**Status**: ✅ Error handling is **already standardized** across the codebase.

## Core Principles

### 1. **Always Raise Exceptions** (Never Return Error States)

✅ **Correct** (Current implementation):
```python
if not user_row:
    raise NotFoundException(
        error_code="USER_002",
        message="사용자를 찾을 수 없습니다",
    )
```

❌ **Incorrect** (Anti-pattern - NOT used in codebase):
```python
if not user_row:
    return None  # ❌ Don't return error states

if not user_row:
    return {"error": "user not found"}  # ❌ Don't return error dicts
```

### 2. **Use Specific Exception Classes**

The codebase provides these exception types in `src/shared/exceptions.py`:

| Exception | HTTP Status | Use Case |
|-----------|-------------|----------|
| `NotFoundException` | 404 | Resource not found |
| `ConflictException` | 409 | Resource already exists or conflict |
| `UnauthorizedException` | 401 | Authentication failure (invalid credentials, expired token) |
| `ForbiddenException` | 403 | Authorization failure (insufficient permissions) |
| `ValidationException` | 422 | Input validation failure |

### 3. **Use Standardized Error Codes**

All error codes are defined in `src/shared/constants.py`:

```python
from src.shared.constants import ErrorCode, ErrorMessage

raise NotFoundException(
    error_code=ErrorCode.USER_002,  # ✅ Use constant
    message=ErrorMessage.USER_NOT_FOUND,  # ✅ Use constant
)
```

**Error Code Naming Convention**:
- `USER_XXX`: User management errors
- `AUTH_XXX`: Authentication errors
- `AUTHZ_XXX`: Authorization errors
- `INTERNAL_XXX`: Internal server errors

## Exception Patterns by Use Case

### 1. Resource Not Found

```python
from src.shared.exceptions import NotFoundException

user_row = await repository.get_user_by_id(connection, user_id)
if not user_row:
    raise NotFoundException(
        error_code="USER_002",
        message="사용자를 찾을 수 없습니다",
    )
```

**Examples in codebase**:
- `src/domains/users/service.py:173-176`
- `src/domains/users/service.py:226-229`
- `src/domains/users/service.py:355-358`

### 2. Resource Conflict (Already Exists)

```python
from src.shared.exceptions import ConflictException

existing_user = await repository.get_user_by_email(connection, email)
if existing_user:
    raise ConflictException(
        error_code="USER_001",
        message="이미 사용 중인 이메일입니다",
    )
```

**Examples in codebase**:
- `src/domains/users/service.py:110-114`

### 3. Authentication Failure

```python
from src.shared.exceptions import UnauthorizedException

# Invalid credentials
if not password_hasher.verify(password, stored_hash):
    raise UnauthorizedException(
        error_code="AUTH_001",
        message="이메일 또는 비밀번호가 올바르지 않습니다",
    )

# Token expired
try:
    payload = jwt.decode(token, key, algorithms=["RS256"])
except TokenExpiredError:
    raise UnauthorizedException(
        error_code="AUTH_002",
        message="토큰이 만료되었습니다",
    )

# Account locked
if login_attempts >= 5:
    raise UnauthorizedException(
        error_code="AUTH_004",
        message=f"계정이 잠겨있습니다 ({lockout_minutes}분 후 재시도)",
    )
```

**Examples in codebase**:
- `src/domains/authentication/service.py:44-47` (Account locked)
- `src/domains/authentication/service.py:86-90` (Invalid credentials)
- `src/domains/authentication/service.py:256-260` (Token expired)

### 4. Authorization Failure (Insufficient Permissions)

```python
from src.shared.exceptions import ForbiddenException

if required_permission not in user_permissions:
    raise ForbiddenException(
        error_code="AUTHZ_001",
        message="권한이 부족합니다",
        details={"required_permission": required_permission},
    )
```

**Examples in codebase**:
- `src/shared/dependencies.py` (Permission checking)

### 5. Validation Errors

```python
from src.shared.exceptions import ValidationException

validation_errors = password_hasher.validate_strength(password)
if validation_errors:
    raise ValidationException(
        error_code="USER_003",
        message="비밀번호 강도가 부족합니다",
        details={"validation_errors": validation_errors},
    )
```

**Examples in codebase**:
- `src/domains/users/service.py:120-124` (Password strength)
- `src/domains/users/service.py:276-280` (Password change validation)

## Exception Handler Flow

### 1. Custom Exception Handler

All `AppException` subclasses are caught by `app_exception_handler`:

```python
# src/shared/exceptions.py:65-90

async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            },
        },
    )
```

**Response Format**:
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "USER_002",
    "message": "사용자를 찾을 수 없습니다",
    "details": {}
  }
}
```

### 2. Generic Exception Handler

Unexpected exceptions are caught by `generic_exception_handler`:

```python
# src/shared/exceptions.py:93-127

async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled_exception",
        exc_type=type(exc).__name__,
        exc_message=str(exc),
        path=str(request.url),
        method=request.method,
        exc_info=True,  # Includes full traceback
    )

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "서버 내부 오류가 발생했습니다",
                "details": {},
            },
        },
    )
```

**Features**:
- ✅ Logs full exception details (type, message, traceback)
- ✅ Includes request context (path, method)
- ✅ Returns standardized error response
- ✅ Hides internal details from client (security)

## Best Practices

### ✅ DO's

1. **Always use exceptions for error conditions**
   ```python
   if error_condition:
       raise AppropriateException(...)
   ```

2. **Use specific exception types**
   ```python
   raise NotFoundException(...)  # ✅ Specific
   # Not: raise Exception(...)   # ❌ Generic
   ```

3. **Include error codes and messages**
   ```python
   raise UnauthorizedException(
       error_code="AUTH_001",  # ✅ Code for programmatic handling
       message="Invalid credentials",  # ✅ Human-readable message
   )
   ```

4. **Add context in details field**
   ```python
   raise ValidationException(
       error_code="USER_003",
       message="Password too weak",
       details={"min_length": 8, "required": ["uppercase", "digit"]},
   )
   ```

5. **Let exceptions propagate to handlers**
   ```python
   # ✅ Let FastAPI exception handler catch it
   async def get_user(user_id: int):
       user = await repository.get_user(user_id)
       if not user:
           raise NotFoundException(...)
       return user
   ```

### ❌ DON'Ts

1. **Don't return error states**
   ```python
   # ❌ Bad
   if not user:
       return None

   # ✅ Good
   if not user:
       raise NotFoundException(...)
   ```

2. **Don't use generic Exception**
   ```python
   # ❌ Bad
   raise Exception("User not found")

   # ✅ Good
   raise NotFoundException(
       error_code="USER_002",
       message="사용자를 찾을 수 없습니다",
   )
   ```

3. **Don't catch and re-raise without adding value**
   ```python
   # ❌ Bad (unnecessary try/catch)
   try:
       return await do_something()
   except NotFoundException as e:
       raise e  # Just let it propagate!

   # ✅ Good (catch to add context)
   try:
       return await do_something()
   except Exception as e:
       raise InternalException("Failed to process", details={"original": str(e)})
   ```

4. **Don't catch Exception without logging**
   ```python
   # ❌ Bad (silent failure)
   try:
       await do_something()
   except Exception:
       pass  # Swallowed!

   # ✅ Good
   try:
       await do_something()
   except Exception:
       logger.error("Operation failed", exc_info=True)
       raise
   ```

5. **Don't expose internal details to clients**
   ```python
   # ❌ Bad (security risk)
   raise Exception(f"Database query failed: {sql_query}")

   # ✅ Good (hide internals)
   logger.error("Database query failed", extra={"query": sql_query})
   raise InternalException("Failed to fetch data")
   ```

## Testing Error Handling

### 1. Unit Tests

Test that exceptions are raised correctly:

```python
import pytest
from src.shared.exceptions import NotFoundException

@pytest.mark.asyncio
async def test_get_user_not_found(connection):
    """Test that NotFoundException is raised for missing user"""
    with pytest.raises(NotFoundException) as exc_info:
        await service.get_user(connection, user_id=999)

    assert exc_info.value.error_code == "USER_002"
    assert exc_info.value.status_code == 404
```

### 2. Integration Tests

Test that HTTP responses are correct:

```python
async def test_get_user_not_found_returns_404(client):
    """Test that API returns 404 for missing user"""
    response = await client.get("/api/v1/users/999")

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "data": None,
        "error": {
            "code": "USER_002",
            "message": "사용자를 찾을 수 없습니다",
            "details": {}
        }
    }
```

## Error Response Schema

All error responses follow this schema:

```typescript
interface ErrorResponse {
  success: false;
  data: null;
  error: {
    code: string;        // Error code (e.g., "USER_002")
    message: string;     // Human-readable message
    details: object;     // Additional context (optional)
  };
}
```

**Example Responses**:

```json
// 404 Not Found
{
  "success": false,
  "data": null,
  "error": {
    "code": "USER_002",
    "message": "사용자를 찾을 수 없습니다",
    "details": {}
  }
}

// 401 Unauthorized
{
  "success": false,
  "data": null,
  "error": {
    "code": "AUTH_001",
    "message": "이메일 또는 비밀번호가 올바르지 않습니다",
    "details": {}
  }
}

// 422 Validation Error
{
  "success": false,
  "data": null,
  "error": {
    "code": "USER_003",
    "message": "비밀번호 강도가 부족합니다",
    "details": {
      "validation_errors": ["Must contain uppercase letter", "Must be at least 8 characters"]
    }
  }
}
```

## Verification Checklist

- [x] All error conditions raise exceptions (not return statements)
- [x] Specific exception types used (NotFoundException, ConflictException, etc.)
- [x] Error codes from constants.py used consistently
- [x] Exception handlers registered in main.py
- [x] Generic exception handler logs unhandled errors
- [x] Error responses follow standardized schema
- [x] Sensitive data not exposed in error messages

## Migration Guide (If Needed)

If you find code with inconsistent error handling:

### Before (Anti-pattern):
```python
async def get_user(user_id: int):
    user = await repository.get_user(user_id)
    if not user:
        return None  # ❌ Returns None on error
    return user
```

### After (Standard pattern):
```python
async def get_user(user_id: int):
    user = await repository.get_user(user_id)
    if not user:
        raise NotFoundException(  # ✅ Raises exception
            error_code="USER_002",
            message="사용자를 찾을 수 없습니다",
        )
    return user
```

## References

- **Exception Definitions**: `src/shared/exceptions.py`
- **Error Constants**: `src/shared/constants.py`
- **Exception Handlers**: `src/shared/exceptions.py:65-133`
- **Usage Examples**:
  - `src/domains/users/service.py`
  - `src/domains/authentication/service.py`

## Conclusion

**Status**: ✅ Error handling is **standardized and consistent** across the codebase.

All services follow the same pattern:
1. Check error conditions
2. Raise specific exceptions with error codes
3. Let exception handlers format responses
4. Log unexpected errors with full context

**No action required** - current implementation is production-ready.
