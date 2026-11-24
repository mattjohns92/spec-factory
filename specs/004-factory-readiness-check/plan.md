# Implementation Plan: Software Factory Setup & Readiness Check

**Branch**: Spec Kit feature identifier `004-factory-readiness-check` (no Git branch created) | **Date**: 2026-11-21 | **Spec**: [spec.md](spec.md)

**Input**: Owner-approved (as amended, 2026-11-21) specification at `specs/004-factory-readiness-check/spec.md`.

## Summary

Add a standalone, read-only maintenance script `scripts/check_factory_readiness.py` that evaluates a checkout for interactive Spec Kit and specialist-team use. It runs independent checks (tools and versions, Spec Kit configuration, specialist profiles via the Feature 003 validator, interactive hook readiness), aggregates results as PASS / FAIL / NOT VERIFIED with expectation, finding and next step, and returns a verdict of "not ready" (nonzero) or "ready with limitations" (zero). It never modifies files, uses the network, starts a Copilot session, or touches `factory doctor`, the CLI, runner, policy, hook, or sandbox.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Standard library only for the new script. It imports the existing `scripts/validate_specialist_profiles.py`, which needs PyYAML from the existing `validation` dependency group. If PyYAML is unavailable the profile check reports FAIL with remedy `uv sync --group validation`; no new dependency is added and `pyproject.toml`/`uv.lock` are unchanged.

**Storage**: N/A; reads files only.

**Testing**: `unittest` in `tests/unit/test_readiness_check.py` using temporary fixture checkouts, an injected command runner, and an injected environment mapping.

**Target Platform**: Local Windows checkout; portable Python.

**Project Type**: Repository maintenance CLI script (mirrors Feature 003).

**Performance Goals**: Local run bounded by at most two short subprocess queries, each with a 15 s timeout.

**Constraints**: Read-only. No network, no Copilot process execution (including `copilot --version`), no Copilot session, no factory CLI import or invocation, no writes. Subprocess use limited to fixed, argument-list, `shell=False` local queries (`specify --version`, `specify integration status --json`). No secrets or environment values printed. Do not change `src/`, `.github/hooks/`, `scripts/factory_pre_tool_use.ps1`, `.factory/`, `.specify/` assets, or `validate_specialist_profiles.py`.

**Scale/Scope**: One script, one test module, a documented compatibility table, a handful of checks.

## Design

### Checks (each returns a `CheckResult`)

| Id | Verifies | Outcomes |
| --- | --- | --- |
| `tool-specify` | Executable on PATH; `specify --version` parsed and classified against the compatibility table | Missing executable, unparseable output, or nonzero/timeout: FAIL. Version in `incompatible`: FAIL. In `supported`: PASS. Any other parseable version (older or newer): NOT VERIFIED + warning (never "compatible") |
| `tool-copilot` | Executable presence only (PATH search including `.ps1`, since Copilot may be installed as `copilot.ps1`). The checker never executes `copilot` (owner decision: it may perform a network lookup) and no reliable local version metadata is read | Missing: FAIL. Present: NOT VERIFIED (version compatibility not checked; documented supported 1.0.114) |
| `speckit-config` | `.specify/memory/constitution.md`, spec/plan/tasks templates, `.specify/feature.json` points at an existing directory, `specify integration status --json` shows Copilot registered with no managed-file findings, `.specify/workflows/speckit/workflow.yml` present | Missing or invalid item: FAIL with path |
| `specialist-profiles` | Reuse `validate_profiles()` from Feature 003; plus `.github/skills/factory-handoff/SKILL.md` present with non-empty `name`/`description` frontmatter | Findings: FAIL, one line each |
| `interactive-hooks` | See hook logic below | PASS / FAIL (blocking) / NOT VERIFIED |
| `runner-policy` | `.factory/policy.json` presence | Informational only; never FAIL (FR-009) |
| `git-state` | Git repository and dirty/clean | Informational only |
| `unverifiable` | Authentication, live dispatch, effective sandbox enforcement | Always NOT VERIFIED |

Compatibility table (a constant in the script, documented in research): `supported` = Specify 1.0.6, Copilot 1.0.114; `incompatible` = empty, since the repository documents no known-incompatible versions. Versions older or newer than supported are both "compatibility not established" and so NOT VERIFIED, never PASS.

### Interactive hook readiness logic (read-only, static)

