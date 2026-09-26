"""Unit tests for Freelance and Service Contract deterministic risk rules.

Explicitly validates HIGH, MEDIUM, and LOW/None severity bands and exact boundary values
for each pure rule function and for full schema analysis.
"""

import pytest
from core.config import (
    FreelanceThresholds,
    FREELANCE_PAYMENT_TERM_EXTENDED_DAYS,
    FREELANCE_PAYMENT_TERM_STANDARD_DAYS,
    FREELANCE_MAX_INCLUDED_REVISIONS,
)
from schemas.freelance import FreelanceContractSchema
from analysis.freelance_rules import (
    evaluate_ip_transfer_risk,
    evaluate_portfolio_rights_risk,
    evaluate_payment_term_risk,
    evaluate_late_payment_penalty_risk,
    evaluate_kill_fee_risk,
    evaluate_open_ended_scope_risk,
    evaluate_revision_limit_risk,
    evaluate_termination_unpaid_work_risk,
    evaluate_freelance_rules,
)
from output.models import Severity


# ==============================================================================
# 1. Pure Function: Payment Terms Window Rule (3-Tier Band)
# ==============================================================================

def test_payment_term_risk_all_bands_and_boundaries():
    """Verify Freelance Payment Terms (Net Days) bands:
    - HIGH if net_days > 45 days (extended / punitive)
    - MEDIUM if 30 < net_days <= 45 days (moderate delay)
    - None if net_days <= 30 days (standard contractor norm)
    """
    # HIGH (> 45 days)
    assert evaluate_payment_term_risk(60) == Severity.HIGH
    assert evaluate_payment_term_risk(90) == Severity.HIGH
    assert evaluate_payment_term_risk(46) == Severity.HIGH  # exact boundary + 1

    # Boundary: Exactly 45 days is MEDIUM (> 30 and <= 45)
    assert evaluate_payment_term_risk(45) == Severity.MEDIUM

    # MEDIUM (Inside band: e.g. 31, 35, 40 days)
    assert evaluate_payment_term_risk(40) == Severity.MEDIUM
    assert evaluate_payment_term_risk(35) == Severity.MEDIUM
    assert evaluate_payment_term_risk(31) == Severity.MEDIUM  # exact boundary + 1 over 30

    # Boundary: Exactly 30 days is standard contractor baseline (None)
    assert evaluate_payment_term_risk(30) is None

    # Safe: Net 15, Net 7, immediate payment (<= 30 days)
    assert evaluate_payment_term_risk(15) is None
    assert evaluate_payment_term_risk(7) is None
    assert evaluate_payment_term_risk(0) is None

    # Absent or None
    assert evaluate_payment_term_risk(None) is None
    assert evaluate_payment_term_risk(60, payment_present=False) is None

    # Custom thresholds
    strict_cfg = FreelanceThresholds(max_payment_term_days=15, extended_payment_term_days=30)
    assert evaluate_payment_term_risk(15, cfg=strict_cfg) is None
    assert evaluate_payment_term_risk(20, cfg=strict_cfg) == Severity.MEDIUM
    assert evaluate_payment_term_risk(30, cfg=strict_cfg) == Severity.MEDIUM
    assert evaluate_payment_term_risk(31, cfg=strict_cfg) == Severity.HIGH


# ==============================================================================
# 2. Pure Function: IP Transfer Timing Rule (Binary by Design)
# ==============================================================================

def test_ip_transfer_risk_binary_by_design():
    """Verify IP Transfer Timing risk:
    - HIGH if transfers_before_full_payment is True OR timing is creation/delivery/signing
    - None if transfer occurs only upon full payment
    Binary by design per creator rights norms: IP transferring prior to full compensation is HIGH; transfer upon full payment is safe (None).
    """
    # HIGH: Premature transfer flag True
    assert evaluate_ip_transfer_risk(transfers_before_full_payment=True) == Severity.HIGH

    # HIGH: Premature timing keywords
    assert evaluate_ip_transfer_risk(transfers_before_full_payment=False, timing_of_transfer="upon_creation") == Severity.HIGH
    assert evaluate_ip_transfer_risk(transfers_before_full_payment=False, timing_of_transfer="upon_delivery") == Severity.HIGH
    assert evaluate_ip_transfer_risk(transfers_before_full_payment=False, timing_of_transfer="on_signing") == Severity.HIGH
    assert evaluate_ip_transfer_risk(transfers_before_full_payment=None, timing_of_transfer="Creation of deliverables") == Severity.HIGH

    # Safe: Conditioned upon full and final payment
    assert evaluate_ip_transfer_risk(transfers_before_full_payment=False, timing_of_transfer="upon_full_payment") is None
    assert evaluate_ip_transfer_risk(transfers_before_full_payment=False, timing_of_transfer="receipt_of_final_invoice_settlement") is None

    # Absent or None
    assert evaluate_ip_transfer_risk(transfers_before_full_payment=None, timing_of_transfer=None) is None
    assert evaluate_ip_transfer_risk(transfers_before_full_payment=True, ip_present=False) is None


