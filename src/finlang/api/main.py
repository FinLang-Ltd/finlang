"""
FinLang API — FastAPI wrapper around the FinLang CLI.

SOL-041: Thin REST surface over the published CLI entry points
(`finlang`, `finlang-discover`, `finlang-suggest`). All work is dispatched
via subprocess — the API never imports engine internals. This keeps
execution behaviour aligned with the CLI and isolates failures inside
child processes. New CLI flags still need explicit endpoint parameters —
the wrapper is curated, not auto-forwarding.

Run:
    finlang-api
Or:
    uvicorn finlang.api.main:app --host 0.0.0.0 --port 8000

Auth:
    Optional API key via the X-API-Key header. Set FINLANG_API_KEY in the
    environment to enable. If unset, auth is disabled (dev mode).

Limits:
    FINLANG_API_TIMEOUT      Subprocess timeout in seconds (default: 300)
    FINLANG_API_MAX_UPLOAD   Max upload size in bytes (default: 100 MiB)
    FINLANG_API_HOST         Bind host for `finlang-api` script (default: 127.0.0.1)
    FINLANG_API_PORT         Bind port for `finlang-api` script (default: 8000)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import List, Optional

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from finlang import __version__

# ----------------------------------------------------------------------
# App
# ----------------------------------------------------------------------

app = FastAPI(
    title="FinLang API",
    description=(
        "Deterministic financial transaction processing — REST surface "
        "over the FinLang CLI. Categorise, discover, and generate rules "
        "without leaving HTTP."
    ),
    version=__version__,
)

# CLI entry points — resolved at import time. shutil.which is cross-platform.
FINLANG_CLI = shutil.which("finlang") or "finlang"
FINLANG_DISCOVER_CLI = shutil.which("finlang-discover") or "finlang-discover"
FINLANG_SUGGEST_CLI = shutil.which("finlang-suggest") or "finlang-suggest"

DEFAULT_TIMEOUT = int(os.environ.get("FINLANG_API_TIMEOUT", "300"))
MAX_UPLOAD_BYTES = int(
    os.environ.get("FINLANG_API_MAX_UPLOAD", str(100 * 1024 * 1024))
)


# ----------------------------------------------------------------------
# Auth
# ----------------------------------------------------------------------

def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    """API key gate. Active only when FINLANG_API_KEY is set."""
    expected = os.environ.get("FINLANG_API_KEY")
    if expected is None:
        return  # auth disabled (dev mode)
    if x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )


# ----------------------------------------------------------------------
# Response models
# ----------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "finlang-api"
    version: str
    timestamp: float
    cli_resolved: bool


class ProcessStats(BaseModel):
    rows_in: int
    rows_out: int
    audit_entries: int
    duration_seconds: float
    exit_code: int


class ProcessResponse(BaseModel):
    output_csv: str
    audit: Optional[list] = None
    verify_report: Optional[dict] = None
    stats: ProcessStats
    stderr: str = ""


class DiscoverResponse(BaseModel):
    candidates_csv: str
    all_candidates_csv: Optional[str] = None
    stderr: str = ""


class SuggestResponse(BaseModel):
    rules_fin: str
    stderr: str = ""


class ReconcileStats(BaseModel):
    duration_seconds: float
    exit_code: int
    mismatches_found: bool


class ReconcileResponse(BaseModel):
    summary: Optional[dict] = None       # from reconcile_report.json
    mismatches_csv: str = ""              # empty if no mismatches
    orphans_finlang_csv: str = ""        # key mode: FinLang rows with no ML match
    orphans_ml_csv: str = ""             # key mode: ML rows with no FinLang match
    report_html: Optional[str] = None    # only if reconcile_html=True
    audit: Optional[list] = None         # parsed audit.json
    stats: ReconcileStats
    stderr: str = ""


class ImpactStats(BaseModel):
    duration_seconds: float
    exit_code: int
    behavioural_changes_found: bool


class ImpactResponse(BaseModel):
    summary: Optional[dict] = None       # from impact_report.json
    changes_csv: str = ""                # impact_changes.csv (empty if no changes)
    report_html: Optional[str] = None    # only if impact_html=True
    stats: ImpactStats
    stderr: str = ""


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _run(cmd: List[str], timeout: int = DEFAULT_TIMEOUT) -> subprocess.CompletedProcess:
    """Run a CLI subprocess; surface failures as clean HTTP errors."""
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Subprocess exceeded {timeout}s timeout.",
        ) from e
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"FinLang CLI not found on PATH: {cmd[0]}",
        ) from e


async def _save_upload(upload: UploadFile, dest: Path) -> int:
    """Stream an upload to disk; enforce the size cap."""
    written = 0
    with dest.open("wb") as f:
        while chunk := await upload.read(64 * 1024):
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Upload exceeds {MAX_UPLOAD_BYTES} bytes.",
                )
            f.write(chunk)
    return written


def _row_count(path: Path) -> int:
    """Best-effort line count minus header. Returns -1 if unreadable."""
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as f:
            return max(0, sum(1 for _ in f) - 1)
    except Exception:
        return -1


def _engine_http_error(returncode: int, stderr: str) -> HTTPException:
    """Map FinLang exit codes to sensible HTTP statuses."""
    # 0 = ok, 1 = ops error, 2 = validation/parse, 3 = verification mismatch
    if returncode == 2:
        http = 422
        kind = "validation_error"
    elif returncode == 3:
        http = 422
        kind = "verification_failure"
    else:
        http = 500
        kind = "engine_error"
    return HTTPException(
        status_code=http,
        detail={"error": kind, "exit_code": returncode, "stderr": stderr},
    )


def _alignment_http_error(returncode: int, stderr: str) -> HTTPException:
    """Exit-code mapping for the alignment endpoints (/reconcile, /impact).

    Differs from `_engine_http_error` on exit 1. Exit 1 is *overloaded* in the
    engine: on these endpoints it is almost always a client-data condition the
    request can't be processed against (row-count mismatch, missing field,
    identity-guard failure, duplicate keys), but it can — rarely — be a genuine
    I/O failure. The engine does not separate the two with distinct exit codes,
    so we map exit 1 by its *dominant* meaning here: 422 (unprocessable input),
    not 500. Exit 2 (validation) → 422. Anything else → 500. Callers whitelist
    0 and 3 (success / review-needed) to HTTP 200 before reaching this.

    The body is the discriminator: `error` (machine enum), `exit_code`, a short
    `message`, and the full `stderr` (authoritative — names the specific cause).
    An integrator who needs to separate "my data" from "a server hiccup" branches
    on `error` + reads `stderr`. A future engine exit-code split would make this
    exact rather than dominant-meaning (see BACKLOG: API error taxonomy).
    """
    if returncode == 1:
        return HTTPException(
            status_code=422,
            detail={
                "error": "alignment_error",
                "exit_code": 1,
                "message": (
                    "Inputs could not be aligned for this comparison. Exit code 1 "
                    "is overloaded — usually an input problem (duplicate keys, "
                    "row-count mismatch, missing field, identity-guard failure), "
                    "rarely a genuine I/O failure. See stderr for the specific cause."
                ),
                "stderr": stderr,
            },
        )
    if returncode == 2:
        return HTTPException(
            status_code=422,
            detail={"error": "validation_error", "exit_code": 2, "stderr": stderr},
        )
    return HTTPException(
        status_code=500,
        detail={"error": "engine_error", "exit_code": returncode, "stderr": stderr},
    )


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def root() -> str:
    """Minimal landing page that points at the interactive docs."""
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>FinLang API</title></head>
<body style="font-family: system-ui, -apple-system, sans-serif; max-width: 640px; margin: 3rem auto; padding: 0 1rem; line-height: 1.5;">
<h1>FinLang API</h1>
<p>Deterministic financial transaction processing.</p>
<p>Version: <code>{__version__}</code></p>
<ul>
<li>Interactive docs: <a href="/docs">/docs</a></li>
<li>OpenAPI schema: <a href="/openapi.json">/openapi.json</a></li>
<li>Health: <a href="/health">/health</a></li>
</ul>
<p>Source: <a href="https://github.com/FinLang-Ltd/finlang">github.com/FinLang-Ltd/finlang</a></p>
</body></html>"""


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        version=__version__,
        timestamp=time.time(),
        cli_resolved=shutil.which("finlang") is not None,
    )


