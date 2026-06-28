# 📊 Rule-Change Impact Analysis
> **Applies to:** FinLang v0.8.0+
> **Status:** Two-pass in-process analysis (baseline vs candidate rulepack); JSON + CSV + self-contained HTML artefacts.
> **Last verified:** v0.8.0

Impact analysis runs the **same input dataset through two rulepack versions** — your current rules (`--rules`) and a proposed change (`--impact-rules`) — and reports exactly what the change does: which rows re-categorise, the indicative amount moved between categories, which rules gain or lose matches, and a row-level before/after record. It answers the Tuesday-afternoon question — *"if I widen this rule, what else moves?"* — **before** the change goes live, not after the quarter's numbers are wrong.

> **Register:** the public name is **"impact analysis"** and amounts are **"indicative amount moved"**. This feature *supports* a change-control review and *provides evidence* for it; it does not by itself satisfy a regulatory control, and no FinLang material should claim it does.

---

## Baseline vs candidate — the two rulepacks

Impact analysis always compares exactly two rulepacks, run against the **same input data**:

| Term | Flag | What it is | In the report |
|------|------|-----------|---------------|
| **Baseline** | `--rules` | Your **current** rules — what's live today (the "before"). The same `--rules` flag you always use. | left of the arrow, `baseline.fin →` |
| **Candidate** | `--impact-rules` | The **proposed** change — the new rules you're evaluating but haven't deployed (the "after"). | right of the arrow, `→ candidate.fin` |

Read the report's title arrow as a direction: `baseline.fin → candidate.fin` means *"if I move **from** my current rules **to** these proposed ones, here is what changes."* So a transition shown as `Energy → Utilities` means the **baseline** produced `Energy` and the **candidate** produces `Utilities`.

The real-world mapping: **baseline** is the rulepack on your `main`/production branch; **candidate** is the rulepack in your pull request. Run impact and you see the blast radius *before* the candidate merges. (The terms are deliberate change-management language — a known-good *baseline*, and a *candidate* for deployment.)

---

## ✅ When to Use

- **Before merging any rulepack change.** See the blast radius — rows, categories, amounts — before it ships.
- **In CI on rulepack pull requests.** Exit code 3 on any behavioural change lets a pipeline annotate the PR and attach the report; a human approves. Every rule change can carry its own impact report.
- **When adopting `--suggest` candidates.** Understand what accepting generated rules would do to the categorised output first.
- **When inheriting an undocumented rulepack.** Propose a cleanup, run impact, see whether the cleanup is behaviour-neutral or not.

## ❌ When NOT to Use

- **Comparing FinLang against an external system** (e.g. an ML categoriser) — that's [`--reconcile`](reconciliation.md). Impact is FinLang-vs-FinLang on one shared frame.
- **Confirming a past run is unchanged** (same rules, same data) — that's [`--verify`](verify.md). Impact compares *two rulepacks* and expects differences by design.
- **Comparing engine versions on a frozen rulepack** — that's a different concern (canary pack), not impact analysis.

---

## 🔄 How It Works — one frame, two passes

```
input.csv ──► load ──► map ──► normalise ──► FRAME (read-only master)
                                              │
                              ┌── df.copy() ──┴── df.copy() ──┐
                              ▼                               ▼
                     apply rulepack A                apply rulepack B
                  (baseline, --rules)          (candidate, --impact-rules)
                              │                               │
                              └────────────┬──────────────────┘
                                           ▼
                                   vectorised diff
                                           ▼
                        summary · impact_report.json · impact_changes.csv
                                   · impact_report.html (--impact-html)
```

Both passes share the **same loaded, mapped, normalised frame**, each on a fresh copy. Two consequences worth knowing:

- **No alignment problem.** Same frame → identical row identity and order → the diff is exact by construction. None of reconcile's key-alignment machinery is needed.
- **Determinism is inherited.** Each pass is reproducible; the diff of two deterministic passes is deterministic. Same input + same two rulepacks → same report, every run.

---

## 🔁 Diff Semantics — behavioural vs attribution-only

| Change | What it means | Drives exit 3? |
|--------|---------------|----------------|
| **Behavioural** | Any difference in `category`, `flags`, or `status` | **Yes** |
| **Attribution-only** | Same outcome, a *different rule* produced it (rule renamed, reordered, or a new rule shadows an old one with identical effect) | **No** — reported prominently, never gates |

Attribution-only changes are reported in the summary, the JSON, the CSV (`change_class = attribution`), and a dedicated HTML section — but they **do not** set exit code 3. A harmless rename shouldn't make CI noisy. Flags are compared by **set equality** (token order carries no meaning in the engine).

---

## ⚙️ CLI Usage

