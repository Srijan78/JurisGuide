"""Deterministic risk rules for Rental and Residential Lease Agreements.

Evaluates structured lease data against real-world tenant rights norms.
Each rule is implemented as an independent pure function returning Optional[Severity].
"""

from __future__ import annotations

from typing import List, Optional
from core.config import (
    settings,
    RentalThresholds,
    RENTAL_DEPOSIT_HIGH_MONTHS,
    RENTAL_DEPOSIT_MEDIUM_MONTHS,
    RENTAL_REFUND_MAX_DAYS,
    RENTAL_LOCK_IN_MAX_MONTHS,
    RENTAL_ESCALATION_MAX_PCT,
    RENTAL_MIN_TENANT_NOTICE_DAYS,
    RENTAL_MAX_NOTICE_ASYMMETRY_RATIO,
)
from output.models import RiskItem, Severity
from schemas.rental import RentalAgreementSchema


# ==============================================================================
# Pure Rule Evaluation Functions
# ==============================================================================

def evaluate_deposit_amount_risk(
    deposit_months: Optional[float],
    deposit_amount: Optional[float] = None,
    monthly_rent: Optional[float] = None,
    deposit_present: bool = True,
    cfg: Optional[RentalThresholds] = None,
) -> Optional[Severity]:
    """Pure rule function evaluating security deposit magnitude risk.

    - HIGH if deposit exceeds max_security_deposit_months (default 6)
    - MEDIUM if deposit exceeds moderate_security_deposit_months (default 3)
    - None if <= moderate_security_deposit_months or deposit not present
    """
    if not deposit_present:
        return None

    calc_deposit_months = deposit_months
    if not calc_deposit_months and deposit_amount and monthly_rent and monthly_rent > 0:
        calc_deposit_months = deposit_amount / monthly_rent

    if calc_deposit_months is None:
        return None

    thresholds = cfg or settings.rental
    if calc_deposit_months > thresholds.max_security_deposit_months:
        return Severity.HIGH
    elif calc_deposit_months > thresholds.moderate_security_deposit_months:
        return Severity.MEDIUM
    return None


def evaluate_deposit_refund_risk(
    refund_timeline_days: Optional[int],
    deposit_present: bool = True,
    cfg: Optional[RentalThresholds] = None,
) -> Optional[Severity]:
    """Pure rule function evaluating deposit refund turnaround timeline risk.

    - MEDIUM if refund_timeline_days exceeds max_deposit_refund_days (default 30)
    - None if <= max_deposit_refund_days or deposit not present
    """
    if not deposit_present or refund_timeline_days is None:
        return None

    thresholds = cfg or settings.rental
    if refund_timeline_days > thresholds.max_deposit_refund_days:
        return Severity.MEDIUM
    return None


def evaluate_lock_in_duration_risk(
    duration_months: Optional[int],
    lock_in_present: bool = True,
    cfg: Optional[RentalThresholds] = None,
) -> Optional[Severity]:
    """Pure rule function evaluating mandatory lock-in period duration risk.

    - HIGH if lock-in duration exceeds max_lock_in_months (default 11)
    - None if <= max_lock_in_months or lock-in not present
    """
    if not lock_in_present or duration_months is None:
        return None

    thresholds = cfg or settings.rental
    if duration_months > thresholds.max_lock_in_months:
        return Severity.HIGH
    return None


def evaluate_lock_in_forfeiture_risk(
    forfeits_entire_deposit_on_early_exit: Optional[bool],
    lock_in_present: bool = True,
) -> Optional[Severity]:
    """Pure rule function evaluating total deposit forfeiture for early lease vacation.

    - HIGH if forfeits_entire_deposit_on_early_exit is True
    - None otherwise
    """
    if not lock_in_present or not forfeits_entire_deposit_on_early_exit:
        return None
    return Severity.HIGH


def evaluate_structural_maintenance_risk(
    tenant_bears_structural_repairs: Optional[bool],
    maintenance_present: bool = True,
) -> Optional[Severity]:
    """Pure rule function evaluating structural repair liability shift onto tenant.

    - HIGH if tenant_bears_structural_repairs is True
    - None otherwise
    """
    if not maintenance_present or not tenant_bears_structural_repairs:
        return None
    return Severity.HIGH


