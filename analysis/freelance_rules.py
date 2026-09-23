"""Deterministic risk rules for Freelance and Independent Contractor Agreements.

Guards independent creators and gig workers against unpaid IP transfer, scope creep, and non-payment.
"""

from __future__ import annotations

from typing import List
from core.config import settings
from output.models import RiskItem, Severity
from schemas.freelance import FreelanceContractSchema


def evaluate_freelance_rules(schema: FreelanceContractSchema) -> List[RiskItem]:
    """Execute all deterministic rules against a freelance contract schema.

    Args:
        schema: Validated FreelanceContractSchema instance.

    Returns:
        List of identified RiskItem instances.
    """
    risks: List[RiskItem] = []
    cfg = settings.freelance

    # 1. IP Assignment Timing (Cardinal Rule for Freelancers)
    ip = schema.ip_assignment
    if ip.present:
        timing = (ip.timing_of_transfer or "").lower()
        premature = (
            ip.transfers_before_full_payment is True
            or "creation" in timing
            or "delivery" in timing
            or "signing" in timing
        )
        if premature:
            risks.append(RiskItem(
                clause_id="ip_premature_transfer",
                clause_name="IP Transfer Prior to Full Payment",
                severity=Severity.HIGH,
                title="IP Ownership Transfers Before Full Payment",
                explanation=(
                    "The contract assigns copyright and intellectual property to the client before you have been paid in full. "
                    "If the client defaults on payment, you will have surrendered all leverage and rights to your work."
                ),
                raw_text=ip.raw_text,
                recommendation=(
                    "Demand that IP transfer is strictly conditioned on receipt of final payment: "
                    "'Ownership of all deliverables shall transfer to Client solely upon receipt of full and final payment.'"
                )
            ))

        if ip.portfolio_rights_retained is False:
            risks.append(RiskItem(
                clause_id="ip_portfolio_prohibition",
                clause_name="Portfolio Display Rights Barred",
                severity=Severity.LOW,
                title="Barred From Displaying Work in Professional Portfolio",
                explanation="You are prohibited from showcasing non-confidential deliverables in your professional portfolio.",
                raw_text=ip.raw_text,
                recommendation="Request a standard carve-out permitting self-promotional portfolio display after public launch."
            ))

    # 2. Payment Terms & Penalties
    pay = schema.payment_terms
    if pay.present:
        days = pay.net_days
        if days and days > 45:
            risks.append(RiskItem(
                clause_id="payment_delayed_net",
                clause_name="Extended Payment Terms",
                severity=Severity.HIGH,
                title=f"Excessive Payment Window (Net {days} Days)",
                explanation=(
                    f"A payment window of Net {days} is punitive for independent contractors, forcing you to float business expenses "
                    "for months after delivering work."
                ),
                raw_text=pay.raw_text,
                recommendation="Negotiate Net 15 or Net 30 payment terms, coupled with a 50% upfront commencement deposit."
            ))
        elif days and days > cfg.max_payment_term_days:
            risks.append(RiskItem(
                clause_id="payment_moderate_net",
                clause_name="Moderate Payment Terms",
                severity=Severity.MEDIUM,
                title=f"Net {days} Payment Window",
                explanation=f"Payment terms of Net {days} exceed standard contractor expectations of Net 15–30.",
                raw_text=pay.raw_text,
                recommendation="Request milestone-based payments upon specific deliverable completions."
            ))

        if pay.has_late_payment_clause is False:
            risks.append(RiskItem(
                clause_id="payment_late_interest",
                clause_name="Missing Late Payment Protection",
                severity=Severity.MEDIUM,
                title="No Late Payment Penalty or Interest Clause",
                explanation="The contract provides zero penalty or interest if the client delays paying invoices indefinitely.",
                raw_text=pay.raw_text,
                recommendation="Add a standard late fee clause: 1.5% monthly statutory interest on all invoices overdue past 30 days."
            ))

    # 3. Kill Fee & Cancellation
    kill = schema.kill_fee
    if kill.present and kill.kill_fee_defined is False:
        risks.append(RiskItem(
            clause_id="kill_fee_absent",
            clause_name="Missing Kill Fee Protection",
            severity=Severity.HIGH,
            title="No Kill Fee for Client-Initiated Cancellation",
            explanation=(
                "If the client terminates the project midway without cause, you have no contractual entitlement to cancellation compensation "
                "for reserved calendar time."
            ),
            raw_text=kill.raw_text,
            recommendation="Insist on a 25%–50% kill fee of the remaining contract value if terminated by client without cause."
        ))

    # 4. Scope of Work & Revisions
    scope = schema.scope_of_work
    if scope.present:
        if scope.open_ended_scope:
            risks.append(RiskItem(
                clause_id="scope_open_ended",
                clause_name="Open-Ended Scope of Work",
                severity=Severity.HIGH,
                title="Uncapped / Open-Ended Scope of Work",
                explanation=(
                    "The scope of duties is vaguely worded ('as needed' or 'other duties as assigned') without finite deliverables. "
                    "This is the single most common cause of unpaid scope creep."
                ),
                raw_text=scope.raw_text,
                recommendation="Replace generic wording with an explicit Statement of Work (SOW) detailing exact deliverables."
            ))

        if scope.revision_limit_count is None or scope.revision_limit_count > 4:
            risks.append(RiskItem(
                clause_id="scope_unlimited_revisions",
                clause_name="Uncapped Revision Rounds",
                severity=Severity.MEDIUM,
                title="Unlimited or Ambiguous Revision Rounds",
                explanation="The agreement lacks a cap on client review iterations, risking endless revisions without extra pay.",
                raw_text=scope.raw_text,
                recommendation="Limit included revisions to 2 rounds, with additional rounds billed at your hourly rate."
            ))

    # 5. Termination & Compensation
    term = schema.termination
    if term.present:
        if term.payment_for_completed_milestones_guaranteed is False:
            risks.append(RiskItem(
                clause_id="termination_unpaid_work",
                clause_name="Uncompensated Work on Termination",
                severity=Severity.HIGH,
                title="No Guarantee of Payment for Work Done Prior to Termination",
                explanation="The client may terminate without being explicitly obligated to compensate for partially completed milestones.",
                raw_text=term.raw_text,
                recommendation="Specify that all work performed and hours expended up to the date of notice must be paid in full."
            ))

    return risks
