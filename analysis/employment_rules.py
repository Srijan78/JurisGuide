"""Deterministic risk rules for Employment Offer Letters.

Evaluates structured data against objective 3-tier threshold rules (HIGH/MEDIUM/LOW/NONE).
No LLM calls or hallucinations involved.
"""

from __future__ import annotations

from typing import List, Optional
from core.config import (
    settings,
    BOND_DURATION_HIGH_MONTHS,
    BOND_DURATION_MEDIUM_MONTHS,
    BOND_SALARY_MULTIPLE_HIGH,
    BOND_SALARY_MULTIPLE_MEDIUM,
    NOTICE_ASYMMETRY_EMPLOYEE_MIN_DAYS_HIGH,
    NOTICE_ASYMMETRY_GAP_MEDIUM_DAYS,
    MAX_NOTICE_PERIOD_DAYS,
    NON_COMPETE_DURATION_HIGH_MONTHS,
    NON_COMPETE_DURATION_MEDIUM_MONTHS,
    NON_COMPETE_BROAD_SCOPES,
)
from output.models import RiskItem, Severity
from schemas.employment import EmploymentOfferSchema


# ==============================================================================
# Pure Rule Evaluation Functions
# ==============================================================================

def evaluate_bond_duration_risk(
    duration_months: Optional[int],
    bond_present: bool = True
) -> Optional[Severity]:
    """Pure rule function evaluating service bond duration risk.

    - HIGH if duration > 24 months
    - MEDIUM if 12 <= duration <= 24 months
    - LOW if duration < 12 months (still flagged as present, just low severity)
    - None if bond not present or duration is None
    """
    if not bond_present or duration_months is None:
        return None
    if duration_months > BOND_DURATION_HIGH_MONTHS:
        return Severity.HIGH
    elif duration_months >= BOND_DURATION_MEDIUM_MONTHS:
        return Severity.MEDIUM
    else:
        return Severity.LOW


def evaluate_bond_amount_risk(
    bond_amount: Optional[float],
    monthly_salary: Optional[float] = None,
    bond_present: bool = True
) -> Optional[Severity]:
    """Pure rule function evaluating service bond financial penalty risk.

    - HIGH if amount > 6x monthly salary
    - MEDIUM if 3x <= amount <= 6x monthly salary
    - LOW if amount < 3x but bond is present
    - None if bond not present or bond amount is None
    """
    if not bond_present or bond_amount is None:
        return None
    if monthly_salary is not None and monthly_salary > 0:
        ratio = bond_amount / monthly_salary
        if ratio > BOND_SALARY_MULTIPLE_HIGH:
            return Severity.HIGH
        elif ratio >= BOND_SALARY_MULTIPLE_MEDIUM:
            return Severity.MEDIUM
        else:
            return Severity.LOW
    # If bond amount is present without salary context, flag as moderate risk
    return Severity.MEDIUM


def evaluate_notice_asymmetry_risk(
    employee_notice_days: Optional[int],
    employer_notice_days: Optional[int],
    notice_present: bool = True
) -> Optional[Severity]:
    """Pure rule function evaluating notice period asymmetry between employee and employer.

    - HIGH if employer notice == 0 AND employee notice >= 60
    - MEDIUM if gap between employee and employer notice >= 30 days (and not already HIGH)
    - LOW if 0 < gap < 30 days
    - None (no flag) if gap <= 0 or notice is not present or missing notice days
    """
    if not notice_present or employee_notice_days is None or employer_notice_days is None:
        return None

    # HIGH if employer notice == 0 AND employee notice >= 60
    if employer_notice_days == 0 and employee_notice_days >= NOTICE_ASYMMETRY_EMPLOYEE_MIN_DAYS_HIGH:
        return Severity.HIGH

    gap = employee_notice_days - employer_notice_days
    # MEDIUM if gap between employee and employer notice >= 30 days (and not already HIGH)
    if gap >= NOTICE_ASYMMETRY_GAP_MEDIUM_DAYS:
        return Severity.MEDIUM
    elif gap > 0:
        return Severity.LOW
    else:
        return None


