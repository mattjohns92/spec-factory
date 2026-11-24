# Quickstart: Installation & Project Bootstrap

**Status**: Implemented provisional local-build guide. The public package exists in this checkout (`distributions/interactive/`) and has been built and run only from local artifacts; it is not reserved, registered or published, and A6 (real-project Copilot Chat check) has not been run. Contract: [contracts/cli.md](contracts/cli.md).

## Prerequisites

- An existing local Git project whose root you control (run from that root, or pass `--target`).
- Git, and Python 3.11+ on `PATH` (the installed profiles run `python scripts/...`); VS Code with GitHub Copilot Chat.
- The Copilot CLI is checked separately from the Spec Kit Copilot integration. In an installed project it is optional: if absent, readiness gives guidance to use VS Code Copilot Chat, the primary workflow. Other readiness failures remain blocking. Source-checkout readiness keeps Feature 004's existing behavior.
- `uv` is needed to run `uvx`, to install the wheel persistently, and for the optional Specify CLI installation. It is not needed to run an already-installed `specfactory`.
- A valid Spec Kit Copilot integration. Interactive onboarding can offer installation of the official Specify CLI after separate approval. Project initialization or repair is a manual prerequisite; onboarding never runs `specify init` or uses `--force`.

If uv is not installed, use the official [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/) for Windows, macOS or Linux. Supported options include WinGet (`winget install --id=astral-sh.uv -e`), the official standalone installer, and platform package managers. Restart the terminal if needed, then verify `uv --version` and `uvx --version`.

## Public Install (Provisional, local build)

Run inside the existing project. `specfactory` is the provisional local-build name only; it has not been reserved or approved for publication, so `uvx specfactory init` resolves a registry package and does not work until a separately approved release exists. `software-factory` is unavailable: that PyPI name belongs to another project, so do not use `uvx software-factory init`.

Build the artifacts locally (no registry upload), then run the wheel:

```powershell
uv build --wheel --sdist --out-dir <out-dir> distributions/interactive
uvx --from <out-dir>/specfactory-0.1.0-py3-none-any.whl specfactory init --dry-run   # preview; target unchanged
uvx --from <out-dir>/specfactory-0.1.0-py3-none-any.whl specfactory init             # guided setup and separately approved actions
```

For a persistent local install, install the built wheel and invoke the same distinct command:

```powershell
uv tool install <out-dir>/specfactory-0.1.0-py3-none-any.whl
specfactory init
```

The command is `specfactory init [--target PATH] [--dry-run] [--non-interactive] [--yes]`. There is no `--force`, and no `factory` command is installed. Any final public name and `uvx specfactory init` instruction require separate owner approval after the release audit.

### Preview and automation

- `--dry-run`: read-only. It never prompts, never runs a setup command and never installs. When prerequisites pass it shows the installer's own per-path plan (the installer's `--dry-run`); when Spec Kit or the Specify CLI is missing it lists the proposed actions and the files that would be created, and exits 2 because the project is not ready.
- `--non-interactive`: never prompts and is preview-only unless `--yes` is also given. Input that is not a terminal is also preview-only. Preview success exits 0.
- `--non-interactive --yes`: authorizes only the Software Factory install, and only when every prerequisite already passes. It never installs the Specify CLI or initializes Spec Kit; if either is missing it refuses (exit 2) with nothing written.
- `--yes` without `--non-interactive`, and `--yes` with `--dry-run`, are rejected (exit 2).
- Installer exit codes are preserved: 1 for conflicts or an incomplete install (nothing overwritten), 2 for a refusal before any write, 3 when files were installed but a blocking readiness check is `not ready`.

