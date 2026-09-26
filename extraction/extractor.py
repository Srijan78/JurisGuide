"""Schema-constrained extraction engine using Gemini 3.5 Flash-Lite.

Executes Gemini Call 2 to extract typed structured data matching the confirmed schema.
Includes automatic 1-retry self-healing on schema validation failures.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Dict, Optional, Type, Union
from pydantic import BaseModel, ValidationError

from core.config import settings
from core.exceptions import LLMServiceError, SchemaExtractionError
from input.normalizer import NormalizedDocument
from schemas.employment import EmploymentOfferSchema
from schemas.rental import RentalAgreementSchema
from schemas.freelance import FreelanceContractSchema
from schemas.fallback import FallbackDocumentSchema

logger = logging.getLogger(__name__)

SCHEMA_MAP: Dict[str, Type[BaseModel]] = {
    "employment_offer": EmploymentOfferSchema,
    "rental_agreement": RentalAgreementSchema,
    "freelance_contract": FreelanceContractSchema,
    "other": FallbackDocumentSchema,
}


EMPLOYMENT_PROMPT = """You are a precise legal contract extraction engine.
Analyze the provided employment document and extract clause-level structured data into JSON matching the schema below.
For EVERY clause:
1. Set 'present': true if the clause is explicitly mentioned, false otherwise.
2. Set 'raw_text': exact verbatim excerpt from the document where this clause is stated (or null if absent).
3. Extract the requested structured fields. If a specific number or detail is not stated, use null.

Extract:
- bond: amount (number), duration_months (integer), forfeiture_conditions (string)
- notice_period: employer_notice_days (int), employee_notice_days (int), buyout_option (bool)
- non_compete: duration_months (int), geographic_scope (string), industry_scope (string)
- confidentiality_ip: perpetual_ip_assignment (bool), post_employment_ip_claim (bool), scope (string)
- probation: duration_months (int), immediate_termination_allowed (bool)
- salary_breakdown: fixed_amount (float), variable_amount (float), variable_pct (float), currency (string), period ("annual" or "monthly")
- termination: notice_required_days (int), grounds_specified (bool), summary_termination_without_hearing (bool)
- candidate_name, designation_role, joining_date
"""

RENTAL_PROMPT = """You are a precise legal contract extraction engine.
Analyze the provided rental/lease agreement and extract clause-level structured data into JSON matching the schema below.
For EVERY clause:
1. Set 'present': true if explicitly stated, false otherwise.
2. Set 'raw_text': exact verbatim excerpt from the agreement (or null if absent).
3. Extract the requested structured fields (null if omitted).

Extract:
- monthly_rent: monthly_amount (float), due_day (int), late_fee_per_day (float)
- security_deposit: amount (float), deposit_months (float), refund_timeline_days (int), deduction_conditions (string)
- notice_period: landlord_notice_days (int), tenant_notice_days (int)
- maintenance: tenant_bears_structural_repairs (bool), routine_maintenance_cap (float), landlord_repair_turnaround_days (int)
- lock_in: duration_months (int), early_exit_penalty_terms (string), forfeits_entire_deposit_on_early_exit (bool)
- rent_escalation: escalation_pct (float), frequency_months (int)
- tenant_name, landlord_name, property_address, lease_commencement_date
"""

FREELANCE_PROMPT = """You are a precise legal contract extraction engine.
Analyze the provided freelance/service contract and extract clause-level structured data into JSON matching the schema below.
For EVERY clause:
1. Set 'present': true if explicitly stated, false otherwise.
2. Set 'raw_text': exact verbatim excerpt from the contract (or null if absent).
3. Extract the requested structured fields (null if omitted).

Extract:
- payment_terms: net_days (int), advance_deposit_pct (float), late_payment_penalty_pct (float), has_late_payment_clause (bool)
- ip_assignment: timing_of_transfer ("upon_full_payment" / "upon_creation" / "upon_delivery"), transfers_before_full_payment (bool), portfolio_rights_retained (bool), moral_rights_waived (bool)
- kill_fee: kill_fee_defined (bool), kill_fee_amount_or_pct (string)
- scope_of_work: defined_deliverables (bool), revision_limit_count (int), open_ended_scope (bool)
- termination: notice_days (int), payment_for_completed_milestones_guaranteed (bool)
- freelancer_name, client_name, project_title
"""

FALLBACK_PROMPT = """You are a helpful legal assistant analyzing a document that does not fall into standard templates.
FIRST, determine whether this document contains ANY genuine legal, contractual, or binding obligations (e.g., contracts, agreements, NDAs, terms of service, waivers, powers of attorney, settlement terms, licenses, or formal legal notices).
If the document is purely non-legal or non-contractual (e.g., travel itineraries, trip guides, packing lists, trail notes, recipes, general articles, personal notes, casual emails with no legal commitments), set 'document_has_legal_content' to false.

Provide a clear, structured analysis in JSON matching:
{
  "document_has_legal_content": true or false,
  "detected_document_type": "Best guess of document type (e.g. Non-Disclosure Agreement, Terms of Service, or Non-Legal Document)",
  "plain_summary": "Comprehensive 3-5 sentence plain-language summary of what the document contains or agrees to",
  "identified_parties": ["Party A", "Party B"],
  "key_dates_and_deadlines": ["Effective date: ...", "Termination date: ..."],
  "core_obligations": ["Obligation 1...", "Obligation 2..."],
  "points_to_review": ["Ambiguity in clause X...", "Missing protection on Y..."]
}

