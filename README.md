# Spec Factory

## Quick Start

Spec Factory adds a small team of VS Code Copilot Chat agents, led by Factory Lead, and supporting scripts to an existing Spec Kit project. Its guided installer checks the project, shows the planned changes, and asks before installing; it does not run an autonomous coding agent or replace Spec Kit.

### Before You Start

- Python 3.11 or newer, [`uv`](https://docs.astral.sh/uv/getting-started/installation/), and [Git](https://git-scm.com/downloads).
- An existing project that is the root of a Git repository, with Spec Kit already initialized and its Copilot integration working. The `specify` command is used for readiness checks; if it is missing, the installer can offer to install `specify-cli==1.0.6` with `uv` after asking permission.
- [VS Code with GitHub Copilot Chat](https://code.visualstudio.com/docs/copilot/chat/copilot-chat), with access to Copilot, to use the installed agents.

The installer does not initialize or repair Spec Kit. If the project is not ready, set up or repair Spec Kit yourself, then run the installer again.

### Install

Open a terminal at the root of your existing Spec Kit project, then run the published `v0.1.0` wheel directly from GitHub Releases:

```powershell
uvx --from "https://github.com/mattjohns92/spec-factory/releases/download/v0.1.0/specfactory-0.1.0-py3-none-any.whl" specfactory init
```

The installer checks prerequisites and previews its plan. It asks separately before installing the Specify CLI (if needed) and before writing the Spec Factory files. It creates managed files only when they are absent, never overwrites existing files, writes an install manifest, and adds a local Git exclude entry for optional model preferences. Declining an action leaves that action unapplied.

To preview without setup commands, prompts, or project writes:

```powershell
uvx --from "https://github.com/mattjohns92/spec-factory/releases/download/v0.1.0/specfactory-0.1.0-py3-none-any.whl" specfactory init --dry-run
```

This command downloads the published wheel from GitHub Releases; it does not use PyPI.

### Choose Factory Lead

After installation, open the project folder in VS Code, open Copilot Chat, open the agent picker, and select **Factory Lead**. Factory Lead coordinates work with the installed specialist agents and pauses for your approval of specification and plan steps.

The installer does not sign in to Copilot or select model IDs for you. Model preferences are optional; you can choose and confirm them during installation or leave them unset. Readiness checks do not verify Copilot authentication, live task dispatch, or sandbox enforcement.

## Development

Requires Python 3.11 or newer and `uv`. Run the product unit tests with:

```text
python -m unittest tests.unit.test_installer tests.unit.test_agent_profiles tests.unit.test_readiness_check tests.unit.test_specialist_models tests.unit.test_public_package tests.unit.test_public_cli
```

The disposable installer workflow requires the `specify` CLI. The distribution tests build and install from local artifacts; their pinned build dependencies must already be available for offline use.

See [RELEASING.md](RELEASING.md) for the root-level build and release checks.

## License

MIT. See [LICENSE](LICENSE).

## Limitations

- Spec Kit must already be initialized and its Copilot integration must be valid; the installer does not run `specify init` or use `--force`.
- Managed-file upgrades, customization, and uninstall automation are not provided. Review the install manifest and `git status` before committing project changes.
- Each release must include the approved license and a wheel whose version matches the release URL.