def is_broad_non_compete_scope(
    geographic_scope: Optional[str] = None,
    industry_scope: Optional[str] = None
) -> bool:
    """Helper checking if non-compete geographic or industry scope is overly broad."""
    text = f"{geographic_scope or ''} {industry_scope or ''}".lower()
    return any(keyword in text for keyword in NON_COMPETE_BROAD_SCOPES)


def evaluate_non_compete_risk(
    duration_months: Optional[int],
    geographic_scope: Optional[str] = None,
    industry_scope: Optional[str] = None,
    non_compete_present: bool = True
) -> Optional[Severity]:
    """Pure rule function evaluating post-employment non-compete covenants.

    - HIGH if duration > 12 months OR scope is "any industry" / nationwide / worldwide
    - MEDIUM if 6 <= duration <= 12 months and scope is reasonably bounded (same city/region, same industry)
    - LOW if duration < 6 months (and scope not broad)
    - None if non-compete is not present or neither duration nor scope is defined
    """
    if not non_compete_present:
        return None
    if duration_months is None and geographic_scope is None and industry_scope is None:
        return None

    broad_scope = is_broad_non_compete_scope(geographic_scope, industry_scope)

    # HIGH if duration > 12 months OR scope is broad
    if (duration_months is not None and duration_months > NON_COMPETE_DURATION_HIGH_MONTHS) or broad_scope:
        return Severity.HIGH

    if duration_months is not None:
        if duration_months >= NON_COMPETE_DURATION_MEDIUM_MONTHS:
            return Severity.MEDIUM
        else:
            return Severity.LOW

    return None


def evaluate_probation_termination_risk(
    immediate_termination_allowed: Optional[bool] = None,
    cause_required: Optional[bool] = None,
    notice_days: Optional[int] = None,
    probation_present: bool = True
) -> Optional[Severity]:
    """Pure rule function evaluating termination terms during probation.

    - HIGH if termination allowed with 0 days notice AND no stated cause requirement
    - MEDIUM if termination allowed with 0 days notice BUT a cause/reason is required
    - LOW if notice period exists during probation without documented cause requirement
    - None (no flag) if both notice period AND documented cause exist, or probation not present
    """
    if not probation_present:
        return None

    if immediate_termination_allowed is None and cause_required is None and notice_days is None:
        return None

    is_zero_notice = (immediate_termination_allowed is True) or (notice_days == 0)

    if is_zero_notice:
        if not cause_required:
            return Severity.HIGH
        else:
            return Severity.MEDIUM
    else:
        # Notice period exists during probation
        if not cause_required:
            return Severity.LOW
        else:
            return None


# ==============================================================================
# Full Schema Deterministic Rule Engine
# ==============================================================================

