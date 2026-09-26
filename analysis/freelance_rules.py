"""Deterministic risk rules for Freelance and Independent Contractor Agreements.

Guards independent creators and gig workers against unpaid IP transfer, scope creep, and non-payment.
Each rule is implemented as an independent pure function returning Optional[Severity].
"""

from __future__ import annotations

from typing import List, Optional
from core.config import (
    settings,
    FreelanceThresholds,
    FREELANCE_PAYMENT_TERM_EXTENDED_DAYS,
    FREELANCE_PAYMENT_TERM_STANDARD_DAYS,
    FREELANCE_MAX_INCLUDED_REVISIONS,
)
from output.models import RiskItem, Severity
from schemas.freelance import FreelanceContractSchema


# ==============================================================================
# Pure Rule Evaluation Functions
# ==============================================================================

def evaluate_ip_transfer_risk(
    transfers_before_full_payment: Optional[bool],
    timing_of_transfer: Optional[str] = None,
    ip_present: bool = True,
) -> Optional[Severity]:
    """Pure rule function evaluating premature intellectual property transfer risk.

    - HIGH if transfers_before_full_payment is True or timing is 'creation', 'delivery', or 'signing'
    - None if conditioned on full payment or IP clause not present
    """
    if not ip_present:
        return None

    timing = (timing_of_transfer or "").lower()
    premature = (
        transfers_before_full_payment is True
        or "creation" in timing
        or "delivery" in timing
        or "signing" in timing
    )
    if premature:
        return Severity.HIGH
    return None


def evaluate_portfolio_rights_risk(
    portfolio_rights_retained: Optional[bool],
    ip_present: bool = True,
) -> Optional[Severity]:
    """Pure rule function evaluating portfolio display rights retention.

    - LOW if portfolio_rights_retained is False
    - None otherwise
    """
    if not ip_present or portfolio_rights_retained is not False:
        return None
    return Severity.LOW


def evaluate_payment_term_risk(
    net_days: Optional[int],
    payment_present: bool = True,
    cfg: Optional[FreelanceThresholds] = None,
) -> Optional[Severity]:
    """Pure rule function evaluating invoice payment window (net days) risk.

    - HIGH if net_days > extended_payment_term_days (default 45 days)
    - MEDIUM if net_days > max_payment_term_days (default 30 days)
    - None if net_days <= max_payment_term_days or payment terms not present
    """
    if not payment_present or net_days is None:
        return None

    thresholds = cfg or settings.freelance
    if net_days > thresholds.extended_payment_term_days:
        return Severity.HIGH
    elif net_days > thresholds.max_payment_term_days:
        return Severity.MEDIUM
    return None


def evaluate_late_payment_penalty_risk(
    has_late_payment_clause: Optional[bool],
    payment_present: bool = True,
    cfg: Optional[FreelanceThresholds] = None,
) -> Optional[Severity]:
    """Pure rule function evaluating presence of late payment penalty/interest clause.

    - MEDIUM if require_late_payment_penalty is True and has_late_payment_clause is False
    - None otherwise
    """
    if not payment_present:
        return None

    thresholds = cfg or settings.freelance
    if thresholds.require_late_payment_penalty and has_late_payment_clause is False:
        return Severity.MEDIUM
    return None


def evaluate_kill_fee_risk(
    kill_fee_defined: Optional[bool],
    kill_fee_present: bool = True,
    cfg: Optional[FreelanceThresholds] = None,
) -> Optional[Severity]:
    """Pure rule function evaluating presence of kill fee on client cancellation.

    - HIGH if require_kill_fee is True and kill_fee_defined is False
    - None otherwise
    """
    if not kill_fee_present:
        return None

    thresholds = cfg or settings.freelance
    if thresholds.require_kill_fee and kill_fee_defined is False:
        return Severity.HIGH
    return None


