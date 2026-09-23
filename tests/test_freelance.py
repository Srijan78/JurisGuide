"""Unit tests for Freelance and Service Contract deterministic risk rules."""

import pytest
from schemas.freelance import FreelanceContractSchema
from analysis.freelance_rules import evaluate_freelance_rules
from output.models import Severity


def test_ip_transfer_timing_rules(sample_freelance_json):
    # Test Breach: IP transfers before full payment -> HIGH
    free = FreelanceContractSchema.model_validate(sample_freelance_json)
    risks = evaluate_freelance_rules(free)
    assert any(r.clause_id == "ip_premature_transfer" and r.severity == Severity.HIGH for r in risks)
    assert any(r.clause_id == "ip_portfolio_prohibition" and r.severity == Severity.LOW for r in risks)

    # Test No Breach: IP transfers strictly upon full payment, portfolio rights retained
    sample_freelance_json["ip_assignment"]["timing_of_transfer"] = "upon_full_payment"
    sample_freelance_json["ip_assignment"]["transfers_before_full_payment"] = False
    sample_freelance_json["ip_assignment"]["portfolio_rights_retained"] = True
    free_safe = FreelanceContractSchema.model_validate(sample_freelance_json)
    risks_safe = evaluate_freelance_rules(free_safe)
    assert not any(r.clause_id == "ip_premature_transfer" for r in risks_safe)
    assert not any(r.clause_id == "ip_portfolio_prohibition" for r in risks_safe)


def test_payment_terms_rules(sample_freelance_json):
    # Test Breach: Net 60 days & no late interest -> HIGH + MEDIUM
    free = FreelanceContractSchema.model_validate(sample_freelance_json)
    risks = evaluate_freelance_rules(free)
    assert any(r.clause_id == "payment_delayed_net" and r.severity == Severity.HIGH for r in risks)
    assert any(r.clause_id == "payment_late_interest" and r.severity == Severity.MEDIUM for r in risks)

    # Test No Breach: Net 15, late fee specified
    sample_freelance_json["payment_terms"]["net_days"] = 15
    sample_freelance_json["payment_terms"]["has_late_payment_clause"] = True
    free_safe = FreelanceContractSchema.model_validate(sample_freelance_json)
    risks_safe = evaluate_freelance_rules(free_safe)
    assert not any(r.clause_id == "payment_delayed_net" for r in risks_safe)
    assert not any(r.clause_id == "payment_late_interest" for r in risks_safe)


def test_kill_fee_and_scope_rules(sample_freelance_json):
    # Test Breach: No kill fee & open scope -> 2 HIGH risks
    free = FreelanceContractSchema.model_validate(sample_freelance_json)
    risks = evaluate_freelance_rules(free)
    assert any(r.clause_id == "kill_fee_absent" and r.severity == Severity.HIGH for r in risks)
    assert any(r.clause_id == "scope_open_ended" and r.severity == Severity.HIGH for r in risks)

    # Test No Breach: 50% kill fee & defined deliverables with 2 revisions limit
    sample_freelance_json["kill_fee"]["kill_fee_defined"] = True
    sample_freelance_json["scope_of_work"]["open_ended_scope"] = False
    sample_freelance_json["scope_of_work"]["defined_deliverables"] = True
    sample_freelance_json["scope_of_work"]["revision_limit_count"] = 2
    free_safe = FreelanceContractSchema.model_validate(sample_freelance_json)
    risks_safe = evaluate_freelance_rules(free_safe)
    assert not any(r.clause_id == "kill_fee_absent" for r in risks_safe)
    assert not any(r.clause_id == "scope_open_ended" for r in risks_safe)
    assert not any(r.clause_id == "scope_unlimited_revisions" for r in risks_safe)
