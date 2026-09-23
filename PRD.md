# PRD — JurisGuide
### A GenAI legal-contract assistant for the "Legal Information Accessibility" challenge

**Status:** Draft, pre-implementation | **Owner:** Solo project | **Version:** 2.1 (name locked)

---

## 1. Overview

**Problem statement (given):** Build a GenAI-powered solution that makes legal information and basic legal assistance more accessible — helping users understand, compare, and navigate legal documents.

**Core idea:** A schema-driven contract analysis engine. The user uploads any everyday legal document; the system identifies what type of document it is, extracts clause-level structured data against a matching schema, applies deterministic code-based risk rules, flags what's risky or missing, and outputs a plain-language summary, a severity-ranked risk list, and a checklist of questions for HR or a lawyer.

**Supported document types (v1):**
1. **Employment Offer Letter** (primary — bond clauses, notice periods, non-compete)
2. **Rental Agreement** (deposit terms, notice period, maintenance obligations)
3. **Freelance / Service Contract** (payment terms, IP assignment, kill fees, scope)

Anything outside these three still gets a **generic fallback analysis** (plain-language summary + general clause extraction, no schema-specific risk scoring) — see Section 6.4. Nothing the user uploads is ever flatly rejected as "unsupported."

**Why this design, not a single-vertical tool:** An earlier draft of this PRD scoped the tool to job offers only. That was revisited because a tool that can only accept one document type fails "practical and real-world usability" (an explicit Challenge Expectation) in an obvious, visible way — a user testing it with their own agreement would get nothing. The fix keeps the depth (schema-driven, code-based logic, fully testable) while fixing the breadth problem: the *pipeline* is generic, only the *schema config* is per-document-type, so adding coverage doesn't mean rebuilding logic per type.

**Explicitly not legal advice.** The tool informs and flags; it never tells the user what to decide. This is stated in the UI and the README, per the challenge's own NOTE.

---

## 2. Goals / Non-Goals

**Goals**
- Classify the uploaded document into one of the supported types (or "other")
- Extract clause-level structured data against the matching schema
- Apply deterministic, code-based risk rules to that structured data (not model judgment)
- Detect clauses that are conspicuously absent, per schema
- Output a plain-language summary, a severity-ranked risk list, and a "questions for HR / a lawyer" checklist
- Provide a safe generic fallback for document types outside the three supported schemas
- Be fully testable without live API calls
- Stay inside the 10MB repo limit, single branch, public

