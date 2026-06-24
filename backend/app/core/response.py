from datetime import datetime, timezone
from typing import Any, Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    code: str = "OK"
    message: str = "정상 처리되었습니다."
    data: T | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: str = Field(default_factory=lambda: str(uuid4()))


class PagedData(BaseModel, Generic[T]):
    items: list[T]
    page: int = 1
    size: int = 20
    total_count: int = 0
    total_pages: int = 0


def ok(data: Any = None, message: str = "정상 처리되었습니다.", code: str = "OK") -> dict:
    return ApiResponse(success=True, code=code, message=message, data=data).model_dump(mode="json")


def accepted(data: Any, message: str = "요청이 접수되었습니다.") -> dict:
    return ApiResponse(success=True, code="ACCEPTED", message=message, data=data).model_dump(mode="json")


def paged(items: list, page: int, size: int, total_count: int) -> dict:
    total_pages = (total_count + size - 1) // size if size > 0 else 0
    return ok(PagedData(items=items, page=page, size=size, total_count=total_count, total_pages=total_pages).model_dump())
