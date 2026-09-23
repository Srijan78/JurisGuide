"""Actionable checklist generator for counterparty negotiations and legal consultations.

Maps flagged risks and missing clauses directly into concrete, polite,
and legally informed questions to ask HR, landlords, clients, or lawyers.
"""

from __future__ import annotations

from typing import List
from output.models import ChecklistQuestion, RiskItem, MissingClauseItem


def generate_action_checklist(
    risks: List[RiskItem],
    missing: List[MissingClauseItem],
    doc_type: str
) -> List[ChecklistQuestion]:
    """Generate prioritized questions tailored to the specific findings in the document."""
    questions: List[ChecklistQuestion] = []
    seen_prompts = set()

    # Determine default counterparty title
    if doc_type == "employment_offer":
        default_party = "HR / Recruiter"
    elif doc_type == "rental_agreement":
        default_party = "Landlord / Broker"
    elif doc_type == "freelance_contract":
        default_party = "Client / Hiring Manager"
    else:
        default_party = "Counterparty / Legal Counsel"

    # Map Risk Items to Questions
    for risk in risks:
        q_text = None
        category = default_party
        rationale = risk.explanation

        if "bond" in risk.clause_id:
            q_text = (
                "Could you provide an itemized breakdown of the specific training costs that justify this bond, "
                "and can we include a pro-rata tapering schedule so liability decreases each month?"
            )
        elif "notice_asymmetry" in risk.clause_id:
            q_text = (
                "Can we align the notice periods so that both parties are subject to the same bilateral notice timeline "
                "(e.g., 30 days for both employee and employer)?"
            )
        elif "notice_duration" in risk.clause_id:
            q_text = (
                "A 90-day notice period is quite extensive; would the company consider a 30 to 45-day notice period, "
                "or confirm an explicit buyout option in writing?"
            )
        elif "non_compete" in risk.clause_id:
            category = "Legal Counsel / HR"
            q_text = (
                "Can we narrow the non-compete clause so it applies strictly to direct competing clients you have worked with, "
                "rather than an entire industry or geographic region?"
            )
        elif "ip_premature" in risk.clause_id:
            q_text = (
                "Can we add a clarification that copyright and IP transfer to the client upon receipt of full and final invoice payment?"
            )
        elif "payment_delayed" in risk.clause_id or "payment_moderate" in risk.clause_id:
            q_text = (
                "Can we adjust payment terms from Net 45/60 to Net 15 or Net 30, or structure payments into deliverable milestones?"
            )
        elif "kill_fee" in risk.clause_id:
            q_text = (
                "Can we include a standard kill fee clause (e.g. 25% to 50% of the remaining milestone) if the project is cancelled without cause?"
            )
        elif "deposit_excessive" in risk.clause_id or "deposit_moderate" in risk.clause_id:
            q_text = (
                "Could we adjust the security deposit closer to standard market norms (2 to 3 months), or deposit the funds into an escrow account?"
            )
        elif "maintenance_structural" in risk.clause_id:
            q_text = (
                "Can the agreement explicitly state that major structural repairs (seepage, plumbing lines, roof integrity) are the landlord's obligation?"
            )
        elif "lock_in" in risk.clause_id:
            q_text = (
                "Can we add an emergency exit clause to the lock-in period allowing vacation without penalty in the event of job relocation or health reasons?"
            )
        elif "scope" in risk.clause_id:
            q_text = (
                "Can we append an explicit Statement of Work itemizing exact deliverables and capping included revisions to 2 rounds?"
            )

        if q_text and q_text not in seen_prompts:
            seen_prompts.add(q_text)
            questions.append(ChecklistQuestion(
                category=category,
                question=q_text,
                rationale=rationale,
            ))

    # Map Missing Clauses to Questions
    for miss in missing:
        q_text = f"The contract does not address '{miss.clause_name}'. Can we add explicit language stating terms for this?"
        if q_text not in seen_prompts:
            seen_prompts.add(q_text)
            questions.append(ChecklistQuestion(
                category=default_party,
                question=q_text,
                rationale=miss.explanation,
            ))

    # Ensure at least 2 general questions if document had no risks
    if not questions:
        questions.append(ChecklistQuestion(
            category=default_party,
            question="Are there any annexures, handbooks, or secondary policies incorporated by reference that have not been provided?",
            rationale="Unprovided secondary documents can contain unexpected binding obligations."
        ))
        questions.append(ChecklistQuestion(
            category="Legal Counsel",
            question="Does this agreement comply with current local statutory labor and tenancy laws?",
            rationale="Ensures the terms are legally enforceable and customary for your jurisdiction."
        ))

    return questions
