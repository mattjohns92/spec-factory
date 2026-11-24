# Quickstart: Per-Agent Model Preferences

## Use it (Option B, current)

Factory Lead's model stays your Chat model picker choice. The four specialists get a model through the native `task` `model` argument, which Factory Lead fills from `python scripts/specialist_models.py resolve <role>` before every delegation. Run from the repository root; settings live in the gitignored `.factory/model-preferences.json`.

```text
python scripts/specialist_models.py status                       # preset, tiers, overrides, resolved model per role
python scripts/specialist_models.py set-tier budget MODEL_ID      # likewise balanced, quality (IDs the task tool accepts)
python scripts/specialist_models.py set-preset balanced           # budget (default) | balanced | quality-first
python scripts/specialist_models.py set-override engineer MODEL_ID
python scripts/specialist_models.py clear-override engineer
python scripts/specialist_models.py report                        # requested vs actual model, tokens, duration per delegation
```

- Budget: QA Engineer uses the `budget` tier, the other three the `balanced` tier. Balanced: all `balanced`. Quality-first: all `quality`. A preset change applies to the next delegation.
- If a role is unresolved, Factory Lead asks you instead of guessing or inheriting silently. It recommends, but never silently applies, a stronger model.
- `report` reads the newest session `events.jsonl` (`--events PATH` for another). A delegation's completed event can appear a few seconds after the task returns; re-run if it shows `not available`.
- Limits: tokens and duration only (no price, no `assistant.usage`); the runtime rejects model IDs it does not offer; a cheaper model can cost more tokens overall (see [research.md](research.md)).
- Tests: `$env:PYTHONPATH="src"; python -m unittest discover -s tests -t .` (without `src` on the path, six existing modules fail to import; unrelated to this feature).

## Historical (superseded) validation notes

**BLOCKED (historical)**: The text below predates Option B and is retained as a record only. The global personal-agent-copy approach is rejected (see [research.md](research.md#final-investigation-decision-2026-11-21-earlier-record)). The checks below are historical proposals, not current instructions.

Current fallback: select an available model manually in the native Chat model picker. This is a per-conversation action, not automated per-agent presets or proof of actual model execution.

## Prerequisites

- Owner approves [plan.md](plan.md); use one ordinary checkout and preserve unrelated changes.
- Python 3.11+ and the repository's existing PyYAML validation dependency.
- Use a temporary home and fixture checkout for automated checks; do not replace real personal profiles during tests.
- Any hosted session or live delegation test needs separate run-specific owner authorization. No CLI result substitutes for a VS Code Chat result.
- Before helper implementation, perform the owner-authorized disposable Chat precedence test described in [plan.md](plan.md#compatibility-first-gate), after separate explicit confirmation to create the personal agent. If precedence fails or remains unverified, stop before building the helper.

## Automated and static checks

1. Run `python -m unittest tests.unit.test_specialist_models tests.unit.test_agent_profiles` after implementation; report the exact command and outcome.
2. In an isolated fixture, verify first-run instructions guide users to their available model IDs and unresolved choices are never reported as applied. Set three synthetic model IDs, select each preset, and verify all five generated personal profiles request the expected native `model`. Budget maps Factory Lead and QA Engineer to Budget, and the other three roles to Balanced. Override each role in turn, switch presets, clear the override, and confirm correct reversion and persistence.
3. Compare every generated role's complete metadata except `model` and exact body against its repository source. Confirm Code Reviewer's strict flag and exactly `read`, `grep`, `glob`; test unknown fields, malformed profiles, symlinks, conflicts, target/source drift, different checkouts and partial I/O failures. No unowned file may be overwritten.
4. Test unresolved and unavailable-by-runtime guidance, but do not call offline fixture IDs verified available models. Confirm statuses distinguish requested, applied and actual/unknown.

## Authorized interactive checks

If separately authorized, document exact versions and whether the Copilot harness is selected; check native profile discovery, source identity, model selection, parent/session versus delegated preference, unavailable model guidance, and actual model visibility independently in VS Code Chat and CLI. Exercise the requested specialist handoffs, then review the actual diff with the approved requirements and plan. Capture runtime-visible evidence of separate task execution and reviewer effective permissions independently. Label unobservable results NOT VERIFIED; if reviewer read-only enforcement is not evidenced, report self-review rather than independent review.

VS Code's documentation states `strict-tools-list` is not forwarded in SDK agent conversion. Preserving and statically validating that declaration does not prove effective enforcement.

## Rollback

Use the helper's documented ownership checks and explicit user action to remove only generated unchanged personal files, or manually inspect and restore them. Preserve user-modified files and unrelated personal agents. Removing the per-checkout preference file requires deliberate user action; stale personal profiles otherwise continue to shadow repository agents. Do not reset the checkout or change security infrastructure.
