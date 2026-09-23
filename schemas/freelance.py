"""Pydantic schema for Freelance / Independent Contractor / Service Agreement analysis."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field, field_validator
from schemas.base import BaseClause, clean_numeric_value, clean_integer_value, clean_boolean_value


class FreelancePaymentClause(BaseClause):
    """Payment milestones, net days, and penalties."""
    net_days: Optional[int] = Field(default=None, description="Days to pay after invoice (e.g., Net 30, Net 60).")
    advance_deposit_pct: Optional[float] = Field(default=None, description="Upfront deposit percentage before work starts.")
    late_payment_penalty_pct: Optional[float] = Field(default=None, description="Monthly/annual interest on overdue invoices.")
    has_late_payment_clause: Optional[bool] = Field(default=None, description="Whether late payment incurs interest/penalty.")

    @field_validator("net_days", mode="before")
    @classmethod
    def val_days(cls, v):
        return clean_integer_value(v)

    @field_validator("advance_deposit_pct", "late_payment_penalty_pct", mode="before")
    @classmethod
    def val_numeric(cls, v):
        return clean_numeric_value(v)

    @field_validator("has_late_payment_clause", mode="before")
    @classmethod
    def val_bool(cls, v):
        return clean_boolean_value(v)


class FreelanceIPClause(BaseClause):
    """Intellectual property transfer terms and timing."""
    timing_of_transfer: Optional[str] = Field(
        default=None,
        description="When IP transfers: 'upon_full_payment', 'upon_creation', or 'upon_delivery'."
    )
    transfers_before_full_payment: Optional[bool] = Field(
        default=None,
        description="Whether client owns IP before freelancer has been paid in full."
    )
    portfolio_rights_retained: Optional[bool] = Field(
        default=None,
        description="Whether freelancer retains the right to display work in their portfolio."
    )
    moral_rights_waived: Optional[bool] = Field(
        default=None,
        description="Whether creator waives moral rights / authorship credit."
    )

    @field_validator("transfers_before_full_payment", "portfolio_rights_retained", "moral_rights_waived", mode="before")
    @classmethod
    def val_bool(cls, v):
        return clean_boolean_value(v)


class KillFeeClause(BaseClause):
    """Cancellation compensation and kill fees."""
    kill_fee_defined: Optional[bool] = Field(
        default=None,
        description="Whether compensation is guaranteed if client cancels project without cause."
    )
    kill_fee_amount_or_pct: Optional[str] = Field(
        default=None,
        description="Specification of kill fee (e.g. 50% of remaining contract, or pro-rated)."
    )

    @field_validator("kill_fee_defined", mode="before")
    @classmethod
    def val_bool(cls, v):
        return clean_boolean_value(v)


class ScopeOfWorkClause(BaseClause):
    """Scope boundaries, revisions, and change orders."""
    defined_deliverables: Optional[bool] = Field(
        default=None,
        description="Whether specific deliverables and milestones are itemized."
    )
    revision_limit_count: Optional[int] = Field(
        default=None,
        description="Maximum number of included client revisions (e.g., 2 rounds)."
    )
    open_ended_scope: Optional[bool] = Field(
        default=None,
        description="Whether duties are described vaguely as 'any duties as requested' without limit."
    )

    @field_validator("revision_limit_count", mode="before")
    @classmethod
    def val_int(cls, v):
        return clean_integer_value(v)

    @field_validator("defined_deliverables", "open_ended_scope", mode="before")
    @classmethod
    def val_bool(cls, v):
        return clean_boolean_value(v)


class FreelanceTerminationClause(BaseClause):
    """Contract termination procedures and notice."""
    notice_days: Optional[int] = Field(default=None, description="Notice days required to end contract.")
    payment_for_completed_milestones_guaranteed: Optional[bool] = Field(
        default=None,
        description="Whether client must compensate for work performed up to notice date."
    )

    @field_validator("notice_days", mode="before")
    @classmethod
    def val_int(cls, v):
        return clean_integer_value(v)

    @field_validator("payment_for_completed_milestones_guaranteed", mode="before")
    @classmethod
    def val_bool(cls, v):
        return clean_boolean_value(v)


class FreelanceContractSchema(BaseModel):
    """Complete structured extraction model for Freelance and Service Agreements."""
    freelancer_name: Optional[str] = None
    client_name: Optional[str] = None
    project_title: Optional[str] = None

    payment_terms: FreelancePaymentClause = Field(default_factory=FreelancePaymentClause)
    ip_assignment: FreelanceIPClause = Field(default_factory=FreelanceIPClause)
    kill_fee: KillFeeClause = Field(default_factory=KillFeeClause)
    scope_of_work: ScopeOfWorkClause = Field(default_factory=ScopeOfWorkClause)
    termination: FreelanceTerminationClause = Field(default_factory=FreelanceTerminationClause)