def evaluate_rent_escalation_risk(
    escalation_pct: Optional[float],
    escalation_present: bool = True,
    cfg: Optional[RentalThresholds] = None,
) -> Optional[Severity]:
    """Pure rule function evaluating annual rent increase percentage.

    - MEDIUM if escalation_pct exceeds max_annual_escalation_pct (default 10.0%)
    - None if <= max_annual_escalation_pct or escalation not present
    """
    if not escalation_present or escalation_pct is None:
        return None

    thresholds = cfg or settings.rental
    if escalation_pct > thresholds.max_annual_escalation_pct:
        return Severity.MEDIUM
    return None


def evaluate_rental_notice_asymmetry_risk(
    tenant_notice_days: Optional[int],
    landlord_notice_days: Optional[int],
    notice_present: bool = True,
    cfg: Optional[RentalThresholds] = None,
) -> Optional[Severity]:
    """Pure rule function evaluating notice period asymmetry between tenant and landlord.

    Wired directly to RentalThresholds.min_tenant_notice_days and max_notice_asymmetry_ratio:
    - HIGH if:
        * landlord_notice_days == 0 and tenant_notice_days >= min_tenant_notice_days
        * OR (tenant_notice_days / landlord_notice_days) >= max_notice_asymmetry_ratio
        * OR landlord_notice_days < min_tenant_notice_days and tenant_notice_days >= min_tenant_notice_days
    - MEDIUM if:
        * landlord_notice_days < min_tenant_notice_days and tenant_notice_days > landlord_notice_days
        * OR (tenant_notice_days / landlord_notice_days) > 1.0
    - None if balanced (tenant_notice_days <= landlord_notice_days and landlord_notice_days >= min_tenant_notice_days)
    """
    if not notice_present:
        return None

    if tenant_notice_days is None and landlord_notice_days is None:
        return None

    thresholds = cfg or settings.rental
    t_days = tenant_notice_days
    l_days = landlord_notice_days

    # Extreme asymmetry: Landlord can terminate with 0 notice while tenant has standard notice
    if (l_days == 0 or l_days is None) and t_days is not None and t_days >= thresholds.min_tenant_notice_days:
        return Severity.HIGH

    if t_days is not None and l_days is not None and l_days > 0:
        ratio = t_days / l_days
        if ratio >= thresholds.max_notice_asymmetry_ratio:
            return Severity.HIGH
        if l_days < thresholds.min_tenant_notice_days and t_days >= thresholds.min_tenant_notice_days:
            return Severity.HIGH
        if ratio > 1.0 or l_days < thresholds.min_tenant_notice_days:
            return Severity.MEDIUM

    return None


# ==============================================================================
# Full Schema Deterministic Rule Engine
# ==============================================================================

