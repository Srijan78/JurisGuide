"""Pydantic v2 schemas for all supported document verticals and generic fallback."""

from schemas.base import BaseClause
from schemas.employment import EmploymentOfferSchema
from schemas.rental import RentalAgreementSchema
from schemas.freelance import FreelanceContractSchema
from schemas.fallback import FallbackDocumentSchema

__all__ = [
    "BaseClause",
    "EmploymentOfferSchema",
    "RentalAgreementSchema",
    "FreelanceContractSchema",
    "FallbackDocumentSchema",
]
