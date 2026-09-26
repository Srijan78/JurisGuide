"""Unit tests for Rental / Lease Agreement deterministic risk rules.

Explicitly validates HIGH, MEDIUM, and LOW/None severity bands and exact boundary values
for each pure rule function and for full schema analysis.
"""

import pytest
from core.config import (
    RentalThresholds,
    RENTAL_DEPOSIT_HIGH_MONTHS,
    RENTAL_DEPOSIT_MEDIUM_MONTHS,
    RENTAL_REFUND_MAX_DAYS,
    RENTAL_LOCK_IN_MAX_MONTHS,
    RENTAL_ESCALATION_MAX_PCT,
    RENTAL_MIN_TENANT_NOTICE_DAYS,
    RENTAL_MAX_NOTICE_ASYMMETRY_RATIO,
)
from schemas.rental import RentalAgreementSchema
from analysis.rental_rules import (
    evaluate_deposit_amount_risk,
    evaluate_deposit_refund_risk,
    evaluate_lock_in_duration_risk,
    evaluate_lock_in_forfeiture_risk,
    evaluate_structural_maintenance_risk,
    evaluate_rent_escalation_risk,
    evaluate_rental_notice_asymmetry_risk,
    evaluate_rental_rules,
)
from output.models import Severity


# ==============================================================================
# 1. Pure Function: Security Deposit Amount Rule (3-Tier Band)
# ==============================================================================

def test_deposit_amount_risk_all_bands_and_boundaries():
    """Verify Security Deposit magnitude bands:
    - HIGH if deposit > 6 months rent
    - MEDIUM if 3 < deposit <= 6 months rent
    - None if deposit <= 3 months rent
    """
    # HIGH (> 6.0 months rent)
    assert evaluate_deposit_amount_risk(8.0) == Severity.HIGH
    assert evaluate_deposit_amount_risk(6.1) == Severity.HIGH

    # Boundary: Exactly 6.0 months is MEDIUM (> 3 and <= 6)
    assert evaluate_deposit_amount_risk(6.0) == Severity.MEDIUM

    # MEDIUM (Inside band: e.g. 3.5, 4.0, 5.0 months)
    assert evaluate_deposit_amount_risk(5.0) == Severity.MEDIUM
    assert evaluate_deposit_amount_risk(4.0) == Severity.MEDIUM
    assert evaluate_deposit_amount_risk(3.1) == Severity.MEDIUM

    # Boundary: Exactly 3.0 months is None/safe (not > 3)
    assert evaluate_deposit_amount_risk(3.0) is None

    # Safe / low (<= 3.0 months)
    assert evaluate_deposit_amount_risk(2.0) is None
    assert evaluate_deposit_amount_risk(1.0) is None
    assert evaluate_deposit_amount_risk(0.0) is None

    # Evaluated via amount / monthly_rent calculation
    rent = 30_000.0
    assert evaluate_deposit_amount_risk(None, deposit_amount=240_000.0, monthly_rent=rent) == Severity.HIGH   # 8.0x
    assert evaluate_deposit_amount_risk(None, deposit_amount=180_000.0, monthly_rent=rent) == Severity.MEDIUM # 6.0x (boundary)
    assert evaluate_deposit_amount_risk(None, deposit_amount=120_000.0, monthly_rent=rent) == Severity.MEDIUM # 4.0x
    assert evaluate_deposit_amount_risk(None, deposit_amount=90_000.0, monthly_rent=rent) is None             # 3.0x (boundary)
    assert evaluate_deposit_amount_risk(None, deposit_amount=60_000.0, monthly_rent=rent) is None             # 2.0x

    # Absent or None
    assert evaluate_deposit_amount_risk(None) is None
    assert evaluate_deposit_amount_risk(8.0, deposit_present=False) is None


# ==============================================================================
# 2. Pure Function: Deposit Refund Timeline Rule (Binary by Design)
# ==============================================================================

