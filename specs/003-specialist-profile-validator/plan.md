# Implementation Plan: Specialist Profile Integrity Validator

**Branch**: Spec Kit feature identifier `003-specialist-profile-validator` (setup did not create or switch a Git branch) | **Date**: 2026-11-20 | **Spec**: [spec.md](spec.md)

**Input**: Approved-scope request recorded in `specs/002-specialist-ai-team/quickstart.md`; feature specification at `specs/003-specialist-profile-validator/spec.md`.

## Summary

Add a local Python validator for the five repository Copilot profiles. Parse YAML frontmatter with PyYAML's safe loader, require non-empty string `name` and `description`, and enforce the Code Reviewer's strict tool list as exactly `read`, `grep`, and `glob`. Aggregate path-specific findings and return nonzero for invalid configuration. Keep PyYAML in a dedicated `validation` dependency group and leave factory runtime dependencies and infrastructure unchanged.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Python standard library; PyYAML in the `validation` dependency group for standards-compliant frontmatter parsing. No factory runtime dependency is added.

**Storage**: N/A; read profile files only.

**Testing**: `unittest`, including temporary repository fixtures and a CLI exit-status check.

**Target Platform**: Local Windows checkout; implementation remains portable across Python-supported platforms.

**Project Type**: Repository maintenance CLI script.

**Performance Goals**: Validate five small files in a local run; no latency target.

**Constraints**: No network, Copilot process, or factory CLI invocation. No writes to profile files. Inspect only the five expected profile paths. Keep tests focused in `tests/unit/test_agent_profiles.py`; do not change factory source, policy, sandbox, or Spec Kit workflow assets. Add no runtime dependencies. The CLI defaults to the repository containing the script and accepts an optional `--root PATH` for explicit checkout/fixture selection.

**Scale/Scope**: Five profiles under `.github/agents/`; one read-only validation command and focused unit tests.

## Constitution Check

The repository constitution is still a draft pending owner ratification. This feature plan applies its constraints but does not ratify or amend it.

| Principle                                     | Gate | Plan decision                                                                                                                                                                          |
| --------------------------------------------- | ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| I. Spec Kit Remains the Foundation            | PASS | Keep the approved spec and plan as the authority for this feature; no parallel workflow or task tracker.                                                                               |
| II. Product-Owner Authority and Approvals     | PASS | The owner approved the current child specification and plan on 2026-11-20; implementation proceeds only within that scope.                                                             |
| III. Roles, Delegation and Relevant Expertise | PASS | The validator adds no delegation infrastructure. Use the existing specialist profiles when supported, and report only runtime-evidenced delegation.                                    |
| IV. Evidence-Based Quality                    | PASS | Focused unit tests cover valid and invalid profiles, and the CLI status reflects the findings actually observed.                                                                       |
| V. Security, Provenance and Permissions       | PASS | Use safe YAML loading; read only fixed profile paths; make no network or subprocess calls. Keep the parser in a validation-only dependency group and record its rationale in research. |
| VI. Simplicity and Developer Experience       | PASS | One script, one focused test module, standard-library CLI/test support, and one parser dependency isolated from factory runtime.                                                       |
| VII. Controlled Self-Improvement              | PASS | No changes to the factory, its rules, execution permissions, or workflows are in scope.                                                                                                |
| VIII. Traceability, Transparency and Delivery | PASS | Emit repository-relative findings and a clear successful result; document runnable checks in quickstart.                                                                               |

### Post-Design Check

PASS. The design remains local and read-only and introduces no factory behavior. Implementation is authorized within this approved scope. The constitution remains draft.

## Project Structure

### Documentation

```text
specs/003-specialist-profile-validator/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── cli.md
└── tasks.md
```

### Source and Tests

```text
pyproject.toml            # Add isolated validation dependency group after approval
uv.lock                   # Resolve validation dependency after approval
scripts/
└── validate_specialist_profiles.py
tests/
└── unit/
    └── test_agent_profiles.py
.github/
└── agents/               # Read-only inputs; no profile edits planned
```

**Structure Decision**: Follow the existing repository layout: a standalone script under `scripts/` and `unittest` coverage under `tests/unit/`. Keep profile parsing, checks, and CLI entry point in this small maintenance script; no package/module or factory integration is warranted.
