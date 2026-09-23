"""Unit tests for classification and extraction pipeline components."""

import json
from unittest.mock import MagicMock
import pytest
from core.exceptions import SchemaExtractionError, LLMServiceError
from input.normalizer import normalize_pasted_text
from classification.classifier import classify_document
from extraction.extractor import extract_structured_clauses
from schemas.employment import EmploymentOfferSchema
from schemas.rental import RentalAgreementSchema
from schemas.freelance import FreelanceContractSchema
from schemas.fallback import FallbackDocumentSchema


def test_classify_all_four_categories():
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_client.models.generate_content.return_value = mock_resp

    doc = normalize_pasted_text("This is an agreement of legal binding terms.")

    for cat in ["employment_offer", "rental_agreement", "freelance_contract", "other"]:
        mock_resp.text = json.dumps({
            "document_type": cat,
            "confidence": 0.95,
            "detected_title": cat.title(),
            "summary_reason": f"Identified as {cat}"
        })
        res = classify_document(doc, client_override=mock_client)
        assert res.document_type == cat
        assert res.confidence == 0.95


def test_extraction_self_healing_retry(sample_employment_json):
    doc = normalize_pasted_text("This is an employment contract text.")
    mock_client = MagicMock()
    
    # Attempt 1: Returns broken non-JSON
    bad_resp = MagicMock()
    bad_resp.text = "Broken response from model"
    
    # Attempt 2: Returns valid JSON schema
    good_resp = MagicMock()
    good_resp.text = json.dumps(sample_employment_json)
    
    mock_client.models.generate_content.side_effect = [bad_resp, good_resp]
    
    result = extract_structured_clauses(doc, "employment_offer", client_override=mock_client)
    assert isinstance(result, EmploymentOfferSchema)
    assert result.bond.duration_months == 24


def test_extraction_unrecoverable_failure():
    doc = normalize_pasted_text("This is an employment contract text.")
    mock_client = MagicMock()
    
    bad_resp = MagicMock()
    bad_resp.text = "Invalid JSON"
    mock_client.models.generate_content.side_effect = [bad_resp, bad_resp]
    
    with pytest.raises(SchemaExtractionError) as exc:
        extract_structured_clauses(doc, "employment_offer", client_override=mock_client)
    assert exc.value.status_code == 422