1. Read `.github/hooks/*.json`. None declared: PASS.
2. Malformed JSON, missing `hooks` structure, or a referenced script path that does not exist: FAIL (blocking, certain defect).
3. Read the gitignored `.github/copilot/settings.local.json` if present. `disableAllHooks: true`: NOT VERIFIED ("hooks declared but locally disabled; whether Copilot honors this cannot be established without a live session").
4. Otherwise the hook is presumed active. If the referenced script text requires `FACTORY_POLICY_PATH`/`FACTORY_REPOSITORY_ROOT` and the checker's environment does not provide a policy path to an existing file: FAIL ("not ready"). The finding states that this applies to the current shell/launching environment and does not assume other Copilot environments are configured identically.
5. Policy path available: NOT VERIFIED (preconditions met; effective permission decisions need a live session).

Every non-FAIL hook outcome keeps the overall verdict at "ready with limitations" (FR-015). The check inspects script text only by searching for the two environment variable names; it never executes the hook script or reads policy contents beyond existence.

### Verdict and exit status

- Any FAIL: "not ready", exit 1.
- No FAIL: "ready with limitations" (always, since authentication/dispatch/sandbox are NOT VERIFIED), exit 0. NOT VERIFIED items and warnings never change the exit status.
- Invalid `--root`: usage error, exit 2.

### Output

One line per check: `[PASS|FAIL|NOT VERIFIED|INFO] id: finding`. Each FAIL and NOT VERIFIED additionally prints `expected:` and `next step:` lines. Final line: verdict and the limitation list. Paths are repository-relative; environment values are never printed. See [contracts/cli.md](contracts/cli.md).

## Constitution Check

The constitution remains a draft pending owner ratification; this plan applies its constraints without ratifying or amending it.

| Principle | Gate | Decision |
| --- | --- | --- |
| I. Spec Kit Foundation | PASS | Uses the existing Spec Kit artifacts; no parallel tracker or workflow. |
| II. Owner Authority | PASS | Spec approved as amended; this plan is submitted for approval before tasks or implementation. |
| III. Roles and Delegation | PASS | Smallest set; no specialist was used for planning (see research). Implementation may use Engineer then Code Reviewer, reported as evidenced. |
| IV. Evidence-Based Quality | PASS | Focused unit tests per failure category; real command results reported; unknowns reported NOT VERIFIED. |
| V. Security and Permissions | PASS | Read-only, fixed local queries, no network or credentials, hooks/policy/sandbox untouched. |
| VI. Simplicity | PASS | One script, one test module, no new dependency or CLI integration. |
| VII. Self-Improvement | PASS | No change to factory rules, gates, permissions, or workflows. |
| VIII. Traceability | PASS | Explicit verdict, limitations list, and documented quickstart. |

Post-design: PASS.

## Project Structure

### Documentation

```text
specs/004-factory-readiness-check/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/cli.md
├── checklists/requirements.md
└── tasks.md        # generated only after plan approval
```

### Source and Tests

```text
scripts/check_factory_readiness.py          # new
tests/unit/test_readiness_check.py          # new
scripts/validate_specialist_profiles.py     # read-only reuse, unchanged
```

**Structure Decision**: Mirror Feature 003: a standalone script under `scripts/` with `unittest` coverage under `tests/unit/`. No package module, since placing it in `src/software_factory/` would couple it to the factory CLI infrastructure that is out of scope.

## Test Plan (maps to FR-012, SC-001 to SC-008)

Ready case; each missing Spec Kit file; invalid feature pointer; missing/invalid profile and reviewer tool list (reusing 003 rules); missing executable; supported / known-incompatible / newer / older / unparseable versions; hook declared with malformed JSON or missing script; hook active with missing policy env (FAIL); hook locally disabled (NOT VERIFIED); policy env present (NOT VERIFIED); missing `.factory/policy.json` alone not a FAIL; verdict never plain "ready"; multiple simultaneous failures reported together; timeout/nonzero command handled; fixture tree unchanged byte-for-byte after a run; the injected runner is the only subprocess path (no network/Copilot session). Final verification also runs the script against the real repository and the existing test suite for the touched area.

## Owner Decisions on Plan Risks (2026-11-21)

1. **Copilot**: never executed; presence only, version NOT VERIFIED (no reliable local version metadata).
2. **Active hook with unavailable policy**: FAIL / "not ready", scoped explicitly to the current shell/launching environment. Locally disabled hooks or undeterminable enforcement: NOT VERIFIED.
3. **Versions**: documented supported set kept; known-incompatible list initially empty; unknown older or newer versions NOT VERIFIED; newer is never assumed compatible.
4. The working tree has uncommitted changes to hook/policy/profile files from earlier work; the checker reads them as they are and they must be preserved.
