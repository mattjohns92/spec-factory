# Research: Installation & Project Bootstrap

All findings were observed on 2026-11-22 in this checkout or in a disposable temporary repository (since deleted).

## Observed facts

1. **A fresh `specify init` project has no `.specify/feature.json`.** `specify init --here --force --non-interactive --integration copilot` (offline, bundled assets, Specify 1.0.6) produced `.specify/` templates, scripts, workflow, constitution, memory and two integration manifests. `specify integration status --json` reported `status: ok`, `default_integration: copilot` and no findings. The current readiness checker then reported `FAIL speckit-config: .specify/feature.json: missing`. A freshly installed project would be "not ready" for a reason that is not a defect, so the pointer must be optional in an installed project (Plan section 3).
2. **Readiness on that fresh project** also failed on the missing profiles and skill, as expected; its Specify, hooks, policy and Git checks passed or reported normally, so they work on any repository.
3. **Path coupling.** `specialist_models.py` (`DEFAULT_CONFIG`), `validate_specialist_profiles.py` and `check_factory_readiness.py` (`--root` default) all use `Path(__file__).resolve().parent.parent`. If installed at `<target>/scripts/`, that is the target root.
4. **Import coupling.** The readiness checker imports `validate_specialist_profiles` from its own directory, and that module imports PyYAML at import time. `pyproject.toml` lists PyYAML only in the optional `validation` dependency group. The only non-stdlib dependency of the three tools is PyYAML.
5. **Profile frontmatter** in all five profiles and the skill uses only `key: plain-scalar`, `key: true` and inline double-quoted lists (`tools: ["read", ...]`).
6. **Source-specific text** exists only in Factory Lead (three sentences) and in one sentence of `factory-handoff`; the other four profiles have none. Existing tests assert only the `scripts/specialist_models.py resolve` text and profile structure.
7. **Gitignore state in this repository**: `.factory/` and `.github/copilot/settings.local.json` are ignored, `.github/hooks/factory-policy.json` is tracked; `.specify/feature.json` is ignored here. Personal configuration and security hooks therefore never need to be copied.
8. **Existing code worth reusing**: `check_specify`, `check_speckit`, `_query`, the injectable `runner`, `fingerprint`-style hashing (new but tiny), and the validator's `PROFILE_PATHS`.

## Decisions

