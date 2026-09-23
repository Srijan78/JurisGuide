"""Pytest configuration and static mock fixtures for 100% offline testing."""

import json
from unittest.mock import MagicMock
import pytest
from core.session import session_store


@pytest.fixture(autouse=True)
def clean_session_store():
    """Ensure session store is completely cleared before and after each test."""
    session_store.clear_all()
    yield
    session_store.clear_all()


@pytest.fixture
def mock_gemini_client():
    """Create a mock Google GenAI client returning structured JSON."""
    client = MagicMock()
    return client


@pytest.fixture
def sample_employment_json():
    """Static mock JSON fixture for employment offer letter."""
    return {
        "candidate_name": "Alice Developer",
        "designation_role": "Senior Fullstack Engineer",
        "joining_date": "2026-10-01",
        "bond": {
            "present": True,
            "amount": 500000.0,
            "duration_months": 24,
            "raw_text": "The candidate agrees to serve the company for 24 months or pay a bond of INR 5,00,000."
        },
        "notice_period": {
            "present": True,
            "employer_notice_days": 15,
            "employee_notice_days": 90,
            "buyout_option": False,
            "raw_text": "Employee must give 90 days notice; company may terminate with 15 days notice."
        },
        "non_compete": {
            "present": True,
            "duration_months": 12,
            "geographic_scope": "Worldwide",
            "industry_scope": "Software Engineering",
            "raw_text": "Employee shall not engage in competing business worldwide for 12 months."
        },
        "confidentiality_ip": {
            "present": True,
            "perpetual_ip_assignment": True,
            "post_employment_ip_claim": True,
            "raw_text": "All inventions created during or after employment belong to the company."
        },
        "probation": {
            "present": True,
            "duration_months": 6,
            "immediate_termination_allowed": True,
            "raw_text": "During probation, employer may terminate without cause or notice."
        },
        "salary_breakdown": {
            "present": True,
            "fixed_amount": 1200000.0,
            "variable_amount": 600000.0,
            "variable_pct": 33.3,
            "currency": "INR",
            "period": "annual"
        },
        "termination": {
            "present": True,
            "notice_required_days": 30,
            "grounds_specified": True,
            "summary_termination_without_hearing": True,
            "raw_text": "Company reserves the right to terminate immediately without enquiry."
        }
    }


@pytest.fixture
def sample_rental_json():
    """Static mock JSON fixture for rental agreement."""
    return {
        "tenant_name": "Bob Tenant",
        "landlord_name": "Landlord Larry",
        "property_address": "Apartment 5B, Skyline Heights",
        "monthly_rent": {
            "present": True,
            "monthly_amount": 30000.0,
            "due_day": 5,
            "late_fee_per_day": 200.0
        },
        "security_deposit": {
            "present": True,
            "amount": 240000.0,
            "deposit_months": 8.0,
            "refund_timeline_days": 45,
            "raw_text": "Tenant shall deposit 8 months rent refundable within 45 days."
        },
        "notice_period": {
            "present": True,
            "tenant_notice_days": 60,
            "landlord_notice_days": 15,
            "raw_text": "Tenant gives 60 days notice; Landlord gives 15 days notice."
        },
        "maintenance": {
            "present": True,
            "tenant_bears_structural_repairs": True,
            "raw_text": "Tenant is responsible for all structural, wall seepage, and plumbing repairs."
        },
        "lock_in": {
            "present": True,
            "duration_months": 24,
            "forfeits_entire_deposit_on_early_exit": True,
            "raw_text": "Mandatory 24 months lock-in. 100% deposit forfeited if tenant vacates early."
        },
        "rent_escalation": {
            "present": True,
            "escalation_pct": 15.0,
            "frequency_months": 11,
            "raw_text": "Rent escalates by 15% after 11 months."
        }
    }


@pytest.fixture
def sample_freelance_json():
    """Static mock JSON fixture for freelance contract."""
    return {
        "freelancer_name": "Charlie Designer",
        "client_name": "Acme Brand",
        "project_title": "Brand Design System",
        "payment_terms": {
            "present": True,
            "net_days": 60,
            "advance_deposit_pct": 10.0,
            "has_late_payment_clause": False,
            "raw_text": "Payment shall be made Net 60 days after invoice. No interest on delay."
        },
        "ip_assignment": {
            "present": True,
            "timing_of_transfer": "upon_creation",
            "transfers_before_full_payment": True,
            "portfolio_rights_retained": False,
            "raw_text": "All IP vests in Client upon creation regardless of payment status."
        },
        "kill_fee": {
            "present": True,
            "kill_fee_defined": False,
            "raw_text": "Client may cancel at any time with no kill fee."
        },
        "scope_of_work": {
            "present": True,
            "defined_deliverables": False,
            "open_ended_scope": True,
            "revision_limit_count": None,
            "raw_text": "Contractor shall perform design tasks as requested with unlimited revisions."
        },
        "termination": {
            "present": True,
            "notice_days": 3,
            "payment_for_completed_milestones_guaranteed": False,
            "raw_text": "Client may terminate with 3 days notice without obligation for unapproved work."
        }
    }
