"""Unit tests for Employment Offer Letter deterministic 3-tier risk rules.

Explicitly validates HIGH, MEDIUM, LOW bands and exact boundary values
for each pure rule function and for full schema analysis.
"""

import pytest
from core.config import (
    BOND_DURATION_HIGH_MONTHS,
    BOND_DURATION_MEDIUM_MONTHS,
    BOND_SALARY_MULTIPLE_HIGH,
    BOND_SALARY_MULTIPLE_MEDIUM,
    NOTICE_ASYMMETRY_EMPLOYEE_MIN_DAYS_HIGH,
    NOTICE_ASYMMETRY_GAP_MEDIUM_DAYS,
    NON_COMPETE_DURATION_HIGH_MONTHS,
    NON_COMPETE_DURATION_MEDIUM_MONTHS,
)
from schemas.employment import EmploymentOfferSchema
from analysis.employment_rules import (
    evaluate_bond_duration_risk,
    evaluate_bond_amount_risk,
    evaluate_notice_asymmetry_risk,
    evaluate_non_compete_risk,
    evaluate_probation_termination_risk,
    evaluate_employment_rules,
)
from output.models import Severity


# ==============================================================================
# 1. Pure Function: Bond Duration Rule
# ==============================================================================

def test_bond_duration_risk_all_bands_and_boundaries():
    """Verify Bond Duration bands:
    - HIGH if duration > 24 months
    - MEDIUM if 12 <= duration <= 24 months
    - LOW if duration < 12 months
    """
    # HIGH (> 24 months)
    assert evaluate_bond_duration_risk(25) == Severity.HIGH
    assert evaluate_bond_duration_risk(36) == Severity.HIGH

    # Boundary: Exactly 24 months is MEDIUM (12 <= duration <= 24)
    assert evaluate_bond_duration_risk(24) == Severity.MEDIUM

    # MEDIUM (Inside band: e.g. 15, 18 months)
    assert evaluate_bond_duration_risk(15) == Severity.MEDIUM
    assert evaluate_bond_duration_risk(18) == Severity.MEDIUM

    # Boundary: Exactly 12 months is MEDIUM (12 <= duration <= 24)
    assert evaluate_bond_duration_risk(12) == Severity.MEDIUM

    # LOW (< 12 months, still flagged as present)
    assert evaluate_bond_duration_risk(11) == Severity.LOW
    assert evaluate_bond_duration_risk(10) == Severity.LOW
    assert evaluate_bond_duration_risk(6) == Severity.LOW
    assert evaluate_bond_duration_risk(0) == Severity.LOW

    # None if bond not present or duration is None
    assert evaluate_bond_duration_risk(None) is None
    assert evaluate_bond_duration_risk(25, bond_present=False) is None


# ==============================================================================
# 2. Pure Function: Bond Amount Rule
# ==============================================================================

def test_bond_amount_risk_all_bands_and_boundaries():
    """Verify Bond Amount bands (relative to monthly salary):
    - HIGH if amount > 6x monthly salary
    - MEDIUM if 3x <= amount <= 6x monthly salary
    - LOW if amount < 3x but bond is present
    """
    salary = 100_000.0  # 1 Lakh / month

    # HIGH (> 6x monthly salary)
    assert evaluate_bond_amount_risk(650_000.0, salary) == Severity.HIGH
    assert evaluate_bond_amount_risk(700_000.0, salary) == Severity.HIGH

    # Boundary: Exactly 6.0x is MEDIUM (3x <= amount <= 6x)
    assert evaluate_bond_amount_risk(600_000.0, salary) == Severity.MEDIUM

    # MEDIUM (Inside band: e.g. 3.8x, 4.5x)
    assert evaluate_bond_amount_risk(380_000.0, salary) == Severity.MEDIUM
    assert evaluate_bond_amount_risk(450_000.0, salary) == Severity.MEDIUM

    # Boundary: Exactly 3.0x is MEDIUM (3x <= amount <= 6x)
    assert evaluate_bond_amount_risk(300_000.0, salary) == Severity.MEDIUM

    # LOW (< 3x monthly salary)
    assert evaluate_bond_amount_risk(290_000.0, salary) == Severity.LOW
    assert evaluate_bond_amount_risk(250_000.0, salary) == Severity.LOW
    assert evaluate_bond_amount_risk(50_000.0, salary) == Severity.LOW

    # Default without salary context: MEDIUM
    assert evaluate_bond_amount_risk(100_000.0, None) == Severity.MEDIUM

    # None if bond not present or amount is None
    assert evaluate_bond_amount_risk(None, salary) is None
    assert evaluate_bond_amount_risk(500_000.0, salary, bond_present=False) is None


