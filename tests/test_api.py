"""Integration tests for FastAPI endpoints using TestClient (100% offline)."""

import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app import app
from schemas.employment import EmploymentOfferSchema

client = TestClient(app)


def test_health_check_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "JurisGuide"


def test_classify_empty_payload_rejected():
    response = client.post("/api/classify", data={})
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "No document provided" in data["message"]


def test_classify_and_analyze_flow_mocked(sample_employment_json):
    # 1. Mock classification response
    with patch("app.classify_document") as mock_classify:
        mock_result = MagicMock()
        mock_result.document_type = "employment_offer"
        mock_result.confidence = 0.96
        mock_result.detected_title = "Employment Offer"
        mock_result.summary_reason = "Contains compensation and bond clauses."
        mock_classify.return_value = mock_result

        # Step 1: Call /api/classify
        classify_res = client.post(
            "/api/classify",
            data={"text_content": "This is an employment contract for Alice at Acme Corp with full terms."}
        )
        assert classify_res.status_code == 200
        classify_data = classify_res.json()
        assert classify_data["success"] is True
        session_id = classify_data["session_id"]
        assert classify_data["detected_type"] == "employment_offer"

    # 2. Mock extraction response
    with patch("app.extract_structured_clauses") as mock_extract:
        mock_extract.return_value = EmploymentOfferSchema.model_validate(sample_employment_json)

        # Step 2: Call /api/analyze with confirmation
        analyze_res = client.post(
            "/api/analyze",
            json={"session_id": session_id, "confirmed_type": "employment_offer"}
        )
        assert analyze_res.status_code == 200
        report = analyze_res.json()
        assert report["document_type"] == "employment_offer"
        assert report["overall_risk_level"] == "HIGH"
        assert len(report["risk_items"]) > 0
        assert len(report["checklist"]) > 0
        assert "does NOT constitute formal legal advice" in report["legal_disclaimer"]


def test_analyze_with_invalid_session_returns_404():
    response = client.post(
        "/api/analyze",
        json={"session_id": "non_existent_token_123", "confirmed_type": "employment_offer"}
    )
    assert response.status_code == 404
    data = response.json()
    assert data["error_type"] == "SessionExpired"


def test_homepage_and_static_assets_serve():
    home_res = client.get("/")
    assert home_res.status_code == 200
    assert "JurisGuide" in home_res.text
    assert "style.css" in home_res.text
    assert "app.js" in home_res.text

    css_res = client.get("/static/css/style.css")
    assert css_res.status_code == 200
    assert "--bg-primary" in css_res.text

    js_res = client.get("/static/js/app.js")
    assert js_res.status_code == 200
    assert "DOMContentLoaded" in js_res.text
