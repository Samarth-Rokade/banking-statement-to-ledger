# AI Bank Statement → Tally Ledger Generator — Technical Plan (v1.0)

> Companion to `AI_Bank_Statement_to_Tally_Ledger_Project_Specification.md`. That file is the
> **what/why**; this file is the **how** — concrete enough to build module-by-module without
> re-deriving decisions mid-implementation. If something here conflicts with the spec, the spec
> wins on scope/goals, this file wins on implementation detail.

---

## Table of Contents

**Part A — System Architecture & AI Design**
1. End-to-end workflow
2. AI decision pipeline
3. Confidence scoring
4. Ledger matching algorithm
5. Prompt engineering
6. Database relationships (ERD)
7. Processing queue
8. Error handling
9. Performance considerations

**Part B — Backend & Frontend Implementation Guide**
10. Database models (every table, every column)
11. API endpoints (every route, request/response)
12. React pages (every screen, every state)
13. Folder structure (backend + frontend)
14. Component hierarchy
15. Service layer
16. Repository layer
17. AI service implementation
18. Sequence diagrams
19. State management
20. Testing strategy
21. Deployment

---

# PART A — System Architecture & AI Design

## 1. End-to-end workflow

```
User uploads file (PDF/CSV/XLSX)
    │
    ▼
[Upload API] validates MIME/size → stores raw file → creates ProcessingJob (status=QUEUED)
    │                                                        returns job_id immediately (202)
    ▼
[Job Worker] picks job off queue
    │
    ├─▶ Statement Parser        → raw rows (date, description, ref, debit, credit, balance)
    ├─▶ Transaction Normalizer  → canonical narration + transaction_type tag
    ├─▶ Rule Engine             → deterministic ledger/group hits (no AI)
    ├─▶ Ledger Matching Engine  → Exact → Alias → Similarity (pg_trgm/fuzzy), still no AI
    ├─▶ AI Prediction Engine    → ONLY for transactions unresolved above
    ├─▶ Validation Engine       → ledger/group/voucher exist, dr/cr sign check, duplicate check
    ├─▶ Voucher Generator       → Receipt/Payment/Contra/Journal assignment
    └─▶ persist ParsedTransaction rows with resolution_source + confidence
    │
    ▼
Job status → REVIEW_REQUIRED or READY, transaction counts updated
    │
    ▼
[Manual Review UI] shows only low-confidence rows
    │  user approves / edits ledger / edits group / edits voucher
    ▼
[Learning System] on every correction → upsert LedgerAlias / narration→ledger mapping
    │
    ▼
[Export] Excel / CSV / Tally XML — re-validated at export time, never trusts stale state
```

Key invariant: **every stage after the parser can mark a transaction "resolved" and short-circuit
all later stages for that transaction.** This is what keeps Gemini usage to the residual only.

## 2. AI decision pipeline

Per-transaction resolution is a strict waterfall. Each stage either resolves the transaction
(writes `ledger_id`, `group_id`, `voucher_type`, `confidence`, `resolution_source`) or passes it
to the next stage untouched.

| Stage | Source enum | Can it resolve? | Typical confidence |
|---|---|---|---|
| 0. Rule Engine | `RULE` | Yes, exact keyword/regex match | 100 |
| 1. Exact Ledger Match | `EXACT_MATCH` | Yes, normalized narration == ledger name/alias | 100 |
| 2. Alias Match | `ALIAS_MATCH` | Yes, narration matches a stored `ledger_aliases` row | 95–100 |
| 3. Similarity Match | `SIMILARITY_MATCH` | Yes, **only if** top similarity score ≥ `SIMILARITY_AUTO_THRESHOLD` (default 0.90) | scaled from similarity score |
| 4. AI Prediction (Gemini) | `AI_PREDICTION` | Yes, if Gemini confidence ≥ `AI_AUTO_ACCEPT_THRESHOLD` (default 90) | as returned by model |
| 5. Manual Review | `MANUAL` | Human sets it | 100 (post-correction) |

A transaction that reaches stage 4 without full resolution but scores below the auto-accept
threshold is still saved with `resolution_source=AI_PREDICTION` and `requires_review=true` — it is
never discarded, always shown in Module 12 (Manual Review) with the AI's best guess pre-filled.

**Batching rule:** Gemini is called once per **upload job**, not once per transaction. All
unresolved transactions in a job are batched into a single prompt (chunked at ~40 transactions per
call to stay within reliable JSON-output length), because:
- One call carries the full ledger/group/rule context once instead of N times (cost + latency).
- Reduces rate-limit exposure.
- Chunk size is configurable (`AI_BATCH_SIZE`); if a chunk's transactions are highly similar
  narrations (e.g., 200 identical "UPI-SWIGGY" rows), collapse to one representative + fan-out the
  result to all identical narrations before calling Gemini at all (this is really a similarity-match
  optimization, not an AI one).

