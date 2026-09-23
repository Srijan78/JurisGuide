"""Unit tests for missing-clause detection across schemas."""

from schemas.employment import EmploymentOfferSchema
from schemas.rental import RentalAgreementSchema
from schemas.freelance import FreelanceContractSchema
from analysis.missing_detector import detect_missing_clauses


def test_missing_clauses_in_empty_employment():
    empty_emp = EmploymentOfferSchema()
    missing = detect_missing_clauses(empty_emp)
    missing_ids = [m.clause_id for m in missing]
    assert "missing_salary_breakdown" in missing_ids
    assert "missing_notice_period" in missing_ids
    assert "missing_probation" in missing_ids
    assert "missing_confidentiality_ip" in missing_ids
    assert "missing_termination" in missing_ids


def test_no_missing_clauses_when_all_present():
    complete_emp = EmploymentOfferSchema(
        salary_breakdown={"present": True},
        notice_period={"present": True},
        probation={"present": True},
        confidentiality_ip={"present": True},
        termination={"present": True},
    )
    missing = detect_missing_clauses(complete_emp)
    assert len(missing) == 0


def test_missing_clauses_rental():
    empty_rental = RentalAgreementSchema()
    missing = detect_missing_clauses(empty_rental)
    missing_ids = [m.clause_id for m in missing]
    assert "missing_security_deposit" in missing_ids
    assert "missing_notice_period" in missing_ids
    assert "missing_maintenance" in missing_ids
    assert "missing_rent_escalation" in missing_ids


def test_missing_clauses_freelance():
    empty_free = FreelanceContractSchema()
    missing = detect_missing_clauses(empty_free)
    missing_ids = [m.clause_id for m in missing]
    assert "missing_payment_terms" in missing_ids
    assert "missing_ip_assignment" in missing_ids
    assert "missing_kill_fee" in missing_ids
    assert "missing_scope_of_work" in missing_ids
