"""Missing-clause detection engine via deterministic schema diffing.

Identifies crucial standard clauses that are conspicuously absent from
an uploaded contract (Pillar 1: Code Quality, Pillar 3: Efficiency).
Runs entirely in pure Python with zero API calls.
"""

from __future__ import annotations

from typing import List, Union
from output.models import MissingClauseItem, Severity
from schemas.employment import EmploymentOfferSchema
from schemas.rental import RentalAgreementSchema
from schemas.freelance import FreelanceContractSchema


EXPECTED_EMPLOYMENT_CLAUSES = [
    {
        "attr": "salary_breakdown",
        "name": "Salary Breakdown & Compensation Structure",
        "severity": Severity.HIGH,
        "explanation": "No clear breakdown of fixed vs. variable pay or payment schedule is specified.",
        "recommendation": "Demand an explicit annexure specifying base monthly salary, allowances, and bonus criteria.",
    },
    {
        "attr": "notice_period",
        "name": "Notice Period Terms",
        "severity": Severity.HIGH,
        "explanation": "The contract does not state how many days notice are required for resignation or termination.",
        "recommendation": "Specify a bilateral 30-day notice period for both employee and employer.",
    },
    {
        "attr": "probation",
        "name": "Probation Period Details",
        "severity": Severity.MEDIUM,
        "explanation": "Duration and evaluation criteria for probation are omitted.",
        "recommendation": "Clarify whether a probation period applies, its duration, and confirmation criteria.",
    },
    {
        "attr": "confidentiality_ip",
        "name": "Intellectual Property & Inventions Assignment",
        "severity": Severity.MEDIUM,
        "explanation": "Rights regarding work-product, inventions, or confidential information are not delineated.",
        "recommendation": "Confirm whether company policy requires a separate IP assignment covenant.",
    },
    {
        "attr": "termination",
        "name": "Termination Grounds & Procedure",
        "severity": Severity.HIGH,
        "explanation": "No procedural rights or permissible grounds for termination are documented.",
        "recommendation": "Insist on written notice requirements and a fair opportunity to respond before termination.",
    },
]

EXPECTED_RENTAL_CLAUSES = [
    {
        "attr": "security_deposit",
        "name": "Security Deposit & Refund Conditions",
        "severity": Severity.HIGH,
        "explanation": "The agreement fails to document deposit amount, deductions, or mandatory return timelines.",
        "recommendation": "State the exact deposit amount and require refund within 14 days of handover.",
    },
    {
        "attr": "notice_period",
        "name": "Vacation / Termination Notice Period",
        "severity": Severity.HIGH,
        "explanation": "Notice requirements for vacating or terminating tenancy are absent.",
        "recommendation": "Include an explicit clause specifying 30 days written notice by either tenant or landlord.",
    },
    {
        "attr": "maintenance",
        "name": "Maintenance & Repair Responsibilities",
        "severity": Severity.HIGH,
        "explanation": "No distinction between landlord capital/structural repairs and tenant minor repairs.",
        "recommendation": "Explicitly state that landlord handles structural repairs and tenant pays minor upkeep.",
    },
    {
        "attr": "rent_escalation",
        "name": "Rent Escalation & Renewal Terms",
        "severity": Severity.MEDIUM,
        "explanation": "Renewal terms and escalation rate are undefined, allowing arbitrary rent hikes.",
        "recommendation": "Cap annual escalation at 5% to 10% upon formal lease extension.",
    },
]

EXPECTED_FREELANCE_CLAUSES = [
    {
        "attr": "payment_terms",
        "name": "Payment Schedule & Net Terms",
        "severity": Severity.HIGH,
        "explanation": "The agreement contains no defined invoicing schedule, payment due dates, or currency.",
        "recommendation": "Specify Net 15 or Net 30 payment terms and require a 50% advance deposit.",
    },
    {
        "attr": "ip_assignment",
        "name": "Intellectual Property Rights & Transfer Timing",
        "severity": Severity.HIGH,
        "explanation": "Ownership of deliverables, copyright assignment, and licensing are unaddressed.",
        "recommendation": "Include a clause transferring IP solely upon receipt of full and final payment.",
    },
    {
        "attr": "kill_fee",
        "name": "Cancellation Compensation / Kill Fee",
        "severity": Severity.HIGH,
        "explanation": "No provision protects you if the client cancels the engagement midway.",
        "recommendation": "Add a kill fee provision entitling you to compensation for reserved time.",
    },
    {
        "attr": "scope_of_work",
        "name": "Deliverables & Revision Limits",
        "severity": Severity.HIGH,
        "explanation": "No clear itemization of milestones or revision limits, risking uncontrolled scope creep.",
        "recommendation": "Include an itemized Statement of Work and cap revisions to 2 rounds.",
    },
]


def detect_missing_clauses(
    schema: Union[EmploymentOfferSchema, RentalAgreementSchema, FreelanceContractSchema]
) -> List[MissingClauseItem]:
    """Detect expected clauses that are absent from the extracted schema."""
    missing: List[MissingClauseItem] = []

    if isinstance(schema, EmploymentOfferSchema):
        expected_list = EXPECTED_EMPLOYMENT_CLAUSES
    elif isinstance(schema, RentalAgreementSchema):
        expected_list = EXPECTED_RENTAL_CLAUSES
    elif isinstance(schema, FreelanceContractSchema):
        expected_list = EXPECTED_FREELANCE_CLAUSES
    else:
        return []

    for item in expected_list:
        clause_obj = getattr(schema, item["attr"], None)
        # Check if clause object is absent or marked as not present
        if not clause_obj or not getattr(clause_obj, "present", False):
            missing.append(MissingClauseItem(
                clause_id=f"missing_{item['attr']}",
                clause_name=item["name"],
                severity=item["severity"],
                explanation=item["explanation"],
                recommendation=item["recommendation"],
            ))

    return missing
