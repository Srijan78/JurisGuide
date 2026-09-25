"""Orchestration engine for deterministic contract analysis.

Executes rule engines, missing clause detection, risk ranking, summary generation,
and actionable checklist compilation. 100% deterministic with zero LLM calls.
"""

from __future__ import annotations

from typing import Union, Dict, Any, List
from core.config import settings, NON_LEGAL_DOCUMENT_MESSAGE
from output.models import AnalysisReport, RiskItem, MissingClauseItem, ChecklistQuestion, Severity
from output.templater import generate_plain_summary
from output.checklist import generate_action_checklist
from schemas.employment import EmploymentOfferSchema
from schemas.rental import RentalAgreementSchema
from schemas.freelance import FreelanceContractSchema
from schemas.fallback import FallbackDocumentSchema
from analysis.employment_rules import evaluate_employment_rules
from analysis.rental_rules import evaluate_rental_rules
from analysis.freelance_rules import evaluate_freelance_rules
from analysis.missing_detector import detect_missing_clauses


# Severity sort priority
SEVERITY_ORDER = {
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
    Severity.INFO: 4,
}


def analyze_extracted_document(
    schema: Union[EmploymentOfferSchema, RentalAgreementSchema, FreelanceContractSchema, FallbackDocumentSchema],
    document_type: str,
    document_title: str = "Analyzed Contract"
) -> AnalysisReport:
    """Run full deterministic analysis against extracted structured schema.

    Args:
        schema: The validated Pydantic schema instance.
        document_type: One of 'employment_offer', 'rental_agreement', 'freelance_contract', 'other'.
        document_title: Title or filename of the document.

    Returns:
        Complete AnalysisReport containing plain summary, ranked risks, and checklist.
    """
    risks: List[RiskItem] = []
    missing: List[MissingClauseItem] = []

    if isinstance(schema, EmploymentOfferSchema):
        risks = evaluate_employment_rules(schema)
        missing = detect_missing_clauses(schema)
    elif isinstance(schema, RentalAgreementSchema):
        risks = evaluate_rental_rules(schema)
        missing = detect_missing_clauses(schema)
    elif isinstance(schema, FreelanceContractSchema):
        risks = evaluate_freelance_rules(schema)
        missing = detect_missing_clauses(schema)
    elif isinstance(schema, FallbackDocumentSchema):
        if not schema.document_has_legal_content:
            # OUTCOME B: Not a legal document (no contractual content at all)
            # Enforce split in code: do not parse or render any risk items, severity badges, or questions
            return AnalysisReport(
                document_type=document_type,
                document_title=document_title,
                overall_risk_level="NON_LEGAL",
                summary=NON_LEGAL_DOCUMENT_MESSAGE,
                risk_items=[],
                missing_clauses=[],
                checklist=[],
                structured_data=schema.model_dump(),
                legal_disclaimer=settings.legal_disclaimer,
                stats={
                    "high_risks": 0,
                    "medium_risks": 0,
                    "low_risks": 0,
                    "info_risks": 0,
                    "missing_clauses": 0,
                    "total_flags": 0,
                },
            )

        # OUTCOME A: General legal document (genuinely contractual, e.g. NDA, generic ToS)
        # Transform fallback points_to_review into informational risk items
        for idx, point in enumerate(schema.points_to_review):
            risks.append(RiskItem(
                clause_id=f"fallback_review_{idx}",
                clause_name="Point for Review",
                severity=Severity.INFO,
                title="Review Point Identified",
                explanation=point,
                raw_text=None,
                recommendation="Review this clause with the other party or have legal counsel inspect."
            ))

    # Sort risks strictly by severity
    risks.sort(key=lambda r: SEVERITY_ORDER.get(r.severity, 99))

    # Calculate overall risk posture
    high_count = sum(1 for r in risks if r.severity == Severity.HIGH)
    med_count = sum(1 for r in risks if r.severity == Severity.MEDIUM)
    low_count = sum(1 for r in risks if r.severity == Severity.LOW)
    info_count = sum(1 for r in risks if r.severity == Severity.INFO)

    if document_type == "other":
        overall_risk = "GENERAL"
    elif high_count > 0:
        overall_risk = "HIGH"
    elif med_count >= 2:
        overall_risk = "MODERATE"
    else:
        overall_risk = "LOW"

    # Generate summary & checklist
    summary = generate_plain_summary(schema)
    checklist = generate_action_checklist(risks, missing, document_type)

    stats = {
        "high_risks": high_count,
        "medium_risks": med_count,
        "low_risks": low_count,
        "info_risks": info_count,
        "missing_clauses": len(missing),
        "total_flags": len(risks) + len(missing),
    }

    return AnalysisReport(
        document_type=document_type,
        document_title=document_title,
        overall_risk_level=overall_risk,
        summary=summary,
        risk_items=risks,
        missing_clauses=missing,
        checklist=checklist,
        structured_data=schema.model_dump(),
        legal_disclaimer=settings.legal_disclaimer,
        stats=stats,
    )