**Non-goals (v1)**
- Not a fully open-ended "any legal document, full logic" analyzer — only 3 types get full schema-based risk scoring; everything else gets the lighter fallback
- Not a chatbot / open-ended Q&A interface
- No OCR pipeline of its own (image/PDF understanding is delegated to Gemini's native multimodal input)
- No user accounts, no persistence/database beyond what a single session needs
- No legal-advice generation — no "you should sign" / "you should not sign" language anywhere
- **No cross-document comparison in v1** (the brief lists "comparing contracts" as one potential use case, but it is explicitly optional, not required — see the brief's own "not exhaustive or prescriptive" note). Single-document analysis was prioritized over comparison to keep the risk-scoring logic deep rather than splitting effort across two different capabilities. Worth flagging as a possible v2 addition in the README if time permits.

---

## 3. Target User & Core Use Case

**Persona:** Someone who has received or is reviewing an everyday legal document — a job offer, a rental agreement, or a freelance contract — and wants to understand what they're agreeing to, without paying for or having access to a lawyer at this stage.

**Core flow:**
Upload document (or paste text) → system classifies document type → extracted clauses shown → flagged risks ranked by severity (schema types) or general highlights (fallback) → missing-but-expected clauses shown (schema types) → checklist of questions to raise with the other party or a lawyer.

---

## 4. Input Handling

Four input paths, normalized into **two underlying code branches**:

| Input type | Path | Mechanism |
|---|---|---|
| PDF | Direct to Gemini | `inline_data`, `mime_type: application/pdf`, base64 |
| JPG | Direct to Gemini | `inline_data`, `mime_type: image/jpeg`, base64 |
| DOCX | Local extraction first | `python-docx` → plain text → sent as `text` part |
| Pasted text | Direct | Sent as `text` part |

**Validation required before any file reaches the model:**
- File type allow-list (reject anything not in {pdf, jpg, jpeg, docx}) — checked by content/magic bytes, not just file extension
- File size cap (e.g. 5MB per upload) — both for cost control and to stay clear of inline-data best-practice limits
- Reject empty files / empty pasted text with a clear user-facing error, not a raw exception

---

## 5. System Architecture

```
[Input Layer]
  → normalizes PDF/JPG/DOCX/text into a single request payload

[Classification Layer]  (Gemini, ONE small call)
  → "Which category does this document belong to: Employment Offer,
     Rental Agreement, Freelance Contract, or Other?"
  → this is real context-aware branching logic, not decoration

[Confirmation Step]  (no API call — UI only)
  → detected type shown to the user; user confirms or manually
    overrides before extraction proceeds (see Section 6.5)
  → held in in-memory session state only, never persisted to disk/DB

[Extraction Layer]  (Gemini, ONE call)
  → runs only after confirmation, against the confirmed type
  → if confirmed type is one of the 3 supported schemas:
      prompted to return strict JSON matching that Clause Schema (Section 6)
  → if "Other":
      prompted to return a lighter general-purpose extraction
      (plain summary + any clauses it can identify, unstructured-ish)
  → Gemini's job either way: read the document, extract data.
    No judgment, no advice, no risk scoring — that never happens in the model.
  → if the model returns malformed/non-schema-conforming JSON: one retry
    with a stricter re-prompt, then a clean user-facing error (never a
    raw exception or partial/garbled result shown as if it were valid)

[Analysis Layer]  (pure Python, NO API calls — this is the "logic" of the product)
  → for schema types: risk-scoring functions per clause type,
    missing-clause detector (schema diff), severity ranking
  → for "Other": pass-through of the general extraction, no scoring claims made

[Output Layer]
  → plain-language summary (template-based, not a second AI call — see Section 9)
  → severity-ranked risk list (schema types only)
  → "questions to ask" checklist
```

**Key design principle:** The model classifies and extracts; your code decides. This is what separates the submission from a thin LLM wrapper, and it's what makes the Analysis Layer unit-testable without ever touching the API. Adding a 4th supported document type later means writing a 4th schema config — not touching the pipeline.

**API call budget:** 2 Gemini calls per document in the normal path (classify + extract), 3 in the worst case (one extraction retry on malformed JSON) — comfortably inside a 500/day quota for development and demo use.

---

## 6. Clause Schemas (draft — to be finalized before coding starts)

Each clause type extracted has: `present` (bool), `raw_text` (string or null), and type-specific structured fields.

### 6.1 Employment Offer Letter

| Clause type | Key fields extracted | Example risk rule (code, not model) |
|---|---|---|
| Bond / training cost | amount, duration (months), forfeiture conditions | Flag if amount > N months' stated salary, or duration > 24 months |
| Notice period | employer-side notice, employee-side notice | Flag if asymmetric (e.g. employer 0 days vs employee 90 days) |
| Non-compete | duration, geographic scope, industry scope | Flag if duration > 12 months or scope overly broad |
| Confidentiality / IP assignment | scope, duration | Flag if IP assignment extends beyond employment without limit |
| Probation terms | duration, termination conditions | Flag if terms allow termination with no notice/reason |
| Salary / CTC breakdown | fixed vs variable split | Informational flag if variable component unusually high |
| Termination clause | grounds, notice required | Flag if grounds are vague/unbounded |

### 6.2 Rental Agreement

| Clause type | Key fields extracted | Example risk rule (code, not model) |
|---|---|---|
| Security deposit | amount, refund conditions, deduction terms | Flag if amount > N months' rent, or refund terms vague |
| Notice period | landlord-side, tenant-side | Flag if asymmetric or unusually short for tenant |
| Maintenance obligations | who pays for what, response time | Flag if tenant bears structural repair costs |
| Lock-in period | duration, penalty for early exit | Flag if lock-in > 11 months (common regional norm) or penalty excessive |
| Rent escalation | percentage, frequency | Flag if escalation clause is undefined or unusually high |

### 6.3 Freelance / Service Contract

| Clause type | Key fields extracted | Example risk rule (code, not model) |
|---|---|---|
| Payment terms | amount, milestones, late-payment penalty | Flag if no late-payment protection for freelancer |
| IP assignment | scope, timing (on payment vs on delivery) | Flag if IP transfers before payment is made |
| Kill fee / cancellation | conditions, compensation | Flag if no kill fee defined for client-side cancellation |
| Scope of work | defined deliverables, revision limits | Flag if scope is open-ended ("as needed") with no cap |
| Termination clause | notice required, grounds | Flag if client can terminate with no notice or compensation |

### 6.4 Fallback ("Other" document types)

- No schema-specific risk scoring or missing-clause detection (would be false confidence on an undefined schema)
- Extraction limited to: plain-language summary, any obligations/dates/parties the model can identify, generic "things to review" prompts
- UI clearly communicates this is a lighter-weight, general analysis — not the full risk-ranked treatment the 3 supported types get

**Missing-clause detection (schema types only):** if a clause type expected in that schema is entirely absent from extraction output, flag it as "not addressed" — runs entirely in code once extraction is done, no model call needed.

*(Exact numeric thresholds for all three schemas need to be defined with real numbers before coding; flagged as a TODO — Section 13.)*

### 6.5 Classification Confidence Handling — DECIDED

If Gemini's classification is not clearly one of the 3 supported types (or returns low confidence / ambiguous signal), the system does **not** silently auto-proceed. It surfaces the detected type(s) to the user and asks them to confirm or manually select the correct category before extraction runs. Only after confirmation does the pipeline proceed to the matching schema (or fallback, if the user selects "Other" / none apply).

This avoids two failure modes: (a) silently misclassifying a rental agreement as a freelance contract and applying the wrong risk rules with no indication anything was uncertain, and (b) never letting the user override a wrong guess.

---

## 7. Non-Functional Requirements (mapped to evaluation criteria)

### 7.1 Code Quality — High Impact
- Clear module separation: `input/`, `classification/`, `extraction/`, `analysis/`, `output/` — no logic mixed across layers
- Each document schema lives as its own config object (e.g. `schemas/employment_offer.py`, `schemas/rental_agreement.py`) — adding a type never means editing the engine
- Type hints throughout; docstrings on every public function
- No hardcoded thresholds inside logic functions — pull from each schema's own config, not scattered magic numbers
- No dead code, no commented-out experiments left in the final repo
- Consistent naming and formatting (run a formatter — e.g. `black` for Python — before each commit)

### 7.2 Security — High Impact
- API key loaded from environment variable / `.env`, never hardcoded; `.env` in `.gitignore` from commit #1
- Input validation on every upload (type, size, non-empty) before any processing
- **Prompt-injection awareness:** treat all extracted document text as untrusted data. The model is only ever asked to classify or extract into a fixed schema — it is never given the ability to alter your risk-scoring logic, since that logic lives entirely in your own code and never re-reads model-generated instructions as commands
- No raw exceptions or API error bodies shown to the end user — catch and present a generic, safe error message
- No PII persisted beyond the current session unless explicitly designed and disclosed (default: don't persist uploaded documents at all)

### 7.3 Efficiency — Medium Impact
- Maximum two Gemini API calls per document analyzed (classify + extract) — see Section 9 on why a third "phrasing" call is deferred
- No unnecessary dependencies — `python-docx` only, nothing added "just in case"
- Avoid reprocessing: cache/reuse extracted JSON within a session rather than re-calling the model if the user revisits the same result

### 7.4 Testing — High Impact (commonly skipped by other teams — a real differentiator)
- All Analysis Layer functions (risk scoring, missing-clause detection, ranking) unit-tested per schema with **mocked extraction JSON** — zero live API calls required to run the test suite
- At least one test per risk rule, per schema (e.g. bond threshold breach/no breach, deposit-amount breach/no breach, IP-timing breach/no breach)
- Classification logic tested with mocked model responses across all 4 categories (3 schemas + "Other")
- Input validation tested (oversized file, wrong file type, empty input)
- Tests must be runnable via a single documented command (e.g. `pytest`) and referenced in the README

### 7.5 Accessibility — Medium Impact (often forgotten)
- Semantic HTML structure (proper headings, labeled form inputs, not div-soup)
- Keyboard-navigable upload flow
- Risk severity never conveyed by color alone — pair every color indicator with a text label ("High Risk", not just a red dot)
- Sufficient contrast on all text/background combinations
- Alt text on any icons used
- Fallback-mode output visually distinguished from schema-scored output without relying on color alone (e.g. explicit heading: "General Analysis — Limited Detail")

---

## 8. Tech Stack (proposed — confirm before locking)

- **Backend:** Python, **FastAPI** — chosen over Flask because Pydantic models map directly onto the clause schemas (free validation on both extracted JSON and API request/response shapes), `TestClient` gives clean `pytest` integration, and auto-generated OpenAPI docs at `/docs` are a zero-effort accessibility/documentation bonus
- **LLM:** Gemini 3.5 Flash-Lite via `google-genai` SDK
- **DOCX parsing:** `python-docx`
- **Frontend:** Simple server-rendered HTML/CSS/JS or a minimal templating approach — no heavy framework, to keep repo size and complexity down
- **Testing:** `pytest`, with API calls mocked (e.g. `unittest.mock`)

---

## 9. Explicit Decisions & Rationale (for README "assumptions" section)

- **Classification step added deliberately** so the tool works on more than one document type without turning into an open-ended, unscored chatbot — classification output determines which fixed schema (or fallback) is used, it never determines model "judgment."
- **Only 3 document types get full schema-based risk scoring; everything else gets a lighter, clearly-labeled fallback.** This is a stated scope boundary, not a silent gap — chosen so depth of logic isn't diluted trying to cover every possible document type.
- **Third "phrasing" AI call deferred to post-v1.** Output text is generated from code-written templates filled with structured data, not an additional free-form model call. Keeps the pipeline to two API calls per document, removes a failure mode, keeps output deterministic and testable.
- **DOCX supported via text extraction (`python-docx`), not DOCX→PDF conversion.** Conversion would require a LibreOffice/Office binary dependency, adding infrastructure risk and repo complexity for no analytical benefit over direct text extraction.
- **JPG/PDF sent directly to Gemini's native multimodal input** rather than a custom OCR pipeline — confirmed supported via Google's official `generateContent` documentation (`inline_data` with `mime_type: image/jpeg` or `application/pdf`).
- **No user accounts or persistent storage in v1** — single-session tool, reduces security surface area significantly.
- **Fixed clause schemas, not fully open-ended extraction, for the 3 supported types** — a deliberate constraint so extraction output is structured, testable, and each risk rule maps cleanly to a schema field.

---

## 10. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Gemini misclassifies document type | Wrong schema applied, wrong risk rules run | Confirmation step (Section 6.5) — user always has final say before extraction |
| Gemini returns malformed/incomplete JSON | Analysis layer crashes or produces garbage output | Schema validation on receipt (Pydantic models), one retry, then clean error — never silently pass bad data downstream |
| Daily API quota (500 req/day) exhausted during testing or demo | Tool appears broken at the worst time | Mock Gemini responses for all automated tests; reserve live calls for manual verification only |
| Repo creeps over 10MB | Submission may not be evaluated at all (explicit rule) | `.gitignore` written before first commit; periodic `du -sh .git` checks; no sample files >1MB committed |
| Hallucinated clause values (e.g. wrong bond amount) presented as fact | User misled by confident-sounding wrong data | Always show `raw_text` alongside extracted structured values so the user can verify against the source; never hide the original clause text |
| Scope creep mid-build (adding a 4th document type, a comparison feature, etc.) | Risks missing the 3-attempt window with an unfinished submission | This PRD's Non-Goals (Section 2) are treated as binding for v1; new ideas go in a "v2 ideas" note, not into the current build |

---

## 11. Definition of Done (v1 submission-ready)

- [ ] All 3 schemas (Employment Offer, Rental Agreement, Freelance Contract) extract correctly on at least 3 real/realistic sample documents each
- [ ] Fallback path tested on at least 1 document outside the 3 schemas and produces a clearly-labeled general analysis, not an error
- [ ] Confirmation step works: user can override a detected type before extraction runs
- [ ] Full test suite passes with zero live API calls (all mocked)
- [ ] No secrets in git history; `.env.example` provided instead of real `.env`
- [ ] Repo verified under 10MB (`du -sh .git .`)
- [ ] Single branch, public visibility confirmed on GitHub itself, not just locally
- [ ] README contains all four required sections, explicitly labeled, matching Section 9's assumptions
- [ ] Manual pass through the UI with a screen reader or keyboard-only navigation, at minimum on the upload and results screens

---

## 12. Submission Constraints Checklist

- [ ] Repository is public
- [ ] Single branch only
- [ ] Repo size < 10MB (verify before each of the 3 attempts — check `.gitignore` covers `.env`, `__pycache__`, any sample test documents)
- [ ] README includes, explicitly labeled: chosen vertical/approach, logic, how the solution works, assumptions made
- [ ] No API key or secret committed anywhere in history (not just the latest commit)

---

## 13. Open Items (need answers before coding begins)

1. Final numeric thresholds for each risk rule, across all three schemas
2. Exact wording/tone for the "not legal advice" disclaimer, and where it's shown
3. Sample documents to test against — need 3–5 examples per schema type (offer letters, rental agreements, freelance contracts) covering different risk profiles, plus 1–2 "Other" type documents to test the fallback path
4. Exact classification prompt wording (the confirm-before-proceeding behavior itself is decided — see Section 6.5)

**Resolved:**
- ~~Flask vs FastAPI~~ → FastAPI (Section 8)
- ~~Low-confidence classification handling~~ → user confirms/selects type before extraction proceeds (Section 6.5)
- ~~Team structure~~ → solo project; no task-split planning needed

---

*This PRD is a living document — update Section 6 (schemas) and Section 13 (open items) as decisions are finalized. Everything in Sections 7, 9, 10 and 11 should be treated as binding constraints for code review, not aspirational notes.*
