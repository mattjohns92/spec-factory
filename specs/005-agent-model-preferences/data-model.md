# Data Model: Per-Agent Model Preferences

## Current model (Option B)

Local file `.factory/model-preferences.json`, gitignored, user-owned:

```json
{"version": 1, "preset": "budget", "tiers": {"budget": null, "balanced": null, "quality": null}, "overrides": {}}
```

- `preset`: `budget` | `balanced` | `quality-first`.
- `tiers`: user-supplied model ID or `null` (unresolved) per tier.
- `overrides`: optional role to model ID, for `architect`, `engineer`, `qa-engineer`, `code-reviewer` only.
- Preset maps: budget = {architect, engineer, code-reviewer: balanced; qa-engineer: budget}; balanced = all balanced; quality-first = all quality.
- Resolution: override, else preset tier ID, else unresolved. Invalid version, preset, tier, role, or ID is a configuration error.
- Delegation record (runtime-owned, read-only for this feature): `subagent.started`/`subagent.completed` events in `events.jsonl`, joined by `toolCallId`.

## Historical (superseded) design

**Status**: Historical proposed design only. The automatic global personal-agent approach is blocked and has not been implemented; do not treat these structures as current functionality.

## User configuration

Per checkout, stored in a user-owned configuration directory under `<user-local configuration directory>`, where the key is a stable hash of the resolved checkout root, not a secret. The helper explains the resolved path and supports explicitly selecting a config path for isolated testing. No credentials or price data are stored.

- `version`: schema version for explicit validation.
- `checkout_root`: canonical source checkout identity, used to identify cross-checkout conflicts.
- `preset`: one of `budget`, `balanced`, `quality-first`; defaults to `budget`.
- `tiers`: user-supplied `budget`, `balanced`, `quality` model IDs or unresolved values.
- `overrides`: optional map from each of the five stable profile IDs to a user-supplied model ID.

The repository-provided preset maps are defined in the [plan](plan.md#user-choice-and-native-application). Role resolution is override, otherwise selected preset's tier; clearing an override restores that mapping. A missing, empty, malformed or unsupported value never becomes a success-shaped result.

## Generated personal profile and provenance

- Source: one complete `.github/agents/<id>.agent.md` profile in the current checkout.
- Target: `<Copilot user/session directory>`, with the same ID and complete source metadata/body, except the selected `model` value.
- Provenance: per-checkout record of source and exact target digests, target paths and originating checkout, stored separately from agent frontmatter. No provenance record alone authorizes overwrite: target path, exact content digest, and source ownership must all agree.
- State: **unresolved**, **ready**, **applied**, **drifted**, **conflict**, or **error**. State describes local file evidence, not runtime selection or permission enforcement.

Before a refresh or removal, compare the actual source and target with the provenance record. A changed target, foreign origin, unknown existing target, link, malformed file, or unsupported source causes refusal with actionable reconciliation. If a source changes, report drift and require an explicit refresh of still-owned unchanged targets; never silently refresh. A stale native profile can still be selected outside this helper, so the warning must not be described as enforcement.

## Selection evidence

For each role distinguish configured requested ID, personal profile file state, runtime, observable actual ID (or `not verified`), and source of evidence. A native fallback is reported only if observed. Read-only reviewer declaration, separate execution context and effective tool enforcement are distinct evidence items.
