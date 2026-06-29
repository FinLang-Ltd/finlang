# FinLang API Reference

> **Status:** v0.1 — SOL-041 MVP
> **Applies to:** FinLang with the `[api]` extras installed (`pip install finlang[api]`)

A thin REST surface over the FinLang CLI. Every endpoint dispatches to the
published CLI entry points (`finlang`, `finlang-discover`, `finlang-suggest`)
via subprocess. The API never imports engine internals; it inherits the CLI's
underlying behaviour and exit codes (with one endpoint-specific override —
`/reconcile` maps exit 3 to HTTP 200, since mismatches are an expected
review outcome). The HTTP surface is curated, not auto-forwarding: each
endpoint exposes specific Form parameters that map to CLI flags.

---

## Install & run

```bash
pip install "finlang[api]"
finlang-api               # binds 127.0.0.1:8000 by default
```

Or with uvicorn directly:
```bash
uvicorn finlang.api.main:app --host 0.0.0.0 --port 8000
```

Interactive Swagger UI at `http://localhost:8000/docs`.

---

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `FINLANG_API_KEY` | unset (auth disabled) | When set, all non-health endpoints require `X-API-Key: <key>` |
| `FINLANG_API_HOST` | `127.0.0.1` | Bind host for `finlang-api` script |
| `FINLANG_API_PORT` | `8000` | Bind port |
| `FINLANG_API_TIMEOUT` | `300` | Subprocess timeout in seconds |
| `FINLANG_API_MAX_UPLOAD` | `104857600` | Max upload size in bytes (100 MiB) |
| `FINLANG_API_LOG_LEVEL` | `info` | Uvicorn log level |

---

## Endpoints

### `GET /health`

Liveness check. No auth required.

```json
{
  "status": "ok",
  "service": "finlang-api",
  "version": "0.7.9",
  "timestamp": 1747000000.0,
  "cli_resolved": true
}
```

### `POST /process`

Categorise a transactions CSV. Multipart form upload.

**Form fields:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `input_csv` | file | yes | Transactions CSV |
| `rules` | file | one of `rules`/`include_pack` | `.fin` rules file |
| `map_file` | file | no | Custom header mapping JSON |
| `include_pack` | string | one of `rules`/`include_pack` | Comma-separated bundled packs (e.g. `retail,transport`) |
| `audit_mode` | string | no | `none` \| `lite` (default) \| `full` |
| `fastio` | bool | no | Use PyArrow IO |
| `decimal` | string | no | Decimal separator (default `.`) |
| `thousands` | string | no | Thousands separator |
| `dayfirst` | bool | no | Parse dates as DD/MM |
| `encoding` | string | no | Input encoding (default `utf-8-sig`) |
| `output_encoding` | string | no | Output encoding (default `utf-8`) |
| `strict_parse` | bool | no | Fail fast on malformed CSV |
| `fail_threshold` | float | no | Max drop rate (default `0.01`) |
| `return_audit` | bool | no | Include audit log in response (default true) |
| `verify` | bool | no | Run SHA-256 verify after categorisation |
| `verify_full` | bool | no | Run full verify (overrides `verify`) |

**Response 200:**
```json
{
  "output_csv": "date,counterparty,amount,...,category,flags\n2024-01-15,...",
  "audit": [{"row": 0, "rule": "GROCERIES: Tesco", "changes": {...}}],
  "verify_report": {"status": "PASS", "rows": 5, "mismatches": 0, ...},
  "stats": {
    "rows_in": 5,
    "rows_out": 5,
    "audit_entries": 2,
    "duration_seconds": 0.0612,
    "exit_code": 0
  },
  "stderr": ""
}
```

**Error mapping:**

| Engine exit code | HTTP | Meaning |
|---|---|---|
| 0 | 200 | Success |
| 1 | 500 | Ops error (file not found, IO failure) |
| 2 | 422 | Validation/parse error |
| 3 | 422 | Verification mismatch |

### `POST /discover`

Find uncategorised counterparties as candidates for new rules.