## 3. Confidence scoring

Confidence is a single 0–100 integer stored per transaction, but computed differently per source:

- **Rule / Exact / Alias**: fixed 100 (deterministic, no ambiguity).
- **Similarity match**: `confidence = round(similarity_score * 100)` where `similarity_score` is
  the blended score described in §4. Only auto-accepted ≥ 90; otherwise routed to AI stage anyway
  (a below-threshold similarity hit is passed to Gemini **as a candidate**, not discarded — see §5
  prompt inputs).
- **AI prediction**: Gemini is instructed to self-report confidence 0–100 based on explicit rubric
  (see prompt in §5). The backend does not blindly trust this number — it is clamped by two
  guardrails:
  1. If the predicted `ledger_name` doesn't exist yet (new ledger) → confidence capped at 85,
     regardless of what Gemini returned, because new-ledger creation always needs a human glance
     the first time.
  2. If amount sign (debit vs credit) contradicts the predicted voucher type (e.g., voucher=Receipt
     but transaction is a debit) → confidence forced to 0 and `requires_review=true` (this is a
     validation-engine catch, logged as `AI_INCONSISTENT`).
- **Review threshold**: `MANUAL_REVIEW_THRESHOLD` (default 90). Anything below → surfaced in
  Module 12. This threshold is a `rules` table row (`rule_type=CONFIG`), not a hardcoded constant,
  so it's tunable without a deploy.

## 4. Ledger matching algorithm

Input: normalized narration string (from Module 5) + transaction amount/direction.

```
normalize(narration) → strip amounts/dates/reference numbers, uppercase, collapse whitespace,
                        strip common noise tokens (NEFT, IMPS, UPI, prefixes/suffixes already
                        classified by the normalizer, not the ledger name itself)

1. EXACT MATCH
   SELECT * FROM ledgers WHERE upper(name) = normalize(narration)
   → if 1 row: resolved, confidence=100, source=EXACT_MATCH

2. ALIAS MATCH
   SELECT * FROM ledger_aliases WHERE upper(alias) = normalize(narration)
   → if 1 row: resolved via alias.ledger_id, confidence=100, source=ALIAS_MATCH
   (aliases are populated both manually via Module 7 UI and automatically by Module 13
    Learning System on every manual correction)

3. SIMILARITY MATCH
   Candidate generation: pg_trgm GIN index on ledgers.name and ledger_aliases.alias
     SELECT id, name, similarity(name, :narration) AS score
     FROM ledgers
     WHERE name % :narration              -- trigram operator, uses index
     ORDER BY score DESC LIMIT 5

   Blended score = 0.7 * trigram_similarity + 0.3 * (1 - normalized_levenshtein_distance)
   Top candidate score ≥ SIMILARITY_AUTO_THRESHOLD (0.90) → resolved, source=SIMILARITY_MATCH
   Top candidate score in [0.60, 0.90)  → NOT auto-resolved, but the top 3 candidates are
     attached to the transaction as `similar_candidates` (JSONB) and forwarded to the AI stage
     as extra context so Gemini can pick from real, existing ledgers instead of hallucinating
     near-duplicates.
   Top candidate score < 0.60 → no candidates forwarded; AI stage treats this as a probable
     new ledger.
```

Rationale for the blend: trigram similarity alone over-rewards short common substrings ("SBI");
Levenshtein alone is too strict on reordered words ("PRODUCTS VCT" vs "VCT PRODUCTS"). The blend
was chosen for robustness, not tuned against a labeled set yet — **flag this as a v1 assumption to
revisit once real statements are available**, and expose the weights as config, not constants.

## 5. Prompt engineering

Four dedicated prompt templates (Markdown files under `backend/app/prompts/`), each doing exactly
one job, each demanding **JSON-only output** validated against a Pydantic schema on receipt (a
response that fails schema validation is retried once with the validation error appended to the
prompt, then falls back to `requires_review=true` with `resolution_source=AI_FAILED`).

### `ledger_prediction.md`
Used for: assigning ledger_name (existing or new) + group + confidence to a batch of unresolved
transactions.

Inputs injected at call time:
- List of transactions: `{id, date, normalized_narration, original_narration, debit, credit}`
- Full list of existing ledger names + groups (or a filtered subset if the ledger table is large —
  see performance notes in §9)
- `similar_candidates` per transaction (from §4, when present)
- Active `rules` table entries (as illustrative examples, not authoritative — rules already
  resolved their matches upstream, so anything reaching this prompt did NOT match a rule)
