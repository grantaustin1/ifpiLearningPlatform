from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class PathCreate(BaseModel):
    title: str
    description: Optional[str] = None
    cover_color: str = "bg-violet-500"
    estimated_hours: Optional[int] = None
    price_cents: int = 0
    currency: str = "ZAR"


class PathUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    cover_color: Optional[str] = None
    estimated_hours: Optional[int] = None
    price_cents: Optional[int] = None
    status: Optional[str] = None


class PathItemIn(BaseModel):
    course_id: int
    order_index: Optional[int] = None
    is_required: bool = True


class PathItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    course_id: int
    course_title: str
    course_status: str
    order_index: int
    is_required: bool


class PathSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: Optional[str]
    cover_color: str
    status: str
    estimated_hours: Optional[int]
    price_cents: int
    currency: str
    course_count: int
    enrollment_count: int


class PathDetail(PathSummary):
    items: List[PathItemOut]
    user_progress: float = 0.0
    user_status: Optional[str] = None