```bash
finlang \
  --input transactions.csv \
  --rules current_rules.fin \
  --impact-rules proposed_rules.fin \
  --impact-output-dir impact_out/ \
  --impact-html
```

| Flag | Argument | What it does |
|------|----------|--------------|
| `--impact-rules` | path to candidate `.fin` | Activates impact analysis. `--rules` is the **baseline**; this is the **candidate**. Both run against the identical normalised input. |
| `--impact-output-dir` | directory path | Where artefacts are written. **Required** in impact mode; created if absent. |
| `--impact-html` | *(flag)* | Additionally emit a self-contained `impact_report.html`. Requires `--impact-rules` (and `--impact-output-dir`). |

> **Analysis run, not a production run.** Impact mode writes **no categorised output files** — `--output` is not required (and is ignored if given for the impact pass). It is mutually exclusive with `--reconcile` and `--verify` in a single invocation (fail fast, exit 2).

---

## 📋 Output Anatomy

### stdout summary
Headline counts (behavioural / attribution-only / stable + % stable), the top 5 category transitions by indicative absolute amount, rules added/removed, the float disclaimer line, and the exit-code result. Mirrors reconcile's CLI summary style.

### 📄 `impact_report.json` *(always written)*
Versioned schema (`"schema": "impact/1"`). Contains run metadata (finlang version, UTC timestamp, input file, both rulepack basenames **and their SHA-256 hashes**), headline counts, the full transition matrix, per-rule match deltas, flag deltas, status deltas, and the float disclaimer as `amount_note`. The **rulepack hashes tie the report to the exact rule text reviewed** — the artefact a change-approval record can reference.

### 📊 `impact_changes.csv` *(written when there are changes)*
Row-level before/after: `row_number`, `counterparty`, `amount`, `date`, `memo`, `old_category`, `new_category`, `old_flags`, `new_flags`, `old_status`, `new_status`, `old_rule`, `new_rule`, `change_class` (`behavioural` / `attribution`). Sorted by `row_number`. This is the complete record.

### 🌐 `impact_report.html` *(written with `--impact-html`)*
Self-contained, opens offline, no JavaScript, prints to PDF — suitable for a change-approval meeting. Header carries the rulepack hashes and the float disclaimer. Status banner is **amber "REVIEW REQUIRED — N rows change behaviour"** when behavioural changes exist, **green "NO BEHAVIOURAL CHANGE"** otherwise (amber, not red — a rule change producing changes is *expected*, not an error). Headline cards, transition matrix, per-rule deltas, and a prominent attribution-only section follow. The **row-level table is capped at the first 50 rows** — enough to read the character of the change in a meeting; the complete set is always in `impact_changes.csv`. Every user-provided string is `html.escape()`-ed.

---

## 🚦 Exit Codes

| Code | Meaning |
|------|---------|
| `0` | No behavioural changes. Attribution-only changes may exist — reported, never gating. |
| `2` | Validation error — e.g. `--impact-rules` without `--impact-output-dir`, `--impact-html` without `--impact-rules`, or impact combined with `--reconcile` / `--verify`. |
| `3` | Behavioural changes detected — review required (consistent with reconcile semantics). |

Exit 3 fires on **any** behavioural change, not on a threshold — there are no threshold flags. CI decides whether exit 3 blocks; the engine stays policy-free.

---

## 🔗 CI Integration

```bash
finlang --input reference_quarter.csv \
        --rules main_rules.fin \
        --impact-rules pr_rules.fin \
        --impact-output-dir impact_out/ \
        --impact-html
if [ $? -eq 3 ]; then
  echo "Rule change alters categorisation — see impact_out/impact_report.html"
  # attach the report to the PR; a human approves
fi
```
Run impact against a recent representative period (e.g. the last closed quarter) — *results are only as representative as the input.*

---

## 🚧 Limitations

- **Indicative amounts use float arithmetic**, not accounting-grade decimals — reproducible run-to-run, but not for penny-exact reconciliation. The disclaimer appears in the CLI summary and the HTML header, not just here.
- **No threshold/policy flags.** Exit 3 on any behavioural change; the pipeline decides what to gate on.
- **HTML row-level table capped at 50** — the CSV is the full record.
- **No N-way comparison** — two rulepacks at a time.

---

## 📚 Related Documentation

- [reconciliation.md](reconciliation.md) — `--reconcile`: FinLang vs an external system (different primitive — *their* system, not *your* rule change)
- [verify.md](verify.md) — `--verify`: confirm a past run is reproducible
- [cli_reference.md](cli_reference.md) · [flags.md](flags.md) — full flag tables
- [workflows.md](workflows.md) — CI/CD integration patterns

*Impact analysis reports what a rule change does to your categorised output. It shows and reports; it does not prove. Use it to make the change with eyes open.*
