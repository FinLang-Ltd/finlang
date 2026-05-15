# 🌐 FinLang HTTP API
> **Status:** v0.1 — SOL-041 MVP
> **Applies to:** FinLang with the `[api]` extras installed (`pip install finlang[api]`)

The FinLang API is a thin REST surface over the published CLI. Categorise transactions, discover counterparties, and generate draft rules without leaving HTTP — same engine, same audit trail, with curated HTTP parameters mapping to the most-used CLI flags. **It is not a SaaS, not a hosted service, not a replacement for the CLI**: it makes the same deterministic engine reachable over HTTP for buyers, integrators, and demo widgets that evaluate FinLang as a deployable service rather than a Python tool.

---

## 🎯 Quick Navigation

**I want to…**
- [Understand when the API fits my workflow](#-when-to-use) → Bidirectional When / When NOT
- [See the API in action](#-worked-example) → curl POST /process end-to-end
- [Look up an endpoint's exact form fields and response schema](api_reference.md) → Reference doc
- [Understand auth and configuration](#-auth-and-configuration) → Env vars, X-API-Key
- [Map HTTP status codes to engine exit codes](#-http-status--exit-code-mapping) → 200 / 422 / 500 table

> **New to FinLang?** Start with [install.md](install.md) and the [Daily Run](workflows.md#-daily-run) workflow. The API runs on top of a working FinLang install — it isn't first-touch.

---

## ✅ When to Use

- **Wrapping FinLang in your service stack.** The API is the natural surface when FinLang sits behind a downstream service that already speaks HTTP. Drop in a microservice, point your existing client at it.
- **Demoing FinLang to a buyer or integrator.** A POST `/process` with curl on a sample CSV beats a "let me show you the CLI flags" walkthrough. Buyer evaluates "service you can deploy" differently from "CLI you install."
- **Powering an interactive demo widget.** The website widget can hit `/process` against pre-baked input and render the response. A prospect experiences the product before speaking to anyone.
- **Multi-language client integration.** Anything that can POST a multipart form can call FinLang. No Python required on the caller's side.
- **Containerised deployment.** Run `finlang-api` inside a Docker container, expose port 8000, put nginx or Caddy in front. Same shape any Python service ships in.

## ❌ When NOT to Use

- **Single-user batch jobs on your own machine.** The CLI is faster and produces the same output. The API adds HTTP overhead for no gain.
- **You expect a SaaS.** No multi-tenancy, no persistent storage, no async job queue, no rate limiting, no metering. Those concerns belong to a hosted-service layer above this wrapper. The wrapper itself is intentionally simple.
- **Long-running streaming jobs.** Each request runs synchronously to completion within the configured timeout (300s default). For multi-hour batches, run the CLI directly.
- **Anything requiring per-request encryption keys, fine-grained authz, or audit-of-the-API-itself.** The wrapper is single-process with one optional API key. Production deployments behind a reverse proxy can layer those concerns; the API itself does not.

---

## 🔄 The Request Flow

```
   ┌─────────────────────┐
   │  Your client        │
   │  (curl, browser,    │
   │   downstream svc)   │
   └──────────┬──────────┘
              │  POST /process
              │  multipart form
              ▼
   ┌─────────────────────┐         ┌─────────────────────┐
   │  FastAPI app        │ ──────► │  Temp directory     │
   │  (uvicorn, single   │  stage  │  input.csv          │
   │   process)          │  files  │  rules.fin          │
   └──────────┬──────────┘         │  audit.json         │
              │                     └─────────────────────┘
              │  subprocess.run([finlang, --input, ...])
              ▼
   ┌─────────────────────┐
   │  finlang CLI        │
   │  (fresh process,    │
   │   same engine)      │
   └──────────┬──────────┘
              │  exits 0 / 1 / 2 / 3
              ▼
   ┌─────────────────────┐
   │  FastAPI app        │
   │  reads outputs,     │
   │  maps exit code,    │
   │  returns JSON       │
   └──────────┬──────────┘
              │  HTTP 200 / 422 / 500
              ▼
   ┌─────────────────────┐
   │  Your client        │
   │  receives:          │
   │  output_csv,        │
   │  audit, stats       │
   └─────────────────────┘
```

The **subprocess boundary** is load-bearing. The API never imports `finlang.engine.*`. Every request runs the published CLI as a fresh child process — same binary your end users run from a terminal. Failures are isolated; engine state can't leak between requests.

---

## 📍 Worked Example

A 5-row sample CSV, two rules, a single curl command.

```bash
# transactions.csv
date,counterparty,amount,memo
2024-01-15,TESCO STORES 1234,-45.20,GROCERIES
2024-01-16,SHELL FUEL,-65.00,FORECOURT
2024-01-17,UBER TRIP,-12.50,RIDE
2024-01-18,SALARY ACME LTD,3200.00,JAN PAY
2024-01-19,UNKNOWN VENDOR XYZ,-19.99,MEMO
```

```bash
# rules.fin
rule "GROCERIES: Tesco" {
  match:
    - counterparty ~ "*TESCO*"
  set:
    - category = "Groceries"
}

rule "FUEL: Shell" {
  match:
    - counterparty ~ "*SHELL*"
  set:
    - category = "Fuel"
}
```

Start the API and POST:

```bash
finlang-api &
curl -s -X POST http://localhost:8000/process \
  -F "input_csv=@transactions.csv" \
  -F "rules=@rules.fin" \
  -F "audit_mode=lite"
```

Response:

```json
{
  "output_csv": "date,counterparty,amount,memo,category,...\n2024-01-15,TESCO STORES 1234,-45.20,GROCERIES,Groceries,...\n2024-01-16,SHELL FUEL,-65.00,FORECOURT,Fuel,...\n...",
  "audit": [
    {"row": 0, "rule": "GROCERIES: Tesco", "changes": {"category": "Groceries"}},
    {"row": 1, "rule": "FUEL: Shell", "changes": {"category": "Fuel"}}
  ],
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

Two rules fired (Tesco, Shell). Three rows were left uncategorised — FinLang doesn't assign a default; rows that match no rule keep an empty `category` field. The full output CSV is returned as a string in the response — pipe it to a file, render it in a UI, or pass it to the next stage of your pipeline.

> **🌍 Locale flags inherited:** The same i18n flags that the engine honours (`decimal`, `thousands`, `dayfirst`, `encoding`, `output_encoding`) are form fields on `/process`. European-format input doesn't need a separate code path — it's a flag.

---

## ⚙️ Endpoints at a Glance

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `GET` | `/` | HTML landing page → `/docs` | no |
| `GET` | `/health` | Liveness check + version + cli_resolved | no |
| `POST` | `/process` | Categorise transactions; optional `--verify` | yes |
| `POST` | `/discover` | Find uncategorised counterparties | yes |
| `POST` | `/suggest` | Generate draft `.fin` rules from candidates | yes |
| `POST` | `/reconcile` | Reconcile against ML output; returns JSON summary + (optional) HTML report | yes |

For the full form-field schema on each endpoint, response shapes, and curl recipes, see **[api_reference.md](api_reference.md)**. Interactive Swagger UI is always live at `http://localhost:8000/docs` while `finlang-api` is running.

> **⚠️ `/reconcile` exit code semantics:** unlike `/process`, where exit code 3 (verify mismatch) maps to HTTP 422, `/reconcile` maps **exit 3 → HTTP 200** with mismatches surfaced in the response body. Finding mismatches is the expected outcome of reconciliation, not an error. The caller reads `stats.mismatches_found` and `summary.mismatches` to know what happened. Only ops errors (exit 1 → 500) and validation errors (exit 2 → 422) map to error statuses on this endpoint.

> **🌐 `/reconcile?format=html` shortcut:** for human inspection of the HTML report, append `?format=html` to the POST URL and the API returns the HTML directly with `Content-Type: text/html` — no JSON unwrapping, no escape-character cleanup. Save with `curl -o report.html` or open in a browser. Requires `reconcile_html=true`. Default `format=json` returns the full `ReconcileResponse` (existing behaviour).

---

## 🔐 Auth and Configuration

### Auth

Auth is **opt-in via env var**. Set `FINLANG_API_KEY` in the process environment, and every non-`/health` endpoint requires the matching `X-API-Key` header on incoming requests.

```bash
export FINLANG_API_KEY="your-secret-string"
finlang-api &

curl -H "X-API-Key: your-secret-string" \
  -X POST http://localhost:8000/process \
  -F "input_csv=@transactions.csv" \
  -F "rules=@rules.fin"
```

If `FINLANG_API_KEY` is unset, auth is disabled (dev mode). `/health` is always public regardless of auth state — useful for liveness probes behind a load balancer.

For production, set the key, rotate it on a schedule, and put TLS termination in front (nginx, Caddy, your cloud provider's LB). Per-tenant keys, OAuth, and JWT are explicitly out of scope for this wrapper — those concerns belong to a hosted service layer above.

### Configuration

| Env var | Default | Purpose |
|---|---|---|
| `FINLANG_API_KEY` | unset (auth disabled) | When set, all non-health endpoints require `X-API-Key: <key>` |
| `FINLANG_API_HOST` | `127.0.0.1` | Bind host for the `finlang-api` script |
| `FINLANG_API_PORT` | `8000` | Bind port |
| `FINLANG_API_TIMEOUT` | `300` | Subprocess timeout in seconds |
| `FINLANG_API_MAX_UPLOAD` | `104857600` | Max upload size in bytes (100 MiB) |
| `FINLANG_API_LOG_LEVEL` | `info` | Uvicorn log level |

> **⚠️ Trap to know about:** the API does **not** rate-limit, throttle, or cap concurrent requests. A single `finlang-api` process serves requests from one Uvicorn worker. For production loads, run multiple workers (`uvicorn --workers N`) and put a reverse proxy in front. The API is a service surface, not a SaaS — sizing it is the operator's job.

---

## 🚦 HTTP Status ↔ Exit Code Mapping

The engine returns four exit codes; the API maps them to clean HTTP statuses.

| Engine exit code | HTTP status | Meaning |
|---|---|---|
| `0` | `200 OK` | Engine succeeded; output CSV + audit + stats returned |
| `1` | `500 Internal Server Error` | Ops error — file not found, IO failure, unexpected crash |
| `2` | `422 Unprocessable Entity` | Validation/parse error — malformed CSV, bad flag combination, missing required field |
| `3` | `422 Unprocessable Entity` | Verify mismatch (when `--verify` or `--verify-full` is on) |

Other HTTP statuses the API can return:

- **`400 Bad Request`** — input validation failed at the API layer (e.g. neither `rules` nor `include_pack` provided to `/process`)
- **`401 Unauthorized`** — auth required (env var set) and request missing or has wrong `X-API-Key`
- **`413 Request Entity Too Large`** — upload exceeds `FINLANG_API_MAX_UPLOAD`
- **`503 Service Unavailable`** — FinLang CLI not found on PATH (installation issue)
- **`504 Gateway Timeout`** — subprocess exceeded `FINLANG_API_TIMEOUT`

For CI/CD pipelines: `200` = success on `/process`, and on `/reconcile` check `stats.mismatches_found` in the body for the review signal; `422` = engine validation/parse error or verify mismatch (data didn't flow cleanly); `500/503/504` = ops failure to investigate; `400/401/413` = caller error.

---

## 🚧 Limitations (v0.1 MVP)

- **Single-process, synchronous.** One request runs at a time per worker. No async job queue.
- **No persistent storage.** Uploaded files live in a temp directory for the duration of one request, then disappear.
- **No streaming response.** Whole output CSV is returned as a string in the JSON body. For multi-million-row outputs, prefer the CLI.
- **No multi-tenancy.** One API key, one set of users.
- **No rate limiting.** Operator's concern; layer at the reverse proxy.
- **No WebSocket / Server-Sent Events.** HTTP request/response only.
- **Subprocess overhead per request.** ~50–150ms of process-startup cost on top of engine time. Negligible for human-driven requests; consider the CLI for batch loops where startup dominates.

---

## 🛣️ Roadmap (direction, not promises)

Candidates being evaluated when buyer or customer demand surfaces:

- **OpenAPI client SDK generation** (TypeScript / Python) — scaffold a typed client straight from `/openapi.json`.
- **Streaming response on `/process` and `/reconcile`** for very large outputs — chunked CSV instead of one JSON blob.
- **Optional per-request audit log download** — instead of inlining `audit` in the JSON response, return a presigned link or multipart attachment.
- **Health check enrichment** — surface engine version, rule pack inventory, last-N-request stats.
- **Standalone reconcile mode** — once the engine ships `--reconcile-only`, expose it as a separate endpoint that takes two pre-existing CSVs without re-running the engine.
- **`--date-format` form field on `/process`** — currently not exposed; add if a buyer asks. Most users get adequate locale handling via `dayfirst` + auto-parsing.

Async job queues, persistent storage, multi-tenancy, OAuth/JWT, and rate metering remain explicitly **out of scope**. Those are hosted-SaaS concerns.

---

## 📚 Related Documentation

- [api_reference.md](api_reference.md) — full form-field tables, response schemas, curl recipes per endpoint
- [cli_reference.md](cli_reference.md) — the underlying CLI surface (every API form field maps to a CLI flag)
- [workflows.md](workflows.md) — Daily Run / Growth Loop patterns the API can drive
- [reconciliation.md](reconciliation.md) — `--reconcile` engine feature (exposed via `/reconcile`)
- [verify.md](verify.md) — `--verify` integrity primitive (already wired to `/process` via the `verify` form field)
- [install.md](install.md) — `pip install finlang[api]` and getting `finlang-api` on PATH
- [faq.md](faq.md) — general FinLang FAQ

---

*The CLI is canonical. The API makes it reachable. Same engine, same audit trail, same determinism — over HTTP.*
