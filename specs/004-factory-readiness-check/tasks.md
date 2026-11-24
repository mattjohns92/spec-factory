---
description: "Task list for the Software Factory Setup & Readiness Check"
---

# Tasks: Software Factory Setup & Readiness Check

**Input**: `specs/004-factory-readiness-check/` (`spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/cli.md`, `quickstart.md`)

**Authorization**: The owner approved the specification and plan as amended on 2026-11-21 and authorized implementation. Implement only this scope. Do not modify the factory CLI/runner (`src/`), `.github/hooks/`, `scripts/factory_pre_tool_use.ps1`, `.factory/`, security policies, sandbox, `.specify/` workflow assets, `scripts/validate_specialist_profiles.py`, `pyproject.toml`, or `uv.lock`. Preserve unrelated uncommitted working-tree changes. Do not run Feature 002 tasks T026/T028, deploy, push, or merge. The checker never executes `copilot`, uses the network, or starts a hosted session.

**Tests**: Focused `unittest` cases are required (FR-012), using an injected command runner and environment, with no Copilot or network use.

## Phase 1: Tests (US1-US3)

- [x] T001 [P] Add `tests/unit/test_readiness_check.py` covering: ready-with-limitations case; never a plain "ready"; each missing Spec Kit file; invalid/missing feature pointer; integration-status findings; invalid profile and reviewer tool list (via the Feature 003 rules); missing `factory-handoff` skill; missing `specify` executable; `specify` version supported / known-incompatible / older / newer / unparseable / timeout / nonzero; `copilot` missing (FAIL), present (NOT VERIFIED, never executed); hook declared with malformed JSON or missing script (FAIL); active hook with unavailable policy (FAIL, finding scoped to the current shell/launching environment); hook locally disabled (NOT VERIFIED); policy available (NOT VERIFIED); missing `.factory/policy.json` alone not a FAIL; Authentication/live-dispatch/sandbox always NOT VERIFIED; multiple simultaneous failures reported together; exit codes 0/1/2; fixture tree byte-for-byte unchanged after a run; no environment values printed; the injected runner is the only subprocess path.

## Phase 2: Implementation

- [x] T002 Implement `scripts/check_factory_readiness.py` per `plan.md` and `contracts/cli.md`: stdlib only; imports `validate_specialist_profiles` for profile rules (FAIL with remedy `uv sync --group validation` if PyYAML is unavailable); `CheckResult`/report model; PATH search for `copilot` that also considers `.ps1`; fixed `specify --version` and `specify integration status --json` queries (list args, `shell=False`, 15 s timeout); static hook analysis; verdict and exit codes; `--root` option.

## Phase 3: Verification

- [x] T003 QA: run `uv run --group validation python -m unittest tests.unit.test_readiness_check -v`, the existing `tests.unit.test_agent_profiles` and the wider unit suite, and `uv run --group validation python scripts/check_factory_readiness.py` against the real repository; record exact outcomes, and confirm via `git status`/`git diff` that only the two new files (plus this feature's specs) changed and pre-existing modifications are intact.
- [x] T004 Code Review: read-only review of the actual Git diff and new files against the approved spec and plan; findings only. **Completed as self-review; independence unverified** (see Acceptance Record).
- [x] T005 Factory Lead: reconcile findings, apply or route corrections within scope, re-run affected checks, and report delivery evidence.

## Dependencies & Execution Order

T001 precedes T002 (tests first); T003 depends on T001-T002; T004 depends on T003; T005 depends on T004.

## Acceptance Record

**Status**: Owner-accepted on 2026-11-21 **with an explicit exception**. Not recorded as independently reviewed.

**Review exception**: The owner waived the independently evidenced Code Reviewer requirement for Feature 004 only. The two Code Reviewer passes were delegated through the task tool, but runtime-visible evidence of a distinct context and of the reviewer's effective read-only tool restriction was not available. They are recorded as **self-review, independence unverified**. This waiver does not apply to Feature 002, whose independent-review criteria (T008, T010, T011, T015, T017) remain outstanding, nor to any future feature.

**Evidence (actual)**:
- Engineer ×3 task-tool delegations (implementation; review-finding fixes; PyYAML handling fixes). QA Engineer ×1 and Code Reviewer ×2 task-tool delegations. No runtime evidence of separate contexts was inspected.
- Final `uv run --group validation python -m unittest discover -s tests/unit -t .`: 115 tests, OK (readiness module: 52 tests).
- Real-repository `scripts/check_factory_readiness.py`: verdict "ready with limitations", exit 0; Specify 1.0.6 PASS; Copilot present, version NOT VERIFIED (never executed); hooks locally disabled, NOT VERIFIED; `.factory/policy.json` INFO; authentication, live dispatch and sandbox enforcement NOT VERIFIED.
- `git status`: only `scripts/check_factory_readiness.py`, `tests/unit/test_readiness_check.py` and `specs/004-factory-readiness-check/` added; pre-existing uncommitted changes untouched. Nothing committed, pushed or merged.

**Not verified (not claimed as passed)**: independent review; Copilot CLI version; effective hook/permission behavior; authentication; live dispatch; sandbox enforcement; FR-006 and FR-013 were not reviewed in detail by QA (QA reported them unchecked), and Code Reviewer round 1 read the documents only in part.

**Technical debt (minor findings, accepted unfixed)**:
- Version token with a `v` prefix is NOT VERIFIED, never PASS; document this.
- `specify.ps1`-only installs are found on PATH but cannot run with `shell=False` (reports FAIL "could not run").
- Possible `UnicodeEncodeError` printing non-ASCII hook paths on a cp1252 console.
- Missing tests: integration-status timeout, symlink/junction containment, `feature_directory` of `.`, unquoted script paths with spaces; no test checks real `specify integration status --json` output shape beyond the live run.
- `git-state` is informational only and does not report a dirty working tree.
- Validator `_frontmatter` private helper is used for the skill file check (coupling to Feature 003 internals).
- `COMPATIBILITY["copilot"]` is unused because Copilot is never executed.
- PATH lookup does not honor `PATHEXT`; injected PATH mapping is case-sensitive.