@app.post(
    "/process",
    response_model=ProcessResponse,
    dependencies=[Depends(require_api_key)],
)
async def process_csv(
    input_csv: UploadFile = File(..., description="Input transactions CSV"),
    rules: Optional[UploadFile] = File(
        None, description="Rules .fin file (optional if include_pack supplied)"
    ),
    map_file: Optional[UploadFile] = File(
        None, description="Optional header mapping JSON"
    ),
    include_pack: Optional[str] = Form(
        None,
        description="Comma-separated bundled packs (e.g. 'retail,transport,subs')",
    ),
    audit_mode: str = Form("lite", description="none | lite | full"),
    fastio: bool = Form(False),
    decimal: str = Form("."),
    thousands: Optional[str] = Form(None),
    dayfirst: bool = Form(False),
    encoding: str = Form("utf-8-sig"),
    output_encoding: str = Form("utf-8"),
    strict_parse: bool = Form(False),
    fail_threshold: float = Form(0.01),
    return_audit: bool = Form(True),
    verify: bool = Form(False, description="Run --verify after categorisation"),
    verify_full: bool = Form(False, description="Run --verify-full after categorisation"),
):
    """Categorise transactions. Returns output CSV + audit + stats."""
    if rules is None and not include_pack:
        raise HTTPException(
            400, "Provide either a rules file or include_pack (or both)."
        )
    if audit_mode not in ("none", "lite", "full"):
        raise HTTPException(400, "audit_mode must be one of: none, lite, full.")

    with tempfile.TemporaryDirectory(prefix="finlang_api_proc_") as tmp:
        d = Path(tmp)
        in_csv = d / "input.csv"
        out_csv = d / "output.csv"
        rules_fin = d / "rules.fin" if rules else None
        map_json = d / "map.json" if map_file else None
        audit_json = d / "audit.json" if (return_audit and audit_mode != "none") else None
        verify_dir = d / "verify" if (verify or verify_full) else None
        if verify_dir:
            verify_dir.mkdir()

        await _save_upload(input_csv, in_csv)
        if rules and rules_fin:
            await _save_upload(rules, rules_fin)
        if map_file and map_json:
            await _save_upload(map_file, map_json)

        cmd: List[str] = [
            FINLANG_CLI,
            "--input", str(in_csv),
            "--output", str(out_csv),
            "--audit-mode", audit_mode,
            "--encoding", encoding,
            "--output-encoding", output_encoding,
            "--decimal", decimal,
            "--fail-threshold", str(fail_threshold),
            "--headless",
        ]
        if thousands:
            cmd += ["--thousands", thousands]
        if dayfirst:
            cmd.append("--dayfirst")
        if fastio:
            cmd.append("--fastio")
        if strict_parse:
            cmd.append("--strict-parse")
        if rules_fin:
            cmd += ["--rules", str(rules_fin)]
        if include_pack:
            cmd += ["--include-pack", include_pack]
        if map_json:
            cmd += ["--map", str(map_json)]
        if audit_json:
            cmd += ["--audit", str(audit_json)]
        if verify_full:
            cmd.append("--verify-full")
        elif verify:
            cmd.append("--verify")
        if verify_dir:
            cmd += ["--verify-output-dir", str(verify_dir)]

        t0 = time.perf_counter()
        result = _run(cmd)
        elapsed = time.perf_counter() - t0

        if result.returncode != 0:
            raise _engine_http_error(result.returncode, result.stderr)
        if not out_csv.exists():
            raise HTTPException(500, "Engine completed but produced no output file.")

        audit_data: Optional[list] = None
        if audit_json and audit_json.exists():
            try:
                loaded = json.loads(audit_json.read_text(encoding="utf-8"))
                audit_data = loaded if isinstance(loaded, list) else None
            except Exception:
                audit_data = None

        verify_report: Optional[dict] = None
        if verify_dir:
            report_path = verify_dir / "verify_report.json"
            if report_path.exists():
                try:
                    verify_report = json.loads(report_path.read_text(encoding="utf-8"))
                except Exception:
                    verify_report = None

        return ProcessResponse(
            output_csv=out_csv.read_text(encoding="utf-8"),
            audit=audit_data,
            verify_report=verify_report,
            stats=ProcessStats(
                rows_in=_row_count(in_csv),
                rows_out=_row_count(out_csv),
                audit_entries=len(audit_data) if isinstance(audit_data, list) else 0,
                duration_seconds=round(elapsed, 4),
                exit_code=result.returncode,
            ),
            stderr=result.stderr,
        )


