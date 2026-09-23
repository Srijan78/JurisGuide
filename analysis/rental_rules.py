"""Deterministic risk rules for Rental and Residential Lease Agreements.

Evaluates structured lease data against real-world tenant rights norms.
"""

from __future__ import annotations

from typing import List
from core.config import settings
from output.models import RiskItem, Severity
from schemas.rental import RentalAgreementSchema


def evaluate_rental_rules(schema: RentalAgreementSchema) -> List[RiskItem]:
    """Execute all deterministic rules against a rental agreement schema.

    Args:
        schema: Validated RentalAgreementSchema instance.

    Returns:
        List of identified RiskItem instances.
    """
    risks: List[RiskItem] = []
    cfg = settings.rental

    # 1. Security Deposit
    dep = schema.security_deposit
    rent = schema.monthly_rent

    calc_deposit_months = dep.deposit_months
    if not calc_deposit_months and dep.amount and rent.monthly_amount and rent.monthly_amount > 0:
        calc_deposit_months = dep.amount / rent.monthly_amount

    if dep.present and calc_deposit_months:
        if calc_deposit_months > cfg.max_security_deposit_months:
            risks.append(RiskItem(
                clause_id="deposit_excessive",
                clause_name="Security Deposit Amount",
                severity=Severity.HIGH,
                title=f"Excessive Security Deposit ({calc_deposit_months:.1f} Months Rent)",
                explanation=(
                    f"The required security deposit equals {calc_deposit_months:.1f} months of rent, "
                    f"substantially higher than typical residential caps of {cfg.max_security_deposit_months} months. "
                    "Large deposits increase tenant financial exposure if the landlord disputes wear-and-tear."
                ),
                raw_text=dep.raw_text,
                recommendation="Negotiate capping deposit to 2–3 months rent, or request depositing in an escrow account."
            ))
        elif calc_deposit_months > 3:
            risks.append(RiskItem(
                clause_id="deposit_moderate",
                clause_name="Elevated Security Deposit",
                severity=Severity.MEDIUM,
                title=f"Substantial Security Deposit ({calc_deposit_months:.1f} Months Rent)",
                explanation=f"A {calc_deposit_months:.1f}-month deposit locks up significant liquidity.",
                raw_text=dep.raw_text,
                recommendation="Ensure the agreement has crystal-clear itemized deduction and refund conditions."
            ))

    if dep.present and dep.refund_timeline_days and dep.refund_timeline_days > 30:
        risks.append(RiskItem(
            clause_id="deposit_refund_timeline",
            clause_name="Delayed Deposit Refund",
            severity=Severity.MEDIUM,
            title=f"Delayed Deposit Refund Timeline ({dep.refund_timeline_days} Days)",
            explanation=(
                f"Landlord has {dep.refund_timeline_days} days after keys are returned to refund the deposit. "
                "Standard residential practice requires inspection and refund within 7–14 days."
            ),
            raw_text=dep.raw_text,
            recommendation="Request reducing the refund turnaround to 7 to 10 days post-inspection."
        ))

    # 2. Lock-In Period & Forfeiture
    lock = schema.lock_in
    if lock.present:
        if lock.duration_months and lock.duration_months > cfg.max_lock_in_months:
            risks.append(RiskItem(
                clause_id="lock_in_duration",
                clause_name="Excessive Lock-in Period",
                severity=Severity.HIGH,
                title=f"Lock-In Exceeds Standard Norm ({lock.duration_months} Months)",
                explanation=(
                    f"The lock-in period of {lock.duration_months} months exceeds the standard 11-month lease convention. "
                    "If you are relocated or have personal emergencies, you may be held liable for the entire term's rent."
                ),
                raw_text=lock.raw_text,
                recommendation="Ask for a standard 3 to 6-month lock-in with an emergency relocation breakout clause."
            ))

        if lock.forfeits_entire_deposit_on_early_exit:
            risks.append(RiskItem(
                clause_id="lock_in_forfeiture",
                clause_name="Total Deposit Forfeit for Early Exit",
                severity=Severity.HIGH,
                title="Total Forfeiture of Deposit on Early Vacation",
                explanation=(
                    "The contract allows the landlord to seize 100% of your deposit if you vacate before the lock-in ends, "
                    "regardless of whether a replacement tenant is found or proper notice was served."
                ),
                raw_text=lock.raw_text,
                recommendation="Limit early exit liability to 1 month's rent or until a new replacement tenant moves in."
            ))

    # 3. Maintenance & Repair Duties
    maint = schema.maintenance
    if maint.present:
        if maint.tenant_bears_structural_repairs:
            risks.append(RiskItem(
                clause_id="maintenance_structural",
                clause_name="Structural Maintenance on Tenant",
                severity=Severity.HIGH,
                title="Tenant Liable for Structural and Major Repairs",
                explanation=(
                    "The lease shifts responsibility for structural repairs (e.g. wall seepage, roof leaks, plumbing mains) "
                    "onto the tenant. By law and custom, capital repairs are the sole responsibility of property owners."
                ),
                raw_text=maint.raw_text,
                recommendation="Explicitly exclude structural, electrical conduit, and foundational repairs from tenant obligations."
            ))

    # 4. Rent Escalation
    esc = schema.rent_escalation
    if esc.present:
        if esc.escalation_pct and esc.escalation_pct > cfg.max_annual_escalation_pct:
            risks.append(RiskItem(
                clause_id="escalation_rate",
                clause_name="High Rent Escalation",
                severity=Severity.MEDIUM,
                title=f"Steep Rent Escalation Rate ({esc.escalation_pct:.1f}% Increase)",
                explanation=(
                    f"The lease mandates an annual increase of {esc.escalation_pct:.1f}%, exceeding the typical "
                    f"residential market baseline of {cfg.max_annual_escalation_pct:.1f}%."
                ),
                raw_text=esc.raw_text,
                recommendation=f"Negotiate tying escalation to 5%–7% or prevailing inflation."
            ))

    # 5. Notice Period & Asymmetry
    notc = schema.notice_period
    if notc.present:
        t_days = notc.tenant_notice_days
        l_days = notc.landlord_notice_days

        if t_days and l_days and l_days > 0 and (t_days / l_days) >= cfg.max_notice_asymmetry_ratio:
            risks.append(RiskItem(
                clause_id="notice_rental_asymmetry",
                clause_name="Rental Notice Asymmetry",
                severity=Severity.HIGH,
                title=f"Unfair Notice Asymmetry ({t_days}d Tenant vs {l_days}d Landlord)",
                explanation=f"Tenant must give {t_days} days notice while landlord can terminate in {l_days} days.",
                raw_text=notc.raw_text,
                recommendation="Set equal notice periods (e.g., 30 days for both parties)."
            ))

    return risks
