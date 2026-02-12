"""공통 응답 스키마

API 응답 형식을 표준화하는 Pydantic 스키마를 정의합니다.
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """에러 상세 정보"""

    code: str = Field(..., description="에러 코드")
    message: str = Field(..., description="에러 메시지")
    details: dict[str, Any] = Field(default_factory=dict, description="추가 상세 정보")


class ApiResponse(BaseModel, Generic[T]):
    """표준 API 응답 형식

    성공 응답:
    {
        "success": true,
        "data": {...},
        "error": null
    }

    에러 응답:
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

    success: bool = Field(..., description="성공 여부")
    data: T | None = Field(None, description="응답 데이터")
    error: ErrorDetail | None = Field(None, description="에러 정보")


class PaginatedResponse(BaseModel, Generic[T]):
    """페이징된 응답 형식"""

    items: list[T] = Field(..., description="항목 목록")
    total: int = Field(..., description="전체 항목 수")
    page: int = Field(..., description="현재 페이지 (1부터 시작)")
    page_size: int = Field(..., description="페이지 크기")
    total_pages: int = Field(..., description="전체 페이지 수")

    @classmethod
    def create(
        cls, items: list[T], total: int, page: int, page_size: int
    ) -> "PaginatedResponse[T]":
        """페이징 응답 생성 헬퍼 메서드"""
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
