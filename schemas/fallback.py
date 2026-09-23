"""Pydantic schema for generic fallback document analysis ('Other' category)."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class FallbackDocumentSchema(BaseModel):
    """Structured extraction for unsupported or miscellaneous legal documents."""
    detected_document_type: str = Field(
        default="General Legal Document",
        description="Best-guess document type (e.g., Non-Disclosure Agreement, Power of Attorney)."
    )
    plain_summary: str = Field(
        ...,
        description="Comprehensive plain-language summary of what this document agrees to."
    )
    identified_parties: List[str] = Field(
        default_factory=list,
        description="Names of parties, companies, or individuals entering the agreement."
    )
    key_dates_and_deadlines: List[str] = Field(
        default_factory=list,
        description="Important dates, deadlines, or durations specified."
    )
    core_obligations: List[str] = Field(
        default_factory=list,
        description="Primary responsibilities or duties stipulated in the text."
    )
    points_to_review: List[str] = Field(
        default_factory=list,
        description="General cautionary notes or ambiguous clauses the signer should inspect."
    )