- Confidence rubric spelled out explicitly:
  - 95–100: narration unambiguously matches a known counterparty/pattern
  - 80–94: strong lexical/contextual match but some ambiguity (e.g., generic "TRANSFER")
  - 60–79: plausible guess, multiple candidates equally likely
  - <60: insufficient information, default to a generic "Suspense Account" ledger suggestion

Output schema (array, one object per input transaction):
```json
[{
  "transaction_id": "uuid",
  "ledger_name": "VCT PRODUCTS",
  "is_new_ledger": false,
  "group": "Sundry Creditors",
  "confidence": 96,
  "reasoning": "short string, logged not shown to end user by default"
}]
```

### `ledger_group_prediction.md`
Used only when `is_new_ledger=true` and the group couldn't be inferred with confidence in the main
call (rare — kept separate so the main prompt doesn't need the full group taxonomy inline every
time). Given a new ledger name + narration + amount pattern, return one of Tally's standard groups
(Sundry Debtors, Sundry Creditors, Indirect Expenses, Indirect Income, Bank Accounts, Cash-in-Hand,
Loans & Advances, Duties & Taxes, etc. — enumerated in `ledger_groups` seed data, never freeform).

### `voucher_prediction.md`
Given resolved ledger + group + debit/credit direction, return voucher type. This is *mostly*
rule-based (see Module 14) — Gemini is only consulted when the rule table has no entry for that
group+direction combination yet, which should shrink over time as rules are added.

### `validation.md`
A lightweight secondary check used only for high-value transactions (amount over a configurable
`AI_VALIDATION_AMOUNT_THRESHOLD`) or when the Validation Engine's deterministic checks (§ Module
11) flag an anomaly. Asks Gemini a yes/no + reason: "does this ledger/group/voucher assignment look
correct given the narration and amount?" Used as a second opinion, not a primary decision path —
keeps the "Gemini decides only when deterministic stages fail" principle intact even for edge
cases.

**Shared prompt discipline:**
- Every prompt ends with an explicit instruction: *"Respond with JSON only. No markdown fences, no
  commentary."*
- Every prompt call uses Gemini's structured output / response schema mode (not just prompt-level
  instruction) as the primary enforcement; the instruction text is a belt-and-suspenders backup for
  models/configs where structured mode isn't available.
- Temperature is set low (0.1–0.2) — this is a classification task, not a creative one.
- Gemini 2.5 Flash is used for `voucher_prediction` and `ledger_group_prediction` (cheap,
  low-ambiguity classification); Gemini 2.5 Pro is reserved for `ledger_prediction` (the highest
  stakes, most ambiguous decision) and `validation`.

## 6. Database relationships (ERD)

```
users ─┬──< uploaded_files ──< processing_jobs ──< parsed_transactions >──┬── ledgers ──< ledger_aliases
       │                                                │                 │      │
       │                                                │                 │      └──< ledger_groups (FK: ledgers.group_id)
       │                                                │                 │
       │                                                ├──< ai_predictions (1:1 per transaction, audit trail)
       │                                                ├──< manual_corrections (append-only log)
       │                                                └──< vouchers (1:1 once voucher generated)
       │
       └──< audit_logs (polymorphic: entity_type + entity_id)

rules (standalone config table, referenced by keyword match, not FK)
voucher_types (lookup table: Receipt/Payment/Contra/Journal)
```

Full column-level detail in §10.

## 7. Processing queue

- Upload endpoint **never** parses inline. It stores the file, inserts a `processing_jobs` row
  with `status=QUEUED`, and returns `202 Accepted` with `job_id`.
- Queue implementation: **Postgres-backed job table + a polling/async worker** (no Redis/Celery
  dependency for v1, since throughput is statement-upload-driven, not high-frequency — this keeps
  infra minimal per the "correctness before performance" guideline). FastAPI `BackgroundTasks` is
  insufficient for durability across restarts, so a dedicated worker process (`app/jobs/worker.py`)
  polls `processing_jobs WHERE status='QUEUED' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1`.
  This is a deliberate choice to avoid adding Celery/RabbitMQ complexity until proven necessary —
  **flag for revisit if concurrent upload volume grows.**
- Job states: `QUEUED → PARSING → NORMALIZING → MATCHING → AI_PREDICTING → VALIDATING →
  REVIEW_REQUIRED | READY → EXPORTED`, plus terminal `FAILED` from any state.
- Each state transition is written with a timestamp (`processing_jobs.status_history` JSONB) for
  the Processing Status page (Module 4) to render a real progress trail, not just a spinner.
- Idempotency: worker claims a job row via `SKIP LOCKED` before processing, so two worker
  processes never double-process the same job.

