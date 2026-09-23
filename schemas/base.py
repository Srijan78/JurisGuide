"""Base clause model and resilient data normalization utilities for Pydantic."""

from __future__ import annotations

import re
from typing import Any, Optional
from pydantic import BaseModel, Field


def clean_numeric_value(val: Any) -> Optional[float]:
    """Coerce various messy representations of numbers into float.

    Handles: '$50,000', '₹ 2,50,000.00', '15%', '50k', None
    """
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val)

    if not isinstance(val, str):
        return None

    s = val.strip().lower()

    # Handle multiplier suffixes
    multiplier = 1.0
    if s.endswith("k"):
        multiplier = 1_000.0
        s = s[:-1]
    elif s.endswith("m") or s.endswith("cr") or s.endswith("crore"):
        multiplier = 10_000_000.0 if "cr" in s else 1_000_000.0
        s = re.sub(r"(m|cr|crore)", "", s)
    elif s.endswith("l") or s.endswith("lac") or s.endswith("lakh"):
        multiplier = 100_000.0
        s = re.sub(r"(l|lac|lakh)", "", s)

    # Strip currency signs, commas, and percentage symbols
    cleaned = re.sub(r"[^\d.-]", "", s)
    if not cleaned or cleaned in ("-", "."):
        return None

    try:
        return float(cleaned) * multiplier
    except ValueError:
        return None


def clean_integer_value(val: Any) -> Optional[int]:
    """Coerce values (including duration strings like '24 months', '90 days') to int."""
    num = clean_numeric_value(val)
    if num is None:
        return None
    return int(round(num))


def clean_boolean_value(val: Any) -> Optional[bool]:
    """Coerce various boolean representations to bool."""
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        s = val.strip().lower()
        if s in ("true", "yes", "1", "y", "t", "present", "applicable", "required"):
            return True
        if s in ("false", "no", "0", "n", "f", "absent", "none", "not applicable", "n/a"):
            return False
    return None


class BaseClause(BaseModel):
    """Foundation clause model shared across all legal document schemas."""
    present: bool = Field(
        default=False,
        description="Whether this clause is explicitly present in the document."
    )
    raw_text: Optional[str] = Field(
        default=None,
        description="Verbatim or near-verbatim excerpt from the document for grounding and verification."
    )