# ==============================================================================
# 3. Pure Function: Notice Period Asymmetry Rule
# ==============================================================================

def test_notice_asymmetry_risk_all_bands_and_boundaries():
    """Verify Notice Period Asymmetry bands:
    - HIGH if employer notice == 0 AND employee notice >= 60
    - MEDIUM if gap between employee and employer notice >= 30 days (and not already HIGH)
    - LOW/no flag if gap < 30 days (LOW if gap > 0, None if gap <= 0)
    """
    # HIGH: employer notice == 0 AND employee notice >= 60
    assert evaluate_notice_asymmetry_risk(employee_notice_days=60, employer_notice_days=0) == Severity.HIGH
    assert evaluate_notice_asymmetry_risk(employee_notice_days=90, employer_notice_days=0) == Severity.HIGH

    # If employer notice == 0 BUT employee notice < 60:
    # employee=59, employer=0 -> gap=59 >= 30 -> MEDIUM
    assert evaluate_notice_asymmetry_risk(employee_notice_days=59, employer_notice_days=0) == Severity.MEDIUM
    # employee=20, employer=0 -> gap=20 < 30 -> LOW
    assert evaluate_notice_asymmetry_risk(employee_notice_days=20, employer_notice_days=0) == Severity.LOW

    # MEDIUM: gap >= 30 days (and not already HIGH)
    assert evaluate_notice_asymmetry_risk(employee_notice_days=90, employer_notice_days=15) == Severity.MEDIUM  # gap=75
    # Boundary: Exactly 30 days gap is MEDIUM
    assert evaluate_notice_asymmetry_risk(employee_notice_days=60, employer_notice_days=30) == Severity.MEDIUM  # gap=30

    # LOW: gap < 30 days and gap > 0
    # Boundary: 29 days gap is LOW
    assert evaluate_notice_asymmetry_risk(employee_notice_days=59, employer_notice_days=30) == Severity.LOW   # gap=29
    assert evaluate_notice_asymmetry_risk(employee_notice_days=45, employer_notice_days=30) == Severity.LOW   # gap=15
    assert evaluate_notice_asymmetry_risk(employee_notice_days=31, employer_notice_days=30) == Severity.LOW   # gap=1

    # Parity: gap <= 0 -> None (no flag)
    assert evaluate_notice_asymmetry_risk(employee_notice_days=30, employer_notice_days=30) is None            # gap=0
    assert evaluate_notice_asymmetry_risk(employee_notice_days=15, employer_notice_days=30) is None            # gap=-15

    # None if not present or missing
    assert evaluate_notice_asymmetry_risk(None, 30) is None
    assert evaluate_notice_asymmetry_risk(60, None) is None
    assert evaluate_notice_asymmetry_risk(60, 0, notice_present=False) is None


# ==============================================================================
# 4. Pure Function: Non-Compete Risk Rule
# ==============================================================================