def test_deposit_refund_risk_all_bands_and_boundaries():
    """Verify Deposit Refund Turnaround bands:
    - MEDIUM if refund_timeline_days > 30 days
    - None if refund_timeline_days <= 30 days
    Binary flag by design per rental spec: within standard refund timeline (<= 30d) vs delayed (> 30d, MEDIUM).
    """
    # MEDIUM: delayed beyond standard timeline (> 30 days)
    assert evaluate_deposit_refund_risk(31) == Severity.MEDIUM
    assert evaluate_deposit_refund_risk(45) == Severity.MEDIUM
    assert evaluate_deposit_refund_risk(60) == Severity.MEDIUM

    # Boundary: Exactly 30 days is acceptable under residential norms (None)
    assert evaluate_deposit_refund_risk(30) is None

    # Safe: within standard 7-14 day inspection/turnaround window
    assert evaluate_deposit_refund_risk(29) is None
    assert evaluate_deposit_refund_risk(14) is None
    assert evaluate_deposit_refund_risk(7) is None
    assert evaluate_deposit_refund_risk(0) is None

    # Absent or None
    assert evaluate_deposit_refund_risk(None) is None
    assert evaluate_deposit_refund_risk(45, deposit_present=False) is None


# ==============================================================================
# 3. Pure Function: Lock-in Duration Rule (Binary by Design)
# ==============================================================================

def test_lock_in_duration_risk_all_bands_and_boundaries():
    """Verify Lock-in Duration bands:
    - HIGH if duration_months > 11 months
    - None if duration_months <= 11 months
    Binary flag by design per residential lease norm: standard 11-month convention (<= 11m, None) vs excessive lock-in (> 11m, HIGH).
    """
    # HIGH: exceeds standard 11-month convention (> 11 months)
    assert evaluate_lock_in_duration_risk(12) == Severity.HIGH
    assert evaluate_lock_in_duration_risk(24) == Severity.HIGH
    assert evaluate_lock_in_duration_risk(36) == Severity.HIGH

    # Boundary: Exactly 11 months matches standard convention (None)
    assert evaluate_lock_in_duration_risk(11) is None

    # Safe: standard 3-6 month lock-in or zero lock-in
    assert evaluate_lock_in_duration_risk(10) is None
    assert evaluate_lock_in_duration_risk(6) is None
    assert evaluate_lock_in_duration_risk(3) is None
    assert evaluate_lock_in_duration_risk(0) is None

    # Absent or None
    assert evaluate_lock_in_duration_risk(None) is None
    assert evaluate_lock_in_duration_risk(24, lock_in_present=False) is None


# ==============================================================================
# 4. Pure Function: Lock-in Forfeiture Rule (Binary by Design)
# ==============================================================================

def test_lock_in_forfeiture_risk_binary_by_design():
    """Verify Early Exit Deposit Forfeiture risk:
    - HIGH if forfeits_entire_deposit_on_early_exit is True
    - None if False or absent
    Binary by design per spec: total deposit seizure on early vacation is an all-or-nothing penalty clause; present -> HIGH, absent -> None.
    """
    assert evaluate_lock_in_forfeiture_risk(True) == Severity.HIGH
    assert evaluate_lock_in_forfeiture_risk(False) is None
    assert evaluate_lock_in_forfeiture_risk(None) is None
    assert evaluate_lock_in_forfeiture_risk(True, lock_in_present=False) is None


# ==============================================================================
# 5. Pure Function: Structural Maintenance Liability Rule (Binary by Design)
# ==============================================================================

def test_structural_maintenance_risk_binary_by_design():
    """Verify Structural Maintenance Liability risk:
    - HIGH if tenant_bears_structural_repairs is True
    - None if False or absent
    Binary by design per tenancy law: shifting capital/structural maintenance liability onto residential tenants is inherently HIGH risk, absent -> None.
    """
    assert evaluate_structural_maintenance_risk(True) == Severity.HIGH
    assert evaluate_structural_maintenance_risk(False) is None
    assert evaluate_structural_maintenance_risk(None) is None
    assert evaluate_structural_maintenance_risk(True, maintenance_present=False) is None