@app.post(
    "/discover",
    response_model=DiscoverResponse,
    dependencies=[Depends(require_api_key)],
)
async def discover(
    input_csv: UploadFile = File(
        ..., description="Categorised CSV from a prior /process run"
    ),
    min_count: int = Form(3),
    min_amount: Optional[float] = Form(None),
    top_k: Optional[int] = Form(None),
    since_date: Optional[str] = Form(None, description="YYYY-MM-DD"),
    include_excluded: bool = Form(False),
    return_all: bool = Form(False, description="Also return the all-candidates table"),
    encoding: str = Form("utf-8-sig"),
    decimal: str = Form("."),
    thousands: Optional[str] = Form(None),
    dayfirst: bool = Form(False),
):
    """Find uncategorised counterparties as candidates for new rules."""
    with tempfile.TemporaryDirectory(prefix="finlang_api_disc_") as tmp:
        d = Path(tmp)
        in_csv = d / "input.csv"
        candidates_csv = d / "candidates.csv"
        all_csv = d / "all_candidates.csv"

        await _save_upload(input_csv, in_csv)

        cmd: List[str] = [
            FINLANG_DISCOVER_CLI,
            "--input", str(in_csv),
            "--candidates", str(candidates_csv),
            "--all", str(all_csv),
            "--min-count", str(min_count),
            "--encoding", encoding,
            "--decimal", decimal,
        ]
        if thousands:
            cmd += ["--thousands", thousands]
        if dayfirst:
            cmd.append("--dayfirst")
        if min_amount is not None:
            cmd += ["--min-amount", str(min_amount)]
        if top_k is not None:
            cmd += ["--top-k", str(top_k)]
        if since_date:
            cmd += ["--since-date", since_date]
        if include_excluded:
            cmd.append("--include-excluded")

        result = _run(cmd)
        if result.returncode != 0:
            raise _engine_http_error(result.returncode, result.stderr)

        return DiscoverResponse(
            candidates_csv=(
                candidates_csv.read_text(encoding="utf-8")
                if candidates_csv.exists()
                else ""
            ),
            all_candidates_csv=(
                all_csv.read_text(encoding="utf-8")
                if return_all and all_csv.exists()
                else None
            ),
            stderr=result.stderr,
        )


