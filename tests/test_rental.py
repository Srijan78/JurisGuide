"""Unit tests for Rental / Lease Agreement deterministic risk rules."""

import pytest
from schemas.rental import RentalAgreementSchema
from analysis.rental_rules import evaluate_rental_rules
from output.models import Severity


def test_security_deposit_rules(sample_rental_json):
    # Test Breach: 8 months deposit > 6 months threshold -> HIGH
    rental = RentalAgreementSchema.model_validate(sample_rental_json)
    risks = evaluate_rental_rules(rental)
    assert any(r.clause_id == "deposit_excessive" and r.severity == Severity.HIGH for r in risks)
    assert any(r.clause_id == "deposit_refund_timeline" and r.severity == Severity.MEDIUM for r in risks)

    # Test No Breach: 2 months deposit, 10 days refund -> No deposit risk
    sample_rental_json["security_deposit"]["deposit_months"] = 2.0
    sample_rental_json["security_deposit"]["amount"] = 60000.0
    sample_rental_json["security_deposit"]["refund_timeline_days"] = 10
    rental_safe = RentalAgreementSchema.model_validate(sample_rental_json)
    risks_safe = evaluate_rental_rules(rental_safe)
    assert not any(r.clause_id == "deposit_excessive" for r in risks_safe)
    assert not any(r.clause_id == "deposit_refund_timeline" for r in risks_safe)


def test_lock_in_duration_and_forfeiture(sample_rental_json):
    # Test Breach: 24 months lock-in & full deposit forfeit -> 2 HIGH risks
    rental = RentalAgreementSchema.model_validate(sample_rental_json)
    risks = evaluate_rental_rules(rental)
    assert any(r.clause_id == "lock_in_duration" and r.severity == Severity.HIGH for r in risks)
    assert any(r.clause_id == "lock_in_forfeiture" and r.severity == Severity.HIGH for r in risks)

    # Test No Breach: 11 months lock-in, reasonable exit terms
    sample_rental_json["lock_in"]["duration_months"] = 11
    sample_rental_json["lock_in"]["forfeits_entire_deposit_on_early_exit"] = False
    rental_safe = RentalAgreementSchema.model_validate(sample_rental_json)
    risks_safe = evaluate_rental_rules(rental_safe)
    assert not any(r.clause_id == "lock_in_duration" for r in risks_safe)
    assert not any(r.clause_id == "lock_in_forfeiture" for r in risks_safe)


def test_structural_maintenance_liability(sample_rental_json):
    # Test Breach: Tenant liable for structural repairs -> HIGH
    rental = RentalAgreementSchema.model_validate(sample_rental_json)
    risks = evaluate_rental_rules(rental)
    assert any(r.clause_id == "maintenance_structural" and r.severity == Severity.HIGH for r in risks)

    # Test No Breach: Landlord liable for structural
    sample_rental_json["maintenance"]["tenant_bears_structural_repairs"] = False
    rental_safe = RentalAgreementSchema.model_validate(sample_rental_json)
    risks_safe = evaluate_rental_rules(rental_safe)
    assert not any(r.clause_id == "maintenance_structural" for r in risks_safe)


def test_rent_escalation_rule(sample_rental_json):
    # Test Breach: 15% escalation > 10% threshold -> MEDIUM
    rental = RentalAgreementSchema.model_validate(sample_rental_json)
    risks = evaluate_rental_rules(rental)
    assert any(r.clause_id == "escalation_rate" and r.severity == Severity.MEDIUM for r in risks)

    # Test No Breach: 5% escalation
    sample_rental_json["rent_escalation"]["escalation_pct"] = 5.0
    rental_safe = RentalAgreementSchema.model_validate(sample_rental_json)
    risks_safe = evaluate_rental_rules(rental_safe)
    assert not any(r.clause_id == "escalation_rate" for r in risks_safe)