# ==============================================================================
# 6. Pure Function: Rent Escalation Rule (Binary by Design)
# ==============================================================================

def test_rent_escalation_risk_all_bands_and_boundaries():
    """Verify Rent Escalation Percentage bands:
    - MEDIUM if escalation_pct > 10.0%
    - None if escalation_pct <= 10.0%
    Binary flag by design per residential norm: standard renewal hike (<= 10.0%, None) vs steep escalation (> 10.0%, MEDIUM).
    """
    # MEDIUM: exceeds standard 10.0% market ceiling
    assert evaluate_rent_escalation_risk(10.1) == Severity.MEDIUM
    assert evaluate_rent_escalation_risk(15.0) == Severity.MEDIUM
    assert evaluate_rent_escalation_risk(25.0) == Severity.MEDIUM

    # Boundary: Exactly 10.0% matches standard residential norm (None)
    assert evaluate_rent_escalation_risk(10.0) is None

    # Safe: modest inflation-indexed escalation
    assert evaluate_rent_escalation_risk(9.9) is None
    assert evaluate_rent_escalation_risk(5.0) is None
    assert evaluate_rent_escalation_risk(0.0) is None

    # Absent or None
    assert evaluate_rent_escalation_risk(None) is None
    assert evaluate_rent_escalation_risk(15.0, escalation_present=False) is None


# ==============================================================================
# 7. Pure Function: Notice Period Asymmetry Rule (3-Tier Band)
# ==============================================================================

def test_rental_notice_asymmetry_risk_all_bands_and_boundaries():
    """Verify Notice Period Asymmetry bands between tenant and landlord:
    - HIGH if:
        * landlord notice == 0 AND tenant notice >= min_tenant_notice_days (30)
        * OR ratio >= max_notice_asymmetry_ratio (2.0) with tenant notice >= 30
        * OR landlord notice < 30 AND tenant notice >= 30
    - MEDIUM if tenant notice > landlord notice (asymmetric without meeting HIGH conditions)
    - None if balanced (tenant notice <= landlord notice and landlord notice >= 30)
    """
    # HIGH Case 1: Landlord 0 notice while tenant has standard notice (>= 30 days)
    assert evaluate_rental_notice_asymmetry_risk(tenant_notice_days=30, landlord_notice_days=0) == Severity.HIGH  # exact boundary 30d
    assert evaluate_rental_notice_asymmetry_risk(tenant_notice_days=60, landlord_notice_days=0) == Severity.HIGH

    # HIGH Case 2: Ratio >= 2.0 with tenant notice >= 30 days
    assert evaluate_rental_notice_asymmetry_risk(tenant_notice_days=60, landlord_notice_days=30) == Severity.HIGH  # exact ratio boundary 2.0
    assert evaluate_rental_notice_asymmetry_risk(tenant_notice_days=60, landlord_notice_days=15) == Severity.HIGH  # ratio 4.0
    assert evaluate_rental_notice_asymmetry_risk(tenant_notice_days=90, landlord_notice_days=45) == Severity.HIGH  # ratio 2.0

    # HIGH Case 3: Landlord notice below minimum 30 days while tenant has standard notice
    assert evaluate_rental_notice_asymmetry_risk(tenant_notice_days=30, landlord_notice_days=29) == Severity.HIGH  # exact landlord boundary 29d < 30d
    assert evaluate_rental_notice_asymmetry_risk(tenant_notice_days=30, landlord_notice_days=15) == Severity.HIGH

    # MEDIUM Case: Tenant notice > landlord notice, but below HIGH ratio and landlord >= 30d
    assert evaluate_rental_notice_asymmetry_risk(tenant_notice_days=59, landlord_notice_days=30) == Severity.MEDIUM # ratio 1.966 < 2.0 (boundary just below 2.0)
    assert evaluate_rental_notice_asymmetry_risk(tenant_notice_days=45, landlord_notice_days=30) == Severity.MEDIUM # ratio 1.5

    # MEDIUM Case: Landlord notice below minimum 30 days and tenant > landlord with ratio < 2.0
    assert evaluate_rental_notice_asymmetry_risk(tenant_notice_days=25, landlord_notice_days=20) == Severity.MEDIUM # ratio 1.25 < 2.0, landlord < 30d

    # None / Safe Case: Balanced notice periods
    assert evaluate_rental_notice_asymmetry_risk(tenant_notice_days=30, landlord_notice_days=30) is None # exact boundary balanced
    assert evaluate_rental_notice_asymmetry_risk(tenant_notice_days=60, landlord_notice_days=60) is None # balanced 60d
    assert evaluate_rental_notice_asymmetry_risk(tenant_notice_days=15, landlord_notice_days=30) is None # favorable to tenant (tenant < landlord)

    # Absent or None
    assert evaluate_rental_notice_asymmetry_risk(None, None) is None
    assert evaluate_rental_notice_asymmetry_risk(60, 15, notice_present=False) is None