@app.post(
    "/suggest",
    response_model=SuggestResponse,
    dependencies=[Depends(require_api_key)],
)
async def suggest(
    candidates_csv: UploadFile = File(..., description="Candidates CSV from /discover"),
    existing_rules: Optional[UploadFile] = File(
        None, description="Existing .fin rules (used for dedup)"
    ),
    emit_match: str = Form("fuzzy", description="exact | fuzzy"),
    category: str = Form("Review"),
    prefix: str = Form("SUGGEST"),
    quote_style: str = Form('"', description='" or \''),
):
    """Generate draft .fin rules from discovery candidates."""
    if emit_match not in ("exact", "fuzzy"):
        raise HTTPException(400, "emit_match must be 'exact' or 'fuzzy'.")
    if quote_style not in ('"', "'"):
        raise HTTPException(400, "quote_style must be \" or '.")

    with tempfile.TemporaryDirectory(prefix="finlang_api_sug_") as tmp:
        d = Path(tmp)
        in_csv = d / "candidates.csv"
        out_fin = d / "suggested.fin"
        rules_fin = d / "existing.fin" if existing_rules else None

        await _save_upload(candidates_csv, in_csv)
        if existing_rules and rules_fin:
            await _save_upload(existing_rules, rules_fin)

        cmd: List[str] = [
            FINLANG_SUGGEST_CLI,
            "--input", str(in_csv),
            "--output", str(out_fin),
            "--emit-match", emit_match,
            "--category", category,
            "--prefix", prefix,
            "--quote-style", quote_style,
            "--overwrite",
        ]
        if rules_fin:
            cmd += ["--rules", str(rules_fin)]

        result = _run(cmd)
        if result.returncode != 0:
            raise _engine_http_error(result.returncode, result.stderr)

        return SuggestResponse(
            rules_fin=out_fin.read_text(encoding="utf-8") if out_fin.exists() else "",
            stderr=result.stderr,
        )