def test_non_compete_risk_all_bands_and_boundaries():
    """Verify Non-Compete bands:
    - HIGH if duration > 12 months OR scope is "any industry" / nationwide / worldwide
    - MEDIUM if 6 <= duration <= 12 months and scope is reasonably bounded
    - LOW if duration < 6 months (and scope is bounded)
    """
    bounded_geo = "City of Bangalore"
    bounded_ind = "Software Engineering"

    # HIGH: duration > 12 months even if bounded
    assert evaluate_non_compete_risk(13, bounded_geo, bounded_ind) == Severity.HIGH
    assert evaluate_non_compete_risk(24, bounded_geo, bounded_ind) == Severity.HIGH

    # HIGH: broad scope regardless of duration
    assert evaluate_non_compete_risk(3, "Worldwide", bounded_ind) == Severity.HIGH
    assert evaluate_non_compete_risk(6, "Global", bounded_ind) == Severity.HIGH
    assert evaluate_non_compete_risk(12, "Nationwide", bounded_ind) == Severity.HIGH
    assert evaluate_non_compete_risk(6, bounded_geo, "any industry") == Severity.HIGH
    assert evaluate_non_compete_risk(6, bounded_geo, "all industries") == Severity.HIGH

    # Boundary: Exactly 12 months with bounded scope is MEDIUM
    assert evaluate_non_compete_risk(12, bounded_geo, bounded_ind) == Severity.MEDIUM

    # MEDIUM: 6 <= duration <= 12 months bounded
    assert evaluate_non_compete_risk(9, bounded_geo, bounded_ind) == Severity.MEDIUM

    # Boundary: Exactly 6 months with bounded scope is MEDIUM
    assert evaluate_non_compete_risk(6, bounded_geo, bounded_ind) == Severity.MEDIUM

    # LOW: duration < 6 months bounded
    assert evaluate_non_compete_risk(5, bounded_geo, bounded_ind) == Severity.LOW
    assert evaluate_non_compete_risk(3, bounded_geo, bounded_ind) == Severity.LOW
    assert evaluate_non_compete_risk(1, bounded_geo, bounded_ind) == Severity.LOW

    # None if not present or empty
    assert evaluate_non_compete_risk(None, None, None) is None
    assert evaluate_non_compete_risk(12, bounded_geo, bounded_ind, non_compete_present=False) is None


# ==============================================================================
# 5. Pure Function: Probation Termination Risk Rule
# ==============================================================================

def test_probation_termination_risk_all_bands():
    """Verify Probation Termination bands:
    - HIGH if termination allowed with 0 days notice AND no stated cause requirement
    - MEDIUM if termination allowed with 0 days notice BUT a cause/reason is required
    - LOW/no flag if notice period or documented-cause requirement exists during probation
    """
    # HIGH: 0 days notice AND no cause requirement
    assert evaluate_probation_termination_risk(
        immediate_termination_allowed=True,
        cause_required=False
    ) == Severity.HIGH
    assert evaluate_probation_termination_risk(
        notice_days=0,
        cause_required=False
    ) == Severity.HIGH

    # MEDIUM: 0 days notice BUT cause/reason is required
    assert evaluate_probation_termination_risk(
        immediate_termination_allowed=True,
        cause_required=True
    ) == Severity.MEDIUM
    assert evaluate_probation_termination_risk(
        notice_days=0,
        cause_required=True
    ) == Severity.MEDIUM

    # LOW: notice period exists BUT no cause required
    assert evaluate_probation_termination_risk(
        immediate_termination_allowed=False,
        cause_required=False
    ) == Severity.LOW
    assert evaluate_probation_termination_risk(
        notice_days=14,
        cause_required=False
    ) == Severity.LOW

    # No flag (None): notice period exists AND cause is required
    assert evaluate_probation_termination_risk(
        immediate_termination_allowed=False,
        cause_required=True
    ) is None
    assert evaluate_probation_termination_risk(
        notice_days=14,
        cause_required=True
    ) is None

    # None if probation not present
    assert evaluate_probation_termination_risk(
        immediate_termination_allowed=True,
        cause_required=False,
        probation_present=False
    ) is None


# ==============================================================================
# 6. Specific Bug Reproduction & Verification Test
# ==============================================================================

def test_bug_15_month_bond_and_3_8x_salary_scored_medium(sample_employment_json):
    """BUG SPECIFICATION TEST:
    A document with a 15-month bond and a 3.8x-monthly-salary bond penalty
    must be scored as MEDIUM on both counts (not HIGH).
    """
    # Monthly salary = 1,200,000 / 12 = 100,000
    # 3.8x monthly salary penalty = 380,000
    sample_employment_json["bond"]["duration_months"] = 15
    sample_employment_json["bond"]["amount"] = 380_000.0

    emp = EmploymentOfferSchema.model_validate(sample_employment_json)
    risks = evaluate_employment_rules(emp)

    # 1. Bond duration must be MEDIUM, not HIGH
    dur_risk = next((r for r in risks if r.clause_id == "bond_duration"), None)
    assert dur_risk is not None, "bond_duration risk must be flagged"
    assert dur_risk.severity == Severity.MEDIUM, f"Expected MEDIUM, got {dur_risk.severity}"

    # 2. Bond amount must be MEDIUM, not HIGH
    amt_risk = next((r for r in risks if r.clause_id == "bond_amount"), None)
    assert amt_risk is not None, "bond_amount risk must be flagged"
    assert amt_risk.severity == Severity.MEDIUM, f"Expected MEDIUM, got {amt_risk.severity}"