def evaluate_rental_rules(
    schema: RentalAgreementSchema,
    cfg: Optional[RentalThresholds] = None,
) -> List[RiskItem]:
    """Execute all deterministic rules against a rental agreement schema.

    Args:
        schema: Validated RentalAgreementSchema instance.
        cfg: Optional custom RentalThresholds (defaults to settings.rental).

    Returns:
        List of identified RiskItem instances.
    """
    risks: List[RiskItem] = []
    thresholds = cfg or settings.rental

    # 1. Security Deposit
    dep = schema.security_deposit
    rent = schema.monthly_rent

    calc_deposit_months = dep.deposit_months
    if not calc_deposit_months and dep.amount and rent.monthly_amount and rent.monthly_amount > 0:
        calc_deposit_months = dep.amount / rent.monthly_amount

    dep_severity = evaluate_deposit_amount_risk(
        deposit_months=dep.deposit_months,
        deposit_amount=dep.amount,
        monthly_rent=rent.monthly_amount,
        deposit_present=dep.present,
        cfg=thresholds,
    )
    if dep_severity == Severity.HIGH and calc_deposit_months:
        risks.append(RiskItem(
            clause_id="deposit_excessive",
            clause_name="Security Deposit Amount",
            severity=Severity.HIGH,
            title=f"Excessive Security Deposit ({calc_deposit_months:.1f} Months Rent)",
            explanation=(
                f"The required security deposit equals {calc_deposit_months:.1f} months of rent, "
                f"substantially higher than typical residential caps of {thresholds.max_security_deposit_months} months. "
                "Large deposits increase tenant financial exposure if the landlord disputes wear-and-tear."
            ),
            raw_text=dep.raw_text,
            recommendation="Negotiate capping deposit to 2–3 months rent, or request depositing in an escrow account."
        ))
    elif dep_severity == Severity.MEDIUM and calc_deposit_months:
        risks.append(RiskItem(
            clause_id="deposit_moderate",
            clause_name="Elevated Security Deposit",
            severity=Severity.MEDIUM,
            title=f"Substantial Security Deposit ({calc_deposit_months:.1f} Months Rent)",
            explanation=f"A {calc_deposit_months:.1f}-month deposit locks up significant liquidity.",
            raw_text=dep.raw_text,
            recommendation="Ensure the agreement has crystal-clear itemized deduction and refund conditions."
        ))

    refund_severity = evaluate_deposit_refund_risk(
        refund_timeline_days=dep.refund_timeline_days,
        deposit_present=dep.present,
        cfg=thresholds,
    )
    if refund_severity is not None and dep.refund_timeline_days:
        risks.append(RiskItem(
            clause_id="deposit_refund_timeline",
            clause_name="Delayed Deposit Refund",
            severity=refund_severity,
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
    lock_dur_severity = evaluate_lock_in_duration_risk(
        duration_months=lock.duration_months,
        lock_in_present=lock.present,
        cfg=thresholds,
    )
    if lock_dur_severity is not None and lock.duration_months:
        risks.append(RiskItem(
            clause_id="lock_in_duration",
            clause_name="Excessive Lock-in Period",
            severity=lock_dur_severity,
            title=f"Lock-In Exceeds Standard Norm ({lock.duration_months} Months)",
            explanation=(
                f"The lock-in period of {lock.duration_months} months exceeds the standard {thresholds.max_lock_in_months}-month lease convention. "
                "If you are relocated or have personal emergencies, you may be held liable for the entire term's rent."
            ),
            raw_text=lock.raw_text,
            recommendation="Ask for a standard 3 to 6-month lock-in with an emergency relocation breakout clause."
        ))

    lock_forfeit_severity = evaluate_lock_in_forfeiture_risk(
        forfeits_entire_deposit_on_early_exit=lock.forfeits_entire_deposit_on_early_exit,
        lock_in_present=lock.present,
    )
    if lock_forfeit_severity is not None:
        risks.append(RiskItem(
            clause_id="lock_in_forfeiture",
            clause_name="Total Deposit Forfeit for Early Exit",
            severity=lock_forfeit_severity,
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
    maint_severity = evaluate_structural_maintenance_risk(
        tenant_bears_structural_repairs=maint.tenant_bears_structural_repairs,
        maintenance_present=maint.present,
    )
    if maint_severity is not None:
        risks.append(RiskItem(
            clause_id="maintenance_structural",
            clause_name="Structural Maintenance on Tenant",
            severity=maint_severity,
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
    esc_severity = evaluate_rent_escalation_risk(
        escalation_pct=esc.escalation_pct,
        escalation_present=esc.present,
        cfg=thresholds,
    )
    if esc_severity is not None and esc.escalation_pct:
        risks.append(RiskItem(
            clause_id="escalation_rate",
            clause_name="High Rent Escalation",
            severity=esc_severity,
            title=f"Steep Rent Escalation Rate ({esc.escalation_pct:.1f}% Increase)",
            explanation=(
                f"The lease mandates an annual increase of {esc.escalation_pct:.1f}%, exceeding the typical "
                f"residential market baseline of {thresholds.max_annual_escalation_pct:.1f}%."
            ),
            raw_text=esc.raw_text,
            recommendation="Negotiate tying escalation to 5%–7% or prevailing inflation."
        ))

    # 5. Notice Period & Asymmetry
    notc = schema.notice_period
    notice_severity = evaluate_rental_notice_asymmetry_risk(
        tenant_notice_days=notc.tenant_notice_days,
        landlord_notice_days=notc.landlord_notice_days,
        notice_present=notc.present,
        cfg=thresholds,
    )
    if notice_severity is not None:
        t_days = notc.tenant_notice_days
        l_days = notc.landlord_notice_days
        risks.append(RiskItem(
            clause_id="notice_rental_asymmetry",
            clause_name="Rental Notice Asymmetry",
            severity=notice_severity,
            title=f"Unfair Notice Asymmetry ({t_days}d Tenant vs {l_days}d Landlord)",
            explanation=f"Tenant must give {t_days} days notice while landlord can terminate in {l_days} days.",
            raw_text=notc.raw_text,
            recommendation="Set equal notice periods (e.g., 30 days for both parties)."
        ))

    return risks