# ==============================================================================
# 3. Pure Function: Portfolio Display Rights Rule (Binary by Design)
# ==============================================================================

def test_portfolio_rights_risk_binary_by_design():
    """Verify Portfolio Display Rights retention:
    - LOW if portfolio_rights_retained is False
    - None if True or absent
    Binary by design per spec: gagging creator from showcasing completed work in portfolio is a LOW severity advisory; permitted -> None.
    """
    # LOW: expressly barred from portfolio display
    assert evaluate_portfolio_rights_risk(portfolio_rights_retained=False) == Severity.LOW

    # Safe: rights retained
    assert evaluate_portfolio_rights_risk(portfolio_rights_retained=True) is None

    # Absent or None
    assert evaluate_portfolio_rights_risk(portfolio_rights_retained=None) is None
    assert evaluate_portfolio_rights_risk(portfolio_rights_retained=False, ip_present=False) is None


# ==============================================================================
# 4. Pure Function: Late Payment Penalty Clause Rule (Binary by Design)
# ==============================================================================

def test_late_payment_penalty_risk_binary_by_design():
    """Verify Late Payment Penalty / Statutory Interest clause presence:
    - MEDIUM if require_late_payment_penalty is True AND has_late_payment_clause is False
    - None if late payment clause exists or not required
    Binary by design: lack of statutory/contractual late interest is MEDIUM; present -> None.
    """
    # MEDIUM: no late payment penalty clause
    assert evaluate_late_payment_penalty_risk(has_late_payment_clause=False) == Severity.MEDIUM

    # Safe: late payment clause present
    assert evaluate_late_payment_penalty_risk(has_late_payment_clause=True) is None

    # Absent or None
    assert evaluate_late_payment_penalty_risk(has_late_payment_clause=None) is None
    assert evaluate_late_payment_penalty_risk(has_late_payment_clause=False, payment_present=False) is None

    # Custom config disabling requirement
    lenient_cfg = FreelanceThresholds(require_late_payment_penalty=False)
    assert evaluate_late_payment_penalty_risk(has_late_payment_clause=False, cfg=lenient_cfg) is None


# ==============================================================================
# 5. Pure Function: Kill Fee & Cancellation Clause Rule (Binary by Design)
# ==============================================================================

def test_kill_fee_risk_binary_by_design():
    """Verify Kill Fee on client-initiated cancellation:
    - HIGH if require_kill_fee is True AND kill_fee_defined is False
    - None if kill fee is defined or not required
    Binary by design: client cancellation without kill fee compensation for reserved time is HIGH; defined -> None.
    """
    # HIGH: missing kill fee
    assert evaluate_kill_fee_risk(kill_fee_defined=False) == Severity.HIGH

    # Safe: kill fee defined
    assert evaluate_kill_fee_risk(kill_fee_defined=True) is None

    # Absent or None
    assert evaluate_kill_fee_risk(kill_fee_defined=None) is None
    assert evaluate_kill_fee_risk(kill_fee_defined=False, kill_fee_present=False) is None

    # Custom config disabling requirement
    lenient_cfg = FreelanceThresholds(require_kill_fee=False)
    assert evaluate_kill_fee_risk(kill_fee_defined=False, cfg=lenient_cfg) is None


# ==============================================================================
# 6. Pure Function: Open-Ended Scope of Work Rule (Binary by Design)
# ==============================================================================

def test_open_ended_scope_risk_binary_by_design():
    """Verify Open-Ended / Uncapped Scope of Work risk:
    - HIGH if open_ended_scope is True
    - None if False or absent
    Binary by design: open-ended / 'as needed' scope clauses represent high scope-creep risk (HIGH); bounded scope -> None.
    """
    # HIGH: open-ended scope ('as needed', vague duties)
    assert evaluate_open_ended_scope_risk(open_ended_scope=True) == Severity.HIGH

    # Safe: defined deliverables / fixed scope
    assert evaluate_open_ended_scope_risk(open_ended_scope=False) is None
    assert evaluate_open_ended_scope_risk(open_ended_scope=None) is None
    assert evaluate_open_ended_scope_risk(open_ended_scope=True, scope_present=False) is None