## 8. Error handling

| Failure point | Handling |
|---|---|
| Corrupt/unparseable PDF | Job → `FAILED`, `error_message` stored, user notified with a specific reason (not a generic "processing failed") |
| Camelot/pdfplumber extracts 0 rows | Fallback to PaddleOCR → Tesseract chain; if all fail, `FAILED` with "no transactions detected — file may be a scanned image with poor quality" |
| Gemini API error/timeout | Retry with exponential backoff (max 3 attempts); on final failure, affected transactions saved with `resolution_source=AI_FAILED`, `requires_review=true` — job still completes, doesn't block the whole batch |
| Gemini returns invalid JSON | One retry with the parse error fed back into the prompt; second failure → same `AI_FAILED` path above |
| Duplicate transaction detected | Not an error — flagged (`is_duplicate=true`, linked to the original via `duplicate_of_transaction_id`), surfaced in review, excluded from export by default but never silently dropped |
| Validation Engine finds inconsistency (e.g., predicted ledger doesn't exist, dr/cr mismatch) | Confidence forced to 0, `requires_review=true`, reason stored in `validation_errors` (JSONB array) |
| Export requested while job not `READY`/has unresolved reviews | `409 Conflict` — export is blocked until all required transactions are resolved (or user explicitly opts to export "as-is, excluding unresolved") |

All errors are logged to `audit_logs` with enough context (job_id, transaction_id, stage, raw
error) to debug without reproducing.

## 9. Performance considerations

- **Ledger context size in prompts**: if `ledgers` table grows large (hundreds+), don't inline the
  full list into every Gemini call. Pre-filter to the top-N candidates via the same pg_trgm query
  used in §4 (just with a looser threshold), plus all ledgers in groups that rule-matching has
  historically produced for similar narrations. Cap at a configurable `AI_MAX_LEDGER_CONTEXT` (e.g.
  150) to bound token cost and latency.
- **Indexes**: GIN trigram index on `ledgers.name` and `ledger_aliases.alias`
  (`CREATE EXTENSION pg_trgm`); btree indexes on `parsed_transactions(processing_job_id)`,
  `(resolution_source)`, `(requires_review)` for the review-queue query; unique constraint on
  `(processing_job_id, date, description, debit, credit, balance)` hash for fast duplicate
  detection within a job, plus a broader cross-job duplicate check on
  `(ledger_id, date, amount, reference)`.
- **Batch AI calls**: as described in §2, one call per chunk of unresolved transactions, not per
  row — this is the single biggest cost/latency lever.
- **Async I/O**: FastAPI endpoints that only enqueue work stay fully async; the worker process
  doing PDF parsing/OCR is CPU-bound and should run parsing in a process pool
  (`concurrent.futures.ProcessPoolExecutor`), not block the async event loop.
- **Large statements**: stream-parse PDFs page-by-page rather than loading the whole document into
  memory; commit `parsed_transactions` in batches (e.g., 200 rows) rather than one INSERT per row.
- Per the spec's priorities: correctness first. None of the above should compromise the
  waterfall-before-AI principle even under load — if anything, tightening it (smaller AI context,
  more rule/alias hits) is the correct lever, not skipping validation.

---

# PART B — Backend & Frontend Implementation Guide

## 10. Database models (every table, every column)

All tables have `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `created_at`, `updated_at`
timestamps unless noted. FKs use `ON DELETE RESTRICT` unless stated otherwise (this domain should
never silently cascade-delete financial records).

**users**
| column | type | notes |
|---|---|---|
| email | varchar unique | |
| hashed_password | varchar | bcrypt |
| full_name | varchar | |
| is_active | boolean default true | |

**uploaded_files**
| column | type | notes |
|---|---|---|
| user_id | FK users | |
| original_filename | varchar | |
| storage_path | varchar | local disk or S3-compatible path |
| file_type | enum(PDF,CSV,XLSX) | |
| file_size_bytes | bigint | |
| checksum_sha256 | varchar | dedupe re-uploads |

**processing_jobs**
| column | type | notes |
|---|---|---|
| uploaded_file_id | FK uploaded_files | |
| status | enum (see §7 state list) | |
| status_history | JSONB | array of {status, timestamp} |
| total_transactions | int default 0 | |
| auto_matched_count | int default 0 | |
| ai_predicted_count | int default 0 | |
| manual_review_count | int default 0 | |
| export_ready_count | int default 0 | |
| error_message | text nullable | |
| started_at / completed_at | timestamp nullable | |

**parsed_transactions**
| column | type | notes |
|---|---|---|
| processing_job_id | FK processing_jobs | |
| row_number | int | order within source file |
| txn_date | date | |
| original_narration | text | as extracted |
| normalized_narration | text | Module 5 output |
| reference | varchar nullable | cheque no / UTR etc |
| debit | numeric(15,2) default 0 | |
| credit | numeric(15,2) default 0 | |
| balance | numeric(15,2) nullable | |
| transaction_type_tag | varchar nullable | UPI/NEFT/RTGS/etc from normalizer |
| ledger_id | FK ledgers nullable | |
| group_id | FK ledger_groups nullable | |
| voucher_type_id | FK voucher_types nullable | |
| confidence | int (0-100) | |
| resolution_source | enum (RULE, EXACT_MATCH, ALIAS_MATCH, SIMILARITY_MATCH, AI_PREDICTION, MANUAL, AI_FAILED) | |
| similar_candidates | JSONB nullable | top-3 from similarity stage |
| requires_review | boolean default false | |
| is_duplicate | boolean default false | |
| duplicate_of_transaction_id | FK parsed_transactions nullable | self-ref |
| validation_errors | JSONB nullable | array of strings |
| reviewed_by_user_id | FK users nullable | set on approval/edit |
| reviewed_at | timestamp nullable | |

**ledger_groups**
| column | type | notes |
|---|---|---|
| name | varchar unique | e.g. "Sundry Creditors" |
| tally_group_type | varchar | maps to Tally's standard group taxonomy |
| parent_group_id | FK ledger_groups nullable | self-ref, Tally groups nest |

**ledgers**
| column | type | notes |
|---|---|---|
| name | varchar unique | |
| group_id | FK ledger_groups | |
| usage_count | int default 0 | incremented every time matched/assigned |
| confidence_baseline | int default 100 | drifts down if repeatedly corrected |
| created_via | enum(SEED, AI, MANUAL) | audit trail |

**ledger_aliases**
| column | type | notes |
|---|---|---|
| ledger_id | FK ledgers | |
| alias | varchar | unique per ledger_id, GIN trigram index |
| source | enum(MANUAL, LEARNED) | LEARNED = written by Module 13 |

**voucher_types**
| column | type | notes |
|---|---|---|
| name | varchar unique | Receipt/Payment/Contra/Journal |

**vouchers**
| column | type | notes |
|---|---|---|
| parsed_transaction_id | FK parsed_transactions unique | 1:1 |
| voucher_type_id | FK voucher_types | |
| voucher_number | varchar | generated sequential per job |
| narration | text | final narration written to export |

**ai_predictions** (audit trail, append-only — never updated)
| column | type | notes |
|---|---|---|
| parsed_transaction_id | FK parsed_transactions | |
| prompt_name | varchar | which prompt template |
| model_used | varchar | gemini-2.5-pro / flash |
| raw_request | JSONB | |
| raw_response | JSONB | |
| predicted_confidence | int | |
| latency_ms | int | |

**manual_corrections** (append-only)
| column | type | notes |
|---|---|---|
| parsed_transaction_id | FK parsed_transactions | |
| user_id | FK users | |
| field_changed | enum(LEDGER, GROUP, VOUCHER) | |
| old_value | varchar | |
| new_value | varchar | |

**rules**
| column | type | notes |
|---|---|---|
| rule_type | enum(KEYWORD, REGEX, CONFIG) | CONFIG rows hold tunables like thresholds |
| pattern | varchar | keyword/regex, or config key |
| ledger_name | varchar nullable | |
| group_name | varchar nullable | |
| voucher_type | varchar nullable | |
| config_value | varchar nullable | for CONFIG rows |
| is_active | boolean default true | |
| priority | int default 0 | higher runs first when multiple match |

**audit_logs**
| column | type | notes |
|---|---|---|
| entity_type | varchar | polymorphic: "processing_job", "parsed_transaction", etc |
| entity_id | UUID | |
| action | varchar | |
| detail | JSONB | |
| user_id | FK users nullable | null for system actions |

## 11. API endpoints

All routes under `/api/v1`, JWT bearer auth except `/auth/*`. Every list endpoint supports
pagination (`page`, `page_size`) and returns `{items, total, page, page_size}`.

| Method | Path | Purpose | Notes |
|---|---|---|---|
| POST | `/auth/register` | create user | |
| POST | `/auth/login` | returns JWT | |
| GET | `/auth/me` | current user | |
| POST | `/upload` | upload statement file | returns `{job_id}`, 202 |
| GET | `/jobs` | list jobs for dashboard | filters: status, date range |
| GET | `/jobs/{id}` | job detail + counts + status_history | polled by Processing Status page |
| GET | `/jobs/{id}/transactions` | paginated transactions for a job | filters: requires_review, resolution_source |
| GET | `/transactions/{id}` | single transaction detail incl. ai_predictions history | |
| POST | `/transactions/{id}/approve` | accept current ledger/group/voucher as-is | writes reviewed_by/at |
| PATCH | `/transactions/{id}` | change ledger/group/voucher | body: `{ledger_id?, group_id?, voucher_type_id?}`; writes manual_corrections rows + triggers Module 13 alias learning |
| POST | `/transactions/{id}/mark-duplicate` | manual duplicate override | |
| GET | `/ledgers` | list/search ledgers | query param `q` for typeahead |
| POST | `/ledgers` | create ledger manually | |
| PATCH | `/ledgers/{id}` | edit ledger (name/group) | |
| GET | `/ledgers/{id}/aliases` | list aliases | |
| POST | `/ledgers/{id}/aliases` | add manual alias | |
| GET | `/groups` | list ledger_groups | |
| GET | `/rules` | list rule engine entries | admin/config view |
| POST | `/rules` | add rule | |
| PATCH | `/rules/{id}` | edit/disable rule | |
| GET | `/export/{job_id}/excel` | download Excel export | 409 if job not ready |
| GET | `/export/{job_id}/csv` | download CSV export | |
| GET | `/export/{job_id}/xml` | download Tally XML export | |
| GET | `/dashboard/summary` | aggregate counts across jobs for Module 2 | |

Note: the spec listed flat routes (`POST /predict`, `POST /voucher`) as conceptual pipeline steps —
in implementation these are **not** user-facing endpoints; they're internal service calls invoked
by the job worker (§7), not HTTP routes, since prediction/voucher generation only ever happens as
part of the automated pipeline, never triggered ad hoc by the frontend. Flagging this deviation
explicitly rather than building dead endpoints.

## 12. React pages

1. **Login / Register** — plain form, React Hook Form + zod validation, JWT stored in memory +
   httpOnly refresh cookie (not localStorage, to reduce XSS exposure).
2. **Dashboard** — cards: total statements, processing status breakdown, auto-matched vs
   AI-predicted vs manual-review-required vs export-ready, recent jobs table. Data via
   `/dashboard/summary` + `/jobs` (TanStack Query, 30s poll while any job is non-terminal).
3. **Upload Statement** — drag-drop, file type validation client-side (still re-validated
   server-side), shows upload progress, redirects to Processing Status on success.
4. **Processing Status** — per-job view, polls `/jobs/{id}` every 2s while status is non-terminal,
   renders `status_history` as a stepper/timeline.
5. **Transactions** — full table for a job, filterable (resolution_source, requires_review,
   ledger, date range), server-side pagination and sorting.
6. **Review Predictions** — filtered to `requires_review=true`, one-row-at-a-time or table-with-
   inline-edit UX (inline table preferred for throughput), ledger/group typeahead against
   `/ledgers?q=`, Approve / Change actions call `/transactions/{id}/approve` or `PATCH`.
7. **Ledger Master** — CRUD over ledgers/aliases/groups, mostly for initial seeding and ongoing
   maintenance.
8. **Export** — pick job → pick format (Excel/CSV/XML) → pre-export validation summary (shows any
   blocking issues) → download.

## 13. Folder structure

### Backend
```
backend/
└── app/
    ├── main.py
    ├── config/
    │   └── settings.py            # pydantic-settings, env-driven, incl. thresholds from §3/§4
    ├── auth/
    │   ├── router.py  service.py  schemas.py  security.py (JWT/bcrypt)
    ├── upload/
    │   ├── router.py  service.py  schemas.py
    ├── parser/
    │   ├── pdf_parser.py  csv_parser.py  excel_parser.py  ocr_fallback.py
    │   └── base.py                # Parser interface, one impl per bank format later
    ├── normalizer/
    │   └── narration_normalizer.py
    ├── rules/
    │   └── rule_engine.py
    ├── ledger/
    │   ├── router.py  service.py  schemas.py
    ├── matcher/
    │   ├── exact_matcher.py  alias_matcher.py  similarity_matcher.py
    ├── ai/
    │   ├── gemini_client.py        # thin wrapper: call, retry, schema-validate
    │   ├── ledger_predictor.py
    │   ├── voucher_predictor.py
    │   └── validator_ai.py
    ├── validator/
    │   └── validation_engine.py
    ├── vouchers/
    │   └── voucher_generator.py
    ├── export/
    │   ├── excel_exporter.py  csv_exporter.py  tally_xml_exporter.py
    ├── jobs/
    │   ├── worker.py  job_state_machine.py  router.py
    ├── models/                     # SQLAlchemy ORM, one file per table
    ├── schemas/                     # Pydantic request/response models
    ├── services/                    # orchestration logic sitting above repositories
    ├── repositories/                 # DB access only, no business logic
    ├── prompts/
    │   ├── ledger_prediction.md  voucher_prediction.md
    │   ├── ledger_group_prediction.md  validation.md
    ├── utils/
    ├── alembic/                      # migrations
    └── tests/
        ├── unit/  integration/
```

### Frontend
```
frontend/
└── src/
    ├── main.tsx  App.tsx  routes.tsx
    ├── pages/
    │   ├── Login/  Dashboard/  UploadStatement/  ProcessingStatus/
    │   ├── Transactions/  ReviewPredictions/  LedgerMaster/  Export/
    ├── components/
    │   ├── ui/                      # buttons, inputs, tables — dumb, reusable
    │   ├── layout/                   # shell, nav, header
    │   └── domain/                   # TransactionRow, LedgerTypeahead, ConfidenceBadge, etc
    ├── hooks/                        # useJobPolling, useLedgerSearch, etc
    ├── services/                     # api client functions per resource (axios/fetch wrappers)
    ├── store/                        # Zustand slices (auth, uploadDraft, uiFilters)
    ├── types/                        # shared TS types mirroring backend schemas
    └── lib/                          # queryClient config, formatters
```

## 14. Component hierarchy

```
App
└── AuthGuard
    └── AppShell (nav, header)
        ├── DashboardPage
        │   ├── SummaryCards
        │   └── RecentJobsTable
        ├── UploadStatementPage
        │   └── FileDropzone
        ├── ProcessingStatusPage
        │   └── JobStatusStepper
        ├── TransactionsPage
        │   ├── TransactionFilters
        │   └── TransactionTable
        │       └── TransactionRow → ConfidenceBadge, LedgerCell
        ├── ReviewPredictionsPage
        │   └── ReviewTable
        │       └── ReviewRow → LedgerTypeahead, GroupSelect, VoucherSelect, ApproveButton
        ├── LedgerMasterPage
        │   ├── LedgerTable
        │   └── LedgerFormModal
        └── ExportPage
            ├── JobPicker
            ├── PreExportValidationSummary
            └── FormatDownloadButtons
```

## 15. Service layer

Services orchestrate — they call repositories, call the AI layer, enforce the waterfall order
from §2, and are the only place business rules live. Example shape:

```python
class TransactionResolutionService:
    def __init__(self, ledger_repo, rule_engine, matcher, ai_predictor, validator, voucher_gen):
        ...

    def resolve_job(self, job_id: UUID) -> None:
        transactions = self.transaction_repo.get_unresolved(job_id)
        for txn in transactions:
            if self.rule_engine.try_resolve(txn):      continue
            if self.matcher.try_exact(txn):            continue
            if self.matcher.try_alias(txn):             continue
            if self.matcher.try_similarity(txn):         continue
            # remaining transactions batched below, not per-row
        self._resolve_via_ai(job_id, remaining=self.transaction_repo.get_unresolved(job_id))
        self.validator.validate_job(job_id)
        self.voucher_gen.generate_for_job(job_id)
```

Services never construct raw SQL — that's the repository layer's job. Services never call the
Gemini client directly — that goes through `ai/ledger_predictor.py` etc., which owns
prompt-loading, batching, retry, and schema validation.

## 16. Repository layer

Thin, DB-only, no business logic — one repository per aggregate root:
`TransactionRepository`, `LedgerRepository`, `JobRepository`, `RuleRepository`. Each exposes
intent-named methods (`get_unresolved(job_id)`, `find_by_exact_name(name)`,
`find_similar(narration, limit=5)`) rather than leaking query-building to callers. This is the only
layer allowed to import SQLAlchemy session/query constructs directly.

## 17. AI service implementation

```python
class GeminiClient:
    def call(self, prompt_name: str, context: dict, model: str) -> dict:
        prompt = self._render_template(prompt_name, context)
        response = self._call_with_retry(prompt, model, max_attempts=3)
        return self._validate_schema(response, prompt_name)  # raises on final failure

class LedgerPredictor:
    def predict_batch(self, transactions: list[Txn], ledger_context: list[Ledger]) -> list[Prediction]:
        chunks = chunk(transactions, size=settings.AI_BATCH_SIZE)
        results = []
        for chunk in chunks:
            raw = self.gemini_client.call(
                "ledger_prediction",
                {"transactions": chunk, "ledgers": ledger_context, "rules": self.rules},
                model="gemini-2.5-pro",
            )
            results.extend(self._apply_guardrails(raw))  # §3 confidence clamping
        return results
```

Every Gemini call is persisted to `ai_predictions` (raw request + raw response) regardless of
outcome — this is the audit trail that makes the Learning System (Module 13) and future prompt
tuning possible.

## 18. Sequence diagrams

**Upload → Resolution**
```
User → UploadAPI: POST /upload
UploadAPI → DB: insert uploaded_files, processing_jobs(status=QUEUED)
UploadAPI → User: 202 {job_id}
Worker → DB: claim job (SKIP LOCKED), status=PARSING
Worker → Parser: parse file
Parser → Worker: raw rows
Worker → Normalizer: normalize narrations
Worker → DB: bulk insert parsed_transactions, status=MATCHING
Worker → RuleEngine/Matcher: resolve per §2 waterfall
Worker → AI(LedgerPredictor): batch-predict remaining, status=AI_PREDICTING
Worker → ValidationEngine: validate all, status=VALIDATING
Worker → VoucherGenerator: assign vouchers
Worker → DB: update job counts, status=REVIEW_REQUIRED|READY
```

**Manual Correction → Learning**
```
User → ReviewAPI: PATCH /transactions/{id} {ledger_id: X}
ReviewAPI → DB: update parsed_transactions, insert manual_corrections
ReviewAPI → LearningService: on_correction(txn, new_ledger)
LearningService → DB: upsert ledger_aliases(alias=normalized_narration, ledger_id=X, source=LEARNED)
```

## 19. State management

- **Server state** (jobs, transactions, ledgers): TanStack Query exclusively — no duplication into
  Zustand. Query keys namespaced per resource (`['job', id]`, `['transactions', jobId, filters]`);
  mutations invalidate the relevant keys (e.g., approving a transaction invalidates both the
  transaction list and the job summary counts).
- **Client-only state** (active filters, upload draft/in-progress file, auth token): Zustand, kept
  minimal — this is UI state that has no server source of truth.
- **Polling**: `refetchInterval` on the job-detail query while status is non-terminal; disabled
  once `READY`/`REVIEW_REQUIRED`/`FAILED`.

## 20. Testing strategy

- **Unit tests** (per Module, per guideline #6 in the spec):
  - Parser: fixture PDFs/CSVs per supported bank format → expected normalized rows.
  - Normalizer: table-driven tests for every narration pattern in Module 5.
  - Rule Engine: each rule → expected ledger/group/voucher.
  - Matchers: exact/alias/similarity, including near-miss cases that should NOT auto-resolve.
  - Validation Engine: every validation rule with a deliberately-broken fixture.
  - Voucher Generator: every group+direction combination.
- **Integration tests**: full pipeline against a small real (anonymized) statement, asserting final
  transaction resolution matches a hand-labeled expected output — this is the test that actually
  protects the accuracy metrics in the spec.
- **AI layer tests**: mock the Gemini client at the `GeminiClient.call` boundary; test
  guardrail/clamping logic (§3) with synthetic responses, including malformed-JSON and
  schema-violation cases, without hitting the real API in CI.
- **Frontend**: component tests for ReviewRow/TransactionTable (Testing Library), and a couple of
  Playwright e2e flows (upload → wait for processing → review → export) against a seeded backend.
- **Golden-file tests for export**: Tally XML output diffed against known-good sample files —
  export correctness is a hard requirement (100% validity target) and easy to regress silently.

## 21. Deployment

- **Backend**: containerized FastAPI app + separate worker container (same image, different
  entrypoint/command), both connecting to a managed PostgreSQL instance (with `pg_trgm` extension
  enabled). Alembic migrations run as a release step, not on app boot.
- **File storage**: local volume acceptable for v1 single-instance deployment; abstract behind a
  storage interface (`upload/storage.py`) so swapping to S3-compatible storage later doesn't touch
  callers.
- **Frontend**: static build served via CDN/static host, API base URL via env var at build time.
- **Secrets**: Gemini API key, DB credentials, JWT signing key — via environment variables /
  secrets manager, never committed; `config/settings.py` is the single place that reads them.
- **Environments**: dev / staging / prod, each with its own DB and its own confidence-threshold
  `rules` CONFIG rows — thresholds are expected to be tuned per environment based on real statement
  accuracy results before this ships to real accounting use.

---

## Open assumptions to validate before/while building (not blockers, just flagged)

- Similarity-match blend weights (§4) are a reasonable starting point, not tuned against labeled
  data yet.
- Postgres-polling job queue (§7) is chosen for infra simplicity; revisit if upload volume/concurrency
  grows past what polling handles comfortably.
- `AI_BATCH_SIZE` and `AI_MAX_LEDGER_CONTEXT` defaults are placeholders — tune once real statement
  sizes and ledger-table sizes are known.
