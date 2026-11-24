# Research: Software Factory Setup & Readiness Check

## Observed facts (inspected 2026-11-21)

- `factory doctor` (`src/software_factory/preflight.py`) requires `.factory/policy.json` and exact versions Specify 1.0.6, Copilot 1.0.114, workflow 1.0.2; the policy file is gitignored and absent, so doctor returns BLOCKED before any other check. Doctor is unchanged by this feature.
- `.github/hooks/factory-policy.json` declares a `preToolUse` PowerShell hook. `scripts/factory_pre_tool_use.ps1` denies every tool request when `FACTORY_POLICY_PATH` is unset or not an existing file (fail closed) and requires `FACTORY_REPOSITORY_ROOT`.
- `.github/copilot/settings.local.json` (gitignored) sets `disableAllHooks: true`. Its effect in a live session is not established by this feature.
- Neither environment variable is set in the current session.
- Installed: Specify 1.0.6, Copilot CLI 1.0.114 (observed earlier). `copilot` resolves on PATH as `copilot.ps1`, so presence detection must consider `.ps1`. `.specify/extensions.yml` does not exist.
- Feature 003 exposes `validate_profiles(repository_root)` returning findings; the script needs PyYAML (the `validation` group).

## Decisions

1. **Standalone script, not `factory doctor` or `src/`** (owner decision Q1). Rationale: avoids coupling to out-of-scope infrastructure. Alternative rejected: extending doctor.
2. **Tri-state version classification** (owner decision Q2) against an in-script table. Rationale: exact equality is not required, and newer is not assumed compatible. The repository documents no incompatible versions, so that list starts empty. Alternative rejected: pin equality.
3. **Reuse Feature 003 via import.** Rationale: no duplicated rules. Fallback FAIL with remedy if PyYAML is missing. Alternative rejected: copying the rules.
4. **Static hook analysis only.** Rationale: executing the hook or a live session would risk side effects and is prohibited. Only existence, structure, local-disable flag, and referenced environment variable names are examined.
5. **Verdict vocabulary**: "not ready" / "ready with limitations"; never plain "ready" (FR-015), because authentication, live dispatch, and sandbox enforcement are always NOT VERIFIED.
6. **Injected runner and environment** for testability and to guarantee tests never start Copilot or use the network.
7. **No specialist delegated for planning.** The design is one small script; the Architect would have repeated the same repository reading without adding independent expertise. Recorded per the minimal-specialists principle.

## Open Items

- Owner decisions (2026-11-21): Copilot is never executed (presence only, version NOT VERIFIED); active-hook-without-policy is NOT READY scoped to the checked environment; version table kept with empty incompatible list.
