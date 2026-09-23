"""Pydantic schema for Rental / Residential Lease Agreement analysis."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field, field_validator
from schemas.base import BaseClause, clean_numeric_value, clean_integer_value, clean_boolean_value


class SecurityDepositClause(BaseClause):
    """Deposit payment and refund criteria."""
    amount: Optional[float] = Field(default=None, description="Security deposit amount.")
    deposit_months: Optional[float] = Field(default=None, description="Equivalent months of rent for deposit.")
    refund_timeline_days: Optional[int] = Field(default=None, description="Days after handover deposit must be refunded.")
    deduction_conditions: Optional[str] = Field(default=None, description="Permissible deductions (painting, damages).")

    @field_validator("amount", "deposit_months", mode="before")
    @classmethod
    def val_amount(cls, v):
        return clean_numeric_value(v)

    @field_validator("refund_timeline_days", mode="before")
    @classmethod
    def val_days(cls, v):
        return clean_integer_value(v)


class RentalNoticeClause(BaseClause):
    """Notice period for vacating premises."""
    landlord_notice_days: Optional[int] = Field(default=None, description="Notice required from landlord.")
    tenant_notice_days: Optional[int] = Field(default=None, description="Notice required from tenant.")

    @field_validator("landlord_notice_days", "tenant_notice_days", mode="before")
    @classmethod
    def val_notice(cls, v):
        return clean_integer_value(v)


class MaintenanceClause(BaseClause):
    """Maintenance and repair responsibilities."""
    tenant_bears_structural_repairs: Optional[bool] = Field(
        default=None,
        description="Whether tenant is liable for major/structural repairs (seepage, plumbing, roof)."
    )
    routine_maintenance_cap: Optional[float] = Field(
        default=None,
        description="Monetary cap up to which tenant pays for minor repairs."
    )
    landlord_repair_turnaround_days: Optional[int] = Field(
        default=None,
        description="Maximum timeline for landlord to address major defects."
    )

    @field_validator("tenant_bears_structural_repairs", mode="before")
    @classmethod
    def val_bool(cls, v):
        return clean_boolean_value(v)

    @field_validator("routine_maintenance_cap", mode="before")
    @classmethod
    def val_numeric(cls, v):
        return clean_numeric_value(v)

    @field_validator("landlord_repair_turnaround_days", mode="before")
    @classmethod
    def val_int(cls, v):
        return clean_integer_value(v)


class LockInClause(BaseClause):
    """Lock-in period and early exit penalties."""
    duration_months: Optional[int] = Field(default=None, description="Mandatory lock-in period in months.")
    early_exit_penalty_terms: Optional[str] = Field(default=None, description="Penalty for early termination.")
    forfeits_entire_deposit_on_early_exit: Optional[bool] = Field(
        default=None,
        description="Whether early departure triggers total loss of deposit or remainder rent."
    )

    @field_validator("duration_months", mode="before")
    @classmethod
    def val_duration(cls, v):
        return clean_integer_value(v)

    @field_validator("forfeits_entire_deposit_on_early_exit", mode="before")
    @classmethod
    def val_bool(cls, v):
        return clean_boolean_value(v)


class RentEscalationClause(BaseClause):
    """Rent hike percentage and frequency."""
    escalation_pct: Optional[float] = Field(default=None, description="Percentage increase upon renewal.")
    frequency_months: Optional[int] = Field(default=None, description="Interval between increases (usually 11 or 12).")

    @field_validator("escalation_pct", mode="before")
    @classmethod
    def val_numeric(cls, v):
        return clean_numeric_value(v)

    @field_validator("frequency_months", mode="before")
    @classmethod
    def val_int(cls, v):
        return clean_integer_value(v)


class MonthlyRentClause(BaseClause):
    """Base monthly rental and payment schedule."""
    monthly_amount: Optional[float] = Field(default=None, description="Monthly rent figure.")
    due_day: Optional[int] = Field(default=None, description="Due date of month.")
    late_fee_per_day: Optional[float] = Field(default=None, description="Late fee charged per day of delay.")

    @field_validator("monthly_amount", "late_fee_per_day", mode="before")
    @classmethod
    def val_numeric(cls, v):
        return clean_numeric_value(v)

    @field_validator("due_day", mode="before")
    @classmethod
    def val_int(cls, v):
        return clean_integer_value(v)


class RentalAgreementSchema(BaseModel):
    """Complete structured extraction model for Rental Lease Agreements."""
    tenant_name: Optional[str] = None
    landlord_name: Optional[str] = None
    property_address: Optional[str] = None
    lease_commencement_date: Optional[str] = None

    monthly_rent: MonthlyRentClause = Field(default_factory=MonthlyRentClause)
    security_deposit: SecurityDepositClause = Field(default_factory=SecurityDepositClause)
    notice_period: RentalNoticeClause = Field(default_factory=RentalNoticeClause)
    maintenance: MaintenanceClause = Field(default_factory=MaintenanceClause)
    lock_in: LockInClause = Field(default_factory=LockInClause)
    rent_escalation: RentEscalationClause = Field(default_factory=RentEscalationClause)
