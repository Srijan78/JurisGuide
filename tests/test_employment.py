"""Unit tests for Employment Offer Letter deterministic risk rules."""

import pytest
from schemas.employment import EmploymentOfferSchema
from analysis.employment_rules import evaluate_employment_rules
from output.models import Severity


def test_bond_rules_breach_and_no_breach(sample_employment_json):
    # Test Breach: 24 months bond > 12 months threshold -> HIGH
    emp = EmploymentOfferSchema.model_validate(sample_employment_json)
    risks = evaluate_employment_rules(emp)
    bond_risks = [r for r in risks if "bond" in r.clause_id]
    assert any(r.clause_id == "bond_duration" and r.severity == Severity.HIGH for r in bond_risks)

    # Test No Breach: 6 months bond, amount 50k (under 3x of 100k/mo salary) -> No high risk
    sample_employment_json["bond"]["duration_months"] = 6
    sample_employment_json["bond"]["amount"] = 50000.0
    emp_safe = EmploymentOfferSchema.model_validate(sample_employment_json)
    risks_safe = evaluate_employment_rules(emp_safe)
    assert not any(r.clause_id == "bond_duration" for r in risks_safe)
    assert not any(r.clause_id == "bond_amount" for r in risks_safe)


def test_notice_period_asymmetry_breach_and_no_breach(sample_employment_json):
    # Test Breach: 90 days employee vs 15 days employer (6x ratio) -> HIGH
    emp = EmploymentOfferSchema.model_validate(sample_employment_json)
    risks = evaluate_employment_rules(emp)
    assert any(r.clause_id == "notice_asymmetry" and r.severity == Severity.HIGH for r in risks)

    # Test No Breach: 30 days bilateral parity -> No asymmetry risk
    sample_employment_json["notice_period"]["employer_notice_days"] = 30
    sample_employment_json["notice_period"]["employee_notice_days"] = 30
    emp_safe = EmploymentOfferSchema.model_validate(sample_employment_json)
    risks_safe = evaluate_employment_rules(emp_safe)
    assert not any(r.clause_id == "notice_asymmetry" for r in risks_safe)


def test_non_compete_duration_and_scope(sample_employment_json):
    # Test Breach: 12 months & Worldwide -> 2 HIGH risks
    emp = EmploymentOfferSchema.model_validate(sample_employment_json)
    risks = evaluate_employment_rules(emp)
    assert any(r.clause_id == "non_compete_duration" and r.severity == Severity.HIGH for r in risks)
    assert any(r.clause_id == "non_compete_geo" and r.severity == Severity.HIGH for r in risks)

    # Test No Breach: 3 months, local city scope
    sample_employment_json["non_compete"]["duration_months"] = 3
    sample_employment_json["non_compete"]["geographic_scope"] = "City of Bangalore"
    emp_safe = EmploymentOfferSchema.model_validate(sample_employment_json)
    risks_safe = evaluate_employment_rules(emp_safe)
    assert not any(r.clause_id == "non_compete_duration" for r in risks_safe)
    assert not any(r.clause_id == "non_compete_geo" for r in risks_safe)


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
