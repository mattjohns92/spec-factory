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

### Multi-Repository VS Code Workspaces

Workspace installation is supported by builds that include the `--workspace` option. The pinned `v0.1.0` wheel above predates this option; use a release that includes workspace support before running these commands:

```powershell
specfactory init --workspace --target "C:\work\my-workspace" --dry-run
specfactory init --workspace --target "C:\work\my-workspace"
```

The target must be a Gitless workspace root outside any Git working tree and contain at least two independent child Git repositories. Spec Factory reads each child repository's path, branch, HEAD, and working-tree state, then installs one shared set of agents and scripts at the workspace root. It does not write files or Git metadata in child repositories, initialize Git at the root, change Git excludes, or prompt for model preferences. `.factory/workspace.json` records the child paths found during installation; readiness reports live child state and notes later inventory changes.

Spec Kit must be initialized and its Copilot integration valid at the workspace root. If needed, initialize it there yourself with `specify init --here --integration copilot`, review Specify's merge prompt, and run Spec Factory again. Do not use `--force`. The root-level Spec Kit configuration and `specs/` are shared; existing Spec Kit configuration inside child repositories is outside this installation boundary and is not modified.

Open the workspace root in VS Code so its `.github/agents` files are in the opened workspace. Readiness does not verify that Copilot Chat lists the agents or that live delegation works.

VS Code's usual single-folder workspace is the simplest layout: open the physical parent directory directly. A saved multi-root `.code-workspace` is different. The installer still targets the physical parent directory, not the `.code-workspace` file; include that parent as a workspace folder or the parent's `.github/agents` directory is outside the open workspace. Opening only the individual service directories does not expose the shared parent agents. Some extensions and tools remain scoped to the first or active workspace folder, so a multi-root workspace does not guarantee that a Copilot session can navigate every service. Verify the picker and cross-service context in the actual session; file placement alone is not evidence of delegation.

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
