# FinLang v0.7.2 Release Notes
**Date:** 2026-01-31
**Tag:** `Stability & Standards`

## Overview
This patch release focuses on **runtime stability** and **architectural transparency**. It resolves a critical compatibility issue between Python's `re` module and the PyArrow/RE2 engine, ensuring reliable "FastIO" execution across all platforms. It also formalizes the project's architecture with a new Runtime Contract.

## 🚀 Key Changes

### 1. PyArrow & Regex Stability Fix
We identified and patched a regex string handling issue that caused the `pyarrow` engine to crash due to raw string formatting conflicts.
* **Fix:** Removed raw string prefixes (`r"..."`) that conflicted with specific backend parsers.
* **Impact:** All internal patterns are now RE2-compatible, eliminating crashes when using `--fastio` (or when PyArrow is installed) regardless of the operating system. User-defined rules remain unaffected.

### 2. Unified Tool Logging
The `finlang-discover` tool now provides the same runtime transparency as the main engine.
* It explicitly reports the active engine: `(Engine: pyarrow)` or `(Engine: c)`.
* Users can now verify at a glance that performance optimizations are active.

### 3. The Runtime Contract
We have introduced `docs/runtime_contract.md`. This document serves as the authoritative source of truth for:
* Supported execution environments (Python 3.10-3.14).
* Backend selection guarantees (Standard vs. FastIO).
* Strictness and Fallback behaviors.

## 🛠 Upgrade Instructions
No breaking changes. Upgrade via standard mechanisms:

```bash
pip install --upgrade finlang
# or for local dev
git pull && pip install -e .
```