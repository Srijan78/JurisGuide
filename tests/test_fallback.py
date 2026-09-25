"""Unit and integration tests for 'Other' category Outcome A vs Outcome B split.

Validates that:
- Outcome B (non-legal documents, e.g. trek guide) produces ZERO RiskItems, ZERO checklist
  questions, and the exact specified non-legal guidance message.
- Outcome A (general legal documents, e.g. NDA) produces a general summary and review items.
- Two outcomes are code-enforced via document_has_legal_content: bool.
"""

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app import app
from core.config import NON_LEGAL_DOCUMENT_MESSAGE
from schemas.fallback import FallbackDocumentSchema
from analysis.engine import analyze_extracted_document
from output.models import Severity

client = TestClient(app)

EXPECTED_OUTCOME_B_MESSAGE = (
    "This document doesn't appear to contain legal or contractual content. "
    "JurisGuide is designed to analyze contracts and agreements — "
    "try uploading an employment offer, rental agreement, or freelance contract instead."
)


# ==============================================================================
# Unit Tests: Analysis Engine Direct Execution
# ==============================================================================

def test_outcome_b_non_legal_document_trek_guide():
    """OUTCOME B TEST:
    A non-legal document (e.g., hiking trek itinerary, packing list) must NOT produce
    any RiskItem objects, severity badges, or questions checklist.
    Even if the raw model output attempted to fabricate points_to_review,
    the code must short-circuit to the exact Outcome B message.
    """
    non_legal_schema = FallbackDocumentSchema(
        document_has_legal_content=False,
        detected_document_type="Trekking Itinerary / Travel Guide",
        plain_summary="This document outlines a 5-day Himalayan hiking itinerary with packing checklist.",
        identified_parties=[],
        key_dates_and_deadlines=["Day 1 departure: 6:00 AM"],
        core_obligations=[],
        # Model hallucinated review points on a non-legal document
        points_to_review=["Lack of formal safety disclaimers or liability waivers", "Unclear refund terms for bad weather"]
    )

    report = analyze_extracted_document(
        schema=non_legal_schema,
        document_type="other",
        document_title="Himalayan_Trek_Guide.txt"
    )

    # 1. Assert exactly ZERO RiskItem objects
    assert len(report.risk_items) == 0, f"Expected 0 risk items, got {len(report.risk_items)}"

    # 2. Assert exactly ZERO checklist questions
    assert len(report.checklist) == 0, f"Expected 0 checklist questions, got {len(report.checklist)}"

    # 3. Assert zero missing clauses
    assert len(report.missing_clauses) == 0

    # 4. Assert overall_risk_level is NON_LEGAL
    assert report.overall_risk_level == "NON_LEGAL"

    # 5. Assert the exact Outcome B message returned
    assert report.summary == EXPECTED_OUTCOME_B_MESSAGE
    assert report.summary == NON_LEGAL_DOCUMENT_MESSAGE

    # 6. Assert stats reflect zero flags
    assert report.stats["high_risks"] == 0
    assert report.stats["medium_risks"] == 0
    assert report.stats["info_risks"] == 0
    assert report.stats["total_flags"] == 0


def test_outcome_a_genuine_legal_document_nda():
    """OUTCOME A TEST:
    A genuine-but-unsupported legal contract (e.g. an NDA or ToS) must go through
    Outcome A: producing a general summary and best-effort clause review items.
    Confirms Outcome B does not replace Outcome A entirely.
    """
    nda_schema = FallbackDocumentSchema(
        document_has_legal_content=True,
        detected_document_type="Non-Disclosure Agreement",
        plain_summary="Mutual confidentiality agreement protecting proprietary source code and trade secrets for 2 years.",
        identified_parties=["Alpha Corp", "Beta LLC"],
        key_dates_and_deadlines=["Confidentiality period: 24 months from disclosure"],
        core_obligations=["Maintain strict secrecy of proprietary source code", "Return materials within 10 days of request"],
        points_to_review=["Injunctive relief clause does not require posting a bond", "Indefinite survival for trade secrets"]
    )

    report = analyze_extracted_document(
        schema=nda_schema,
        document_type="other",
        document_title="Mutual_NDA.pdf"
    )

    # 1. Assert overall_risk_level is GENERAL
    assert report.overall_risk_level == "GENERAL"

    # 2. Assert general summary is preserved (not Outcome B message)
    assert report.summary == "Mutual confidentiality agreement protecting proprietary source code and trade secrets for 2 years."
    assert report.summary != EXPECTED_OUTCOME_B_MESSAGE

    # 3. Assert review items were converted to RiskItems
    assert len(report.risk_items) == 2
    assert all(r.severity == Severity.INFO for r in report.risk_items)
    assert any("Injunctive relief" in r.explanation for r in report.risk_items)

    # 4. Assert checklist questions are generated for legal counterparty negotiation
    assert len(report.checklist) > 0


