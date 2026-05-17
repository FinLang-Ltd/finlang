# FinLang v0.7.9 — Three Surfaces, One Engine
*Released: TBC*

---

## Summary

FinLang's deterministic categorisation engine is now reachable three ways: the original CLI for batch processing, the Python package for embedding, and a new FastAPI wrapper for service integration.

Same engine. Same audit trail. Same deterministic behaviour. The API adds an HTTP surface without creating a second source of truth.

---

## What's New

### `[api]` optional extras group + `finlang-api` console script

```bash
pip install "finlang[api]"
finlang-api    # binds 127.0.0.1:8000 — interactive docs at /docs
```

The `[api]` extras group pulls `fastapi`, `uvicorn`, and `python-multipart`. The `finlang-api` console script launches the FastAPI app via uvicorn for local development, demos, and service integration. Core install (`pip install finlang`) is unchanged — users who don't install `[api]` are unaffected.

### Six HTTP endpoints, all subprocess-dispatched

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Landing page → `/docs` |
| `GET` | `/health` | Liveness + version + `cli_resolved` |
| `POST` | `/process` | Categorise transactions |
| `POST` | `/discover` | Find uncategorised counterparties |
| `POST` | `/suggest` | Generate draft `.fin` rules from discovery candidates |
| `POST` | `/reconcile` | Run the v0.7.8 reconcile pass and return JSON summary + (optional) HTML report |

Every endpoint dispatches to the published CLI via subprocess. **The API is a thin FastAPI/subprocess wrapper — not a second engine.** Engine internals are never imported; failures are isolated inside child processes; the CLI remains the canonical surface.

### `/reconcile` exit-code semantics

Unlike `/process` (where engine exit 3 from `--verify` is a data-integrity error → HTTP 422), `/reconcile` maps **exit 3 → HTTP 200 with mismatches in the response body**. Finding mismatches is the expected outcome of reconciliation, not an error. The caller reads `stats.mismatches_found` and `summary.mismatches`. Only ops errors (exit 1 → 500) and validation errors (exit 2 → 422) map to error statuses on this endpoint.

### `/reconcile?format=html` — direct HTML response

Append `?format=html` to the POST URL and the API returns the HTML report directly with `Content-Type: text/html`, bypassing JSON wrapping:

```bash
curl -s -X POST 'http://localhost:8000/reconcile?format=html' \
  -F "input_csv=@transactions.csv" \
  -F "ml_output_csv=@ml_output.csv" \
  -F "rules=@rules.fin" \
  -F "reconcile_html=true" \
  -F "audit_mode=full" \
  -o reconcile_report.html
```

One step. Open the file in any browser. Improves the demo/report UX — previously, viewing the HTML report from a JSON response required manual `report_html` field extraction and backslash-escape cleanup. Default `format=json` returns the full `ReconcileResponse` (existing behaviour, no breaking change).

### Optional API-key authentication

Set `FINLANG_API_KEY` in the process environment and every non-`/health` endpoint requires a matching `X-API-Key` header. Auth is **opt-in** — when the env var is unset, auth is disabled (dev mode). `/health` is always public (load-balancer liveness probes).

### Configurable limits

| Env var | Default | Purpose |
|---|---|---|
| `FINLANG_API_TIMEOUT` | `300` (seconds) | Subprocess timeout |
| `FINLANG_API_MAX_UPLOAD` | `104857600` (100 MiB) | Upload size cap |
| `FINLANG_API_HOST` | `127.0.0.1` | `finlang-api` bind host |
| `FINLANG_API_PORT` | `8000` | `finlang-api` bind port |
| `FINLANG_API_LOG_LEVEL` | `info` | Uvicorn log level |

### Curated, not auto-forwarding

Each endpoint exposes specific `Form()` parameters that map to CLI flags. **New CLI flags do NOT automatically become API parameters** — adding a CLI flag to the API surface requires a deliberate endpoint edit. This is the strategic guardrail: the wrapper exists to expose existing engine behaviour over HTTP, not to be a flag-forwarding shim.

### 17 standalone API tests

`test-suite/test_api.py` carries 17 integration tests (TestClient-based) covering health, root, all 5 active endpoints, both reconcile response formats, auth gating, and a CLI/API reconcile parity contract test that runs the CLI and the API on the same demo inputs and asserts identical mismatch counts and exit semantics.

The API tests are a **standalone gate** — they run via `python -m pytest test_api.py -v` from `test-suite/` with the `[api]` extras + `httpx` installed in the test venv. They are **not** part of the daily `quick_check.ps1` gate.

### Two new documentation files

