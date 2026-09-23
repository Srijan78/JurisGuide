"""Deterministic risk rules for Employment Offer Letters.

Evaluates structured data against objective threshold rules (Pillar 1: Code Quality, Pillar 2: Security).
No LLM calls or hallucinations involved.
"""

from __future__ import annotations

from typing import List
from core.config import settings
from output.models import RiskItem, Severity
from schemas.employment import EmploymentOfferSchema


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
        # Check bond duration
        if bond.duration_months and bond.duration_months > cfg.max_bond_duration_months:
            risks.append(RiskItem(
                clause_id="bond_duration",
                clause_name="Service Bond Duration",
                severity=Severity.HIGH,
                title=f"Excessive Service Bond ({bond.duration_months} Months)",
                explanation=(
                    f"The contract imposes a mandatory service bond of {bond.duration_months} months, "
                    f"exceeding the standard reasonable threshold of {cfg.max_bond_duration_months} months. "
                    "In many jurisdictions, prolonged employment bonds are legally contentious as restraint of trade."
                ),
                raw_text=bond.raw_text,
                recommendation="Request reducing the bond period or removing the penalty clause altogether."
            ))

        # Check bond amount relative to monthly salary if salary is available
        monthly_salary = None
        if schema.salary_breakdown.present and schema.salary_breakdown.fixed_amount:
            is_annual = schema.salary_breakdown.period == "annual" or schema.salary_breakdown.fixed_amount > 100_000
            monthly_salary = schema.salary_breakdown.fixed_amount / 12.0 if is_annual else schema.salary_breakdown.fixed_amount

        if bond.amount and monthly_salary:
            ratio = bond.amount / monthly_salary
            if ratio > cfg.max_bond_salary_multiple:
                currency = schema.salary_breakdown.currency or "INR"
                risks.append(RiskItem(
                    clause_id="bond_amount",
                    clause_name="Service Bond Penalty Amount",
                    severity=Severity.HIGH,
                    title=f"Disproportionate Bond Penalty ({ratio:.1f}x Monthly Salary)",
                    explanation=(
                        f"The bond forfeiture sum of {currency} {bond.amount:,.0f} equals {ratio:.1f} months of base salary, "
                        f"violating the reasonable ceiling of {cfg.max_bond_salary_multiple:.1f}x monthly salary. "
                        "Courts typically enforce bonds only up to actual, proven training expenses incurred."
                    ),
                    raw_text=bond.raw_text,
                    recommendation="Request documentation of actual training expenses incurred and a pro-rated tapering schedule."
                ))
        elif bond.amount:
            risks.append(RiskItem(
                clause_id="bond_present",
                clause_name="Mandatory Financial Bond",
                severity=Severity.MEDIUM,
                title="Service Commitment Bond Imposed",
                explanation=f"A financial penalty of {bond.amount:,.0f} is stipulated if you exit early.",
                raw_text=bond.raw_text,
                recommendation="Clarify whether the company provides specialized formal training justifying this bond."
            ))

    # 2. Notice Period & Asymmetry Evaluation
    notice = schema.notice_period
    if notice.present:
        ee_days = notice.employee_notice_days
        er_days = notice.employer_notice_days

        if ee_days and er_days:
            if er_days > 0 and (ee_days / er_days) >= cfg.max_notice_asymmetry_ratio and ee_days >= 30:
                risks.append(RiskItem(
                    clause_id="notice_asymmetry",
                    clause_name="Notice Period Asymmetry",
                    severity=Severity.HIGH,
                    title=f"Unfair Notice Asymmetry ({ee_days}d Employee vs {er_days}d Employer)",
                    explanation=(
                        f"You must give {ee_days} days notice to resign, but the employer only needs to give {er_days} days. "
                        "One-sided notice periods severely disadvantage workers during job transitions."
                    ),
                    raw_text=notice.raw_text,
                    recommendation="Ask for bilateral notice parity so both parties are held to the exact same notice period."
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
        dur = non_compete.duration_months
        if dur and dur > cfg.max_non_compete_duration_months:
            risks.append(RiskItem(
                clause_id="non_compete_duration",
                clause_name="Post-Employment Non-Compete",
                severity=Severity.HIGH,
                title=f"Lengthy Non-Compete Restriction ({dur} Months Post-Exit)",
                explanation=(
                    f"A non-compete restriction lasting {dur} months significantly limits your ability to find work "
                    "in your field. (In jurisdictions like India, post-employment non-competes are generally void under Section 27)."
                ),
                raw_text=non_compete.raw_text,
                recommendation="Request deleting the post-employment non-compete or narrowing it strictly to direct trade secrets."
            ))

        scope_geo = (non_compete.geographic_scope or "").lower()
        if any(w in scope_geo for w in ("worldwide", "global", "unlimited", "anywhere")):
            risks.append(RiskItem(
                clause_id="non_compete_geo",
                clause_name="Overly Broad Geographic Restriction",
                severity=Severity.HIGH,
                title="Worldwide Non-Compete Restriction",
                explanation="The geographic scope of the non-compete is unbounded ('worldwide' / 'global'), which is overly punitive.",
                raw_text=non_compete.raw_text,
                recommendation="Limit the restriction to a specific metropolitan area or remove the geographical constraint."
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
    if prob.present and prob.immediate_termination_allowed:
        risks.append(RiskItem(
            clause_id="probation_termination",
            clause_name="Immediate Termination on Probation",
            severity=Severity.MEDIUM,
            title="Unilateral Immediate Termination During Probation",
            explanation="The company reserves the right to terminate your employment instantly without reason or cure period during probation.",
            raw_text=prob.raw_text,
            recommendation="Request at least 7 to 14 days written notice or pay-in-lieu during the probation period."
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
