"""Document classification engine using Gemini 3.5 Flash-Lite.

Executes Gemini Call 1 to classify the document into one of 4 categories:
- employment_offer
- rental_agreement
- freelance_contract
- other
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Optional
from pydantic import BaseModel, Field
from core.config import settings
from core.exceptions import LLMServiceError
from input.normalizer import NormalizedDocument

logger = logging.getLogger(__name__)


class ClassificationResult(BaseModel):
    """Structured result returned by the classification step."""
    document_type: str = Field(
        ...,
        description="One of: 'employment_offer', 'rental_agreement', 'freelance_contract', 'other'"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0"
    )
    detected_title: str = Field(
        default="Legal Document",
        description="Identified title or headline of the agreement"
    )
    summary_reason: str = Field(
        ...,
        description="Brief 1-sentence rationale for the classification decision"
    )


CLASSIFICATION_PROMPT = """You are a legal document classifier. Analyze the provided document and determine which category it belongs to:

1. 'employment_offer': Job offer letter, employment agreement, appointment letter, or internship contract.
2. 'rental_agreement': Residential lease, tenancy agreement, house rent agreement, or commercial shop lease.
3. 'freelance_contract': Independent contractor agreement, consulting services contract, work order, or statement of work (SOW).
4. 'other': Any other legal or general document (e.g., NDA, terms of service, invoice, loan agreement, or general correspondence).

Analyze the first few pages / sections carefully.
Output your decision strictly as a JSON object matching this schema:
{
  "document_type": "employment_offer" | "rental_agreement" | "freelance_contract" | "other",
  "confidence": float between 0.0 and 1.0,
  "detected_title": "string title",
  "summary_reason": "one sentence explaining key identifying terms found"
}
"""


_cached_client = None


def _get_gemini_client():
    """Lazily initialize and cache Google GenAI client for connection reuse."""
    global _cached_client
    if _cached_client is not None:
        return _cached_client

    if not settings.gemini_api_key:
        logger.error("GEMINI_API_KEY is not configured in environment.")
        raise LLMServiceError(
            message="The AI service is not configured.",
            internal_detail="GEMINI_API_KEY is not configured in .env file."
        )
    try:
        from google import genai
        _cached_client = genai.Client(api_key=settings.gemini_api_key)
        return _cached_client
    except Exception as exc:
        logger.error("Failed to initialize Gemini client: %s", exc)
        raise LLMServiceError(
            message="The AI service is temporarily unavailable.",
            internal_detail=f"Failed to initialize Gemini client: {str(exc)}"
        ) from exc


def classify_document(doc: NormalizedDocument, client_override: Optional[object] = None) -> ClassificationResult:
    """Classify a normalized document using a single fast Gemini call.

    Args:
        doc: The normalized document (multimodal or text).
        client_override: Optional mock client for automated testing.

    Returns:
        ClassificationResult with category, confidence, and reasoning.
    """
    client = client_override or _get_gemini_client()

    contents = []

    if doc.is_multimodal and doc.base64_data:
        try:
            from google.genai import types
            raw_bytes = base64.b64decode(doc.base64_data)
            part = types.Part.from_bytes(data=raw_bytes, mime_type=doc.mime_type)
            contents.append(part)
        except Exception as exc:
            logger.error("Failed to construct multimodal part: %s", exc)
            raise LLMServiceError(
                message="Failed to process document media.",
                internal_detail=f"Failed to encode document for Gemini multimodal analysis: {str(exc)}"
            ) from exc
    elif doc.raw_text:
        # Use first ~4000 characters for classification to ensure low latency and minimal quota usage
        truncated_sample = doc.raw_text[:4000]
        contents.append(f"Document Text Sample:\n\n{truncated_sample}")
    else:
        raise LLMServiceError(
            message="Document content could not be read.",
            internal_detail="Document contains neither text nor multimodal payload."
        )

    contents.append(CLASSIFICATION_PROMPT)

    try:
        from google.genai import types
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        )
        models_to_try = [settings.gemini_model]
        if settings.gemini_fallback_model and settings.gemini_fallback_model != settings.gemini_model:
            models_to_try.append(settings.gemini_fallback_model)

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
                logger.warning("Classification with model %s failed: %s", m, e)
                if m == models_to_try[-1]:
                    raise

        response_text = response.text.strip()
        parsed_json = json.loads(response_text)

        # Ensure valid document_type value
        valid_types = {"employment_offer", "rental_agreement", "freelance_contract", "other"}
        doc_type = parsed_json.get("document_type", "other")
        if doc_type not in valid_types:
            doc_type = "other"

        return ClassificationResult(
            document_type=doc_type,
            confidence=float(parsed_json.get("confidence", 0.8)),
            detected_title=str(parsed_json.get("detected_title", "Legal Document")),
            summary_reason=str(parsed_json.get("summary_reason", "Classified based on document content.")),
        )
    except json.JSONDecodeError as exc:
        logger.warning("Gemini returned invalid JSON during classification: %s", exc)
        return ClassificationResult(
            document_type="other",
            confidence=0.5,
            detected_title="Unclassified Document",
            summary_reason="Classification output format was irregular; defaulted to general fallback."
        )
    except Exception as exc:
        if isinstance(exc, LLMServiceError):
            raise
        logger.error("Gemini classification API call failed: %s", exc)
        raise LLMServiceError(
            message="The AI service was temporarily unable to classify the document. Please try again.",
            internal_detail=f"Classification service error: {str(exc)}"
        ) from exc
