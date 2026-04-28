# FinLang — Working Contract
*For Claude Code sessions in `{workspace}\prod\`*
*Baseline: v0.7.7 (shipped 4 April 2026) | Tests: 118 (9 gates) | Current focus: SOL-040 `--reconcile`*

---

## Standards this project inherits

Standards live in `(private angus-os workspace) `. Work from these canonical paths — don't guess or paraphrase from memory.

**Session contract (read first):**
- `(private angus-os workspace) .claude\AGENTS.md`

**Package-structure standards:**
- `(private angus-os workspace) engineering\DRAFT-folder-structure-package-v3.md`
- `(private angus-os workspace) engineering\DRAFT-branch-workflow-package-v1.md`
- `(private angus-os workspace) engineering\DRAFT-release-promotion-package-v1.md`
- `(private angus-os workspace) engineering\DRAFT-claude-md-pattern-v3.md`
- `(private angus-os workspace) engineering\DRAFT-gitignore-patterns-v2.md`
- `(private angus-os workspace) engineering\ci-cd-package.md`

**Code + security (shared):**
- `(private angus-os workspace) engineering\coding-standards.md` (FinLang is the pilot-reviewed source)
- `(private angus-os workspace) engineering\machine-grade-checklist.md`
- `(private angus-os workspace) engineering\secrets-management.md`
- `(private angus-os workspace) engineering\security.md`
- `(private angus-os workspace) engineering\security-review-package.md`
- `(private angus-os workspace) engineering\security-supply-chain.md`

**Anti-patterns:**
- `(private angus-os workspace) anti-patterns\README.md`
- `(private angus-os workspace) anti-patterns\anti-patterns-CHANGELOG.md` (refresh trigger)

**Project-specific:**
- `{workspace}\strategy-backlog\BACKLOG.md`
- `(private angus-os workspace) MANIFEST.md`
- `(private angus-os workspace) projects.yaml`

---

## What this folder is

This is the **tracked codebase** — `prod/` is the FinLang git repo and the working tree where Claude Code develops features on feature branches. Post-consolidation (27 April 2026), the dev/prod folder split is retired; `prod/` serves as both the editable working tree and the release source.

This is the published codebase. PyPI builds from here. `git push origin` happens here. Nothing experimental touches `main` directly — feature branches isolate work-in-progress, hooks block direct commits to main, and the release gate (when built) blocks bad publishes.

---

## How this file works

This file (`prod/CLAUDE.md`) is the **working contract** — tracked in git as part of the prod repo. Edits are persistent. Updates happen on feature branches like any other code change.

Post-consolidation (27 April 2026) the file lives once, tracked in git. The pre-consolidation canonical-source-mirror pattern is retired (see `angus-os/engineering/DRAFT-claude-md-pattern-v3.md` for the single-tree spec).

What this means for you:

- **Edits to this file are persistent and tracked.** Path A (trivial doc edits) commit directly to main; Path B (substantive or CC-authored rewrites) go on a feature branch. See § "Workflow doctrine" below.
- **The header line `Tests: N (G gates)` is a canary.** If it doesn't match the actual test count when you read it, surface to the human — do not auto-edit as a side-effect of feature work.

---

## Workflow doctrine — Process Lock 280426

*Locked 28 April 2026. Reference: Process Lock 280426 runbook (executed and archived to `..\scratch\archive\` post-completion).*

> **FinLang uses a solo-maintainer trunk workflow with branch isolation for CC-assisted or substantive work. Main is the working truth; PyPI is protected by the release gate.**

**Trigger test (one-line decision rule):**

> If the change requires me to think about it more than once, or if CC is doing the writing, it goes on a branch.

**Three paths:**

**Path A — Angus-driven, lightweight, on main.** Permitted scope: typos, doc updates, roadmap edits, small single-file config corrections, tiny inspected fixes. Never: version bumps, CHANGELOG entries, release notes, tags (those are Path C). Mechanics: edit in `prod/` on main → `git status` / `git diff` → `quick_check.ps1` if functional → commit → push origin main. **Stop rule:** if the edit unexpectedly expands beyond the intended file/scope, stop and branch before continuing.

**Path B — CC-driven or substantive, branched.** Required scope (non-negotiable): anything CC authors (even one-line fixes), multi-file code changes, engine-semantic changes, packaging/dependency changes, test harness changes, release-gate changes, anything where rollback would be annoying. Mechanics: CC creates a `claude/<auto-name>` branch (CC's auto-naming); deliberate Angus branches use `feat/<name>` or `fix/<name>`. Work happens on the branch; Angus reviews full diff via `git diff main..<branch>`; `quick_check.ps1` against branch state; if satisfied: `git switch main && git merge --no-ff <branch> && git branch -d <branch>` then `git push origin main`. If not: `git branch -D <branch>`. `--no-ff` preserves the branch boundary in main history.

**Path C — Release (PyPI publishing).** Reserved for release state: version bumps across `__init__.py`, `pyproject.toml`, `run_finlang.py`, `canonical_fields.yaml`; CHANGELOG entries; release notes; tags; publishing. **Target state** (build pending, Phase 3 follow-on): `release_preflight.ps1` owns `twine upload` per the 8-condition gate (`angus-os/engineering/DRAFT-release-gate-package-v1.md`). **Current state** (until gate built): `RELEASE_CHECKLIST.md` followed step-by-step; manual `twine upload` permitted ONLY after checklist completion + cleanroom validation. Manual `twine upload` outside that flow is forbidden by policy.

**What changed under Process Lock 280426:**

- Layer 4 (server-side branch protection on `origin/main`) was disabled. Conditional reinstatement triggers: (a) FinLang takes on a contributor; (b) the release gate breaks or is removed; (c) the pre-push hook with path-audit is removed.
- The `wip` remote plan and Phase 3.5 setup were removed from the queue.
- PR-required workflow for routine work is no longer the default.
- Pre-commit hook is now permissive (allows direct main commits per Path A). Discipline lives in this contract, not in mechanical enforcement.
- Pre-push hook gained a new check: only `refs/heads/main` and `refs/tags/*` may be pushed to `origin`. Feature branches stay local; merge to main locally, then push main. Mechanically enforces "merge before push" without relying on Layer 4.

Layers 1–3 (discipline, tooling, hooks), pre-push path-leak/Drive-pattern detection, single-tree consolidation, test-suite at root + editable install, strategy-backlog folder, DOCUMENT_MAP-driven doc updates, anti-elegance discipline, the release gate spec (target state), and the CLA allowlist all stay in place.

---

## CRITICAL SAFETY RULES

These are non-negotiable. Violating any of them is a stop-and-ask situation, not a "carry on and fix later":

1. **Match the work to a path before touching code.** See § "Workflow doctrine — Process Lock 280426". Path A (direct main) is permitted ONLY for Angus-driven typos, doc updates, roadmap edits, tiny single-file config fixes. **Anything CC authors goes on a branch (Path B), no exceptions.** If a Path A edit unexpectedly expands beyond a single intended file or trivial scope, stop and branch before continuing. Pre-commit hook is permissive under Process Lock 280426 — discipline lives here in the working contract, not in mechanical enforcement.
2. **NEVER run `twine upload` directly.** PyPI publishes flow through `test-suite/release_preflight.ps1` (the release gate). Manual `twine upload` outside the gate is a policy violation. The gate refuses to publish unless 8 conditions pass — no override flag.
3. **NEVER bump the FinLang version outside the release flow.** Version bumps happen on a `release/v<version>` branch as part of the release process per `DRAFT-release-promotion-package-v1.md` Phase 4. Current shipped version is `0.7.7`.
4. **Test files: extend, don't restructure.** See dedicated section below — this is the most nuanced rule and deserves its own block.
5. **NEVER use `git add .`** — stage files explicitly so the commit is reviewable.
6. **Public repo discipline:** FinLang's `origin` is public. The pre-push hook blocks any non-`main`, non-tag push to `origin` — feature branches must stay local. Merge feature branches to main locally, then push main. Bypass via `git push --no-verify` is a CLAUDE.md policy violation requiring explicit human approval. (The previously-planned `wip` remote was retracted under Process Lock 280426; the hook check now does the load-bearing work.)

If a request from the human seems to conflict with any of these rules, surface the conflict first. Don't try to satisfy the request by working around the rule.

---

## RULE 4: Test files — extend, don't restructure

The bulk of FinLang's tests live in `..\test-suite\`, not in `tests\` here. The local `tests\` directory only contains the small ship-with-the-repo tests (`test_cli_smoke.py` and `tests/contracts/*.py` AST contract tests). The 118-test daily suite — `test_rule_interactions.py`, `test_discover_suggest.py`, `test_rule_correctness.py`, `test_custom_map.py`, `test_verify.py` plus the orchestration scripts — lives in `..\test-suite\`.

This means CC needs to write tests there. But test infrastructure also lives there — golden masters, gate orchestration, integrity harness, linter — and that infrastructure is the *contract* the test suite enforces. Modifying it changes what "passing" means. Adding to it requires deliberate human review.

The rule splits what CC can and cannot do:

### CC MAY

- Add new test files in `..\test-suite\` for behavioural and integration tests
- Add new test files in `tests\contracts\` for AST contract tests (schema drift detection)
- Add new test cases to existing test files (parametrized cases, new test functions)
- Add new fixture files (CSVs, JSON maps, .fin rules) in fixture directories

### CC MUST (when adding tests)

- **Update test counts in EVERY file that displays them.** The count sweep is mandatory, not optional. See `DOCUMENT_MAP.md` "New test added" change scenario for the canonical list. At minimum: `..\test-suite\quick_check.ps1`, `..\test-suite\full_test_suite.ps1`, `..\test-suite\cleanroom_test.ps1`, `..\test-suite\TEST_SUITE.md`, `RELEASE_CHECKLIST.md`, `DOCUMENT_MAP.md`, `finlang_showcase.ps1`, `finlang_showcase_public.ps1`, `README.md`, `CLAUDE.md` (this file's header line). **Showcase scripts and cleanroom were the most-missed during v0.7.7 — check them explicitly even if you think you've got them all.** (`showcase_narration_script.md` is no longer count-swept — historical artifact, see § "Historical artifacts".)

### CC MUST NOT (without explicit human approval)

**Orchestration scripts** (changing these changes what "passing" means):
- Modify `..\test-suite\quick_check.ps1`
- Modify `..\test-suite\full_test_suite.ps1`
- Modify `..\test-suite\cleanroom_test.ps1`
- Modify `..\test-suite\run_test_matrix.ps1`

**Contract-enforcing Python modules** (changing these changes what the tests are checking):
- Modify `..\test-suite\integrity_testv2.py` (foundational — affects every benchmark and release validation)
- Modify `..\test-suite\rulepack_linter.py` (changing it changes what "safe rulepack" means)
- Modify `..\test-suite\validate_sandbox_port.py` (port validation contract)

**Adversarial and regression fixtures** (existing edge cases — adding new ones is fine, modifying existing requires understanding why each was added):
- Modify `..\test-suite\adversarial_tests.ps1`
- Modify any file in `..\test-suite\golden\` (SHA-256 baselines for matrix verification)
- Modify existing truth-fixture contents:
  - `..\test-suite\debit_only.csv`
  - `..\test-suite\eu_cr_dr.csv`
  - `..\test-suite\cp1252_weird.csv`
  - `..\test-suite\pipe_quotes.csv`
  - `..\test-suite\test_us.csv`
  - `..\test-suite\test_uk.csv`
  - `..\test-suite\test_eu.csv`
  - `..\test-suite\demo_corporate_transactions.csv`
  - `..\test-suite\demo_corporate_transactions.fin`

**Structural changes to the test suite**:
- Delete or rename any existing test file
- Restructure the test directory layout (folder moves, subfolder creation, etc)
- Modify `..\test-suite\TEST_SUITE.md` (it's the contract document for the test suite)

**Why named files instead of categories:** agents behave better against explicit filenames than abstract categories. "Don't modify orchestration scripts" is easier to drive a truck through than "don't modify `quick_check.ps1`". The explicit list closes the ambiguity. If a file you're thinking about changing isn't in the list above, check whether it's in the same category as something that is — if yes, surface the question. If no, the file is probably safe to extend (but add it to the MAY list if you do, so future sessions know it's permitted).

The general principle: **CC can extend the test suite, but cannot modify the contract the test suite enforces.** Adding new tests is feature work. Changing what the tests check, or how the gates are organised, is a deliberate review-worthy decision.

### When in doubt, surface

If you are uncertain whether a file or change falls into the MAY or MUST NOT category, **surface the question to the human before proceeding**. The cost of asking is one message. The cost of guessing wrong is a regression that may not be caught until release.

---

## MANDATORY FIRST STEP (every session)

Before any changes:

1. Identify which path applies (A/B/C — see § "Workflow doctrine"). **CC-authored work is always Path B.** If Path B, switch to a feature branch first: `git switch -c claude/<auto-name>`. If Path A (Angus-driven, trivial), main is permitted but the stop rule applies if scope expands.
2. Activate the venv: `cd {workspace}\prod && .\.venv\Scripts\Activate.ps1`
3. Run `cd ..\test-suite && .\quick_check.ps1`
4. Confirm all 9 gates PASS

Only then begin work. If the gates are red on entry, the cause is upstream — surface it, do not start adding to it.

---

## Project Overview

FinLang is a deterministic financial transaction categorisation engine — a Python DSL that processes CSV transactions against human-readable `.fin` rules, producing fully auditable output. Published on PyPI as `finlang` (currently v0.7.7) under AGPLv3 with commercial dual-licensing. Small, clean, due-diligence-friendly codebase. The repository at `..\prod\` is the source of truth for what is published.

---

## Directory Layout (within `prod\`)

```
prod\
├── src/finlang/
│   ├── cli/run_finlang.py       — main CLI entry point
│   ├── engine/finlang_engine.py — rule engine core
│   ├── tools/discover.py        — discovery tool
│   ├── tools/suggest.py         — rule generator
│   ├── tools/verify.py          — post-engine integrity verification
│   ├── utils/resources.py       — package resource loading
│   ├── mapping/bank.map.json    — default header mapping
│   └── rulepacks/               — bundled .fin rulepacks (01–08)
├── tests/                       — pytest tests that ship with the package
│   ├── test_cli_smoke.py        — CLI subprocess smoke tests
│   ├── contracts/               — AST contract tests (schema drift)
│   │   ├── canonical_fields.yaml
│   │   ├── test_dsl_fields.py
│   │   ├── test_engine_input.py
│   │   └── test_engine_output.py
│   └── data/                    — minimal reproducer fixtures
├── docs/                        — user-facing documentation
├── benchmarks/                  — performance harness scripts
├── examples/                    — demo rules and sample data
├── pyproject.toml               — package metadata
├── README.md                    — project README
├── CHANGELOG.md                 — version history
├── DOCUMENT_MAP.md              — authoritative file map and change scenarios
├── CLAUDE.md                    — this file (working contract, tracked in git, single-tree post-consolidation)
└── .venv\                       — editable install lives here
```

The bulk of the test suite lives at `..\test-suite\` (one level up, sibling of `prod\`). That's where new behavioural/integration tests go. See Rule 4 above.

---

## Commands

| Action | Command | Where |
|--------|---------|-------|
| Activate venv | `.\.venv\Scripts\Activate.ps1` | `{workspace}\prod\` |
| Daily gate (must pass 9/9) | `.\quick_check.ps1` | `{workspace}\test-suite\` |
| Single pytest file | `python -m pytest test_rule_interactions.py -v` | `{workspace}\test-suite\` |
| Full pre-release suite | `.\full_test_suite.ps1` | `{workspace}\test-suite\` |
| Run FinLang | `finlang --input <csv> --output <out> --rules <fin> --headless` | anywhere with venv active |
| Check version | `finlang --version` (should show `FinLang 0.7.7`) | anywhere with venv active |

---

## Code Standards

- Python 3.13, no `type: ignore` without justification
- Source code is the source of truth — docs follow the engine, never the reverse
- Zero-regression standard: every change must pass `quick_check` 9/9 before considering it done
- All test scripts anchor to `$PSScriptRoot` — they're path-independent
- Determinism is sacred: no ML, no randomness, no network calls in the engine

---

## Workflow (mandatory for every change)

1. **Write failing test in the appropriate location:**
   - `..\test-suite\` for behavioural and integration tests (where the bulk of the suite lives)
   - `tests\contracts\` for AST contract tests (drift detection between source and schema)
   - **Reminder:** Rule 4 governs what you can and can't touch in the test suite. Re-read it if uncertain. When in doubt, surface.
2. Confirm the test fails
3. Implement the fix or feature
4. Confirm the test passes
5. Review existing tests in affected files — do any assertions need updating to reflect the change? If so, update them with justification.
6. Run `quick_check` 9/9
7. Update docs (per `DOCUMENT_MAP.md` "Common Change Scenarios" table)
8. **Run the count sweep.** New test → update test counts in: `..\test-suite\quick_check.ps1`, `..\test-suite\full_test_suite.ps1`, `..\test-suite\cleanroom_test.ps1`, `..\test-suite\TEST_SUITE.md`, `DOCUMENT_MAP.md`, `RELEASE_CHECKLIST.md`, `finlang_showcase.ps1`, `finlang_showcase_public.ps1`, `README.md`, `CLAUDE.md` (this file's header line). Showcase scripts and cleanroom were consistently missed during v0.7.7 — check them explicitly. **Note:** `showcase_narration_script.md` (in `..\test-suite\`) is a historical artifact from the pre-v0.7.7 demo recording — no longer count-swept, no longer maintained.
9. Run `quick_check` 9/9 again
10. Show the exact files changed and a short summary of why
11. Single commit, staging files explicitly (no `git add .`)

The eleven steps are not aspirational. Skipping them is how regressions ship.

---

## What NOT to Do

Grouped by theme. All three groups apply at all times.

### Scope discipline

- Do NOT refactor for elegance — the code is clean and working. **"While I'm here..." = stop.**
- Do NOT update docs unrelated to the current task. Only update docs directly impacted by the requested change or explicitly listed in Doc Maintenance.
- Do NOT remove historical comments (e.g., "v0.6.4 requirement", "RC1a Polish") — they show engineering history. Only remove if wrong or misleading.
- Do NOT modify golden master hashes without explicit approval. (See Rule 4 for the full list of off-limits items inside `test-suite\`.)
- Do NOT add ML, probabilistic outputs, or network calls to the engine.
- If a change risks regressions outside the stated scope, STOP and explain the risk before modifying code.

### Language discipline

- Do NOT claim "ensures", "guarantees", "certified", or "compliant" in any docs. FinLang targets regulated finance — those words carry legal weight and create exposure.
- Use **"can"** not **"will"** when describing behaviour (e.g., "FinLang can generate..." not "generates...").
- Prefer **positional framing** over absolute claims (e.g., "increasingly relevant under the EU AI Act" not "mandated by the EU AI Act").

### Git / environment discipline

- Do NOT use `git add .` — stage files explicitly.
- Do NOT run `pip install finlang` from PyPI in this venv — use the editable install.
- Do NOT add additional remotes beyond `origin`. The `wip` remote plan was retracted under Process Lock 280426; the augmented pre-push hook now blocks any non-`main`, non-tag push to `origin` (see Rule 6 in CRITICAL SAFETY RULES).
- Do NOT attempt to bypass the pre-push hook.

---

## Task Discipline

- Do not begin the next task unless the current task is complete, tests pass 9/9, and the user has approved proceeding or explicitly requested the next task.
- One task at a time. No scope creep.
- Every multi-step task is reviewable at every step. If you can't show the human what changed and why, you've moved too far.

---

## Doc Maintenance

`DOCUMENT_MAP.md` (in this directory) is the authoritative source for "what files need updating when X changes". Before completing any task, consult its "Common Change Scenarios" table to identify ALL files that need updating. The pattern is:

- **CLI flag changes**: `run_finlang.py`, `cli_reference.md`, `flags.md`, `workflows.md`, `faq.md`, smoke tests
- **Test count/gate changes**: `..\test-suite\TEST_SUITE.md`, `DOCUMENT_MAP.md`, `..\test-suite\quick_check.ps1`, `..\test-suite\full_test_suite.ps1`, `..\test-suite\cleanroom_test.ps1`, `finlang_showcase.ps1`, `finlang_showcase_public.ps1`, `RELEASE_CHECKLIST.md`, `README.md`, `CLAUDE.md` (this file's header line). Showcase scripts and cleanroom are the most-missed — check them explicitly. (`..\test-suite\showcase_narration_script.md` is a historical artifact — not count-swept.)
- **Version bumps**: happen on a `release/v<version>` feature branch, merged to main per `DRAFT-release-promotion-package-v1.md` Phase 4. Not direct on main.

When updating docs, use **"can"** not **"will"**. After any doc update pass, update `DOCUMENT_MAP.md` itself (header date, changed counts).

---

## Reference Docs

**Note on external files:** files outside `{workspace}\` (Drive, other workspaces) are not directly readable from this session. If a reference below points at such a file and you need its contents, ask the human to paste it. Do not silently guess based on the filename.

**In this directory (`prod\`):**
- `DOCUMENT_MAP.md` — authoritative file map and change scenarios
- `CHANGELOG.md` — historical record of what shipped when
- `README.md`, `pyproject.toml` — standard package files
- `CLAUDE.md` — this file (working contract, tracked in git)
- `RELEASE_CHECKLIST.md` — manual release procedure (gitignored, internal-only per Rule 6 of folder-structure-package)

**Workspace level (`{workspace}\`):**
- `..\strategy-backlog\BACKLOG.md` — tactical project backlog (Now / Next / Later / Done). The canonical source for in-flight and queued work.
- `..\strategy-backlog\ROADMAP.md` — living strategic narrative.
- `..\strategy-backlog\SANDBOX_PARKING_LOT_ARCHIVED.md` — historical engineering backlog from the v0.7.7 release cycle, archived 21 April 2026.
- `..\PROJECT_FOLDER_STRUCTURE.md` — single-tree folder layout + FinLang-specific notes
- `..\test-suite\TEST_SUITE.md` — test suite documentation
- `..\test-suite\release_preflight.ps1` — release gate (8-condition publish safety; build pending Phase 3 follow-on)
- `..\CLAUDE.md` — workspace visitor map (read this for broader workspace context)
- `..\ANGUS_OS_CANDIDATES.md` — curated list of FinLang process & discipline files for angus-os scaffolding
- `..\ANGUS_OS_ENGINEERING_CANDIDATES.md` — curated list of FinLang engineering patterns for angus-os scaffolding

**Inherited standards (in `(private angus-os workspace) engineering\`):**
- `DRAFT-folder-structure-package-v3.md` — single-tree pattern this project implements
- `DRAFT-branch-workflow-package-v1.md` — hooks, dual-remote, four-layer control hierarchy
- `DRAFT-release-gate-package-v1.md` — release gate spec (8 conditions)
- `DRAFT-release-promotion-package-v1.md` — release flow phase-by-phase

**Strategic docs — workspace-readable since 21 April 2026 reorganisation:**
- `..\strategy-backlog\ROADMAP.md` — living strategic narrative
- `..\strategy-backlog\ROADMAP-detailed-110426.md` — frozen detailed roadmap snapshot
- `..\strategy-backlog\SOL-040_reconcile_specification.md` — current focus, full spec
- `..\strategy-backlog\archive\SOLUTIONS_ARCHIVED_*.md` — archived solution outlines (`SOL-###`)
- `..\strategy-backlog\archive\` — historical strategic docs

**Historical artifacts (workspace-readable, no longer maintained):**
- `..\test-suite\showcase_narration_script.md` — voiceover lines for the pre-v0.7.7 demo recording. The demo is recorded; the script reflects that prior state. No longer count-swept, no longer updated.

---

## Current focus

**Next feature to build: `--reconcile` (SOL-040)**

The full specification lives at `..\strategy-backlog\SOL-040_reconcile_specification.md` (workspace-readable since 21 April 2026 reorganisation; previously Drive-hosted). Summary:

- Independent ML validation layer for FinLang
- Compares FinLang's deterministic output against an external ML system row by row
- Produces full audit reasoning for every disagreement
- Requires `--audit --audit-mode full` (errors if missing — Grok's design point)
- Can run alongside `--verify`; both can be active in the same invocation
- Exit code 3 if either `--verify` or `--reconcile` fails (consistent with v0.7.7 verify exit code)
- Estimated ~300 lines in `finlang/tools/reconcile.py` + ~30–40 lines in `run_finlang.py`
- Estimated test suite growth: ~118 → ~130 tests, ~9 → ~10 gates

**Test placement and gate ordering for SOL-040 specifically:**

- `test_reconcile.py` goes in `..\test-suite\`, not the local `tests\` directory
- Gate ordering is **chronological** (new gates appended). The current Gate 9 is `rulepack_linter.py` and stays as Gate 9. `test_reconcile.py` becomes **Gate 10**, appended after the linter.
- Adding Gate 10 to `quick_check.ps1` is one of the orchestration changes that requires explicit human approval per Rule 4 — surface the gate addition as a deliberate step, not a side-effect of dropping the test file.
- **Count sweep for SOL-040 covers TWO separate string types**: test counts (118 → ~130) AND gate counts (9 → 10). These are distinct strings in most files and are easy to miss because docs often conflate them in copy. When sweeping for SOL-040, grep for both `118` and `9 gates` (and any equivalent variants like `9/9`) — fixing one without the other is a partial sweep and will leave the system inconsistent.

Read the SOL-040 spec in full before starting (it's at `..\strategy-backlog\SOL-040_reconcile_specification.md` — directly accessible from this session).

---

## After the current task

Once `--reconcile` ships, the next sources of work are:

1. **`..\strategy-backlog\BACKLOG.md`** — canonical tactical backlog (Now / Next / Later / Done / Won't build). Read directly to see current state — specific item names evolve.
2. **`..\strategy-backlog\ROADMAP.md`** — living strategic narrative.
3. **`..\strategy-backlog\ROADMAP-detailed-110426.md`** — frozen detailed roadmap snapshot for cross-reference.
4. **`..\strategy-backlog\SANDBOX_PARKING_LOT_ARCHIVED.md`** — historical engineering backlog from the v0.7.7 release cycle.

Do not start on these without explicit human direction. The BACKLOG is the source of next-task choices, not a self-serve list.

---

## How releases work (post-consolidation)

**Releases are Path C work.** Routine code work uses Path B (CC-driven, branched); doc/typo/config tweaks use Path A (direct main). See § "Workflow doctrine" for the path model. The Path C release flow is described below.

The pre-consolidation post-release dev refresh procedure is retired (no dev folder to refresh). Releases now follow the branch-based flow per `DRAFT-release-promotion-package-v1.md`:

1. Feature branch → review → merge to main
2. Version bump on `release/v<version>` branch → merge to main → tag
3. Validation against tagged HEAD: `quick_check`, `full_test_suite`, `python -m build`, `cleanroom_local`
4. Release gate (`..\test-suite\release_preflight.ps1`) — 8 conditions, owns `twine upload`
5. Post-publish smoke: `cleanroom_test.ps1` (rename to `cleanroom_pypi.ps1` is planned as part of Phase 3 follow-on, paired with new `cleanroom_local.ps1` for pre-publish wheel validation)
6. Snapshot internal files to `..\scratch\internal_snapshots\v<version>\`

What this means for you:
- Branch discipline replaces folder discipline. `prod/` is the working tree AND the release source.
- `..\scratch\` is still throwaway — don't accumulate things you need to survive a release. Internal snapshots are the exception (Rule 6 corollary).
- `..\scratch\internal_snapshots\v<version>\` preserves gitignored internal files (RELEASE_CHECKLIST.md) at release boundaries — relies on external workspace backup for recovery.
- This file (`CLAUDE.md`) is tracked in git, so its history survives natively.

---

## Last thing

This file is the contract for your behaviour in this folder. If anything in it is wrong, surfaced as wrong, or contradicted by another file you've been given, **stop and ask the human before proceeding**. Don't try to reconcile conflicts in your own head — the human is the tiebreaker.

*Last updated: 28 April 2026 (Process Lock 280426 — solo-maintainer trunk workflow with Path A/B/C model added; Layer 4 retracted, wip remote plan dropped, pre-commit permissive, pre-push now blocks non-main/non-tag pushes to origin. Baseline v0.7.7, 118 tests across 9 gates; release gate build pending.)*