CRITICAL INSTRUCTION FOR NON-LEGAL DOCUMENTS:
If 'document_has_legal_content' is false:
Set 'identified_parties', 'key_dates_and_deadlines', 'core_obligations', and 'points_to_review' to empty lists [].
Do NOT invent, fabricate, or hallucinate any legal risks, disclaimers, liability waivers, or recommendations.
"""

PROMPT_MAP = {
    "employment_offer": EMPLOYMENT_PROMPT,
    "rental_agreement": RENTAL_PROMPT,
    "freelance_contract": FREELANCE_PROMPT,
    "other": FALLBACK_PROMPT,
}


def _get_gemini_client():
    if not settings.gemini_api_key:
        logger.error("GEMINI_API_KEY is not configured in environment.")
        raise LLMServiceError(
            message="The AI service is not configured.",
            internal_detail="GEMINI_API_KEY is not configured in .env file."
        )
    try:
        from google import genai
        return genai.Client(api_key=settings.gemini_api_key)
    except Exception as exc:
        logger.error("Failed to initialize Gemini client: %s", exc)
        raise LLMServiceError(
            message="The AI service is temporarily unavailable.",
            internal_detail=f"Failed to initialize Gemini client: {str(exc)}"
        ) from exc


def _build_content_parts(doc: NormalizedDocument, prompt_text: str) -> list:
    parts = []
    if doc.is_multimodal and doc.base64_data:
        from google.genai import types
        raw_bytes = base64.b64decode(doc.base64_data)
        parts.append(types.Part.from_bytes(data=raw_bytes, mime_type=doc.mime_type))
    elif doc.raw_text:
        parts.append(f"Full Document Content:\n\n{doc.raw_text}")
    else:
        raise LLMServiceError(
            message="Document content could not be read.",
            internal_detail="Normalized document is missing content."
        )
    parts.append(prompt_text)
    return parts


def extract_structured_clauses(
    doc: NormalizedDocument,
    document_type: str,
    client_override: Optional[object] = None,
) -> Union[EmploymentOfferSchema, RentalAgreementSchema, FreelanceContractSchema, FallbackDocumentSchema]:
    """Extract structured data matching the confirmed document type with 1-retry self-healing.

    Args:
        doc: The normalized document input.
        document_type: The confirmed document category.
        client_override: Optional mock client for automated testing.

    Returns:
        Validated Pydantic schema model instance.

    Raises:
        SchemaExtractionError: If schema validation fails after retry.
        LLMServiceError: If Gemini API encounters network/quota errors.
    """
    model_cls = SCHEMA_MAP.get(document_type, FallbackDocumentSchema)
    base_prompt = PROMPT_MAP.get(document_type, FALLBACK_PROMPT)

    client = client_override or _get_gemini_client()

    from google.genai import types
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.0,  # Zero temperature for deterministic extraction
    )

    last_error: Optional[Exception] = None

    for attempt in range(2):  # 1 initial call + at most 1 retry
        if attempt == 0:
            prompt = base_prompt
        else:
            logger.info("Attempting extraction retry 2/2 with schema remedy prompt")
            prompt = (
                f"{base_prompt}\n\n"
                f"IMPORTANT: Your previous output failed schema validation with error: {str(last_error)}.\n"
                "Return valid JSON matching the exact schema keys with proper types."
            )

        contents = _build_content_parts(doc, prompt)

        models_to_try = [settings.gemini_model]
        if settings.gemini_fallback_model and settings.gemini_fallback_model != settings.gemini_model:
            models_to_try.append(settings.gemini_fallback_model)

        try:
            response = None
            for m in models_to_try:
                try:
                    response = client.models.generate_content(
                        model=m,
                        contents=contents,
                        config=config,
                    )
                    break
                except Exception as e:
                    logger.warning("Extraction with model %s failed: %s", m, e)
                    if m == models_to_try[-1]:
                        raise

            raw_text = response.text.strip()
            data = json.loads(raw_text)
            validated_model = model_cls.model_validate(data)
            return validated_model

        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            logger.warning("Extraction attempt %d failed: %s", attempt + 1, exc)
            if attempt == 1:
                raise SchemaExtractionError(
                    message=f"Failed to extract valid {document_type} clauses. Please try again.",
                    internal_detail=f"Validation/JSON decode error on attempt {attempt + 1}: {str(exc)}",
                    details={"attempt": attempt + 1}
                ) from exc
        except Exception as exc:
            if isinstance(exc, (LLMServiceError, SchemaExtractionError)):
                raise
            logger.error("Gemini extraction call failed unexpectedly: %s", exc)
            raise LLMServiceError(
                message="The AI service was temporarily unable to extract document details. Please try again.",
                internal_detail=f"Extraction service error: {str(exc)}"
            ) from exc

    raise SchemaExtractionError(
        message="Extraction failed after retry. Please try again.",
        internal_detail="Extraction failed after retry."
    )
