from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class BadgeTierIn(BaseModel):
    slug: str = Field(min_length=1, max_length=50)
    label: str = Field(min_length=1, max_length=100)
    emoji: str = Field(default="🏅", max_length=8)
    description: Optional[str] = None
    threshold_xp: int = 0
    is_active: bool = True


class BadgeTierUpdate(BaseModel):
    label: Optional[str] = None
    emoji: Optional[str] = None
    description: Optional[str] = None
    threshold_xp: Optional[int] = None
    is_active: Optional[bool] = None