# ==============================================================================
# 7. Pure Function: Revision Limit Rule (Binary by Design with Boundary)
# ==============================================================================

def test_revision_limit_risk_all_bands_and_boundaries():
    """Verify Revision Iteration Limit bands and boundaries:
    - MEDIUM if revision_limit_count is None (uncapped) OR revision_limit_count > 3
    - None if revision_limit_count <= 3
    Binary by design: revision iterations are either uncapped/excessive (MEDIUM) or appropriately bounded (None).
    """
    # MEDIUM: Uncapped revisions (None)
    assert evaluate_revision_limit_risk(None) == Severity.MEDIUM

    # MEDIUM: Exceeds max_included_revisions (> 3)
    assert evaluate_revision_limit_risk(4) == Severity.MEDIUM  # exact boundary + 1 (the fixed bug!)
    assert evaluate_revision_limit_risk(5) == Severity.MEDIUM
    assert evaluate_revision_limit_risk(10) == Severity.MEDIUM

    # Boundary: Exactly 3 revisions matches standard norm (None)
    assert evaluate_revision_limit_risk(3) is None

    # Safe: 1 or 2 revisions limit (<= 3)
    assert evaluate_revision_limit_risk(2) is None
    assert evaluate_revision_limit_risk(1) is None
    assert evaluate_revision_limit_risk(0) is None

    # Absent or None
    assert evaluate_revision_limit_risk(4, scope_present=False) is None

    # Custom config behavior
    custom_cfg = FreelanceThresholds(max_included_revisions=5)
    assert evaluate_revision_limit_risk(4, cfg=custom_cfg) is None
    assert evaluate_revision_limit_risk(5, cfg=custom_cfg) is None
    assert evaluate_revision_limit_risk(6, cfg=custom_cfg) == Severity.MEDIUM


# ==============================================================================
# 8. Pure Function: Uncompensated Work on Termination Rule (Binary by Design)
# ==============================================================================

def test_termination_unpaid_work_risk_binary_by_design():
    """Verify Uncompensated Work upon Termination risk:
    - HIGH if payment_for_completed_milestones_guaranteed is False
    - None if True or absent
    Binary by design: client termination without explicit guarantee of payment for work done prior to notice is HIGH; guaranteed -> None.
    """
    # HIGH: client can terminate without paying for partially completed work
    assert evaluate_termination_unpaid_work_risk(payment_for_completed_milestones_guaranteed=False) == Severity.HIGH

    # Safe: payment for completed milestones is contractually guaranteed
    assert evaluate_termination_unpaid_work_risk(payment_for_completed_milestones_guaranteed=True) is None

    # Absent or None
    assert evaluate_termination_unpaid_work_risk(payment_for_completed_milestones_guaranteed=None) is None
    assert evaluate_termination_unpaid_work_risk(payment_for_completed_milestones_guaranteed=False, termination_present=False) is None


# ==============================================================================
# 9. Full Schema Integration Tests
# ==============================================================================

def test_ip_transfer_timing_rules(sample_freelance_json):
    """Test full schema evaluation of IP transfer rules."""
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
    """Test full schema evaluation of payment terms rules."""
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
    """Test full schema evaluation of kill fee, scope, and revision rules."""
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


def test_termination_unpaid_work_integration(sample_freelance_json):
    """Test full schema evaluation of termination clause unpaid work protection."""
    # Breach: payment not guaranteed for completed work -> HIGH
    sample_freelance_json["termination"]["payment_for_completed_milestones_guaranteed"] = False
    free = FreelanceContractSchema.model_validate(sample_freelance_json)
    risks = evaluate_freelance_rules(free)
    assert any(r.clause_id == "termination_unpaid_work" and r.severity == Severity.HIGH for r in risks)

    # Safe: payment guaranteed -> No risk
    sample_freelance_json["termination"]["payment_for_completed_milestones_guaranteed"] = True
    free_safe = FreelanceContractSchema.model_validate(sample_freelance_json)
    risks_safe = evaluate_freelance_rules(free_safe)
    assert not any(r.clause_id == "termination_unpaid_work" for r in risks_safe)