# ==============================================================================
# Integration Tests: End-to-End API Flow (/api/classify -> /api/analyze)
# ==============================================================================

def test_api_flow_outcome_b_trek_guide():
    """End-to-end API test for Outcome B via HTTP client."""
    trek_doc_json = {
        "document_has_legal_content": False,
        "detected_document_type": "Travel Guide",
        "plain_summary": "Hiking trail guide with packing list.",
        "points_to_review": ["No liability waiver"]
    }

    # Step 1: Mock classify
    with patch("app.classify_document") as mock_classify:
        m = MagicMock()
        m.document_type = "other"
        m.confidence = 0.90
        m.detected_title = "Hiking Guide"
        m.summary_reason = "Itinerary and trail notes."
        mock_classify.return_value = m

        res1 = client.post(
            "/api/classify",
            data={"text_content": "Day 1: Hike to base camp. Pack warm clothing, 2L water, and sturdy boots."}
        )
        assert res1.status_code == 200
        session_id = res1.json()["session_id"]
        assert res1.json()["detected_type"] == "other"

    # Step 2: Mock extract and analyze
    with patch("app.extract_structured_clauses") as mock_extract:
        mock_extract.return_value = FallbackDocumentSchema.model_validate(trek_doc_json)

        res2 = client.post(
            "/api/analyze",
            json={"session_id": session_id, "confirmed_type": "other"}
        )
        assert res2.status_code == 200
        report = res2.json()

        assert report["overall_risk_level"] == "NON_LEGAL"
        assert len(report["risk_items"]) == 0
        assert len(report["checklist"]) == 0
        assert report["summary"] == EXPECTED_OUTCOME_B_MESSAGE


def test_api_flow_outcome_a_nda():
    """End-to-end API test for Outcome A via HTTP client."""
    nda_doc_json = {
        "document_has_legal_content": True,
        "detected_document_type": "Non-Disclosure Agreement",
        "plain_summary": "Mutual non-disclosure agreement between Acme and Vendor.",
        "identified_parties": ["Acme Corp", "Vendor Inc"],
        "points_to_review": ["Unilateral indemnity clause for confidentiality breach"]
    }

    with patch("app.classify_document") as mock_classify:
        m = MagicMock()
        m.document_type = "other"
        m.confidence = 0.95
        m.detected_title = "Non-Disclosure Agreement"
        m.summary_reason = "Confidentiality obligations."
        mock_classify.return_value = m

        res1 = client.post(
            "/api/classify",
            data={"text_content": "This Non-Disclosure Agreement is entered into by and between Acme Corp and Vendor Inc."}
        )
        assert res1.status_code == 200
        session_id = res1.json()["session_id"]

    with patch("app.extract_structured_clauses") as mock_extract:
        mock_extract.return_value = FallbackDocumentSchema.model_validate(nda_doc_json)

        res2 = client.post(
            "/api/analyze",
            json={"session_id": session_id, "confirmed_type": "other"}
        )
        assert res2.status_code == 200
        report = res2.json()

        assert report["overall_risk_level"] == "GENERAL"
        assert len(report["risk_items"]) == 1
        assert report["summary"] == "Mutual non-disclosure agreement between Acme and Vendor."
        assert len(report["checklist"]) > 0
