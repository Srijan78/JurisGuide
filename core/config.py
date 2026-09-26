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


# ==============================================================================
# Deterministic Risk Threshold Constants: Employment Offer Schema
# ==============================================================================

# Bond Duration (Months)
BOND_DURATION_HIGH_MONTHS: int = 24
BOND_DURATION_MEDIUM_MONTHS: int = 12

# Bond Amount (Multiple of Monthly Gross Salary)
BOND_SALARY_MULTIPLE_HIGH: float = 6.0
BOND_SALARY_MULTIPLE_MEDIUM: float = 3.0

# Notice Period Asymmetry (Days)
NOTICE_ASYMMETRY_EMPLOYEE_MIN_DAYS_HIGH: int = 60
NOTICE_ASYMMETRY_GAP_MEDIUM_DAYS: int = 30
MAX_NOTICE_PERIOD_DAYS: int = 90

# Non-Compete Restrictions
NON_COMPETE_DURATION_HIGH_MONTHS: int = 12
NON_COMPETE_DURATION_MEDIUM_MONTHS: int = 6
NON_COMPETE_BROAD_SCOPES: tuple[str, ...] = (
    "worldwide",
    "global",
    "unlimited",
    "anywhere",
    "any industry",
    "all industries",
    "nationwide",
    "across country",
)

# Other Employment Constants
UNREASONABLE_PROBATION_MONTHS: int = 6
HIGH_VARIABLE_PAY_PCT: float = 35.0


@dataclass(frozen=True)
class EmploymentThresholds:
    """Thresholds for deterministic Employment Offer risk analysis."""
    # Bond duration
    bond_duration_high_months: int = BOND_DURATION_HIGH_MONTHS
    bond_duration_medium_months: int = BOND_DURATION_MEDIUM_MONTHS
    max_bond_duration_months: int = BOND_DURATION_HIGH_MONTHS  # backwards compatibility alias
    # Bond salary multiple
    bond_salary_multiple_high: float = BOND_SALARY_MULTIPLE_HIGH
    bond_salary_multiple_medium: float = BOND_SALARY_MULTIPLE_MEDIUM
    max_bond_salary_multiple: float = BOND_SALARY_MULTIPLE_HIGH  # backwards compatibility alias
    # Notice period
    notice_asymmetry_employee_min_days_high: int = NOTICE_ASYMMETRY_EMPLOYEE_MIN_DAYS_HIGH
    notice_asymmetry_gap_medium_days: int = NOTICE_ASYMMETRY_GAP_MEDIUM_DAYS
    max_notice_period_days: int = MAX_NOTICE_PERIOD_DAYS
    max_notice_asymmetry_ratio: float = 2.0
    # Non-compete
    non_compete_duration_high_months: int = NON_COMPETE_DURATION_HIGH_MONTHS
    non_compete_duration_medium_months: int = NON_COMPETE_DURATION_MEDIUM_MONTHS
    max_non_compete_duration_months: int = NON_COMPETE_DURATION_HIGH_MONTHS  # backwards compatibility alias
    non_compete_broad_scopes: tuple[str, ...] = NON_COMPETE_BROAD_SCOPES
    # Probation & pay
    unreasonable_probation_months: int = UNREASONABLE_PROBATION_MONTHS
    high_variable_pay_pct: float = HIGH_VARIABLE_PAY_PCT


# ==============================================================================
# Deterministic Risk Threshold Constants: Rental Agreement Schema
# ==============================================================================
RENTAL_DEPOSIT_HIGH_MONTHS: int = 6
RENTAL_DEPOSIT_MEDIUM_MONTHS: int = 3
RENTAL_REFUND_MAX_DAYS: int = 30
RENTAL_LOCK_IN_MAX_MONTHS: int = 11
RENTAL_ESCALATION_MAX_PCT: float = 10.0
RENTAL_MIN_TENANT_NOTICE_DAYS: int = 30
RENTAL_MAX_NOTICE_ASYMMETRY_RATIO: float = 2.0


@dataclass(frozen=True)
class RentalThresholds:
    """Thresholds for deterministic Rental Agreement risk analysis."""
    max_security_deposit_months: int = RENTAL_DEPOSIT_HIGH_MONTHS
    moderate_security_deposit_months: int = RENTAL_DEPOSIT_MEDIUM_MONTHS
    max_deposit_refund_days: int = RENTAL_REFUND_MAX_DAYS
    max_lock_in_months: int = RENTAL_LOCK_IN_MAX_MONTHS
    max_annual_escalation_pct: float = RENTAL_ESCALATION_MAX_PCT
    min_tenant_notice_days: int = RENTAL_MIN_TENANT_NOTICE_DAYS
    max_notice_asymmetry_ratio: float = RENTAL_MAX_NOTICE_ASYMMETRY_RATIO


# ==============================================================================
# Deterministic Risk Threshold Constants: Freelance Contract Schema
# ==============================================================================
FREELANCE_PAYMENT_TERM_EXTENDED_DAYS: int = 45
FREELANCE_PAYMENT_TERM_STANDARD_DAYS: int = 30
FREELANCE_MAX_INCLUDED_REVISIONS: int = 3


@dataclass(frozen=True)
class FreelanceThresholds:
    """Thresholds for deterministic Freelance Contract risk analysis."""
    extended_payment_term_days: int = FREELANCE_PAYMENT_TERM_EXTENDED_DAYS
    max_payment_term_days: int = FREELANCE_PAYMENT_TERM_STANDARD_DAYS
    require_late_payment_penalty: bool = True
    require_kill_fee: bool = True
    require_payment_before_ip_transfer: bool = True
    max_included_revisions: int = FREELANCE_MAX_INCLUDED_REVISIONS


def _safe_int_env(key: str, default: int) -> int:
    val = os.getenv(key)
    if not val or not val.strip():
        return default
    try:
        return int(val.strip())
    except (ValueError, TypeError):
        return default


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
    gemini_fallback_model: str = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash")

    # Ephemeral Storage & Constraints
    session_ttl_seconds: int = _safe_int_env("SESSION_TTL_SECONDS", 600)
    upstash_redis_rest_url: str = os.getenv("UPSTASH_REDIS_REST_URL", "")
    upstash_redis_rest_token: str = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")
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


# Outcome B message for documents with no legal/contractual content
NON_LEGAL_DOCUMENT_MESSAGE: str = (
    "This document doesn't appear to contain legal or contractual content. "
    "JurisGuide is designed to analyze contracts and agreements — "
    "try uploading an employment offer, rental agreement, or freelance contract instead."
)

# Global settings singleton
settings = Settings()
