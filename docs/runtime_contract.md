# Runtime & Backend Contract

## A. Scope
This document defines the **runtime execution guarantees** of FinLang. It is authoritative for:
* Backend selection
* Regex and string behavior
* CSV parsing guarantees
* Fallback and failure behavior

If behavior differs from this document, it is considered a bug.

## B. Supported Environment Matrix
FinLang is continuously tested and guaranteed to operate correctly on the following environment matrix:

| Component   | Supported Versions | Notes                                       |
| :---------- | :----------------- | :------------------------------------------ |
| **Python**  | 3.10 – 3.14        | Primary support target.                     |
| **Pandas**  | >= 2.0.0           | Required for strictly typed arrow backends. |
| **PyArrow** | >= 14.0.0          | Optional. Required only for `--fastio`.     |

## C. IO / Backend Modes
FinLang operates in two distinct modes. The mode is selected at runtime via CLI flags.

| Mode         | Trigger     | CSV Engine        | String Backend  | Regex Engine                   |
| :----------- | :---------- | :---------------- | :-------------- | :----------------------------- |
| **Standard** | *(default)* | `pandas[c]`       | Python (Object) | **Python `re`** (Full Unicode) |
| **FastIO**   | `--fastio`  | `pandas[pyarrow]` | Arrow / PyArrow | **RE2** (Arrow-compatible)     |

## D. The Contract (Normative)
The following guarantees are **non-negotiable** and enforced by tests:

1.  **Regex Compatibility**
    All internal normalization and cleaning logic MUST be compatible with:
    * Python `re` (Standard mode)
    * Google RE2 (FastIO mode via PyArrow)

2.  **Explicit Backend Selection**
    PyArrow-based execution is only enabled when `--fastio` is explicitly passed. The presence of PyArrow alone MUST NOT alter default behavior.

3.  **Graceful Degradation**
    If `--fastio` is requested but `pyarrow` is unavailable, FinLang MUST:
    * Fall back to **Standard** mode
    * Emit an informational log message
    * Continue execution without error

4.  **Strictness Guarantees**
    When `--strict-parse` is enabled, malformed input (including mixed delimiters) is a fatal error regardless of the backend.

## E. Known Constraints
* **RE2 Limitations:** Certain complex Python regex constructs (e.g., look-behinds) are not supported in FastIO mode. FinLang's internal patterns are designed to be RE2-compatible.

## F. Design Rationale
FinLang deliberately separates:
* **IO backend choice** (performance concern)
* **Rule semantics** (correctness concern)

This ensures:
* Identical outputs across backends
* Predictable behavior across environments
* Safe performance optimizations without semantic drift