# Quickstart: Specialist Profile Integrity Validator

## Prerequisites

- Python 3.11 or newer.
- `uv` installed and the project validation dependency group resolved after implementation approval.

The validator uses PyYAML from the `validation` dependency group; it is not a factory runtime dependency.

## Validate This Repository

```powershell
uv run --group validation python scripts/validate_specialist_profiles.py
```

Expected result for valid profiles: a concise success message and exit code `0`.

## Validate an Explicit Repository Root

```powershell
uv run --group validation python scripts/validate_specialist_profiles.py --root C:\path\to\checkout
```

The selected root must be a repository directory. Findings use paths relative to that root and produce exit code `1`; invalid command usage or an unusable explicit root produces exit code `2`.

## Run Focused Unit Tests

```powershell
uv run --group validation python -m unittest tests.unit.test_agent_profiles -v
```

Tests use temporary profile fixtures and do not start Copilot, invoke the factory CLI, or access the network. They cover valid profiles, missing files, malformed frontmatter, missing, empty, or wrongly typed metadata, and missing, malformed, incomplete, duplicate, or unsafe Code Reviewer tool lists.
