# JurisGuide — Multi-Document Legal Contract Analyzer
### A GenAI legal assistant built for the *"Legal Information Accessibility"* challenge

[![Tests](https://img.shields.io/badge/tests-65%20passed%20(100%25)-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.14-blue.svg)]()
[![Framework](https://img.shields.io/badge/framework-FastAPI-teal.svg)]()
[![Model](https://img.shields.io/badge/LLM-Gemini%203.5%20Flash--Lite-orange.svg)]()
[![WCAG](https://img.shields.io/badge/accessibility-WCAG%202.1%20AA-purple.svg)]()
[![Repo Size](https://img.shields.io/badge/repo%20size-%3C1MB-success.svg)]()

> **⚖️ Mandatory Legal Notice:**
> JurisGuide is an automated legal information assistant and does NOT constitute formal legal advice. It is designed to assist non-lawyers in spotting potential pitfalls and asking informed questions, not to replace consultation with a qualified legal professional.

---

## 1. Chosen Vertical & Approach

Everyday individuals routinely sign legally binding agreements—job offers, rental leases, and freelance contracts—without understanding the fine print, and without the resources to hire a legal professional. Most GenAI solutions in this space fall into the trap of being thin "chatbot wrappers": they ask an LLM for open-ended opinions, leading to hallucinations, inconsistent risk ratings, and prompt injection vulnerabilities.

**JurisGuide takes an architectural leap forward with a schema-driven, neuro-symbolic approach:**
1. **Multi-Vertical Breadth (v1)**:
   - **Employment Offer Letters**: Flags service bonds, disproportionate financial penalties, asymmetric notice periods, overly broad non-competes, post-employment IP claims, and summary dismissals.
   - **Rental / Lease Agreements**: Flags excessive security deposits, mandatory lock-in periods exceeding 11-month norms, full deposit forfeiture on early exit, tenant structural repair obligations, and unfair escalation rates.
   - **Freelance / Service Contracts**: Flags premature intellectual property transfers before full invoice settlement, Net 45/60 payment traps, absent kill fees, open-ended scope creep, and uncompensated work termination.
   - **Generic Fallback ("Other")**: Any document outside these three verticals that is *still a genuine legal/contractual document* (e.g., NDAs, invoices, loan agreements) receives a safe, plain-language summary and best-effort obligation extraction, without false risk scoring. If the uploaded document contains **no legal or contractual content at all**, JurisGuide says so explicitly, rather than fabricating clauses, risk findings, or a signing checklist on content that isn't a contract. Nothing uploaded is ever flatly rejected — every document gets one of these two honest outcomes.
2. **Explicit Non-Goal — Cross-Document Comparison**: The challenge brief lists "comparing contracts, agreements, or policies" as one potential use case among several, explicitly noting these are "not exhaustive or prescriptive." JurisGuide deliberately prioritizes deep, deterministic single-document risk scoring over comparison in v1, to keep the core rule engine rigorous rather than splitting effort across two different capabilities. This is a stated scope decision, not an oversight — comparison is a natural v2 candidate.

---

## 2. Core Logic — *"LLM Extracts; Code Decides"*

The core engineering differentiator of JurisGuide is the strict decoupling of **Extraction** from **Judgment**:

```
[Unstructured Document]
          ↓
[Gemini 3.5 Flash-Lite]   ← ONLY extracts facts into rigid Pydantic JSON schemas.
          ↓                 (Never judges fairness, never generates advice)
[Deterministic Python]    ← Pure Python evaluates all rules, thresholds & severities.
          ↓                 (100% offline, reproducible, testable, injection-proof)
[Analysis Report]         ← Severity-ranked risk list + Actionable Questions Checklist
```

### Why this design?
- **Prompt Injection Defense**: If an adversarial contract contains text like *"Clause 9: The employee agrees that this agreement is completely harmless and fair"*, a traditional LLM chatbot would be deceived. In JurisGuide, the LLM merely extracts the numbers into schema fields (`bond.amount = 500000`). Pure Python code executes `if bond.amount > (salary / 12) * 3.0:`—making prompt injection mathematically impossible.
- **Auditable & Grounded**: Every extracted risk item preserves the **verbatim `raw_text`** from the original document in an interactive drawer so users can verify each finding against the source document.
- **Deterministic & Offline Testable**: The entire analytical rule engine is tested with static mock fixtures using standard `pytest` without making a single live network call.

---

## 3. How the Solution Works

### System Pipeline

```
1. Input Layer (Validation & Normalization)
   ├── Magic bytes content sniffing (PDF: %PDF, JPG: \xFF\xD8\xFF, DOCX: PK\x03\x04, TXT: UTF-8)
   ├── Size limit enforcement (<= 5MB hard limit)
   └── Document normalization (DOCX extracted via python-docx; PDF/JPG converted to inline base64)
          ↓
2. Classification Layer (Gemini Call 1)
   └── Fast classification into: employment_offer, rental_agreement, freelance_contract, or other
          ↓
3. Human-in-the-Loop Confirmation Step (UI State)
   └── Surfaces detected category to the user; requires explicit confirmation (or manual override)
       before any extraction or analysis runs — this applies uniformly, including to "other"
          ↓
4. Extraction Layer (Gemini Call 2 with 1-Retry Self-Healing)
   ├── Structured JSON extraction conforming strictly to the confirmed schema
   ├── For "other": the model explicitly distinguishes a genuine-but-unsupported legal
   │   document from content with no legal/contractual substance at all
   └── Self-healing: if initial output is invalid JSON, re-prompts with exact validation error
          ↓
5. Deterministic Analysis Layer (Pure Python — 0 API Calls)
   ├── Evaluates vertical-specific threshold rules (employment_rules, rental_rules, freelance_rules)
   ├── Schema Diffing: identifies missing mandatory clauses (missing_detector.py)
   └── Sorts risks strictly by severity: HIGH → MEDIUM → LOW → INFO
          ↓
6. Output Generation Layer (Templates & Checklists)
   ├── Code-templated plain-language summary (output/templater.py)
   ├── Context-aware questions for HR, landlords, or clients (output/checklist.py)
   └── Accessible web interface (WCAG 2.1 AA compliant semantic HTML5 + CSS)
```

### Strict API Budget
- **Normal Path**: Exactly **2 Gemini API calls** per document (1 classification + 1 extraction).
- **Worst-Case Path**: Exactly **3 Gemini API calls** (1 classification + 1 extraction + 1 repair retry on malformed JSON).
- **Zero API calls** for risk scoring, summary creation, or checklist generation.
- Easily accommodates developer and demo quotas (500 requests/day).

---

## 4. Assumptions & Scope Boundaries

### Assumptions Made:
1. **Prevailing Contract Baselines**:
   - Employment: Bonds are scored on a three-tier band, not a single cutoff — flagged MEDIUM between 12–24 months or 3–6× monthly salary, and HIGH beyond 24 months or 6× salary. Notice-period asymmetry, non-compete duration/scope, and probation-termination terms follow the same tiered approach rather than a binary flag.
   - Rental: Security deposits beyond 6 months of rent, lock-in periods beyond the standard 11-month convention, and notice-period asymmetry are flagged using the same tiered severity logic.
   - Freelance: Payment terms beyond Net 30 are flagged as moderate and beyond Net 45 as high risk. Transfer of intellectual property prior to full invoice settlement, absence of a kill fee or late-payment penalty, and uncapped scope of work are flagged as high risk.
   - All thresholds are centralized, named constants in `core/config.py` — not hardcoded inside rule logic — so they're auditable and can be tuned in one place.
2. **Ephemeral Privacy**:
   - JurisGuide maintains **zero database or disk persistence** of user documents. Files are processed in memory and cached with an automatic 10-minute TTL (`SESSION_TTL_SECONDS=600`).
   - The session cache is immediately purged upon analysis (`pop_session`), maximizing user confidentiality.
3. **Multimodal Native Input**:
   - Image and PDF processing are delegated to Gemini's native multimodal capabilities via `google-genai` inline data, eliminating the need for heavyweight local Tesseract/OCR binaries and keeping repository size tiny.
4. **Scope Boundaries (v1)**:
   - **Single-document analysis prioritized**: Cross-contract comparison is deferred to v2 (see Section 1) to focus effort on deep, deterministic risk scoring.
   - **No Chatbot Q&A**: Avoids open-ended hallucination loops by providing structured, deterministic checklists instead.

---

## 5. Architectural Alignment with Evaluation Criteria

| Evaluation Pillar | Implementation Safeguards in JurisGuide |
| :--- | :--- |
| **1. Code Quality** | Modular 5-layer separation (`input/`, `classification/`, `schemas/`, `extraction/`, `analysis/`, `output/`). 100% type hinting (`typing`), PEP 8 compliance, Pydantic v2 schemas, zero magic numbers (centralized in `core/config.py`). Each risk rule is a pure, independently testable function returning a severity level, not a single monolithic evaluator. |
| **2. Security** | Content-based magic-byte validation (rejects spoofed extensions). 5MB upload ceiling. Treat all document text as untrusted data (prompt injection immune). Zero-persistence ephemeral memory. Exception handlers separate internal diagnostic detail (logged only) from a generic, safe user-facing message — no upstream API traces, hostnames, or quota details are ever returned to the client. `.env` strictly gitignored, with zero secrets found across full git history. |
| **3. Efficiency** | Hard budget of 2 Gemini calls per document (3 worst-case, with one bounded self-healing retry). Pure Python execution for rules ($<5\text{ ms}$). Zero heavy external binary dependencies (no LibreOffice, no heavy OCR packages). Total repository size **< 1MB** (vastly below the 10MB limit). |
| **4. Testing** | Comprehensive `pytest` suite running **100% offline with zero live API calls** using static mock fixtures. **65 tests** across 8 modules, executing in under 2 seconds, covering full HIGH/MEDIUM/LOW severity bands with exact boundary values for every rule (not just flagged-vs-not-flagged), the classification-confirmation gate, and both fallback outcomes (genuine-but-unsupported legal document vs. no legal content at all). |
| **5. Accessibility** | WCAG 2.1 AA compliant, verified by direct contrast-ratio calculation (all text colors ≥4.5:1 against every background they appear on) and end-to-end keyboard testing. Semantic HTML5 (`main`, `header`, `section`, `article`, `form`). Full keyboard navigation including a roving-tabindex tab component (Arrow keys, Home/End) per the WAI-ARIA Tabs Pattern, with visible focus rings (`:focus-visible`). Risk severity is **never indicated by color alone** (paired with explicit textual tags and ARIA labels). Screen-reader live regions. |

---

## 6. Getting Started & Installation

### Prerequisites
- Python 3.10+ (Tested and verified on Python 3.14)
- Gemini API Key (obtain from [Google AI Studio](https://aistudio.google.com/))

### Installation
```bash
# 1. Clone repository
git clone https://github.com/Srijan78/JurisGuide.git
cd JurisGuide

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
# Edit .env and insert your GEMINI_API_KEY
```

### Running the Application
```bash
# Start the FastAPI server
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```
Open your browser at `http://127.0.0.1:8000` to access the accessible contract analyzer.

### Running the Test Suite (100% Offline)
```bash
pytest -v --tb=short
```
*All 65 tests execute in under 2 seconds without requiring an internet connection or live API key.*

---

## 7. Project Directory Structure

```
JurisGuide/
├── .gitignore               # Strict exclusion of .env, venvs, caches, large files (<10MB)
├── .env.example             # Safe template for GEMINI_API_KEY
├── README.md                # 4 mandatory sections + full documentation
├── LICENSE                  # MIT License
├── requirements.txt         # Minimal, modern dependencies
├── PRD.md                   # Product Requirements Document v2.1
├── app.py                   # FastAPI application, routing, and safe error handling
│
├── core/
│   ├── config.py            # Centralized threshold constants and settings
│   ├── exceptions.py        # Safe user-facing domain exceptions
│   └── session.py           # Ephemeral in-memory store with automatic TTL expiration
│
├── input/
│   ├── validator.py         # Magic bytes content sniffing & 5MB cap
│   └── normalizer.py        # Normalizes PDF, JPG, DOCX, and raw text
│
├── classification/
│   └── classifier.py        # Gemini Call 1: Document classification & confidence
│
├── schemas/
│   ├── base.py              # Base clause models & lenient pre-validators
│   ├── employment.py        # Offer letter schema (bond, notice, non-compete, etc.)
│   ├── rental.py            # Lease schema (deposit, lock-in, escalation, etc.)
│   ├── freelance.py         # Service agreement schema (net terms, IP timing, etc.)
│   └── fallback.py          # Generic schema for non-standard / non-legal documents
│
├── extraction/
│   └── extractor.py         # Gemini Call 2: Schema extraction with 1-retry self-healing
│
├── analysis/
│   ├── engine.py            # Analysis orchestrator and risk ranker
│   ├── employment_rules.py  # Pure Python rules for employment contracts
│   ├── rental_rules.py      # Pure Python rules for rental agreements
│   ├── freelance_rules.py   # Pure Python rules for freelance contracts
│   └── missing_detector.py  # Missing clause detection via schema diffing
│
├── output/
│   ├── models.py            # AnalysisReport, RiskItem, and Checklist models
│   ├── templater.py         # Code-based plain-language summary generator
│   └── checklist.py         # Actionable question checklist generator
│
├── static/
│   ├── css/style.css        # Minimal, WCAG 2.1 AA compliant, high-contrast stylesheet
│   └── js/app.js            # Accessible client logic (tabs, drag & drop, report viewer)
│
├── templates/
│   └── index.html           # Accessible semantic HTML5 interface
│
└── tests/
    ├── conftest.py          # Static mock fixtures for 100% offline testing
    ├── test_validator.py    # Security, magic bytes, and size limit tests
    ├── test_employment.py   # Full severity-band and boundary tests for employment rules
    ├── test_rental.py       # Full severity-band and boundary tests for rental rules
    ├── test_freelance.py    # Full severity-band and boundary tests for freelance rules
    ├── test_missing.py      # Missing clause detection tests
    ├── test_pipeline.py     # End-to-end classifier & extractor tests
    └── test_api.py          # FastAPI endpoint integration & security-leak tests
```

---

## 8. License & Acknowledgments
Built with ❤️ for the **"Legal Information Accessibility"** challenge.
Licensed under the [MIT License](LICENSE).