**Form fields:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `input_csv` | file | yes | Categorised CSV from `/process` |
| `min_count` | int | no | Minimum occurrences (default `3`) |
| `min_amount` | float | no | Minimum absolute amount filter |
| `top_k` | int | no | Top-N by frequency |
| `since_date` | string | no | `YYYY-MM-DD` cutoff |
| `include_excluded` | bool | no | Include `exclude=True` rows |
| `return_all` | bool | no | Also return the all-candidates table |
| `encoding`, `decimal`, `thousands`, `dayfirst` | various | no | Locale flags |

**Response 200:**
```json
{
  "candidates_csv": "counterparty_fingerprint,example_counterparty_name,count,...",
  "all_candidates_csv": null,
  "stderr": ""
}
```

### `POST /suggest`

Generate draft `.fin` rules from discovery candidates.

**Form fields:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `candidates_csv` | file | yes | Output from `/discover` |
| `existing_rules` | file | no | Existing `.fin` for dedup |
| `emit_match` | string | no | `exact` \| `fuzzy` (default) |
| `category` | string | no | Default category (default `Review`) |
| `prefix` | string | no | Rule name prefix (default `SUGGEST`) |
| `quote_style` | string | no | `"` (default) or `'` |

**Response 200:**
```json
{
  "rules_fin": "rule \"SUGGEST: VENDOR\" {\n  match:\n    - counterparty ~ \"*VENDOR*\"\n  ...",
  "stderr": ""
}
```

### `POST /reconcile`

Reconcile FinLang's deterministic categorisation against an external system's
output (typically an ML model). Returns a row-by-row mismatch summary, an
optional self-contained HTML report, and the full audit trail.

**Form fields:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `input_csv` | file | yes | Transactions CSV |
| `ml_output_csv` | file | yes | ML output CSV to reconcile against (positional alignment needs an identical row count; `reconcile_key` removes that requirement) |
| `rules` | file | one of `rules`/`include_pack` | `.fin` rules file |
| `map_file` | file | no | Custom header mapping JSON |
| `include_pack` | string | one of `rules`/`include_pack` | Comma-separated bundled packs |
| `reconcile_fields` | string | no | Comma-separated fields to compare. Default: `category`. Multi-field works (e.g. `category,flags`). |
| `reconcile_html` | bool | no | Emit self-contained HTML report alongside JSON. Default: `false`. |
| `reconcile_identity_fields` | string | no | Identity guard — comma-separated fields verified positionally *before* comparison (e.g. `date,amount,counterparty`). Misaligned rows → structural failure (HTTP 422). Mutually exclusive with `reconcile_key`. |
| `reconcile_key` | string | no | Key-based alignment — comma-separated composite key (e.g. `date,amount,counterparty`). Matches by content; row counts may differ; unmatched rows surface in `orphans_finlang_csv` / `orphans_ml_csv`. Duplicate keys → HTTP 422. Mutually exclusive with `reconcile_identity_fields`. |
| `audit_mode` | string | no | Always `full` for `/reconcile`. Other values rejected with HTTP 400. |
| `fastio` | bool | no | Use PyArrow IO |
| `decimal`, `thousands`, `dayfirst`, `encoding`, `output_encoding`, `strict_parse`, `fail_threshold` | various | no | Same as `/process` |

**Query params:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `format` | string | `json` | Response shape selector. `json` returns the full `ReconcileResponse` (summary + mismatches CSV + HTML report + audit + stats). `html` returns the HTML report directly with `Content-Type: text/html` — convenient for browsers, Swagger UI, and `curl > file.html`. **`format=html` requires `reconcile_html=true`** (otherwise HTTP 400). |

**Response 200 (perfect match — exit 0):**
```json
{
  "summary": {
    "timestamp": "2026-05-15T10:42:13Z",
    "total_rows": 15,
    "matches": 15,
    "mismatches": 0,
    "match_rate_percent": 100.0,
    "perfect_match": true,
    "status": "PASS",
    "alignment_mode": "positional",
    "reconcile_fields": ["category"],
    "audit_entries_loaded": 15,
    "duration_seconds": 0.087
  },
  "mismatches_csv": "",
  "report_html": null,
  "audit": [{"row": 0, "rule": "...", "changes": {...}}, ...],
  "stats": {
    "duration_seconds": 0.0921,
    "exit_code": 0,
    "mismatches_found": false
  },
  "stderr": ""
}
```