def evaluate_open_ended_scope_risk(
    open_ended_scope: Optional[bool],
    scope_present: bool = True,
) -> Optional[Severity]:
    """Pure rule function evaluating vague or open-ended scope of work.

    - HIGH if open_ended_scope is True
    - None otherwise
    """
    if not scope_present or not open_ended_scope:
        return None
    return Severity.HIGH


def evaluate_revision_limit_risk(
    revision_limit_count: Optional[int],
    scope_present: bool = True,
    cfg: Optional[FreelanceThresholds] = None,
) -> Optional[Severity]:
    """Pure rule function evaluating revision iteration limit.

    - MEDIUM if revision_limit_count is None or revision_limit_count > max_included_revisions (default 3)
    - None if revision_limit_count <= max_included_revisions
    """
    if not scope_present:
        return None

    thresholds = cfg or settings.freelance
    if revision_limit_count is None or revision_limit_count > thresholds.max_included_revisions:
        return Severity.MEDIUM
    return None


def evaluate_termination_unpaid_work_risk(
    payment_for_completed_milestones_guaranteed: Optional[bool],
    termination_present: bool = True,
) -> Optional[Severity]:
    """Pure rule function evaluating compensation guarantee for completed milestones upon early termination.

    - HIGH if payment_for_completed_milestones_guaranteed is False
    - None otherwise
    """
    if not termination_present or payment_for_completed_milestones_guaranteed is not False:
        return None
    return Severity.HIGH


# ==============================================================================
# Full Schema Deterministic Rule Engine
# ==============================================================================

