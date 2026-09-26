"""FastAPI application entrypoint for JurisGuide.

Provides REST API endpoints for document upload, classification, confirmation,
and deterministic contract analysis, plus serves the accessible UI.
"""

from __future__ import annotations

import logging
from typing import Optional
from pathlib import Path
from fastapi import FastAPI, File, Form, UploadFile, Request, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.gzip import GZipMiddleware
import anyio
from pydantic import BaseModel, Field

from core.config import settings
from core.exceptions import (
    JurisGuideError,
    InputValidationError,
    FileSizeLimitExceededError,
    SessionExpiredError,
    LLMServiceError,
    SchemaExtractionError,
)
from core.session import session_store
from input.normalizer import normalize_uploaded_file, normalize_pasted_text
from classification.classifier import classify_document
from extraction.extractor import extract_structured_clauses
from analysis.engine import analyze_extracted_document
from output.models import AnalysisReport

# Logging configuration
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("jurisguide")

# Base directory paths
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="GenAI Legal Contract Assistant for Legal Information Accessibility",
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Ensure directories exist and mount static files (safely ignore read-only file systems)
try:
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ---------------------------------------------------------
# Exception Handlers (Pillar 2: Security - Safe Error Handling)
# ---------------------------------------------------------

@app.exception_handler(InputValidationError)
async def handle_validation_error(request: Request, exc: InputValidationError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error_type": "ValidationError", "message": exc.message, "details": exc.details},
    )


@app.exception_handler(SessionExpiredError)
async def handle_session_error(request: Request, exc: SessionExpiredError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error_type": "SessionExpired", "message": exc.message},
    )


SAFE_AI_SERVICE_MESSAGE = "The AI service was temporarily unable to process the document. Please try again."


@app.exception_handler(LLMServiceError)
async def handle_llm_error(request: Request, exc: LLMServiceError):
    logger.error("LLM service exception: %s | internal_detail: %s", exc.message, getattr(exc, "internal_detail", ""))
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error_type": "AIServiceError", "message": SAFE_AI_SERVICE_MESSAGE},
    )


@app.exception_handler(SchemaExtractionError)
async def handle_extraction_error(request: Request, exc: SchemaExtractionError):
    logger.error("Schema extraction exception: %s | internal_detail: %s", exc.message, getattr(exc, "internal_detail", ""))
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error_type": "ExtractionError", "message": "Failed to extract structured clauses from document. Please try again."},
    )


@app.exception_handler(Exception)
async def handle_generic_exception(request: Request, exc: Exception):
    logger.exception("Unhandled server exception: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error_type": "ServerError",
            "message": "An unexpected error occurred while processing your document. Please try again.",
        },
    )


# ---------------------------------------------------------
# Web & API Endpoints
# ---------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def render_homepage(request: Request):
    """Serve the main accessible contract analyzer interface."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": settings.app_name,
            "version": settings.app_version,
            "disclaimer": settings.legal_disclaimer,
        },
    )


@app.get("/api/health")
async def health_check():
    """Health and status endpoint for monitoring and test verification."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "active_ephemeral_sessions": session_store.active_session_count(),
    }


@app.post("/api/classify")
async def classify_contract(
    file: Optional[UploadFile] = File(None),
    text_content: Optional[str] = Form(None),
):
    """Step 1: Ingest document, validate security headers, store in ephemeral memory, and classify with Gemini."""
    if file and file.filename:
        file_bytes = await file.read()
        normalized_doc = normalize_uploaded_file(file_bytes, file.filename)
    elif text_content and text_content.strip():
        normalized_doc = normalize_pasted_text(text_content.strip(), filename="Pasted_Agreement.txt")
    else:
        raise InputValidationError("No document provided. Please upload a file (PDF, DOCX, JPG) or paste contract text.")

    # Execute Gemini Call 1 in worker thread (Fast classification without blocking event loop)
    classification = await anyio.to_thread.run_sync(classify_document, normalized_doc)

    # Store normalized document in session store (in worker thread)
    session_id = await anyio.to_thread.run_sync(session_store.create_session, normalized_doc.to_dict())

    return {
        "success": True,
        "session_id": session_id,
        "filename": normalized_doc.filename,
        "detected_type": classification.document_type,
        "confidence": classification.confidence,
        "detected_title": classification.detected_title,
        "summary_reason": classification.summary_reason,
        "supported_options": [
            {"id": "employment_offer", "label": "Employment Offer Letter"},
            {"id": "rental_agreement", "label": "Rental / Lease Agreement"},
            {"id": "freelance_contract", "label": "Freelance / Service Contract"},
            {"id": "other", "label": "Other Document (General Fallback Analysis)"},
        ],
    }


class AnalyzeRequest(BaseModel):
    session_id: str = Field(..., description="Active session ID from Step 1")
    confirmed_type: str = Field(..., description="Confirmed or overridden document category")


@app.post("/api/analyze", response_model=AnalysisReport)
async def analyze_contract(body: AnalyzeRequest):
    """Step 2: User confirms/overrides category -> Extract structured schema (Gemini Call 2) -> Run deterministic code analysis."""
    # Retrieve and pop session from store in worker thread
    doc_dict = await anyio.to_thread.run_sync(session_store.pop_session, body.session_id)
    from input.normalizer import NormalizedDocument
    normalized_doc = NormalizedDocument.from_dict(doc_dict)

    # Validate confirmed type
    valid_types = {"employment_offer", "rental_agreement", "freelance_contract", "other"}
    confirmed_type = body.confirmed_type if body.confirmed_type in valid_types else "other"

    # Execute Gemini Call 2 in worker thread (Extraction)
    extracted_schema = await anyio.to_thread.run_sync(extract_structured_clauses, normalized_doc, confirmed_type)

    # Execute Pure Python Analysis Layer in worker thread (Deterministic - 0 API calls)
    report = await anyio.to_thread.run_sync(
        analyze_extracted_document,
        extracted_schema,
        confirmed_type,
        normalized_doc.filename,
    )

    return report


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host=getattr(settings, "app_host", "127.0.0.1"), port=getattr(settings, "app_port", 8000), reload=True)
