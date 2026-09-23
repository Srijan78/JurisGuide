"""Central configuration management for JurisGuide.

Provides application settings, Gemini API parameters, input constraints,
and deterministic risk threshold constants.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()


@dataclass(frozen=True)
class EmploymentThresholds:
    """Thresholds for deterministic Employment Offer risk analysis."""
    max_bond_duration_months: int = 12
    max_bond_salary_multiple: float = 3.0
    max_notice_period_days: int = 90
    max_notice_asymmetry_ratio: float = 2.0  # employee_days / employer_days
    max_non_compete_duration_months: int = 6
    unreasonable_probation_months: int = 6
    high_variable_pay_pct: float = 35.0


@dataclass(frozen=True)
class RentalThresholds:
    """Thresholds for deterministic Rental Agreement risk analysis."""
    max_security_deposit_months: int = 6
    max_lock_in_months: int = 11
    max_annual_escalation_pct: float = 10.0
    min_tenant_notice_days: int = 30
    max_notice_asymmetry_ratio: float = 2.0


@dataclass(frozen=True)
class FreelanceThresholds:
    """Thresholds for deterministic Freelance Contract risk analysis."""
    max_payment_term_days: int = 30
    require_late_payment_penalty: bool = True
    require_kill_fee: bool = True
    require_payment_before_ip_transfer: bool = True
    max_included_revisions: int = 3


@dataclass
class Settings:
    """Application-wide settings and risk criteria."""
    # App Information
    app_name: str = "JurisGuide"
    app_version: str = "2.1.0"
    app_env: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # API Keys & LLM Settings
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    gemini_fallback_model: str = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.6-flash")

    # Ephemeral Storage & Constraints
    session_ttl_seconds: int = int(os.getenv("SESSION_TTL_SECONDS", "600"))
    max_upload_size_bytes: int = 5 * 1024 * 1024  # 5 MB
    allowed_extensions: tuple[str, ...] = (".pdf", ".jpg", ".jpeg", ".docx", ".txt")

    # Risk Thresholds
    employment: EmploymentThresholds = field(default_factory=EmploymentThresholds)
    rental: RentalThresholds = field(default_factory=RentalThresholds)
    freelance: FreelanceThresholds = field(default_factory=FreelanceThresholds)

    # Legal Disclaimer (strictly enforced on UI and output reports)
    legal_disclaimer: str = (
        "JurisGuide is an automated legal information assistant and does NOT constitute "
        "formal legal advice. It does not replace consultation with a qualified legal professional."
    )


# Global settings singleton
settings = Settings()