| Decision | Rationale | Alternatives rejected |
| --- | --- | --- |
| Standalone `scripts/install_factory.py` | Feature 004 Q1 precedent; no factory CLI/runner coupling; stdlib only; target needs nothing installed | Subcommand of `factory` (couples to the deferred runner path; requires installing the package in the user's workflow) |
| Mirror layout; byte copies | Existing defaults resolve correctly; no templating; simple conflict logic | Install tools under `.factory/` (would require changing the profiles, skill, three scripts and their tests) |
| Optional PyYAML with a subset parser | Keeps accepted behavior with PyYAML; targets work without it | Vendoring PyYAML (license/provenance burden); requiring PyYAML (violates FR-009); rewriting validation without YAML (changes accepted Feature 003 semantics) |
| Conflict means no writes | No half-installed team; simplest safe rule | Install non-conflicting subset (breaks the team silently) |
| Exclude written before assets; append-only | Fail-safe order; preserves existing bytes | Rewriting the file (risks content change) |
| Manifest records fingerprints, not an update mechanism | FR-011 and reversal; drift visibility | Updater/uninstaller (out of scope) |
| Readiness run as a subprocess of the installed copy | Verifies the installed tool, not the source's | In-process call (would not prove relocation) |

## Open items for implementation (not blocking the plan)

- Confirm the exact `git check-ignore --no-index -v` output format across Git versions when parsing the matching rule for the preview; fall back to printing only "already ignored".
- Confirm `git rev-parse --git-path info/exclude` behavior when `.git` is a file (submodule or linked worktree); the installer relies on Git's answer and treats any failure as "cannot establish".

## Public distribution research (2026-11-23)

1. **uv executable model**: official uv documentation states that `uvx` is an alias for `uv tool run`, resolves a package that provides a console-script command, and runs it in an isolated temporary environment. `uv tool install` provides persistent commands on PATH. The owner's correction rules out the `software-factory` distribution and rejects adding the existing experimental `factory` executable; the local candidate is `specfactory`, matching its primary command. Sources: [uv tool guide](https://docs.astral.sh/uv/guides/tools/) and [Python entry-point specification](https://packaging.python.org/en/latest/specifications/entry-points/).
2. **uv setup**: official uv docs list the standalone installer and platform options including WinGet and package managers. Public quickstart should link to the upstream instructions rather than embed stale installation scripts. Source: [uv installation](https://docs.astral.sh/uv/getting-started/installation/).
3. **Local artifact workflow**: official uv docs support building wheels and source distributions locally with `uv build`; package-install verification can use `uv run --with <package> --no-project`. The implementation test should use the built wheel as the input and run outside the checkout, with a temporary isolated environment, to prove package resources—not source-tree paths—are used. Source: [uv package guide](https://docs.astral.sh/uv/guides/package/).
4. **Existing entry point boundary**: this checkout's root `pyproject.toml` exposes `factory = software_factory.cli:main`; `src/software_factory/cli.py` contains the separate automated CLI/runner surface. The public interactive package therefore cannot simply repoint the root entry point or package all of `src/software_factory`. Keep the local engine reusable and isolate the minimal public distribution.
5. **Registry name is unresolved**: the owner identifies PyPI `software-factory` as another project's distribution with release provenance pointing to `stratonext/software-factory`; it is unavailable to this project. PyPI JSON endpoints returned 404 for candidate `specfactory` on 2026-11-23. Use `specfactory` only for isolated local build/install tests. A 404 is not a reservation or guarantee of availability; do not reserve, register or publish any name without separate owner approval and a release audit.
6. **Model preset behavior**: `scripts/specialist_models.py` defines `budget`, `balanced`, and `quality-first`; mappings are respectively balanced for architect/engineer/reviewer and budget for QA; balanced for all; and quality for all. The preset does not supply model IDs. Onboarding should explain mapping and ask the user to select available IDs; it must not create preferences or make cost choices without consent.
7. **Hatchling file selection**: official Hatchling documentation supports explicit `only-include` and `force-include` selections and reproducible builds. The package plan can use a separate minimal build target and explicit allowlist rather than relying on VCS discovery or the repository's broad root layout. Source: [Hatchling build configuration](https://hatch.pypa.io/latest/config/build/).
8. **Specify installation source and command**: the official [Spec Kit installation guide](https://github.com/github/spec-kit/blob/main/docs/installation.md) documents both the PyPI `specify-cli` package and a pinned GitHub-release installation. This onboarding uses the official PyPI `specify-cli==1.0.6` package through uv's configured index and names both the package and source in its approval text; 1.0.6 is the only version currently in the readiness checker's supported set. A direct 1.0.6 test also confirmed that non-force init refuses a Git-only project root; therefore project initialization is manual.

## Public distribution design decisions

| Decision | Rationale | Alternatives rejected |
| --- | --- | --- |
| Minimal independent public distribution with bundled interactive assets | Proves `uvx` works without a source checkout and avoids leaking unrelated code/history | Packaging the root project unchanged would expose its existing automated CLI/runner and its `factory` entry point |
| Reuse `scripts/install_factory.py` through an asset-source adapter | Keeps all current safe-write guarantees in one installation engine | Duplicate the install flow in a new public CLI |
| Separate approval for environment-level Specify CLI installation and Software Factory installation; project initialization is manual | Prevents broad consent from authorizing unrelated writes and avoids the upstream `--force` requirement | Automatic Spec Kit initialization in an existing Git root |
| Non-interactive defaults to preview; explicit install switch is required | Makes automation safe by default while supporting authorized automation | Assume noninteractive implies consent |
| Local built-wheel clean-environment test; no registry install in tests | Verifies published artifact contents without publishing, downloading source or exposing repository history | Treat an editable/source-tree run as package validation |
| Use provisional `specfactory` only for local artifact tests; verify final ownership at separately approved release time | `software-factory` belongs to another project, and a 404 does not reserve a candidate name | Assume ownership, reserve a name, or authorize publication through implementation approval |
