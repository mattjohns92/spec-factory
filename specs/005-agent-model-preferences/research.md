# Research: Per-Agent Model Preferences

> Migration note: the source research included user-local Copilot paths, raw model identifiers, session/task IDs, event-log evidence, token counts, probe hashes, and temporary personal-profile details. Those personal and session-specific details are omitted here. This is a sanitized recovery of the technical decisions, not a verbatim copy of that evidence. The original owner-acceptance status and exceptions remain in [tasks.md](tasks.md).

## Accepted technical decisions

- Feature 005 selected Option B: resolve a user-configured preference and pass it as the native delegated `task` model argument. Do not generate or replace personal agent files, add a model router, or change shared specialist profiles.
- Factory Lead remains selected by the user in Copilot Chat. Model preferences apply to Architect, Engineer, QA Engineer, and Code Reviewer.
- Budget, Balanced, and Quality-first are preference presets, not verified price or quality rankings. Users supply available model IDs; none are defaults or bundled product configuration.
- A per-role override takes precedence over the selected preset until cleared. Unresolved values must stop delegation for owner input; do not silently inherit or escalate.
- Distinguish the requested preference from any runtime-observed model. Report actual model information only from runtime evidence, never from agent-authored text. Missing or unsupported evidence remains not verified.
- Preserve complete specialist instructions and declared tool restrictions. A declared read-only tool list does not prove effective runtime permission enforcement.

## Rejected or deferred approaches

- Automatic generation of global personal-agent copies was rejected because same-ID precedence, ownership, drift, and cross-checkout shadowing were not safely established.
- A preference file without a supported application path does not satisfy the feature. No custom inference gateway, model router, required model lock, or silent fallback is authorized by the accepted design.
- Further live model-precedence experiments require separate owner authorization. The owner-accepted implementation and its exceptions are recorded in [tasks.md](tasks.md); this note does not add acceptance evidence.

## Remaining limitations

The source records only bounded historical runtime evidence. General VS Code Copilot Chat precedence, unavailable-model behavior, and effective reviewer permissions remain unverified. No local Copilot configuration or session log was migrated.