Interactive onboarding shows the prerequisite findings and the full plan, then asks separately before installing the verified official PyPI Specify CLI (`uv tool install specify-cli==1.0.6`, an environment-level change retrieved from uv's configured index) and before installing Software Factory. It re-checks the CLI after setup. If Spec Kit is missing or incomplete, onboarding refuses the factory install and directs you to the official [existing-project guidance](https://github.com/github/spec-kit/blob/main/docs/how-to/existing-projects.md); it does not run `specify init` because Specify 1.0.6 requires `--force` for a Git project, including a root containing only `.git`.

## Model Setup and Launch

Onboarding explains the existing Budget, Balanced and Quality-first role-to-tier mappings (the `budget`, `balanced` and `quality-first` presets). Choose an exact model identifier or Copilot display name accepted by your task runtime; availability varies by account, and actual runtime selection is not guaranteed by this preference file. No model values are supplied by the package and nothing is configured unless you choose it. Interactively, after install it can set a preset and the tiers that preset uses, each only with your confirmation; non-interactively it prints how to do so later. For example, after install:

```powershell
python scripts/specialist_models.py set-preset balanced
python scripts/specialist_models.py set-tier balanced <your-model-id>
python scripts/specialist_models.py status
python scripts/check_factory_readiness.py
```

Review `git status`; installed project files remain uncommitted for you to review. The preferences file is personal and locally excluded. Open the project in VS Code, open Copilot Chat, and choose **Factory Lead**. Chat discovery and live delegation require the separately authorized A6 check before they can be claimed as verified.

The source-checkout developer command remains available for local testing, but users of the public distribution do not clone Software Factory or manually copy assets:

```powershell
python scripts/install_factory.py --target <target> --dry-run
python scripts/install_factory.py --target <target>
```

## Conflicts and repeat runs

- `[conflict]` lines mean a file already exists with different content. Nothing was written. Compare it with the source file, move or merge yours, and re-run.
- Re-running is safe: unchanged files stay untouched, a deleted managed file is recreated, and the exclude entry is never duplicated.

## Remove

For a persistent tool installation, run `uv tool uninstall specfactory`. In the project, delete the managed files listed in `.github/software-factory/install-manifest.json` and the manifest itself, then remove the exact line `/.factory/model-preferences.json` from `.git/info/exclude`. The installer does not create preferences; delete `.factory/model-preferences.json` only if you no longer need your personal settings. Review `git status` afterwards.

## Troubleshooting

- `specfactory` is not found after a persistent install: verify `uv tool list`, run `uv tool update-shell`, restart the terminal, then check `specfactory --help`.
- A local wheel is not in the registry: use `uvx --from <path-to-wheel> specfactory init`; bare `uvx specfactory init` requires a separately approved published package.
- Onboarding does not initialize or repair Spec Kit. Specify 1.0.6 requires `--force` even in a Git-only project root; review the CLI's [existing-project guidance](https://github.com/github/spec-kit/blob/main/docs/how-to/existing-projects.md), initialize or repair manually, then rerun onboarding.
- The final readiness verdict is `not ready`: the installation is not rolled back; inspect the per-check findings and rerun `python scripts/check_factory_readiness.py` after resolving them.

## Validation scenarios (maps to the spec's matrix)

| # | Scenario | Expected |
| --- | --- | --- |
| A1 | Fresh repository after `specify init` | Install succeeds; readiness `ready with limitations`, no pointer failure |
| A1b | Repository without Spec Kit | Exit 2, nothing written (including `.git/info/exclude`) |
| A2 | Spec Kit repository with uncommitted changes | Only managed files, manifest and one exclude line are new or changed |
| A3 | Conflicting `engineer.agent.md` and a same-name skill | Exit 1, nothing written, conflicts named |
| A4 | Run twice; delete one managed file; run again | Second run changes nothing; third recreates only that file |
| A5 | `--dry-run` in each state | Target byte-identical, including `.git/info/exclude` |
| A3b | Tracked `.factory/model-preferences.json`; symlinked managed path or ancestor; ignored manifest path | Exit 2 or 1 as in the contract, nothing overwritten, guidance printed |
| A4b | Edit an installed managed file, run readiness | `FAIL` naming the path and next step, verdict `not ready` |
| A6 | Separate real project in Chat | Owner-authorized only; see plan section 8 |
| A7 | Install, then move and delete the source checkout; run installed tools with PyYAML blocked and no `FACTORY_*` or `PYTHONPATH` | Same results as before; no source path anywhere |

Public distribution scenarios B1–B8 (wheel/sdist contents, clean-venv wheel install, guided consent, manual Spec Kit refusal, non-interactive modes, conflicts and model guidance) are covered by `python -m unittest tests.integration.test_public_distribution`. It builds the wheel and sdist with `uv build --offline` and uses local fakes for `specify`, `uv` and `copilot`; missing `uv`, `git`, or the pinned offline build backend is a test failure, not a skip. The suite validates the installed console script and disposable install from the wheel; scripted imports drive consent because the stdlib test has no pty. A real Specify 1.0.6 attempt with `init --here --integration copilot --non-interactive` in a disposable Git-only root failed because Specify requires `--force`; onboarding therefore does not initialize projects. A local `uvx --from <wheel>` help invocation was smoke-tested, but persistent `uv tool install <wheel>`, a real interactive terminal, and A6 are not covered by the suite.

Automated run: `$env:PYTHONPATH='src'; python -m unittest discover -s tests -t .` (`PYTHONPATH=src` is only needed by the existing factory CLI tests; distribution tests fail if `git` is missing or the pinned offline build backend is unavailable. The older real-Specify installer fixture skips only when `specify` is absent, while missing `git` is a failure.)