**Response 200 (mismatches found — exit 3):**
```json
{
  "summary": {
    "total_rows": 15,
    "matches": 13,
    "mismatches": 2,
    "match_rate_percent": 86.67,
    "perfect_match": false,
    "status": "REVIEW REQUIRED",
    ...
  },
  "mismatches_csv": "row_number,date,amount,counterparty,differing_fields,ml_category,finlang_category,finlang_rule_matched,finlang_audit_reason\n1,2024-01-15,-89.50,SHELL TRADING INTERNATIONAL,category,Utilities,Energy & Commodities,Energy: Shell,counterparty ~ \"*SHELL*\"\n4,2024-01-22,-250000.00,CAYMAN ISLANDS TRUST,category,Treasury Operations,Compliance: Offshore Jurisdictions,Compliance: Offshore Jurisdictions,counterparty ~ \"*CAYMAN*\"\n",
  "report_html": "<!doctype html>...",
  "audit": [...],
  "stats": {
    "duration_seconds": 0.103,
    "exit_code": 3,
    "mismatches_found": true
  },
  "stderr": ""
}
```

> **⚠️ Exit-code semantics differ from `/process`:** finding mismatches on `/reconcile` is the **expected outcome**, not an error. Engine exit code 3 maps to **HTTP 200** here (with mismatches surfaced in the body), not HTTP 422. Structural/client-data problems (exit 1) and validation errors (exit 2) both map to HTTP 422. The caller reads `stats.mismatches_found` and `summary.mismatches` to know what happened.

**Error mapping (specific to `/reconcile`):**

| Engine exit code | HTTP | Meaning |
|---|---|---|
| 0 | 200 | Perfect match — every row agrees on every reconcile field |
| 1 | 422 | Structural / client-data — row-count mismatch, missing field, identity-guard failure, duplicate keys |
| 2 | 422 | Validation/parse error |
| 3 | 200 | **Mismatches found — expected outcome.** Body carries the detail. |

> **Exit 1 is overloaded — mapped by its dominant meaning.** Honestly: on these endpoints exit 1 is *almost always* an input problem the request can't be processed against (duplicate keys, row-count mismatch, missing field, identity-guard failure), so it returns **422**. It can — *rarely* — be a genuine I/O failure; the engine doesn't separate the two with distinct exit codes, so the API maps by the dominant case rather than pretending exit 1 cleanly equals "alignment failure." So the caller can still discriminate, the 422 body is structured: `error` (machine enum — `alignment_error` for exit 1, `validation_error` for exit 2), `exit_code`, a `message`, and the full `stderr` (authoritative — names the specific cause). Branch on `error` + read `stderr`. A future engine exit-code split (see BACKLOG: API error taxonomy) would make this exact.

> **Key mode (`reconcile_key`):** the response adds `orphans_finlang_csv` (FinLang rows with no ML match) and `orphans_ml_csv` (ML rows with no FinLang match); `summary.alignment_mode` becomes `key:<fields>` and `summary.orphans_finlang_count` / `orphans_ml_count` carry the counts. Orphans set exit 3 → HTTP 200 (review-needed). Identity-guard mode (`reconcile_identity_fields`) instead *suppresses* comparison and returns HTTP 422 when rows misalign.

---

### `POST /impact`

Rule-change impact analysis: run the same input through a **baseline** (`rules`) and a **candidate** (`impact_rules`) rulepack, and report what the change does — rows re-categorised, indicative amount moved per transition, per-rule match deltas. Analysis run: writes no categorised output. (See [impact.md](impact.md) for the feature explainer.)

**Form fields:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `input_csv` | file | yes | Transactions CSV |
| `impact_rules` | file | yes | Candidate (proposed) `.fin` rulepack |
| `rules` | file | one of `rules`/`include_pack` | Baseline (current) `.fin` rulepack |
| `map_file` | file | no | Custom header mapping JSON |
| `include_pack` | string | one of `rules`/`include_pack` | Comma-separated bundled packs (baseline) |
| `impact_html` | bool | no | Emit self-contained HTML report. Default: `false`. |
| `fastio`, `decimal`, `thousands`, `dayfirst`, `encoding`, `strict_parse`, `fail_threshold` | various | no | Same as `/process` |

**Query params:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `format` | string | `json` | `json` returns the full `ImpactResponse` (summary + `changes_csv` + `report_html` + stats). `html` returns the HTML report directly with `Content-Type: text/html`. **`format=html` requires `impact_html=true`** (otherwise HTTP 400). |

