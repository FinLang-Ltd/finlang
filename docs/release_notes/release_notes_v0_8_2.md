# FinLang v0.8.2 — Verify at engine speed
*Released: 20 July 2026*

---

## Summary

One change — `--verify` is now vectorised (SOL-110). No new features, no new flags, no schema changes, and deliberately no semantic changes: the same verification, dramatically faster.

On the 500,000-row full-mode benchmark, verification wall-clock dropped from **~570 seconds to ~15 seconds** on the same hardware (~38×). Artefacts are byte-identical and results field-identical to the previous implementation, and that equivalence is pinned by dedicated tests in the daily gate — not asserted, tested.

Daily test suite: 182 → 187 tests across the same 10 gates; API suite unchanged at 26.

---

## What changed for you

### `--verify` no longer costs you a coffee break
Verification of large outputs used to be the slowest step in the workflow — the scalar implementation re-parsed every date and amount row by row, and profiling showed ~92% of the runtime was per-row date-format guessing. The vectorised path loads both CSVs through a pandas fast path and runs normalisation/fingerprinting once per *unique* value instead of once per row. Real-world ledgers, where dates and amounts repeat heavily, can see proportionally better times than the deliberately repeat-hostile benchmark fixture.

### Nothing else changed — by design
- **Same semantics:** the vectorised path reuses the same scalar normalisation functions — there is no second implementation to drift. Unusual CSV structures automatically fall back to the original reader.
- **Same artefacts:** `verify_report.json` and `verify_proof.csv` are byte-identical to the scalar implementation's output on the same input.
- **Same exit codes:** 0 / 3 behaviour is untouched.

### The equivalence is pinned, not promised
Five new tests in the daily gate hold the fast path in place: byte-identical artefact comparison against the scalar implementation, a scalar/vector unquote property test, a hash-collision guard, reader equivalence + path selection across 19 hostile CSV structures, and a fast-path liveness test — the fallback reader cannot silently become the default without a test failing.

---

## Upgrade

```
pip install -U finlang
```

No flag, schema, or workflow changes required. If you script around `--verify`, everything behaves the same — sooner.