# ==============================================================================
# 7. Integration Tests for Full Schema Evaluation
# ==============================================================================

def test_bond_rules_high_severity(sample_employment_json):
    """Test HIGH severity triggers for bond duration (>24m) and amount (>6x)."""
    sample_employment_json["bond"]["duration_months"] = 30
    sample_employment_json["bond"]["amount"] = 700_000.0  # 7x of 100k/mo salary
    emp = EmploymentOfferSchema.model_validate(sample_employment_json)
    risks = evaluate_employment_rules(emp)

    dur_risk = next((r for r in risks if r.clause_id == "bond_duration"), None)
    assert dur_risk is not None and dur_risk.severity == Severity.HIGH

    amt_risk = next((r for r in risks if r.clause_id == "bond_amount"), None)
    assert amt_risk is not None and amt_risk.severity == Severity.HIGH


def test_notice_period_asymmetry_integration(sample_employment_json):
    # Test HIGH: employer notice 0, employee notice 60
    sample_employment_json["notice_period"]["employer_notice_days"] = 0
    sample_employment_json["notice_period"]["employee_notice_days"] = 60
    emp_high = EmploymentOfferSchema.model_validate(sample_employment_json)
    risks_high = evaluate_employment_rules(emp_high)
    asym_high = next((r for r in risks_high if r.clause_id == "notice_asymmetry"), None)
    assert asym_high is not None and asym_high.severity == Severity.HIGH

    # Test MEDIUM: employer notice 15, employee notice 90 (gap = 75 >= 30)
    sample_employment_json["notice_period"]["employer_notice_days"] = 15
    sample_employment_json["notice_period"]["employee_notice_days"] = 90
    emp_med = EmploymentOfferSchema.model_validate(sample_employment_json)
    risks_med = evaluate_employment_rules(emp_med)
    asym_med = next((r for r in risks_med if r.clause_id == "notice_asymmetry"), None)
    assert asym_med is not None and asym_med.severity == Severity.MEDIUM

    # Test Parity: 30 days bilateral parity -> No asymmetry risk
    sample_employment_json["notice_period"]["employer_notice_days"] = 30
    sample_employment_json["notice_period"]["employee_notice_days"] = 30
    emp_safe = EmploymentOfferSchema.model_validate(sample_employment_json)
    risks_safe = evaluate_employment_rules(emp_safe)
    assert not any(r.clause_id == "notice_asymmetry" for r in risks_safe)


def test_post_employment_ip_claim(sample_employment_json):
    emp = EmploymentOfferSchema.model_validate(sample_employment_json)
    risks = evaluate_employment_rules(emp)
    assert any(r.clause_id == "ip_post_employment" and r.severity == Severity.HIGH for r in risks)

    sample_employment_json["confidentiality_ip"]["post_employment_ip_claim"] = False
    emp_safe = EmploymentOfferSchema.model_validate(sample_employment_json)
    risks_safe = evaluate_employment_rules(emp_safe)
    assert not any(r.clause_id == "ip_post_employment" for r in risks_safe)


def test_summary_termination_rule(sample_employment_json):
    emp = EmploymentOfferSchema.model_validate(sample_employment_json)
    risks = evaluate_employment_rules(emp)
    assert any(r.clause_id == "termination_summary" and r.severity == Severity.HIGH for r in risks)

    sample_employment_json["termination"]["summary_termination_without_hearing"] = False
    emp_safe = EmploymentOfferSchema.model_validate(sample_employment_json)
    risks_safe = evaluate_employment_rules(emp_safe)
    assert not any(r.clause_id == "termination_summary" for r in risks_safe)
