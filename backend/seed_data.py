"""Shim module for CI seed steps that call ``from seed_data import seed; seed()``.

The canonical seed lives in ``seed/seed_minimal.py``; this thin wrapper
exposes a zero-argument ``seed()`` so the CI bootstrap step works without
having to know about the internal package layout.
"""
from seed.seed_minimal import run_if_empty as seed  # noqa: F401