@app.post(
    "/reconcile",
    response_model=ReconcileResponse,
    dependencies=[Depends(require_api_key)],
)
async def reconcile(
    input_csv: UploadFile = File(..., description="Input transactions CSV"),
    ml_output_csv: UploadFile = File(..., description="ML output CSV to reconcile against"),
    rules: Optional[UploadFile] = File(
        None, description="Rules .fin (optional if include_pack supplied)"
    ),
    map_file: Optional[UploadFile] = File(None),
    include_pack: Optional[str] = Form(None),
    reconcile_fields: str = Form("category", description="Comma-separated fields to compare"),
    reconcile_html: bool = Form(False, description="Emit self-contained HTML report"),
    reconcile_identity_fields: Optional[str] = Form(None, description="Comma-separated fields to identity-check positionally before comparison (e.g. date,amount,counterparty). Misaligned rows = structural failure (422)."),
    reconcile_key: Optional[str] = Form(None, description="Comma-separated fields for key-based alignment (e.g. date,amount,counterparty) — match by content, report orphans. Mutually exclusive with reconcile_identity_fields."),
    audit_mode: str = Form("full", description="Reconcile requires --audit-mode full"),
    fastio: bool = Form(False),
    decimal: str = Form("."),
    thousands: Optional[str] = Form(None),
    dayfirst: bool = Form(False),
    encoding: str = Form("utf-8-sig"),
    output_encoding: str = Form("utf-8"),
    strict_parse: bool = Form(False),
    fail_threshold: float = Form(0.01),
    format: str = Query(
        "json",
        description=(
            "Response format: 'json' (default) returns the full ReconcileResponse "
            "with summary + mismatches_csv + report_html + audit + stats. "
            "'html' returns the self-contained HTML report directly with "
            "Content-Type: text/html — convenient for human inspection (browser, "
            "Swagger UI). Requires reconcile_html=true."
        ),
    ),
):
    """Run --reconcile and return JSON summary + (optional) HTML report.

    Two response shapes selected by the ``format`` query param:
      - ``format=json`` (default): the full ``ReconcileResponse`` — summary,
        mismatches CSV, optional HTML report, audit log, stats.
      - ``format=html``: the self-contained HTML report directly, with
        ``Content-Type: text/html``. Bypasses JSON wrapping so the browser
        renders cleanly. Requires ``reconcile_html=true``.

    Exit code 3 (mismatches found) is mapped to HTTP 200 — finding mismatches
    is the expected outcome of reconciliation, not an error. The response body
    surfaces the mismatch count, mismatches CSV, and (if requested) HTML report.
    Exit codes 1 (ops) and 2 (validation) follow standard mapping.
    """
    if audit_mode != "full":
        raise HTTPException(400, "audit_mode must be 'full' for /reconcile.")
    if rules is None and not include_pack:
        raise HTTPException(400, "Provide either a rules file or include_pack (or both).")
    if format not in ("json", "html"):
        raise HTTPException(400, "format must be 'json' or 'html'.")
    if format == "html" and not reconcile_html:
        raise HTTPException(
            400, "format=html requires reconcile_html=true (no HTML report would be generated)."
        )

    with tempfile.TemporaryDirectory(prefix="finlang_api_recon_") as tmp:
        d = Path(tmp)
        in_csv = d / "input.csv"
        ml_csv = d / "ml_output.csv"
        out_csv = d / "finlang_out.csv"
        rules_fin = d / "rules.fin" if rules else None
        map_json = d / "map.json" if map_file else None
        audit_json = d / "audit.json"  # required for reconcile
        recon_dir = d / "reconcile"
        recon_dir.mkdir()

        await _save_upload(input_csv, in_csv)
        await _save_upload(ml_output_csv, ml_csv)
        if rules and rules_fin:
            await _save_upload(rules, rules_fin)
        if map_file and map_json:
            await _save_upload(map_file, map_json)

        cmd: List[str] = [
            FINLANG_CLI,
            "--input", str(in_csv),
            "--output", str(out_csv),
            "--audit", str(audit_json),
            "--audit-mode", "full",
            "--encoding", encoding,
            "--output-encoding", output_encoding,
            "--decimal", decimal,
            "--fail-threshold", str(fail_threshold),
            "--reconcile", str(ml_csv),
            "--reconcile-fields", reconcile_fields,
            "--reconcile-output-dir", str(recon_dir),
            "--headless",
        ]
        if thousands:
            cmd += ["--thousands", thousands]
        if dayfirst:
            cmd.append("--dayfirst")
        if fastio:
            cmd.append("--fastio")
        if strict_parse:
            cmd.append("--strict-parse")
        if rules_fin:
            cmd += ["--rules", str(rules_fin)]
        if include_pack:
            cmd += ["--include-pack", include_pack]
        if map_json:
            cmd += ["--map", str(map_json)]
        if reconcile_html:
            cmd.append("--reconcile-html")
        if reconcile_identity_fields:
            cmd += ["--reconcile-identity-fields", reconcile_identity_fields]
        if reconcile_key:
            cmd += ["--reconcile-key", reconcile_key]

        t0 = time.perf_counter()
        result = _run(cmd)
        elapsed = time.perf_counter() - t0

        # /reconcile contract: exit 0 = clean, exit 3 = mismatches found
        # (HTTP 200, expected outcome). Anything else is an error — 1 (ops),
        # 2 (validation), or any unmapped exit code. Whitelist 0/3 rather
        # than blacklisting 1/2 so future exit codes can't fall through to
        # an HTTP 200 carrying a bad exit_code in the body.
        if result.returncode not in (0, 3):
            raise _alignment_http_error(result.returncode, result.stderr)

        # Read back artefacts
        report_path = recon_dir / "reconcile_report.json"
        mismatches_path = recon_dir / "reconcile_mismatches.csv"
        html_path = recon_dir / "reconcile_report.html"

        summary: Optional[dict] = None
        if report_path.exists():
            try:
                summary = json.loads(report_path.read_text(encoding="utf-8"))
            except Exception:
                summary = None

        mismatches_csv = ""
        if mismatches_path.exists():
            mismatches_csv = mismatches_path.read_text(encoding="utf-8")

        # Key-mode orphan artefacts (absent in positional mode)
        orphans_fl_path = recon_dir / "reconcile_orphans_finlang.csv"
        orphans_ml_path = recon_dir / "reconcile_orphans_ml.csv"
        orphans_finlang_csv = (orphans_fl_path.read_text(encoding="utf-8")
                               if orphans_fl_path.exists() else "")
        orphans_ml_csv = (orphans_ml_path.read_text(encoding="utf-8")
                          if orphans_ml_path.exists() else "")

        report_html: Optional[str] = None
        if reconcile_html and html_path.exists():
            report_html = html_path.read_text(encoding="utf-8")

        audit_data: Optional[list] = None
        if audit_json.exists():
            try:
                loaded = json.loads(audit_json.read_text(encoding="utf-8"))
                audit_data = loaded if isinstance(loaded, list) else None
            except Exception:
                audit_data = None

        # format=html: return the HTML report directly with text/html content-type.
        # Bypasses JSON wrapping so browsers / Swagger UI render cleanly without
        # the caller needing to extract+unescape the report_html field manually.
        # FastAPI's response_model validation is bypassed automatically when a
        # Response subclass is returned.
        if format == "html":
            if not report_html:
                raise HTTPException(
                    500,
                    "Engine completed but produced no HTML report — reconcile_html "
                    "was true but the report file was missing or unreadable.",
                )
            return HTMLResponse(content=report_html, status_code=200)

        return ReconcileResponse(
            summary=summary,
            mismatches_csv=mismatches_csv,
            orphans_finlang_csv=orphans_finlang_csv,
            orphans_ml_csv=orphans_ml_csv,
            report_html=report_html,
            audit=audit_data,
            stats=ReconcileStats(
                duration_seconds=round(elapsed, 4),
                exit_code=result.returncode,
                mismatches_found=result.returncode == 3,
            ),
            stderr=result.stderr,
        )