# ==============================================================================
# 8. Full Schema Integration Tests & Threshold Configuration Tests
# ==============================================================================

def test_security_deposit_rules(sample_rental_json):
    """Test full schema evaluation of security deposit rules."""
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
    """Test full schema evaluation of lock-in rules."""
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
    """Test full schema evaluation of maintenance rules."""
    rental = RentalAgreementSchema.model_validate(sample_rental_json)
    risks = evaluate_rental_rules(rental)
    assert any(r.clause_id == "maintenance_structural" and r.severity == Severity.HIGH for r in risks)

    # Test No Breach: Landlord liable for structural
    sample_rental_json["maintenance"]["tenant_bears_structural_repairs"] = False
    rental_safe = RentalAgreementSchema.model_validate(sample_rental_json)
    risks_safe = evaluate_rental_rules(rental_safe)
    assert not any(r.clause_id == "maintenance_structural" for r in risks_safe)


def test_rent_escalation_rule(sample_rental_json):
    """Test full schema evaluation of rent escalation rules."""
    rental = RentalAgreementSchema.model_validate(sample_rental_json)
    risks = evaluate_rental_rules(rental)
    assert any(r.clause_id == "escalation_rate" and r.severity == Severity.MEDIUM for r in risks)

    # Test No Breach: 5% escalation
    sample_rental_json["rent_escalation"]["escalation_pct"] = 5.0
    rental_safe = RentalAgreementSchema.model_validate(sample_rental_json)
    risks_safe = evaluate_rental_rules(rental_safe)
    assert not any(r.clause_id == "escalation_rate" for r in risks_safe)


def test_rental_notice_asymmetry_rule(sample_rental_json):
    """Test full schema notice period asymmetry evaluation in rental agreements."""
    # Breach: tenant 60 days vs landlord 15 days -> HIGH asymmetry
    rental = RentalAgreementSchema.model_validate(sample_rental_json)
    risks = evaluate_rental_rules(rental)
    assert any(r.clause_id == "notice_rental_asymmetry" and r.severity == Severity.HIGH for r in risks)

    # Safe: balanced notice (tenant 30 days, landlord 30 days) -> No asymmetry
    sample_rental_json["notice_period"]["tenant_notice_days"] = 30
    sample_rental_json["notice_period"]["landlord_notice_days"] = 30
    rental_safe = RentalAgreementSchema.model_validate(sample_rental_json)
    risks_safe = evaluate_rental_rules(rental_safe)
    assert not any(r.clause_id == "notice_rental_asymmetry" for r in risks_safe)

    # Breach: landlord 0 days notice while tenant has 30 days notice -> HIGH
    sample_rental_json["notice_period"]["tenant_notice_days"] = 30
    sample_rental_json["notice_period"]["landlord_notice_days"] = 0
    rental_zero_landlord = RentalAgreementSchema.model_validate(sample_rental_json)
    risks_zero = evaluate_rental_rules(rental_zero_landlord)
    assert any(r.clause_id == "notice_rental_asymmetry" and r.severity == Severity.HIGH for r in risks_zero)


