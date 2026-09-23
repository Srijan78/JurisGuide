"""Pydantic schema for Employment Offer Letter analysis."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field, field_validator
from schemas.base import BaseClause, clean_numeric_value, clean_integer_value, clean_boolean_value


class BondClause(BaseClause):
    """Training cost or service bond requirement."""
    amount: Optional[float] = Field(default=None, description="Monetary penalty or bond sum.")
    duration_months: Optional[int] = Field(default=None, description="Bond commitment duration in months.")
    forfeiture_conditions: Optional[str] = Field(default=None, description="Conditions triggering bond forfeit.")

    @field_validator("amount", mode="before")
    @classmethod
    def val_amount(cls, v):
        return clean_numeric_value(v)

    @field_validator("duration_months", mode="before")
    @classmethod
    def val_duration(cls, v):
        return clean_integer_value(v)


class NoticePeriodClause(BaseClause):
    """Resignation and termination notice requirement."""
    employer_notice_days: Optional[int] = Field(default=None, description="Days notice employer must give.")
    employee_notice_days: Optional[int] = Field(default=None, description="Days notice employee must give.")
    buyout_option: Optional[bool] = Field(default=None, description="Whether pay-in-lieu of notice is permitted.")

    @field_validator("employer_notice_days", "employee_notice_days", mode="before")
    @classmethod
    def val_notice_days(cls, v):
        return clean_integer_value(v)

    @field_validator("buyout_option", mode="before")
    @classmethod
    def val_buyout(cls, v):
        return clean_boolean_value(v)


class NonCompeteClause(BaseClause):
    """Post-employment competition restrictions."""
    duration_months: Optional[int] = Field(default=None, description="Non-compete validity in months post-exit.")
    geographic_scope: Optional[str] = Field(default=None, description="Geographic boundary (city, country, worldwide).")
    industry_scope: Optional[str] = Field(default=None, description="Industry or direct competitors restricted.")

    @field_validator("duration_months", mode="before")
    @classmethod
    def val_duration(cls, v):
        return clean_integer_value(v)


class ConfidentialityIPClause(BaseClause):
    """Intellectual property assignment and confidentiality."""
    perpetual_ip_assignment: Optional[bool] = Field(default=None, description="Whether IP assignment extends indefinitely.")
    post_employment_ip_claim: Optional[bool] = Field(default=None, description="Whether company claims inventions made after employment.")
    scope: Optional[str] = Field(default=None, description="Scope of confidential info or IP covered.")

    @field_validator("perpetual_ip_assignment", "post_employment_ip_claim", mode="before")
    @classmethod
    def val_bool(cls, v):
        return clean_boolean_value(v)


class ProbationClause(BaseClause):
    """Probation terms and review process."""
    duration_months: Optional[int] = Field(default=None, description="Probation period in months.")
    immediate_termination_allowed: Optional[bool] = Field(
        default=None,
        description="Whether employer can terminate immediately during probation without cause or notice."
    )

    @field_validator("duration_months", mode="before")
    @classmethod
    def val_duration(cls, v):
        return clean_integer_value(v)

    @field_validator("immediate_termination_allowed", mode="before")
    @classmethod
    def val_immediate(cls, v):
        return clean_boolean_value(v)


class SalaryBreakdownClause(BaseClause):
    """Compensation breakdown and pay frequency."""
    fixed_amount: Optional[float] = Field(default=None, description="Base salary amount.")
    variable_amount: Optional[float] = Field(default=None, description="Performance or variable bonus component.")
    variable_pct: Optional[float] = Field(default=None, description="Percentage of total CTC that is variable.")
    currency: Optional[str] = Field(default="INR", description="Currency symbol or code (e.g. INR, USD).")
    period: Optional[str] = Field(default="annual", description="Annual or Monthly compensation.")

    @field_validator("fixed_amount", "variable_amount", "variable_pct", mode="before")
    @classmethod
    def val_numeric(cls, v):
        return clean_numeric_value(v)


class TerminationClause(BaseClause):
    """Grounds for termination and procedural rights."""
    notice_required_days: Optional[int] = Field(default=None, description="Standard notice required for termination.")
    grounds_specified: Optional[bool] = Field(default=None, description="Whether termination grounds are defined clearly.")
    summary_termination_without_hearing: Optional[bool] = Field(
        default=None,
        description="Whether unilateral termination without opportunity to cure is allowed."
    )

    @field_validator("notice_required_days", mode="before")
    @classmethod
    def val_notice(cls, v):
        return clean_integer_value(v)

    @field_validator("grounds_specified", "summary_termination_without_hearing", mode="before")
    @classmethod
    def val_bool(cls, v):
        return clean_boolean_value(v)


class EmploymentOfferSchema(BaseModel):
    """Complete structured extraction model for Employment Offer Letters."""
    candidate_name: Optional[str] = None
    designation_role: Optional[str] = None
    joining_date: Optional[str] = None

    bond: BondClause = Field(default_factory=BondClause)
    notice_period: NoticePeriodClause = Field(default_factory=NoticePeriodClause)
    non_compete: NonCompeteClause = Field(default_factory=NonCompeteClause)
    confidentiality_ip: ConfidentialityIPClause = Field(default_factory=ConfidentialityIPClause)
    probation: ProbationClause = Field(default_factory=ProbationClause)
    salary_breakdown: SalaryBreakdownClause = Field(default_factory=SalaryBreakdownClause)
    termination: TerminationClause = Field(default_factory=TerminationClause)
