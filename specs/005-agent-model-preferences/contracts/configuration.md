# Configuration and User Interaction Contract

**Status**: Current contract (Option B, 2026-11-21) is the first section. The "Historical" section is superseded and retained for the record only.

## Current contract: `scripts/specialist_models.py`

Roles: `architect`, `engineer`, `qa-engineer`, `code-reviewer`. Presets: `budget` (default), `balanced`, `quality-first`. Tiers: `budget`, `balanced`, `quality`.

```text
python scripts/specialist_models.py [--config PATH] status [--json]
python scripts/specialist_models.py [--config PATH] resolve ROLE
python scripts/specialist_models.py [--config PATH] set-preset {budget|balanced|quality-first}
python scripts/specialist_models.py [--config PATH] set-tier {budget|balanced|quality} MODEL_ID
python scripts/specialist_models.py [--config PATH] set-override ROLE MODEL_ID
python scripts/specialist_models.py [--config PATH] clear-override ROLE
python scripts/specialist_models.py report [--events PATH] [--json]
```

- Default config: `.factory/model-preferences.json` in the repository root (gitignored). A missing file means defaults: preset `budget`, all tiers unresolved. Mutating commands create the file atomically; unknown keys are preserved. A malformed or invalid file exits non-zero and is never rewritten.
- `resolve ROLE` prints only the model ID and exits 0; an unresolved role or invalid configuration prints a diagnostic to stderr and exits non-zero. Factory Lead passes the printed ID as the native `task` `model` argument.
- Model IDs are single tokens of letters, digits, `.`, `_`, `:`, `/`, `-` (at most 200 characters). The script cannot check availability; the runtime accepts or rejects the ID at delegation.
- `status` lists the preset, tiers, overrides, and each role's resolved model with its source (`override`, `preset:<tier>`, or `unresolved`).
- `report` reads the newest `<Copilot user/session directory>` (or `--events`) and lists each delegation: agent, requested model (`explicitModelOverride`, else none/inherited), `taskModelSource`, `modelSelectionSource`, actual models from `subagent.started` and `subagent.completed`, tokens, duration, and a match flag, plus per-agent totals (delegations, tokens, duration). Missing runtime fields are shown as `not available`; no price is computed.

## Historical (superseded) proposal: personal profile helper

**Status**: Blocked historical proposal, not implemented behavior or authorization to build a helper. Commands below do not exist.

### Local operations

```text
python scripts/configure_specialist_models.py status
python scripts/configure_specialist_models.py set-preset {budget|balanced|quality-first}
python scripts/configure_specialist_models.py set-tier {budget|balanced|quality} MODEL_ID
python scripts/configure_specialist_models.py set-override ROLE MODEL_ID
python scripts/configure_specialist_models.py clear-override ROLE
python scripts/configure_specialist_models.py apply
```

`ROLE` is one of `factory-lead`, `architect`, `engineer`, `qa-engineer`, and `code-reviewer`. Configuration is local per checkout as specified in [data-model.md](../data-model.md). Editing a preference updates local desired state only; it is visibly **not applied** until `apply` succeeds. User-supplied IDs are not independently validated against provider availability by the offline helper.

`status` is read-only and lists selected preset, override or tier, requested ID or unresolved status, intended personal target, source/target drift or conflict, and applied/not-applied state for each role. Actual model, runtime enforcement and availability remain `not verified` unless evidence is provided by the runtime. Never print credentials.

`apply` preflights all five roles; unresolved values, malformed source, unowned target, link, unexpected target changes or invalid generated profile cause failure before writes. It shows targets and warns that personal agents are global and may shadow same-ID agents across repositories. It requires explicit confirmation, or a documented explicit noninteractive confirmation flag. It writes full validated profiles with only the native `model` field changed, plus provenance. It never silently overwrites or removes a user-owned file. Nonzero exit and per-target results are required for I/O errors; if interrupted or partial, do not claim complete success.

Refresh of a known managed, unmodified target after source drift requires explicit `apply` and must preserve updated source instructions. A target modified by the user or owned by another checkout blocks; the helper gives manual review/reconciliation steps and never adopts it automatically. Any removal mechanism must require explicit user action and verify the current content against recorded ownership; it must refuse altered or unowned files.

## Native runtime contract and limits

- The personal filename matches the repository agent ID; the generated `model` is a single user-selected string and no required model lock is introduced.
- GitHub documentation describes personal-over-repository same-ID precedence for Copilot CLI. VS Code documents the Copilot personal agent location and the model preference field, but matching-ID precedence and delegated selection behavior need live verification for the relevant version.
- A selected preset's requested value is not proof of actual model, model availability, fallback, successful task quality, or hard cost enforcement. Parent/session overrides and effective reviewer tool restrictions must be evidenced separately.
- If an environment cannot apply the preference, report that precise limitation. A manual native profile adjustment preserving the full role is a possible fallback; it is not an automated cross-surface compatibility pass.