@app.post(
    "/impact",
    response_model=ImpactResponse,
    dependencies=[Depends(require_api_key)],
)
async def impact(
    input_csv: UploadFile = File(..., description="Input transactions CSV"),
    impact_rules: UploadFile = File(..., description="Candidate (proposed) rules .fin to compare against the baseline"),
    rules: Optional[UploadFile] = File(
        None, description="Baseline (current) rules .fin (optional if include_pack supplied)"
    ),
    map_file: Optional[UploadFile] = File(None),
    include_pack: Optional[str] = Form(None, description="Baseline starter packs (comma-separated)"),
    impact_html: bool = Form(False, description="Emit self-contained HTML impact report"),
    fastio: bool = Form(False),
    decimal: str = Form("."),
    thousands: Optional[str] = Form(None),
    dayfirst: bool = Form(False),
    encoding: str = Form("utf-8-sig"),
    strict_parse: bool = Form(False),
    fail_threshold: float = Form(0.01),
    format: str = Query(
        "json",
        description=(
            "Response format: 'json' (default) returns the full ImpactResponse "
            "(summary + changes_csv + report_html + stats). 'html' returns the "
            "self-contained HTML report directly with Content-Type: text/html. "
            "Requires impact_html=true."
        ),
    ),
):
    """Run rule-change impact analysis (baseline `--rules` vs candidate
    `--impact-rules`) and return the JSON summary + (optional) HTML report.

    Exit-code contract mirrors the CLI: 0 = no behavioural change, 3 =
    behavioural change (review needed) — both map to HTTP 200, because finding
    changes is the expected outcome, not an error. Exit 2 (validation) → 422.
    Impact mode writes no categorised output; `--output` is not used.
    """
    if rules is None and not include_pack:
        raise HTTPException(400, "Provide either a baseline rules file or include_pack (or both).")
    if format not in ("json", "html"):
        raise HTTPException(400, "format must be 'json' or 'html'.")
    if format == "html" and not impact_html:
        raise HTTPException(
            400, "format=html requires impact_html=true (no HTML report would be generated)."
        )

    with tempfile.TemporaryDirectory(prefix="finlang_api_impact_") as tmp:
        d = Path(tmp)
        in_csv = d / "input.csv"
        candidate_fin = d / "candidate.fin"
        baseline_fin = d / "baseline.fin" if rules else None
        map_json = d / "map.json" if map_file else None
        impact_dir = d / "impact"
        impact_dir.mkdir()

        await _save_upload(input_csv, in_csv)
        await _save_upload(impact_rules, candidate_fin)
        if rules and baseline_fin:
            await _save_upload(rules, baseline_fin)
        if map_file and map_json:
            await _save_upload(map_file, map_json)

        # Impact mode is an analysis run — no --output, no --audit.
        cmd: List[str] = [
            FINLANG_CLI,
            "--input", str(in_csv),
            "--impact-rules", str(candidate_fin),
            "--impact-output-dir", str(impact_dir),
            "--encoding", encoding,
            "--decimal", decimal,
            "--fail-threshold", str(fail_threshold),
            "--headless",
        ]
        if thousands:
            cmd += ["--thousands", thousands]
        if dayfirst:
            cmd.append("--dayfirst")
        if fastio:
            cmd.append("--fastio")
        if strict_parse:
            cmd.append("--strict-parse")
        if baseline_fin:
            cmd += ["--rules", str(baseline_fin)]
        if include_pack:
            cmd += ["--include-pack", include_pack]
        if map_json:
            cmd += ["--map", str(map_json)]
        if impact_html:
            cmd.append("--impact-html")

        t0 = time.perf_counter()
        result = _run(cmd)
        elapsed = time.perf_counter() - t0

        # 0 = no behavioural change, 3 = behavioural change (review needed):
        # both HTTP 200. Whitelist rather than blacklist so future exit codes
        # can't fall through to a 200 carrying a bad exit_code.
        if result.returncode not in (0, 3):
            raise _alignment_http_error(result.returncode, result.stderr)

        report_path = impact_dir / "impact_report.json"
        changes_path = impact_dir / "impact_changes.csv"
        html_path = impact_dir / "impact_report.html"

        summary: Optional[dict] = None
        if report_path.exists():
            try:
                summary = json.loads(report_path.read_text(encoding="utf-8"))
            except Exception:
                summary = None

        changes_csv = changes_path.read_text(encoding="utf-8") if changes_path.exists() else ""
        report_html: Optional[str] = None
        if impact_html and html_path.exists():
            report_html = html_path.read_text(encoding="utf-8")

        if format == "html":
            if not report_html:
                raise HTTPException(
                    500,
                    "Engine completed but produced no HTML report — impact_html "
                    "was true but the report file was missing or unreadable.",
                )
            return HTMLResponse(content=report_html, status_code=200)

        return ImpactResponse(
            summary=summary,
            changes_csv=changes_csv,
            report_html=report_html,
            stats=ImpactStats(
                duration_seconds=round(elapsed, 4),
                exit_code=result.returncode,
                behavioural_changes_found=result.returncode == 3,
            ),
            stderr=result.stderr,
        )


# ----------------------------------------------------------------------
# Script entry point
# ----------------------------------------------------------------------

def run() -> None:
    """Entry point for the `finlang-api` script."""
    import uvicorn

    host = os.environ.get("FINLANG_API_HOST", "127.0.0.1")
    port = int(os.environ.get("FINLANG_API_PORT", "8000"))
    uvicorn.run(
        "finlang.api.main:app",
        host=host,
        port=port,
        log_level=os.environ.get("FINLANG_API_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    run()
