"""Data models for analysis reports, risk findings, and action checklists."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Risk severity levels."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class RiskItem(BaseModel):
    """An individual flagged risk finding."""
    clause_id: str = Field(..., description="Machine identifier (e.g., 'bond', 'notice_period')")
    clause_name: str = Field(..., description="Human-readable clause title")
    severity: Severity = Field(..., description="Severity classification: HIGH, MEDIUM, LOW, INFO")
    title: str = Field(..., description="Concise headline for the risk")
    explanation: str = Field(..., description="Plain-language explanation of why this term is risky")
    raw_text: Optional[str] = Field(default=None, description="Verbatim clause text from the contract")
    recommendation: str = Field(..., description="Actionable negotiation guidance or protective counter-proposal")


class MissingClauseItem(BaseModel):
    """An expected clause that is absent from the contract."""
    clause_id: str
    clause_name: str
    severity: Severity = Severity.MEDIUM
    explanation: str
    recommendation: str


class ChecklistQuestion(BaseModel):
    """A specific question to ask the counterparty or legal counsel."""
    category: str = Field(..., description="Target party: 'HR / Recruiter', 'Landlord', 'Client', 'Legal Counsel'")
    question: str = Field(..., description="The exact question to ask")
    rationale: str = Field(..., description="Why this question is essential based on contract findings")


class AnalysisReport(BaseModel):
    """The complete user-facing contract analysis report."""
    document_type: str
    document_title: str
    overall_risk_level: str  # "HIGH", "MODERATE", "LOW", "GENERAL"
    summary: str
    risk_items: List[RiskItem] = Field(default_factory=list)
    missing_clauses: List[MissingClauseItem] = Field(default_factory=list)
    checklist: List[ChecklistQuestion] = Field(default_factory=list)
    structured_data: Dict[str, Any] = Field(default_factory=dict)
    legal_disclaimer: str
    stats: Dict[str, int] = Field(default_factory=dict)
