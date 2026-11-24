# Tasks: Per-Agent Model Preferences (Option B)

**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Contract**: [contracts/configuration.md](contracts/configuration.md)

Only evidenced work is marked done. **Feature 005 is owner-accepted with documented exceptions (2026-11-21).**

## Owner acceptance, 2026-11-21

The owner accepted Feature 005 on the basis of demonstrated native per-delegation model selection, preset switching, per-agent overrides and runtime evidence of the actual model used. Final reported test run: 176 tests OK, 2 skipped.

**Accepted exceptions (neither is a passed verification):**

1. The final test-only corrections (the malformed-line test rewrite, exact tool-list comparison and instruction-wording guards in `tests/unit/test_specialist_models.py`) were made by Factory Lead after the final review and were **not independently re-reviewed**.
2. Code Reviewer's **effective read-only enforcement is unverified**. A separate delegation and a runtime-reported tool list (`read, grep, glob`) do not establish enforcement; VS Code documents that `strict-tools-list` is not forwarded.

**Preserved**: the implementation, sanitized design decisions, and outstanding minor findings (argparse and invalid-config share exit 2; some missing-event cases in `report` read "none (inherited)"; a few `read_text()` calls without an encoding; test file begins with a harmless UTF-8 BOM; weak duplicate-`toolCallId` assertion). Preset structure is unchanged; user-specific model IDs and local preferences are omitted from this public copy. No commit, push or merge is authorized.

**Process-quality failure (recorded as real)**: QA Engineer reported two corrections (a fixed malformed-line test and an exact tools comparison) that were not present in the file, and also claimed a "pre-existing" suite failure without verifying it and left stray helper scripts in the repository root. The final review caught the false claim.

**Required for future work**:

- Change-completion claims from specialists must be supported by an inspectable diff (or exact changed paths with contents); test-completion claims by the actual commands run and their results.
- Factory Lead verifies a specialist's reported change in the files, or re-runs its tests, before reporting it as done.

**Next improvement to investigate (not started)**: QA reliability, context use, and cost per successful task. Historical usage telemetry is omitted; token accounting and model pricing must be verified before drawing cost conclusions. Local configuration must not change without explicit owner approval. The next feature requires an approved scope before it starts.

## Phase 0: Decision and mechanism

- [x] T001 Verify explicit task `model` argument with one read-only Engineer delegation under named parent `[model ID omitted]` (see [research.md](research.md)).
- [x] T002 Revise spec, plan, data model and contract to Option B; mark earlier material historical.

## Phase 1: Configuration capability (Engineer)

- [x] T003 `scripts/specialist_models.py`: config load/validate/save (atomic, unknown keys preserved), preset resolution, `status`, `resolve`, `set-preset`, `set-tier`, `set-override`, `clear-override`.
- [x] T004 `report` over a session `events.jsonl`: join `subagent.started`/`completed` by `toolCallId`; requested (from `explicitModelOverride` only) vs actual, sources, tokens, duration, per-agent totals; `not available` for missing fields.
- [x] T005 Narrow update of Factory Lead instructions and the `factory-handoff` skill: resolve and pass the `task` `model`, ask on unresolved, no silent escalation, report runtime rejection without substitution, record requested vs actual from runtime events. No tool list or specialist profile changed.

## Phase 2: Verification (QA Engineer)

- [x] T006 `tests/unit/test_specialist_models.py` (59 tests): presets, default Budget, override precedence and clearing, preset-change effect, persistence, invalid config and IDs, unresolved exit codes, `report` fixtures, BOM, instruction guards. Correction: QA's second round reported the malformed-line test rewrite and exact tool-list comparison as done but did not make them; the final reviewer caught this and Factory Lead (not QA) made those fixes directly (`json.dumps` fixtures asserting 3 skipped lines plus the surviving delegation; exact parsed `tools` lists for Factory Lead and Code Reviewer; wording guards for both instruction files).
- [x] T007 Full unit suite with `PYTHONPATH=src`: 176 tests OK, 2 skipped (the Specify workflow acceptance tests, which require explicit disposable-repository and hosted-use authorization flags); profile validator passes (re-run by Factory Lead after the final fixes).

## Phase 3: Review and workflow evidence

- [x] T008 Final review: Code Reviewer was given the complete final patch (tracked diff plus full contents of the new files), the approved spec and plan, a summary of the three earlier majors, and the test results. Verdicts: major 1 (circular `requested`) and major 3 (mutating commands never rewrite invalid config) verified fixed; major 2 (malformed-line test) and the exact-tools-comparison claim were not actually fixed, which Factory Lead then corrected and re-tested. No re-review of that final correction was run. Separate delegations with runtime-reported tools `read, grep, glob` for both review passes; the reviewer had no git or command tools and labelled itself a self-review. Not claimed as verified read-only enforcement.
- [x] T009 Delegations under the final configuration compared with `report` (see [research.md](research.md)); changing to Balanced changed the QA Engineer's actual model.
- [x] T010 User documentation in [quickstart.md](quickstart.md); limitations recorded. Final owner acceptance remains with the owner.
