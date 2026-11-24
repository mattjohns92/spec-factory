# CLI Contract: `scripts/install_factory.py`

**Status**: Implemented local-engine contract. Do not change this behavior as part of public onboarding without owner approval.

```text
python scripts/install_factory.py --target PATH [--dry-run]
```

Run from a Software Factory checkout. `--target` is required: the root directory of a local Git working tree. `--dry-run` prints the plan and changes nothing. No other options; no prompts; no network.

## Exit status

| Code | Meaning |
| --- | --- |
| 0 | Installed, or already installed; installed readiness check was not `not ready`. Also dry run completed with no conflicts and no refusal. |
| 1 | Incomplete or failed safely: conflicts (nothing written), the exclude ignore state could not be established (no assets written), a write failed or a destination appeared during installation (created paths are listed; the existing file is untouched; re-run to complete), or the final ignore verification failed (not reported as success). |
| 2 | Refused before any write: usage error, invalid target, target is the source checkout, unsupported manifest, no valid Spec Kit Copilot integration, the manifest path is ignored by Git, or `.factory/model-preferences.json` is already tracked by Git. |
| 3 | Installation completed but the installed readiness check reported `not ready` or could not run (any nonzero readiness status). Nothing is rolled back. |

A dry run with conflicts exits 1; a dry run that would be refused exits 2.

## Output (stdout)

```text
Target: <resolved path>
[create]    .github/agents/factory-lead.agent.md
[unchanged] scripts/specialist_models.py
[conflict]  .github/agents/engineer.agent.md: different content
[exclude]   append '/.factory/model-preferences.json' to <path>/.git/info/exclude
[exclude]   already ignored by <rule>; no change
[warning]   scripts/specialist_models.py is ignored by <rule>; it will not be shared
[cleanup]   scripts/.specialist_models.py.sf-tmp: remove leftover temporary file
[conflict]  .github/skills: blocked path (symlink)
Plan: 7 create, 2 unchanged, 0 conflict
DRY RUN: nothing was changed.                     (dry run only)
```

After a real run: `created`, `unchanged`, the verbatim readiness output, and next steps (set tiers with `python scripts/specialist_models.py set-tier ...`, open the project in VS Code, select Factory Lead, run `python scripts/check_factory_readiness.py`).

## Refusal text for missing Spec Kit

```text
Refused: this repository has no valid Spec Kit Copilot integration (<findings>).
Nothing was written. Onboarding will not initialize or repair Spec Kit because
Specify requires --force for an existing Git project. Review the official
existing-project guidance and complete setup manually, then re-run.
```

## Refusal text for a tracked preferences file or ignored manifest

```text
Refused: .factory/model-preferences.json is already tracked by Git, so an exclude rule would not protect it.
Nothing was written. Untrack it yourself, then re-run:
    git rm --cached .factory/model-preferences.json

Refused: .github/software-factory/install-manifest.json is ignored by <rule>; the manifest must be shareable.
Nothing was written. Adjust that ignore rule, then re-run.
```

## Guarantees

- Writes only the managed paths, the manifest and the one exclude entry, and only after all validation has succeeded and no conflict exists.
- Never modifies an existing file other than appending to `.git/info/exclude`; creates files exclusively so a destination that appears after the conflict check is never overwritten; refuses symlink and junction path conflicts; never stages, commits or changes Git history, index or refs; never runs a `specify` command that writes.
- Subprocesses: fixed argument lists, `shell=False`, 15 s timeout; `git` queries and the readiness subprocess only.
- No environment variable values or secrets are printed.

---

# Public CLI Contract (provisional local build; release not authorized)

Provisional local-build invocation from a built wheel; this name is not reserved or approved for publication:

```text
uvx --from <wheel> specfactory init [--target PATH] [--dry-run] [--non-interactive] [--yes]
```

The bare form `uvx specfactory init` requires a separately approved release to a registry.

The target defaults to the current working directory. `--target` selects an explicit existing project root. The persistent local-build option is `uv tool install <local-wheel>` followed by `specfactory init` (or the final separately approved distribution name after release). The public package must not add or replace the `factory` executable, which belongs to the existing experimental CLI.

## Consent Semantics

- Interactive mode shows prerequisite findings and a complete Software Factory plan before asking for changes. If the Specify CLI is missing, its environment-level installation requires separate approval from Software Factory installation. Missing/incomplete project Spec Kit is a manual prerequisite and is never initialized automatically.
- Prerequisite output reports the Copilot CLI executable separately from the Spec Kit Copilot integration. In installed-project mode, a missing Copilot CLI is informational: VS Code Copilot Chat is the primary workflow, and the CLI is optional. This does not suppress any other readiness failure. Source-checkout readiness retains Feature 004 behavior, including FAIL when the CLI is absent.
- Automatic Spec Kit initialization or repair is not offered. Specify 1.0.6 requires `--force` to initialize even a Git-only project root; onboarding never forwards `--force`. For missing or incomplete Spec Kit, it refuses the factory install and directs the user to review the official existing-project guidance and complete setup manually.
- `--dry-run` is read-only against the target, never prompts for write approval, never runs `specify init`, and may call the existing installation engine only with its own `--dry-run` option to show the authoritative per-path plan; it never invokes the engine in write mode.
- `--non-interactive` does not prompt and defaults to preview-only. `--yes` explicitly authorizes only the Software Factory installation, only after all prerequisites pass. It never authorizes or triggers Spec Kit initialization. Missing/incomplete Spec Kit is a refusal with instructions.
- `--dry-run` with `--yes` is rejected as contradictory; no flag may silently imply approval for both Spec Kit initialization and installation.
- The public adapter must invoke the same safe installation engine and preserve all current safety guarantees and exit meanings. No `--force` option is provided or forwarded.

## Exit Codes

| Exit code | Public onboarding meaning |
| --- | --- |
| 0 | Read-only preview passed, or installation completed and readiness did not fail |
| 1 | Approved Specify CLI installation failed, or the installer reported an incomplete/conflicting install |
| 2 | Invalid invocation, refusal, decline, missing/incomplete Spec Kit, or preview not ready; no factory install was performed |
| 3 | Factory files were installed, but readiness reported `not ready` for a blocking check other than Copilot CLI absence alone |

## Outcomes

| Outcome | Meaning |
| --- | --- |
| Preview success | Prerequisites and planned actions reported; target unchanged |
| Explicit refusal | Invalid project, missing prerequisite, user declined, or non-interactive run lacks authorization; no unauthorized action performed |
| Install success | Installer completed, readiness result and VS Code next steps shown |
| Install incomplete | Installer conflict/write failure/readiness failure shown with exact paths and next steps; never reported as complete |

The `--yes` spelling and provisional `specfactory` distribution name are local implementation choices, not a reservation or publication authorization. Any final name requires a separate owner-approved release audit. This contract does not authorize name reservation/registration, package publication, PyPI upload, GitHub publication, repository exposure, push, merge or deployment.
