from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class LiveSessionIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    meeting_url: HttpUrl
    start_at: datetime
    duration_minutes: int = Field(ge=5, le=8 * 60, default=60)
    host_name: Optional[str] = Field(default=None, max_length=200)
    cohort: Optional[str] = Field(default=None, max_length=100)
    course_id: Optional[int] = None
    max_attendees: Optional[int] = Field(default=None, ge=1)
    # Iter 23 — optional recurrence. Accepts an iCal RRULE without the
    # leading "RRULE:" prefix, e.g. "FREQ=WEEKLY;COUNT=8" or
    # "FREQ=DAILY;INTERVAL=2;UNTIL=20260901T000000Z". Materialised into
    # up to 26 child instances at creation time.
    recurrence_rule: Optional[str] = Field(default=None, max_length=500)


class LiveSessionPatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    meeting_url: Optional[HttpUrl] = None
    start_at: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(default=None, ge=5, le=8 * 60)
    host_name: Optional[str] = Field(default=None, max_length=200)
    cohort: Optional[str] = Field(default=None, max_length=100)
    max_attendees: Optional[int] = Field(default=None, ge=1)


class MarkAttendanceIn(BaseModel):
    user_ids: List[int] = Field(min_length=1)
    status: str = Field(pattern="^(ATTENDED|NO_SHOW)$")
