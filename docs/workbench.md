# 🖥 The FinLang Workbench
> **Applies to:** FinLang v0.9.0+ (`finlang-ui`)
> **Status:** Production
> **Last verified:** v0.9.1

The Workbench is FinLang's local browser interface: run `finlang-ui` and a page opens against a server on **your own machine**. Pick a CSV, pick rules, tick the checks you want, and run — every row comes back with the rule that decided it, verification and reconciliation arrive as reports you can hand to a human, and a rule builder reads your rules back in plain English, checked by the same engine that runs them.

It is a fourth surface over the **same engine** as the CLI, the Python call, and the HTTP API — not a second implementation. Every run shows the equivalent `finlang` command line, so anything you click today you can script tomorrow.

---

## 🎯 Quick Navigation

**I want to…**
- [Get it running](#-setup) → one command
- [Do a first run](#-the-run-screen) → files, checks, results
- [Build and check rules](#-the-rules-screen) → plain-English read-back
- [Understand the local-only design](#-local-by-design) → what leaves your machine (nothing)
- [Fix a problem](#-troubleshooting) → port, browser, PATH

---

## 📦 Setup

**Prerequisites:** Python 3.10+ and a modern browser. Nothing else — the Workbench's server ships in the base package.

```
pip install -U finlang
finlang-ui
```

Your default browser opens at `http://127.0.0.1:8484/ui/`. If a tab doesn't appear, open that address yourself — the server prints it on start.

- **Different port:** set `FINLANG_UI_PORT` before launching (e.g. `8485`) if 8484 is taken.
- **Stopping:** `Ctrl+C` in the terminal that ran `finlang-ui`. Nothing keeps running afterwards; the Workbench holds no state outside your browser.
- **Upgrading from an older install:** `pip install -U finlang` is sufficient. (Before v0.9.0 the server packages lived in the optional `[api]` extra; they are base dependencies now, and `pip install "finlang[api]"` remains valid as a no-op.)

---

## ▶ The Run screen

A run needs two files, chosen with ordinary file pickers:

1. **Transactions CSV** — any columns, any order; it needs date, amount and counterparty to be findable (memo optional). Non-UK/US files are covered by the locale block on the same card: day-first dates, decimal/thousands separators, encoding, and a header-mapping JSON for differently named columns.
2. **Rules** — a `.fin` file from disk, a bundled rulepack, or the draft from the Rules screen.

**What to run:** the audit trail (`full` by default — it is what puts the deciding rule on every row), **Verify** (fast fingerprint or full field-by-field, with an HTML report), and **Reconcile** against a model-output CSV (row-by-row comparison, every disagreement explained, with orphan-reporting key alignment under *Advanced*).

**Results** land in tabs:

| Tab | What it holds |
|---|---|
| rows | Every categorised row — category, flags, status, and the rule that set them |
| key results | Category totals from the run you just did, drawn as charts |
| verify report / reconcile report | The same HTML reports the CLI can produce, inline |
| downloads | The output CSV, audit JSON, and report files |
| run log | **The exact `finlang` command line for this run** — copy it into a script or CI job and you can get the same answer without the Workbench |

A verify or reconcile *finding* is reported in the banner as the product working, not as an error — the run still completes and the reports say exactly what was found.

---

## ✏ The Rules screen

Build a rule step by step on the left — name, match conditions, actions — and **Insert & check** appends it to the editor and runs the whole file through the engine. Or paste/type straight into the editor and hit **Check syntax**.

The payoff is the read-back: **“What the engine understood”** renders every rule in plain English — *when counterparty contains SHELL, then set category to Energy & Commodities…* — produced by the engine's own tokeniser via `/rules/validate`. The Workbench contains no parser of its own, so “valid here” and “valid in a run” are the same fact.

Drafts autosave in your browser. Rules run in file order and the last matching rule sets the category — put specific rules after general ones.

---

## 🔁 The other screens

- **Growth loop** — takes a run's output and finds what no rule claimed, then drafts candidate rules for the gaps. Nothing enters your ruleset without you accepting it.
- **Impact** — point it at your current rules and a candidate version to see what a change would actually move — which rows re-categorise and how much value shifts — before you ship it. It writes no output; it is a rehearsal.

---

## 🔒 Local by design

- The page talks to a server bound to `127.0.0.1` — **pinned, with no override**. Your files are read by the engine on your machine and the results come back to your browser; nothing leaves.
- No CDN, no telemetry, no external fonts or scripts — everything the page uses ships inside the wheel.
- If you genuinely want the HTTP surface on a network, that is a separate, explicit decision: use [`finlang-api`](api.md), which exists for exactly that and makes the exposure yours to own.

---

## 🛠 Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Browser opens on a connection error | The port is taken — set `FINLANG_UI_PORT` to a free port and relaunch. The terminal shows uvicorn's own error. |
| No browser tab appears | Some environments block auto-open. The URL is printed on start — open it manually. |
| `finlang-ui: command not found` | The environment where FinLang is installed isn't active, or its scripts directory isn't on PATH. Activate the venv you installed into. |
| `finlang-ui` reports the web server is missing | Pre-v0.9.0 environment. `pip install -U finlang`. |
| A run fails with dropped rows or missing columns | A locale/mapping problem, not a Workbench one — the banner opens the locale block for you; see [mapping_guide.md](mapping_guide.md). |

---

## See also

- [install.md](install.md) — installation
- [cli_reference.md](cli_reference.md) — the CLI the Workbench mirrors (and shows you, per run)
- [api.md](api.md) — the HTTP surface the Workbench is served by
- [rule_language.md](rule_language.md) — the `.fin` language the Rules screen builds