def evaluate_freelance_rules(
    schema: FreelanceContractSchema,
    cfg: Optional[FreelanceThresholds] = None,
) -> List[RiskItem]:
    """Execute all deterministic rules against a freelance contract schema.

    Args:
        schema: Validated FreelanceContractSchema instance.
        cfg: Optional custom FreelanceThresholds (defaults to settings.freelance).

    Returns:
        List of identified RiskItem instances.
    """
    risks: List[RiskItem] = []
    thresholds = cfg or settings.freelance

    # 1. IP Assignment Timing
    ip = schema.ip_assignment
    ip_severity = evaluate_ip_transfer_risk(
        transfers_before_full_payment=ip.transfers_before_full_payment,
        timing_of_transfer=ip.timing_of_transfer,
        ip_present=ip.present,
    )
    if ip_severity is not None:
        risks.append(RiskItem(
            clause_id="ip_premature_transfer",
            clause_name="IP Transfer Prior to Full Payment",
            severity=ip_severity,
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

    portfolio_severity = evaluate_portfolio_rights_risk(
        portfolio_rights_retained=ip.portfolio_rights_retained,
        ip_present=ip.present,
    )
    if portfolio_severity is not None:
        risks.append(RiskItem(
            clause_id="ip_portfolio_prohibition",
            clause_name="Portfolio Display Rights Barred",
            severity=portfolio_severity,
            title="Barred From Displaying Work in Professional Portfolio",
            explanation="You are prohibited from showcasing non-confidential deliverables in your professional portfolio.",
            raw_text=ip.raw_text,
            recommendation="Request a standard carve-out permitting self-promotional portfolio display after public launch."
        ))

    # 2. Payment Terms & Penalties
    pay = schema.payment_terms
    pay_severity = evaluate_payment_term_risk(
        net_days=pay.net_days,
        payment_present=pay.present,
        cfg=thresholds,
    )
    if pay_severity == Severity.HIGH and pay.net_days:
        risks.append(RiskItem(
            clause_id="payment_delayed_net",
            clause_name="Extended Payment Terms",
            severity=Severity.HIGH,
            title=f"Excessive Payment Window (Net {pay.net_days} Days)",
            explanation=(
                f"A payment window of Net {pay.net_days} is punitive for independent contractors, forcing you to float business expenses "
                "for months after delivering work."
            ),
            raw_text=pay.raw_text,
            recommendation="Negotiate Net 15 or Net 30 payment terms, coupled with a 50% upfront commencement deposit."
        ))
    elif pay_severity == Severity.MEDIUM and pay.net_days:
        risks.append(RiskItem(
            clause_id="payment_moderate_net",
            clause_name="Moderate Payment Terms",
            severity=Severity.MEDIUM,
            title=f"Net {pay.net_days} Payment Window",
            explanation=f"Payment terms of Net {pay.net_days} exceed standard contractor expectations of Net 15–30.",
            raw_text=pay.raw_text,
            recommendation="Request milestone-based payments upon specific deliverable completions."
        ))

    late_fee_severity = evaluate_late_payment_penalty_risk(
        has_late_payment_clause=pay.has_late_payment_clause,
        payment_present=pay.present,
        cfg=thresholds,
    )
    if late_fee_severity is not None:
        risks.append(RiskItem(
            clause_id="payment_late_interest",
            clause_name="Missing Late Payment Protection",
            severity=late_fee_severity,
            title="No Late Payment Penalty or Interest Clause",
            explanation="The contract provides zero penalty or interest if the client delays paying invoices indefinitely.",
            raw_text=pay.raw_text,
            recommendation="Add a standard late fee clause: 1.5% monthly statutory interest on all invoices overdue past 30 days."
        ))

    # 3. Kill Fee & Cancellation
    kill = schema.kill_fee
    kill_severity = evaluate_kill_fee_risk(
        kill_fee_defined=kill.kill_fee_defined,
        kill_fee_present=kill.present,
        cfg=thresholds,
    )
    if kill_severity is not None:
        risks.append(RiskItem(
            clause_id="kill_fee_absent",
            clause_name="Missing Kill Fee Protection",
            severity=kill_severity,
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
    open_scope_severity = evaluate_open_ended_scope_risk(
        open_ended_scope=scope.open_ended_scope,
        scope_present=scope.present,
    )
    if open_scope_severity is not None:
        risks.append(RiskItem(
            clause_id="scope_open_ended",
            clause_name="Open-Ended Scope of Work",
            severity=open_scope_severity,
            title="Uncapped / Open-Ended Scope of Work",
            explanation=(
                "The scope of duties is vaguely worded ('as needed' or 'other duties as assigned') without finite deliverables. "
                "This is the single most common cause of unpaid scope creep."
            ),
            raw_text=scope.raw_text,
            recommendation="Replace generic wording with an explicit Statement of Work (SOW) detailing exact deliverables."
        ))

    revision_severity = evaluate_revision_limit_risk(
        revision_limit_count=scope.revision_limit_count,
        scope_present=scope.present,
        cfg=thresholds,
    )
    if revision_severity is not None:
        risks.append(RiskItem(
            clause_id="scope_unlimited_revisions",
            clause_name="Uncapped Revision Rounds",
            severity=revision_severity,
            title="Unlimited or Ambiguous Revision Rounds",
            explanation="The agreement lacks a cap on client review iterations, risking endless revisions without extra pay.",
            raw_text=scope.raw_text,
            recommendation="Limit included revisions to 2 rounds, with additional rounds billed at your hourly rate."
        ))

    # 5. Termination & Compensation
    term = schema.termination
    term_severity = evaluate_termination_unpaid_work_risk(
        payment_for_completed_milestones_guaranteed=term.payment_for_completed_milestones_guaranteed,
        termination_present=term.present,
    )
    if term_severity is not None:
        risks.append(RiskItem(
            clause_id="termination_unpaid_work",
            clause_name="Uncompensated Work on Termination",
            severity=term_severity,
            title="No Guarantee of Payment for Work Done Prior to Termination",
            explanation="The client may terminate without being explicitly obligated to compensate for partially completed milestones.",
            raw_text=term.raw_text,
            recommendation="Specify that all work performed and hours expended up to the date of notice must be paid in full."
        ))

    return risks
