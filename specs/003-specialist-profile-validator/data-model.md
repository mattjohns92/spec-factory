# Data Model: Specialist Profile Integrity Validator

## Expected Profile

Represents one required Copilot profile, identified by its repository-relative path under `.github/agents/`.

- Paths: `factory-lead.agent.md`, `architect.agent.md`, `engineer.agent.md`, `qa-engineer.agent.md`, and `code-reviewer.agent.md`.
- Missing path: produce a finding for that path and continue checking the other required profiles.

## Parsed Profile

Represents one existing profile's YAML frontmatter.

- `path`: repository-relative profile path.
- `metadata`: YAML mapping from the delimited frontmatter.
- Validation: frontmatter must be present, syntactically valid YAML, and a mapping. `name` and `description` must each be non-empty strings. Unrelated extra metadata is accepted.
- Parsing safety: use PyYAML's safe loader; do not execute or construct arbitrary Python objects.

## Reviewer Tool Restriction

Additional validation applied only to `code-reviewer.agent.md`.

- `strict-tools-list`: must be the boolean `true`.
- `tools`: must be a YAML list of exactly three entries; all entries must be unique and the set must be exactly `read`, `grep`, and `glob`.
- Missing, wrong-type, or unsafe values produce a path-specific finding.

## Validation Finding

One independently reportable validation problem.

- `path`: repository-relative profile path.
- `reason`: concise explanation of the failed check.
- A profile may produce more than one finding when independent checks fail.

## Validation Report

The complete result for one run.

- `findings`: zero or more validation findings, aggregated across all expected profiles.
- Success: the list is empty; CLI exit status is `0`.
- Failure: one or more findings exist; print all findings and return nonzero.

No profile file is modified, and no validation state is persisted.
