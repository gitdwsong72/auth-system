"""공통 예외 클래스 및 전역 핸들러

도메인 예외를 정의하고 FastAPI 애플리케이션에 전역 예외 핸들러를 등록합니다.
"""

from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class AppException(Exception):
    """애플리케이션 기본 예외 클래스"""

    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class NotFoundException(AppException):
    """리소스를 찾을 수 없는 경우 (404)"""

    def __init__(self, error_code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(status.HTTP_404_NOT_FOUND, error_code, message, details)


class ConflictException(AppException):
    """리소스 충돌 (409)"""

    def __init__(self, error_code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(status.HTTP_409_CONFLICT, error_code, message, details)


class UnauthorizedException(AppException):
    """인증 실패 (401)"""

    def __init__(self, error_code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(status.HTTP_401_UNAUTHORIZED, error_code, message, details)


class ForbiddenException(AppException):
    """권한 부족 (403)"""

    def __init__(self, error_code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(status.HTTP_403_FORBIDDEN, error_code, message, details)


class ValidationException(AppException):
    """검증 오류 (422)"""

    def __init__(self, error_code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, error_code, message, details)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """AppException 전역 핸들러

    표준 에러 응답 형식:
    {
        "success": false,
        "data": null,
        "error": {
            "code": "ERROR_CODE",
            "message": "Error message",
            "details": {...}
        }
    }
    """
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


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """예상치 못한 예외 핸들러

    표준 에러 응답 형식:
    {
        "success": false,
        "data": null,
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "서버 내부 오류가 발생했습니다",
            "details": {}
        }
    }
    """
    logger = structlog.get_logger("exceptions")
    logger.error(
        "unhandled_exception",
        exc_type=type(exc).__name__,
        exc_message=str(exc),
        path=str(request.url),
        method=request.method,
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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


def register_exception_handlers(app: FastAPI) -> None:
    """FastAPI 애플리케이션에 예외 핸들러 등록"""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
