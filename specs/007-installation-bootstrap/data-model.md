# Data Model: Installation & Project Bootstrap

## Managed asset (installer constant `MANAGED_FILES`)

Repository-relative POSIX path, identical in source and target. Exactly nine entries:

- `.github/agents/factory-lead.agent.md`
- `.github/agents/architect.agent.md`
- `.github/agents/engineer.agent.md`
- `.github/agents/qa-engineer.agent.md`
- `.github/agents/code-reviewer.agent.md`
- `.github/skills/factory-handoff/SKILL.md`
- `scripts/specialist_models.py`
- `scripts/validate_specialist_profiles.py`
- `scripts/check_factory_readiness.py`

Validation: every entry exists as a regular file in the source; no entry is absolute, contains `..`, or falls under `src/`, `.specify/`, `.github/hooks/`, `.github/copilot/`, `.factory/policy.json`, `specs/` or `tests/`.

## Install manifest (`.github/software-factory/install-manifest.json`)

```json
{
  "version": 1,
  "source_revision": "54f2ded... or unknown",
  "files": {
    ".github/agents/factory-lead.agent.md": "sha256:<hex>",
    "scripts/specialist_models.py": "sha256:<hex>"
  }
}
```

| Field | Rules |
| --- | --- |
| `version` | Integer `1`. Any other value, or a non-object file, is "unsupported manifest": the installer stops, changing nothing. |
| `source_revision` | String; informational; ignored when comparing manifests. |
| `files` | Object with exactly the `MANAGED_FILES` keys; values `sha256:` plus 64 hex characters of the SHA-256 of the content with `\r\n` normalized to `\n`. |

No absolute paths, usernames, model IDs or timestamps. UTF-8, LF, sorted keys, indent 2, trailing newline, so identical inputs give identical bytes.

## Installation plan (in memory; printed by the preview)

| Entry | Fields |
| --- | --- |
| Path disposition | `path`, `state` in `create`, `unchanged`, `conflict`; `reason` for conflicts (`different content`, `not a regular file` (includes symlinks), `blocked path` (file, symlink or junction ancestor), `appeared during installation`) |
| Exclude disposition | `file` (resolved `info/exclude`), `state` in `append`, `already-ignored`, `cannot-establish`; `rule` when already ignored |
| Refusals | target validation, missing Spec Kit integration, manifest path ignored by Git, `.factory/model-preferences.json` tracked by Git |
| Warnings | managed paths other than the manifest ignored by the target's rules |

State transitions of a managed path on a real run: `create` becomes `unchanged` after the write; `unchanged` and `conflict` never change.

## Project-local preferences (not installed)

`.factory/model-preferences.json`, created by the developer with `scripts/specialist_models.py`; format unchanged from Feature 005; locally excluded.

## Exclude entry

Exactly one line: `/.factory/model-preferences.json`.

## Public distribution and onboarding

### Distribution asset

An allowlisted, versioned resource in the public wheel/sdist that the existing installer can consume without a source checkout.

- Identity: package-relative resource path and content fingerprint.
- Required contents: the nine managed interactive assets plus the adapter/engine code needed to install and verify them.
- Excluded: user preferences/model IDs, Git history, specs/tests, `.specify/`, source-local settings, root automated CLI/runner, hooks, policy and sandbox.
- Validation: every required asset is present in the built artifact; every excluded class is absent; the installed process resolves resources only from the distribution.

### Onboarding action

A user-visible operation with a specific scope and separate authorization state.

| Field | Rules |
| --- | --- |
| `action` | `install-specify-cli` or `install-software-factory`; Spec Kit initialization is manual because the supported CLI refuses Git roots without `--force` |
| `target` | Explicit environment or resolved project path; no implicit alternate target |
| `approval` | `not-required` for read-only inspection, otherwise `pending`, `approved`, or `declined` for that action only |
| `result` | `not-run`, `succeeded`, `failed`, or `refused`; revalidation is required after setup actions |

Approving one action does not authorize another. Preview does not create or approve actions. Non-interactive mode does not prompt and defaults to no writes; its explicit apply authorization covers only `install-software-factory` after all prerequisites pass.