- **`docs/api.md`** — user-facing workflow doc (when to use, request flow, worked example, configuration, exit-code mapping, limitations, roadmap). Matches the `workflows.md` / `reconciliation.md` voice register.
- **`docs/api_reference.md`** — technical reference (form-field tables per endpoint, response schemas, HTTP status mapping, curl recipes, deployment notes).

`README.md`, `cli_reference.md`, and `install.md` cross-link to both.

---

## Why This Matters

Three surfaces, one engine — but the strategic shift is about **how FinLang fits into someone else's stack**.

The CLI was always good for batch processing. The Python package was always good for direct embedding. Neither was good for the integration pattern that matters most to buyers running ML categorisation pipelines: **an HTTP service the existing pipeline can POST to, get a rule-attributed answer back, and challenge the ML model's output row by row**.

That's the ML-challenger workflow. Before v0.7.9, integrating FinLang into that pipeline meant wrapping the CLI yourself — temp file staging, subprocess management, output parsing, error handling. Real friction for a team that just wants the audit-layer artefact.

After v0.7.9, teams can request the HTML report directly over HTTP instead of writing their own CLI wrapper and response-extraction logic.

The architecture choice is deliberate: the API never imports engine internals. Every request runs the published CLI as a subprocess, keeping the CLI as the behavioural source of truth and avoiding a second engine surface. A CLI/API parity test guards against drift.

---

## What Hasn't Changed

- **The engine.** `finlang_engine.py` is byte-identical to v0.7.8. Every categorisation decision the engine makes in v0.7.9 is the same decision it made in v0.7.8.
- **The audit trail.** `audit.json` schema, `--audit-mode lite/full` semantics, rule attribution, match-condition extraction — all unchanged.
- **The CLI surface.** Every CLI flag from v0.7.8 still works exactly the same way. The CLI remains the canonical surface; the API is additive.
- **Daily test gate.** Still 137 automated tests across 10 gates in `quick_check.ps1`. The 17 API tests are a separate standalone gate, not part of the daily count.
- **Performance.** Engine throughput characteristics unchanged from v0.7.8 (~217K rows/sec FastIO on the integrity harness). API adds ~50–150 ms subprocess overhead per request — negligible for human-driven requests; for batch loops where startup dominates, the CLI is still the right surface.

---

## Coming Next

Upcoming reconciliation hardening work will focus on safer row identity checks and key-based alignment for workflows where external systems may reorder outputs.

The current `/reconcile` behaviour remains positional and is documented in `docs/reconciliation.md`.

---

## How to Upgrade

For the CLI only (unchanged behaviour from v0.7.8):

```bash
pip install --upgrade finlang
```

For the CLI + the new HTTP API:

```bash
pip install --upgrade "finlang[api]"
finlang-api    # binds 127.0.0.1:8000 — interactive docs at /docs
```

For Fast I/O acceleration (recommended for large datasets, unchanged from prior releases):

```bash
pip install --upgrade "finlang[fastio]"
# Combine: pip install --upgrade "finlang[fastio,api]"
```

Verify the install:

```bash
finlang --version           # FinLang 0.7.9
finlang-api                 # starts the API server on 127.0.0.1:8000
```

---

## Migration Notes

**No migration required.** This release is purely additive:

- Existing `.fin` rules — unchanged.
- Existing CLI invocations — produce byte-identical output to v0.7.8.
- Existing `--audit-mode`, `--verify`, `--reconcile` behaviour — unchanged.
- `pip install finlang` without `[api]` extras — produces a v0.7.9 install that behaves exactly like a v0.7.8 install for CLI-only users.

The only behavioural change is the new HTTP surface, and it's opt-in (requires `[api]` extras + an explicit `finlang-api` invocation).

For exposed deployment (behind a reverse proxy, public-facing):

- Run behind a reverse proxy (nginx, Caddy) with TLS termination.
- Set `FINLANG_API_KEY` to a non-trivial value; rotate on a schedule.
- Lower `FINLANG_API_MAX_UPLOAD` if exposed on the public internet.
- Multi-tenant features, persistent storage, async job queues, and rate metering are explicitly out of scope for this wrapper; those concerns belong to a hosted-service layer above it.

---

## Acknowledgements

This release benefited from multi-model review during the spec-finalisation pass. Several blocking issues were caught before release, including the CLI/API reconcile parity contract.

The `?format=html` direct-HTML-response capability emerged from a real user-experience pain point hit during pre-release demo prep — turning a five-step JSON-extract-and-clean sequence into a one-step `curl -o report.html` download.

---

*See [CHANGELOG.md](../../CHANGELOG.md) for full version history.*
*See [api.md](../api.md) and [api_reference.md](../api_reference.md) for feature-level documentation.*
*See [reconciliation.md](../reconciliation.md) for the v0.7.8 `--reconcile` engine feature that the new `/reconcile` endpoint wraps.*
