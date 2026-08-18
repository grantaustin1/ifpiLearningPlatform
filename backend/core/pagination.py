"""Standard pagination helpers for list endpoints.

Provides a consistent shape across all paginated API responses so
frontends can consume pages without per-endpoint special-casing.
"""
from __future__ import annotations

from typing import Generic, List, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Uniform pagination envelope.

    Fields:
      items      — page of results
      total      — total items across all pages
      page       — current 1-based page number
      page_size  — max items per page
      pages      — total number of pages
    """
    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int


def paginate(
    query,
    *,
    page: int = 1,
    page_size: int = 20,
    max_page_size: int = 100,
) -> tuple[List, int]:
    """SQLAlchemy-friendly pagination.

    Returns `(items, total)` so callers can wrap them in
    `PaginatedResponse` with the appropriate generic type.

    Args:
        query: SQLAlchemy query object
        page: 1-based page number
        page_size: items per page (clamped to max_page_size)
        max_page_size: hard ceiling to prevent abuse
    """
    page = max(1, page)
    page_size = max(1, min(page_size, max_page_size))
    total = query.count()
    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()
    return items, total


def make_response(
    items: List[T],
    total: int,
    *,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse[T]:
    """Build a PaginatedResponse from already-fetched items + total."""
    page = max(1, page)
    page_size = max(1, page_size)
    pages = (total + page_size - 1) // page_size if total > 0 else 1
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )
