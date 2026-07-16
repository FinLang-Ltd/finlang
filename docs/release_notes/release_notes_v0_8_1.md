# FinLang v0.8.1 — Hardening: the trust layer earns its name
*Released: 16 July 2026*

---

## Summary

No new features — thirteen fixes. v0.8.1 is the result of an adversarial sweep of our own codebase: three independent review passes over the comparison layer (verify, reconcile, impact), the CLI boundary, and the engine core, with every finding reproduced before it was fixed and pinned by a failing-first test after.

The theme: **FinLang should never be confidently wrong** — not about your data, not about its own audit trail, not about your rules files, and not about its security settings.

Same engine, same flags, same schemas. Categorisation output is unchanged. Daily test suite: 168 → 182 tests across the same 10 gates; API suite 24 → 26.

---

## What changed for you

### `--verify` now holds up on real-world text
FinLang's CSV output protects you from spreadsheet formula injection by quote-prefixing cells that start with `=` `+` `-` `@` or a tab. Verify (and reconcile's identity/key matching) didn't account for that deliberate transform — so a counterparty like a `+44…` phone number could make `--verify` report an integrity failure on perfectly processed data. Both now strip the guard symmetrically before comparing. `--verify-full` also no longer aborts on a blank or unparseable amount — it reports the row instead of crashing without artefacts.

### The audit trail is stricter about itself
- After a dropped input row (drop-rate guard), rule attribution in impact reports and reconcile audit linkage shifted by one for every subsequent row. Fixed — attribution now stays aligned.
- `audit.json` key order could vary between runs in the default audit mode. It is now canonical — the same run can produce the same audit file.
- The lite-mode audit cap counted matched rows instead of logged entries, so a wide-matching rule could silently stop later rules from being logged. Fixed.

### Your rules files fail loudly
A misspelled `--rules` path or `--include-pack` name previously warned to stderr and carried on with whatever loaded — categorised output missing an entire rulebook, exit code 0. Any named rules source that can't load is now a fatal validation error (exit 2).

### Reconcile rejects malformed input clearly
Ragged rows in a third-party ML CSV produce a row-named structural error (not a raw Python exception), and empty files are rejected instead of reporting "0 rows compared, all match".

---

## Compatibility notes (please read if you use the HTTP API)

1. **`/process` verification-failure detail is now a structured object.** When `verify=true` and verification fails, the HTTP 422 `detail` is `{error, exit_code, message, verify_report, stderr}` — previously a string. If your client parses `detail` as a string, branch on its type. The full verify report is attached because it is the artefact that explains the failure.
2. **An empty `FINLANG_API_KEY` now disables auth** rather than arming a gate an empty header could pass (the misconfiguration risk ran the other way). Set a non-empty key to enable auth; comparison is constant-time.

One test-suite contract change rides along: the paranoia gate now expects a fatal exit 2 on an unknown pack name — the old warn-and-continue expectation was the bug.

---

## Upgrade

```
pip install -U finlang
```

No flag, schema, or workflow changes required for CLI users. API consumers: see compatibility notes above.