def test_rental_thresholds_direct_reference_and_config_change():
    """Import RentalThresholds directly and assert rule function behavior changes when thresholds change."""
    # 1. Security Deposit Thresholds
    default_cfg = RentalThresholds()
    assert default_cfg.max_security_deposit_months == 6
    assert default_cfg.moderate_security_deposit_months == 3
    assert default_cfg.max_deposit_refund_days == 30
    assert default_cfg.min_tenant_notice_days == 30
    assert default_cfg.max_notice_asymmetry_ratio == 2.0

    # Default evaluation: 2 months safe, 4 months medium, 8 months high
    assert evaluate_deposit_amount_risk(2.0, cfg=default_cfg) is None
    assert evaluate_deposit_amount_risk(4.0, cfg=default_cfg) == Severity.MEDIUM
    assert evaluate_deposit_amount_risk(8.0, cfg=default_cfg) == Severity.HIGH

    # Behavior changes when custom RentalThresholds is passed
    strict_deposit_cfg = RentalThresholds(max_security_deposit_months=3, moderate_security_deposit_months=1)
    assert evaluate_deposit_amount_risk(2.0, cfg=strict_deposit_cfg) == Severity.MEDIUM  # changed from None!
    assert evaluate_deposit_amount_risk(4.0, cfg=strict_deposit_cfg) == Severity.HIGH    # changed from MEDIUM!

    # 2. Deposit Refund Timeline
    assert evaluate_deposit_refund_risk(20, cfg=default_cfg) is None
    assert evaluate_deposit_refund_risk(45, cfg=default_cfg) == Severity.MEDIUM
    strict_refund_cfg = RentalThresholds(max_deposit_refund_days=14)
    assert evaluate_deposit_refund_risk(20, cfg=strict_refund_cfg) == Severity.MEDIUM  # changed from None!

    # 3. Lock-in Duration
    assert evaluate_lock_in_duration_risk(11, cfg=default_cfg) is None
    assert evaluate_lock_in_duration_risk(12, cfg=default_cfg) == Severity.HIGH
    strict_lock_cfg = RentalThresholds(max_lock_in_months=6)
    assert evaluate_lock_in_duration_risk(8, cfg=strict_lock_cfg) == Severity.HIGH  # changed from None!

    # 4. Rent Escalation Rate
    assert evaluate_rent_escalation_risk(8.0, cfg=default_cfg) is None
    assert evaluate_rent_escalation_risk(12.0, cfg=default_cfg) == Severity.MEDIUM
    strict_esc_cfg = RentalThresholds(max_annual_escalation_pct=5.0)
    assert evaluate_rent_escalation_risk(8.0, cfg=strict_esc_cfg) == Severity.MEDIUM  # changed from None!

    # 5. Notice Asymmetry and min_tenant_notice_days wiring
    assert evaluate_rental_notice_asymmetry_risk(30, 0, cfg=default_cfg) == Severity.HIGH
    assert evaluate_rental_notice_asymmetry_risk(60, 15, cfg=default_cfg) == Severity.HIGH
    assert evaluate_rental_notice_asymmetry_risk(30, 30, cfg=default_cfg) is None
    assert evaluate_rental_notice_asymmetry_risk(45, 30, cfg=default_cfg) == Severity.MEDIUM

    # If min_tenant_notice_days is set high (e.g. 90), 30 days notice is below the minimum threshold
    high_min_notice_cfg = RentalThresholds(min_tenant_notice_days=90)
    assert evaluate_rental_notice_asymmetry_risk(30, 0, cfg=high_min_notice_cfg) is None
