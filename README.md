# Spec Factory

Software Factory installs a small, interactive team of VS Code Copilot Chat agent profiles and supporting scripts into an existing Spec Kit project. Factory Lead coordinates specialist tasks; the package does not run an autonomous coding agent or make model selections for you.

## Requirements

- Python 3.11 or newer and Git.
- An existing Git project with a valid Spec Kit Copilot integration.
- VS Code with GitHub Copilot Chat for the primary workflow.
- `uv` to download and run the versioned wheel.

The Copilot CLI is optional for readiness in an installed project. A valid Spec Kit integration is required. This tool does not initialize or repair Spec Kit projects.

## Install

From the root of your existing project, run the versioned GitHub Release wheel with `uvx`:

```powershell
uvx --from "https://github.com/mattjohns92/spec-factory/releases/download/v0.1.0/specfactory-0.1.0-py3-none-any.whl" specfactory init
```

This command downloads the published `v0.1.0` wheel directly from its GitHub Release; it does not use PyPI. Review the complete plan and approve each write action separately. Declining leaves the project unchanged. To inspect the plan without writing:

```powershell
uvx --from "https://github.com/mattjohns92/spec-factory/releases/download/v0.1.0/specfactory-0.1.0-py3-none-any.whl" specfactory init --dry-run
```

The command is `specfactory`; no PyPI registration is required for this GitHub Release installation.

## Development

Requires Python 3.11 or newer and `uv`. Run the product unit tests with:

```text
python -m unittest tests.unit.test_installer tests.unit.test_agent_profiles tests.unit.test_readiness_check tests.unit.test_specialist_models tests.unit.test_public_package tests.unit.test_public_cli
```

The disposable installer workflow requires the `specify` CLI. The distribution tests build and install from local artifacts; their pinned build dependencies must already be available for offline use.

See [RELEASING.md](RELEASING.md) for the root-level build and release checks.

## License

MIT. See [LICENSE](LICENSE).

## After Installation

Open the project in VS Code, open Copilot Chat, and select **Factory Lead**. Model preferences are optional and are only written after explicit selection and confirmation. The package supplies no personal model identifiers. Readiness reports project checks and limitations; it does not verify authentication, live task dispatch, or sandbox enforcement.

## Limitations

- Spec Kit must already be initialized and its Copilot integration must be valid; the installer does not run `specify init` or use `--force`.
- Managed-file upgrades, customization, and uninstall automation are not provided. Review the install manifest and `git status` before committing project changes.
- Readiness reports project checks and limitations; it does not verify authentication, live task dispatch, or sandbox enforcement.
- Each release must include the approved license and a wheel whose version matches the release URL.