**Response 200 (behavioural change — exit 3):**
```json
{
  "summary": {
    "schema": "impact/1",
    "rows_compared": 6,
    "behavioural_changed": 2,
    "attribution_changed": 2,
    "rows_stable": 2,
    "transitions": [{"old_category": "Energy", "new_category": "Utilities", "rows": 2, "indicative_amount": 215.50}],
    "rule_deltas": [...],
    "baseline_rules_sha256": "a3f1c2...",
    "candidate_rules_sha256": "b7d09a...",
    "status": "REVIEW REQUIRED",
    "amount_note": "Indicative totals — float arithmetic, not accounting-grade."
  },
  "changes_csv": "row_number,counterparty,amount,date,memo,old_category,new_category,...,change_class\n1,...,behavioural\n",
  "report_html": null,
  "stats": {"duration_seconds": 0.04, "exit_code": 3, "behavioural_changes_found": true},
  "stderr": ""
}
```

**Error mapping (same as `/reconcile`):** `0` → 200 (no behavioural change), `3` → 200 (behavioural change — expected, review-needed), `2` → 422 (validation), `1` → 422 (structural/parse).

---

## Curl examples

```bash
# Health
curl -s http://localhost:8000/health | jq

# Categorise
curl -s -X POST http://localhost:8000/process \
  -F "input_csv=@transactions.csv" \
  -F "rules=@rules.fin" \
  -F "audit_mode=full" \
  -F "verify=true" \
  | jq .stats

# Discover candidates from a categorised CSV
curl -s -X POST http://localhost:8000/discover \
  -F "input_csv=@categorised.csv" \
  -F "min_count=5" \
  | jq -r .candidates_csv

# Generate draft rules
curl -s -X POST http://localhost:8000/suggest \
  -F "candidates_csv=@candidates.csv" \
  -F "emit_match=exact" \
  -F "category=Review" \
  | jq -r .rules_fin

# Reconcile against an ML output (with HTML report)
curl -s -X POST http://localhost:8000/reconcile \
  -F "input_csv=@transactions.csv" \
  -F "ml_output_csv=@ml_output.csv" \
  -F "rules=@rules.fin" \
  -F "reconcile_html=true" \
  | jq '{exit: .stats.exit_code, mismatches: .summary.mismatches, status: .summary.status}'

# Save the HTML report to disk for review (JSON-extract pattern)
curl -s -X POST http://localhost:8000/reconcile \
  -F "input_csv=@transactions.csv" \
  -F "ml_output_csv=@ml_output.csv" \
  -F "rules=@rules.fin" \
  -F "reconcile_html=true" \
  | jq -r .report_html > reconcile_report.html

# Cleaner: ?format=html returns the HTML directly, no JSON unwrapping needed
curl -s -X POST 'http://localhost:8000/reconcile?format=html' \
  -F "input_csv=@transactions.csv" \
  -F "ml_output_csv=@ml_output.csv" \
  -F "rules=@rules.fin" \
  -F "reconcile_html=true" \
  -o reconcile_report.html
```

With auth:
```bash
export FINLANG_API_KEY="your-secret"
finlang-api &
curl -H "X-API-Key: your-secret" http://localhost:8000/process ...
```

---

## Deployment notes

The MVP wrapper is a single-process FastAPI app. For production:

- Run behind a reverse proxy (nginx, Caddy) with TLS termination.
- Use `uvicorn --workers N` or gunicorn with `uvicorn.workers.UvicornWorker`.
- Set a non-zero `FINLANG_API_KEY` and rotate it.
- Lower `FINLANG_API_MAX_UPLOAD` if exposed on the public internet.
- Mount a fast tmpfs at `/tmp` (subprocess CSV staging happens there).

The wrapper is deliberately minimal. It is not a SaaS — it's a deployable
service surface. Multi-tenant features, persistent storage, async job queues,
and rate limiting are explicitly out of scope for this wrapper; those
concerns belong to a hosted-service layer above it.

---

## Determinism

Every endpoint preserves the engine's determinism contract: same input + same
rules → same output, byte-for-byte. The subprocess boundary does not introduce
non-determinism. Audit logs are reproducible.

This is the property that matters for buyers in regulated environments.

© FinLang Ltd
