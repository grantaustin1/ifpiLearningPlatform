from __future__ import annotations

from pydantic import BaseModel


class BulkRevokeIn(BaseModel):
    certificate_ids: list[int]
    reason: str | None = None


class BulkUnrevokeIn(BaseModel):
    certificate_ids: list[int]


class BulkEmailIn(BaseModel):
    certificate_ids: list[int]


class BulkZipIn(BaseModel):
    certificate_ids: list[int]
