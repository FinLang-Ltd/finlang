# 🖥 The FinLang Workbench
> **Applies to:** FinLang v0.9.0+ (`finlang-ui`)
> **Status:** Production
> **Last verified:** v0.9.1

The Workbench is FinLang's local browser interface: run `finlang-ui` and a page opens against a server on **your own machine**. Pick a CSV, pick rules, switch on the checks you want, and run — every row comes back with the rule that decided it, verification and reconciliation arrive as reports you can hand to a human, and a rule builder reads your rules back in plain English, checked by the same engine that runs them.

It is a fourth surface over the **same engine** as the CLI, the Python call, and the HTTP API — not a second implementation. Every run shows the equivalent `finlang` command line, so anything you click today you can script tomorrow.

---

## 🎯 Quick Navigation

**I want to…**
- [Get it running](#-setup) → one command
- [Do a first run](#-categorise-a-file) → files, checks, results
- [Build and check rules](#-rules) → plain-English read-back
- [Find gaps or test a change](#-the-other-screens) → growth loop and impact
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

## ▶ Categorise a file

*(Called the Run screen before the October 2026 redesign.)* One page, three numbered steps:

1. **Your file** — drop a CSV on the page or choose it. Any columns, any order; it needs date, amount and counterparty to be findable (memo optional). Non-UK/US files are covered by *My file isn't a UK/US-style CSV* on the same step: day-first dates, decimal/thousands separators, encoding, and a header-mapping JSON for differently named columns.
2. **Rules** — a `.fin` file from your computer, a bundled starter pack, or your draft from the Rules screen.
3. **Checks** — the audit trail (`full` by default — it is what puts the deciding rule on every row), **Verify** (fast fingerprint or full field-by-field, with an HTML report), and **Compare with another system** — reconcile against a model-output CSV, every disagreement explained. *How rows are paired* sets the alignment: **row by row** (the default: row 1 against row 1, so both files need the same rows in the same order; columns can be in any order), **row by row, checking each pair is the same transaction** (`--reconcile-identity-fields`: stops if the named columns differ on any row), or **match on key columns** (`--reconcile-key`: any row order, row counts can differ, rows only one file has are listed separately). Their file needs a `category` column, plus any columns you check or match on, under the same names. See [reconciliation.md](reconciliation.md). Each check is a switch; its options open when it is on.

**Results** land in tabs:

| Tab | What it holds |
|---|---|
| rows | Every categorised row with the rule that decided it. Click a row to open **Why this category**: every rule that matched, in the order it ran, what each one changed, and which earlier result a later rule replaced — with a *Copy explanation* button. Filters narrow to rows the other system disagrees with, flagged rows, or rows more than one rule matched; *Every column* shows the full output |
| key results | Category totals from the run you just did, drawn as charts |
| verify report / reconcile / reconcile report | The same HTML reports the CLI can produce, inline, plus the reconcile summary |
| downloads | The output CSV, audit JSON, and report files |
| run log | **The exact `finlang` command line for this run** — copy it into a script or CI job and you can get the same answer without the Workbench |

A verify or reconcile *finding* is reported in the banner as the product working, not as an error — the run still completes and the reports say exactly what was found. When you compared with another system, the rows table gains an **Other system** column showing their category wherever it differs, and the banner counts rows with no match in their file and rows only their file has (the reconcile tab lists both). If every date in their file could be read either way, the banner says which convention the engine assumed and where to set it. If the comparison stops — for example the identity check finds the rows in a different order — your categorised rows are still shown, with the reason.

---

## ✏ Rules

Build a rule step by step on the left — name, match conditions, actions — and **Insert & check** appends it to the editor and runs the whole file through the engine. Or paste/type straight into the editor and hit **Check syntax**.

The payoff is the read-back: **“What the engine understood”** renders every rule in plain English — *when counterparty contains SHELL, then set category to Energy & Commodities…* — produced by the engine's own tokeniser via `/rules/validate`. The Workbench contains no parser of its own, so “valid here” and “valid in a run” are the same fact.

Drafts autosave in your browser. Rules run in file order and the last matching rule sets the category — put specific rules after general ones.

---

## 🔁 The other screens

- **Find gaps** (the growth loop) — takes a run's output, or any file plus rules, and finds what no rule claimed, then drafts candidate rules for the ones you tick. Nothing enters your ruleset without you accepting it.
- **Test a change** (impact) — point it at your current rules and a proposed version to see what a change would actually move — which rows re-categorise and how much value shifts — before you ship it. It writes no output; it is a rehearsal.

---

## 🔒 Local by design

- The page talks to a server bound to `127.0.0.1` — **pinned, with no override**. Your files are read by the engine on your machine and the results come back to your browser; nothing leaves.
- No CDN, no telemetry, no external fonts or scripts — everything the Workbench pages use ships inside the wheel. (The HTTP API's interactive docs at `/docs`, linked from the home page, are FastAPI's own and load Swagger UI from a CDN.)
- Your browser keeps, in this site's local storage between visits: your rules draft and its file name, and your last categorised output (up to about 2 MB) with the names of the file and rules it came from and when, so Find gaps can pick it up. A new run replaces the output. Clearing the site's data in your browser removes all of it.
- If you genuinely want the HTTP surface on a network, that is a separate, explicit decision: use [`finlang-api`](api.md), which exists for exactly that and makes the exposure yours to own.

---

## 🛠 Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Browser opens on a connection error | The port is taken — set `FINLANG_UI_PORT` to a free port and relaunch. The terminal shows uvicorn's own error. |
| No browser tab appears | Some environments block auto-open. The URL is printed on start — open it manually. |
| A page looks half-styled after upgrading | Your browser kept files from the older version. Press `Ctrl+F5` once; from this version on, the Workbench tells the browser to check for changes every time. |
| `finlang-ui: command not found` | The environment where FinLang is installed isn't active, or its scripts directory isn't on PATH. Activate the venv you installed into. |
| `finlang-ui` reports the web server is missing | Pre-v0.9.0 environment. `pip install -U finlang`. |
| A run fails with dropped rows or missing columns | A locale/mapping problem, not a Workbench one — the banner opens the locale block for you; see [mapping_guide.md](mapping_guide.md). |

---

## See also

- [install.md](install.md) — installation
- [cli_reference.md](cli_reference.md) — the CLI the Workbench mirrors (and shows you, per run)
- [api.md](api.md) — the HTTP surface the Workbench is served by
- [rule_language.md](rule_language.md) — the `.fin` language the Rules screen builds
