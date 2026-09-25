"""Deterministic plain-language contract summary generator.

Constructs clear, professional summaries from extracted structured fields
without making additional LLM API calls (Pillar 3: Efficiency).
"""

from __future__ import annotations

from typing import Union
from core.config import NON_LEGAL_DOCUMENT_MESSAGE
from schemas.employment import EmploymentOfferSchema
from schemas.rental import RentalAgreementSchema
from schemas.freelance import FreelanceContractSchema
from schemas.fallback import FallbackDocumentSchema


def generate_plain_summary(
    schema: Union[EmploymentOfferSchema, RentalAgreementSchema, FreelanceContractSchema, FallbackDocumentSchema]
) -> str:
    """Generate a clean, readable summary of the agreement based on extracted fields."""
    if isinstance(schema, EmploymentOfferSchema):
        return _summarize_employment(schema)
    elif isinstance(schema, RentalAgreementSchema):
        return _summarize_rental(schema)
    elif isinstance(schema, FreelanceContractSchema):
        return _summarize_freelance(schema)
    elif isinstance(schema, FallbackDocumentSchema):
        if not schema.document_has_legal_content:
            return NON_LEGAL_DOCUMENT_MESSAGE
        return schema.plain_summary or "General legal document analyzed."
    return "Legal document analyzed."


def _summarize_employment(schema: EmploymentOfferSchema) -> str:
    parts = []
    role = schema.designation_role or "an unspecified position"
    candidate = schema.candidate_name or "the candidate"
    parts.append(f"This document is an employment offer appointing {candidate} to the role of {role}.")

    # Compensation
    sal = schema.salary_breakdown
    if sal.present and sal.fixed_amount:
        curr = sal.currency or "INR"
        var_note = f" with {sal.variable_pct:.0f}% variable component" if sal.variable_pct else ""
        parts.append(f"Compensation is set at {curr} {sal.fixed_amount:,.0f} ({sal.period or 'annual'}){var_note}.")

    # Notice & Probation
    prob = schema.probation
    prob_str = f"{prob.duration_months}-month probation period" if (prob.present and prob.duration_months) else None
    notc = schema.notice_period
    notc_str = f"{notc.employee_notice_days}-day employee notice period" if (notc.present and notc.employee_notice_days) else None

    terms = [t for t in [prob_str, notc_str] if t]
    if terms:
        parts.append(f"Key terms include a {' and a '.join(terms)}.")

    # Restrictive Covenants
    covenants = []
    if schema.bond.present and schema.bond.duration_months:
        covenants.append(f"a {schema.bond.duration_months}-month service bond")
    if schema.non_compete.present and schema.non_compete.duration_months:
        covenants.append(f"a {schema.non_compete.duration_months}-month post-exit non-compete")

    if covenants:
        parts.append(f"The contract imposes restrictive covenants including {' as well as '.join(covenants)}.")

    return " ".join(parts)


def _summarize_rental(schema: RentalAgreementSchema) -> str:
    parts = []
    addr = f" for property at {schema.property_address}" if schema.property_address else ""
    parts.append(f"This document is a residential lease agreement{addr}.")

    # Rent & Deposit
    rent = schema.monthly_rent
    dep = schema.security_deposit
    if rent.present and rent.monthly_amount:
        dep_str = f" with a security deposit of {dep.amount:,.0f}" if (dep.present and dep.amount) else ""
        parts.append(f"Monthly rent is agreed at {rent.monthly_amount:,.0f}{dep_str}.")

    # Duration & Terms
    lock = schema.lock_in
    if lock.present and lock.duration_months:
        parts.append(f"The lease includes a mandatory lock-in period of {lock.duration_months} months.")

    notc = schema.notice_period
    if notc.present and notc.tenant_notice_days:
        parts.append(f"Termination requires {notc.tenant_notice_days} days advance written notice by tenant.")

    esc = schema.rent_escalation
    if esc.present and esc.escalation_pct:
        parts.append(f"Rent escalates by {esc.escalation_pct:.1f}% upon renewal.")

    return " ".join(parts)


def _summarize_freelance(schema: FreelanceContractSchema) -> str:
    parts = []
    freelancer = schema.freelancer_name or "the service provider"
    client = schema.client_name or "the client"
    proj = f" for '{schema.project_title}'" if schema.project_title else ""
    parts.append(f"This is an independent contractor agreement between {freelancer} and {client}{proj}.")

    # Payment
    pay = schema.payment_terms
    if pay.present and pay.net_days:
        dep_pct = f" and {pay.advance_deposit_pct:.0f}% upfront deposit" if pay.advance_deposit_pct else ""
        parts.append(f"Payment is structured on Net {pay.net_days} terms{dep_pct}.")

    # IP
    ip = schema.ip_assignment
    if ip.present and ip.timing_of_transfer:
        parts.append(f"Intellectual property transfer is stipulated '{ip.timing_of_transfer.replace('_', ' ')}'.")

    # Scope & Kill fee
    scope = schema.scope_of_work
    if scope.present and scope.revision_limit_count:
        parts.append(f"Deliverables include {scope.revision_limit_count} rounds of revisions.")

    if schema.kill_fee.present and schema.kill_fee.kill_fee_defined:
        parts.append("A project cancellation kill fee is defined.")

    return " ".join(parts)
