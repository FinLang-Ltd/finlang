"""
FinLang API — FastAPI wrapper around the FinLang CLI.

SOL-041: Thin REST surface over the published CLI entry points
(`finlang`, `finlang-discover`, `finlang-suggest`). All work is dispatched
via subprocess — the API never imports engine internals. This keeps the
contract identical to the CLI, isolates failures inside child processes,
and means new CLI flags become available with no API code changes.

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


@app.post("/reconcile", dependencies=[Depends(require_api_key)])
async def reconcile():
    """
    Independent reconcile pass — SOL-040.

    Endpoint reserved. Wire to `finlang --reconcile` (subprocess) once SOL-040
    ships. Mirrors /process structure: accept input CSV + reference output +
    optional rules, return reconcile report (HTML + JSON summary).
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "/reconcile endpoint reserved for SOL-040. "
            "Will be wired after the --reconcile feature lands in the engine."
        ),
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