def evaluate_employment_rules(schema: EmploymentOfferSchema) -> List[RiskItem]:
    """Execute all deterministic rules against an employment offer schema.

    Args:
        schema: Validated EmploymentOfferSchema instance.

    Returns:
        List of identified RiskItem instances.
    """
    risks: List[RiskItem] = []
    cfg = settings.employment

    # 1. Bond / Training Cost Evaluation
    bond = schema.bond
    if bond.present:
        # Bond duration rule
        bond_dur_severity = evaluate_bond_duration_risk(bond.duration_months, bond.present)
        if bond_dur_severity is not None:
            if bond_dur_severity == Severity.HIGH:
                title = f"Excessive Service Bond ({bond.duration_months} Months)"
                explanation = (
                    f"The contract imposes a mandatory service bond of {bond.duration_months} months, "
                    f"exceeding the high-risk threshold of {BOND_DURATION_HIGH_MONTHS} months. "
                    "In many jurisdictions, prolonged employment bonds are legally contentious as restraint of trade."
                )
                rec = "Request reducing the bond period or removing the penalty clause altogether."
            elif bond_dur_severity == Severity.MEDIUM:
                title = f"Moderate Service Bond Commitment ({bond.duration_months} Months)"
                explanation = (
                    f"The contract requires a service bond of {bond.duration_months} months (within the {BOND_DURATION_MEDIUM_MONTHS} "
                    f"to {BOND_DURATION_HIGH_MONTHS} months band). While common, it restricts early mobility."
                )
                rec = "Negotiate a pro-rated tapering of the bond obligation over time."
            else:  # LOW
                title = f"Short-Term Service Bond ({bond.duration_months} Months)"
                explanation = (
                    f"The service bond commitment is {bond.duration_months} months (< {BOND_DURATION_MEDIUM_MONTHS} months). "
                    "This is considered low severity, but still represents a contractual commitment."
                )
                rec = "Ensure that bond terms specify pro-rata reduction and clear exit conditions."

            risks.append(RiskItem(
                clause_id="bond_duration",
                clause_name="Service Bond Duration",
                severity=bond_dur_severity,
                title=title,
                explanation=explanation,
                raw_text=bond.raw_text,
                recommendation=rec
            ))

        # Bond penalty amount relative to monthly salary
        monthly_salary = None
        if schema.salary_breakdown.present and schema.salary_breakdown.fixed_amount:
            is_annual = schema.salary_breakdown.period == "annual" or schema.salary_breakdown.fixed_amount > 100_000
            monthly_salary = schema.salary_breakdown.fixed_amount / 12.0 if is_annual else schema.salary_breakdown.fixed_amount

        bond_amt_severity = evaluate_bond_amount_risk(bond.amount, monthly_salary, bond.present)
        if bond_amt_severity is not None:
            ratio = (bond.amount / monthly_salary) if (monthly_salary and monthly_salary > 0 and bond.amount) else None
            currency = schema.salary_breakdown.currency or "INR"

            if bond_amt_severity == Severity.HIGH:
                ratio_str = f" ({ratio:.1f}x Monthly Salary)" if ratio else ""
                title = f"Disproportionate Bond Penalty{ratio_str}"
                explanation = (
                    f"The bond forfeiture sum of {currency} {bond.amount:,.0f}"
                    + (f" equals {ratio:.1f} months of base salary, exceeding the high-risk ceiling of {BOND_SALARY_MULTIPLE_HIGH:.1f}x monthly salary." if ratio else ".")
                    + " Courts typically enforce bonds only up to actual, proven training expenses incurred."
                )
                rec = "Request documentation of actual training expenses incurred and a pro-rated tapering schedule."
            elif bond_amt_severity == Severity.MEDIUM:
                ratio_str = f" ({ratio:.1f}x Monthly Salary)" if ratio else ""
                title = f"Moderate Bond Penalty Amount{ratio_str}"
                explanation = (
                    f"The bond forfeiture sum of {currency} {bond.amount:,.0f}"
                    + (f" equals {ratio:.1f} months of base salary (within the medium band of {BOND_SALARY_MULTIPLE_MEDIUM:.1f}x to {BOND_SALARY_MULTIPLE_HIGH:.1f}x)." if ratio else ".")
                    + " Verify that this reflects justifiable training and onboarding investments."
                )
                rec = "Clarify training cost breakdowns and ask for pro-rata reduction for completed service."
            else:  # LOW
                ratio_str = f" ({ratio:.1f}x Monthly Salary)" if ratio else ""
                title = f"Low Service Bond Penalty{ratio_str}"
                explanation = (
                    f"The bond penalty of {currency} {bond.amount:,.0f}"
                    + (f" is {ratio:.1f}x monthly salary (< {BOND_SALARY_MULTIPLE_MEDIUM:.1f}x base salary)." if ratio else ".")
                    + " While modest, ensure penalty triggers are limited strictly to voluntary early resignation."
                )
                rec = "Confirm that the bond penalty only applies to voluntary resignation and not termination without cause."

            risks.append(RiskItem(
                clause_id="bond_amount",
                clause_name="Service Bond Penalty Amount",
                severity=bond_amt_severity,
                title=title,
                explanation=explanation,
                raw_text=bond.raw_text,
                recommendation=rec
            ))

    # 2. Notice Period & Asymmetry Evaluation
    notice = schema.notice_period
    if notice.present:
        ee_days = notice.employee_notice_days
        er_days = notice.employer_notice_days

        asymmetry_severity = evaluate_notice_asymmetry_risk(ee_days, er_days, notice.present)
        if asymmetry_severity is not None:
            if asymmetry_severity == Severity.HIGH:
                title = f"Extreme Notice Asymmetry ({ee_days}d Employee vs {er_days}d Employer)"
                explanation = (
                    f"You must give {ee_days} days notice to resign, while the employer gives 0 days notice. "
                    "This extreme asymmetry deprives you of income security while binding you to an extended transition."
                )
                rec = "Demand bilateral notice parity or at least 30-60 days employer notice."
            elif asymmetry_severity == Severity.MEDIUM:
                title = f"Unfair Notice Asymmetry ({ee_days}d Employee vs {er_days}d Employer)"
                explanation = (
                    f"You must give {ee_days} days notice to resign, but the employer only needs to give {er_days} days "
                    f"(a gap of {ee_days - er_days} days). One-sided notice periods disadvantage employees during transitions."
                )
                rec = "Ask for bilateral notice parity so both parties are held to the exact same notice period."
            else:  # LOW
                title = f"Minor Notice Gap ({ee_days}d Employee vs {er_days}d Employer)"
                explanation = (
                    f"There is a minor {ee_days - er_days} day difference between employee and employer notice periods."
                )
                rec = "Request standard bilateral parity if possible during contract negotiations."

            risks.append(RiskItem(
                clause_id="notice_asymmetry",
                clause_name="Notice Period Asymmetry",
                severity=asymmetry_severity,
                title=title,
                explanation=explanation,
                raw_text=notice.raw_text,
                recommendation=rec
            ))

        if ee_days and ee_days > cfg.max_notice_period_days:
            risks.append(RiskItem(
                clause_id="notice_duration",
                clause_name="Prolonged Employee Notice Period",
                severity=Severity.MEDIUM,
                title=f"Extended Notice Period ({ee_days} Days)",
                explanation=(
                    f"A {ee_days}-day notice period is notably long and may hinder future job hunting, "
                    "as many prospective employers will not wait 3+ months for a new hire to join."
                ),
                raw_text=notice.raw_text,
                recommendation="Negotiate a standard 30-day notice or confirm an explicit buyout option in writing."
            ))

    # 3. Non-Compete Scope & Duration
    non_compete = schema.non_compete
    if non_compete.present:
        nc_severity = evaluate_non_compete_risk(
            non_compete.duration_months,
            non_compete.geographic_scope,
            non_compete.industry_scope,
            non_compete.present
        )
        if nc_severity is not None:
            dur = non_compete.duration_months
            geo = non_compete.geographic_scope or ""
            ind = non_compete.industry_scope or ""
            broad = is_broad_non_compete_scope(geo, ind)

            if nc_severity == Severity.HIGH:
                reasons = []
                if dur and dur > NON_COMPETE_DURATION_HIGH_MONTHS:
                    reasons.append(f"{dur} months duration")
                if broad:
                    reasons.append(f"broad scope '{geo or ind}'")
                reason_str = f" ({', '.join(reasons)})" if reasons else ""

                title = f"Post-Employment Non-Compete Restriction{reason_str}"
                explanation = (
                    "The non-compete clause imposes severe post-employment restrictions"
                    + (f" lasting {dur} months" if dur else "")
                    + (f" with broad scope '{geo or ind}'." if broad else ".")
                    + " In many jurisdictions (such as India under Section 27 of the Contract Act), post-employment non-compete covenants are void and unenforceable."
                )
                rec = "Request deleting the post-employment non-compete or narrowing it strictly to direct trade secrets."
            elif nc_severity == Severity.MEDIUM:
                title = f"Moderate Non-Compete Restriction ({dur} Months)"
                explanation = (
                    f"A non-compete restriction lasting {dur} months with bounded geographic and industry scope. "
                    "While narrower than worldwide restrictions, it still curtails your immediate employment mobility."
                )
                rec = "Narrow the restriction to direct competitors and clarify allowable non-conflicting activities."
            else:  # LOW
                title = f"Short-Duration Non-Compete ({dur} Months)"
                explanation = (
                    f"A short non-compete duration of {dur} months (< {NON_COMPETE_DURATION_MEDIUM_MONTHS} months). "
                    "Given the limited duration and bounded scope, the risk profile is low."
                )
                rec = "Confirm whether the restriction includes paid garden leave or applies only to direct competitors."

            risks.append(RiskItem(
                clause_id="non_compete_duration",
                clause_name="Post-Employment Non-Compete",
                severity=nc_severity,
                title=title,
                explanation=explanation,
                raw_text=non_compete.raw_text,
                recommendation=rec
            ))

    # 4. Confidentiality & Post-Employment IP Claims
    ip = schema.confidentiality_ip
    if ip.present:
        if ip.post_employment_ip_claim:
            risks.append(RiskItem(
                clause_id="ip_post_employment",
                clause_name="Post-Employment IP Claim",
                severity=Severity.HIGH,
                title="Company Claims Ownership of Inventions Created After Employment",
                explanation=(
                    "The contract purports to claim IP rights to inventions created even after your employment terminates. "
                    "This is an aggressive overreach into your future intellectual creation."
                ),
                raw_text=ip.raw_text,
                recommendation="Demand that IP assignment apply strictly to works created during active working hours using company assets."
            ))

    # 5. Probation Immediate Termination
    prob = schema.probation
    if prob.present:
        cause_req = False if prob.immediate_termination_allowed else (
            schema.termination.grounds_specified if schema.termination.present else None
        )
        prob_severity = evaluate_probation_termination_risk(
            immediate_termination_allowed=prob.immediate_termination_allowed,
            cause_required=cause_req,
            notice_days=0 if prob.immediate_termination_allowed else None,
            probation_present=prob.present
        )
        if prob_severity is not None:
            if prob_severity == Severity.HIGH:
                title = "Immediate Termination During Probation Without Cause"
                explanation = (
                    "The employer reserves the right to terminate your employment immediately during probation "
                    "with 0 days notice and without requiring any documented cause."
                )
                rec = "Request at least 7 to 14 days written notice or pay-in-lieu during the probation period."
            elif prob_severity == Severity.MEDIUM:
                title = "Immediate Termination With Cause During Probation"
                explanation = (
                    "The employer may terminate with 0 days notice during probation, but a documented cause is required."
                )
                rec = "Request a reasonable cure period or written notice before immediate probation termination."
            else:  # LOW
                title = "At-Will Probation Termination Without Cause"
                explanation = (
                    "A notice period exists during probation, but no documented cause is required for termination."
                )
                rec = "Request an objective performance review before any probation exit decision."

            risks.append(RiskItem(
                clause_id="probation_termination",
                clause_name="Immediate Termination on Probation",
                severity=prob_severity,
                title=title,
                explanation=explanation,
                raw_text=prob.raw_text,
                recommendation=rec
            ))

    # 6. Salary Variable Component Split
    sal = schema.salary_breakdown
    if sal.present and sal.variable_pct:
        if sal.variable_pct > cfg.high_variable_pay_pct:
            risks.append(RiskItem(
                clause_id="salary_variable_split",
                clause_name="High Variable Compensation Split",
                severity=Severity.INFO,
                title=f"High Variable Pay Component ({sal.variable_pct:.0f}% of Total CTC)",
                explanation=(
                    f"{sal.variable_pct:.0f}% of your compensation is variable/performance-contingent. "
                    "Only the fixed component is legally guaranteed on pay day."
                ),
                raw_text=sal.raw_text,
                recommendation="Confirm the exact metric criteria and past payout history for performance bonuses."
            ))

    # 7. Unilateral Summary Termination
    term = schema.termination
    if term.present and term.summary_termination_without_hearing:
        risks.append(RiskItem(
            clause_id="termination_summary",
            clause_name="Summary Termination Without Due Process",
            severity=Severity.HIGH,
            title="Unilateral Summary Termination Without Hearing",
            explanation="The contract allows termination without providing notice, documented cause, or an opportunity to respond.",
            raw_text=term.raw_text,
            recommendation="Insist on a mandatory 14-day notice-and-cure period for alleged performance or conduct issues."
        ))

    return risks
