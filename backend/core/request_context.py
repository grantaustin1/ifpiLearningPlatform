"""Correlation-ID request context.

Lives in its own leaf module so both `core.middleware` (writer) and
`core.query_counter` / loggers (readers) can import it without any
circular dependency.
"""
from __future__ import annotations

import contextvars
from typing import Optional

_correlation_id_var: contextvars.ContextVar[Optional[str]] = \
    contextvars.ContextVar("correlation_id", default=None)


def get_correlation_id() -> Optional[str]:
    return _correlation_id_var.get()
