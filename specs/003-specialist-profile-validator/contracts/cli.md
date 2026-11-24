# CLI Contract: Specialist Profile Integrity Validator

## Invocation

```text
python scripts/validate_specialist_profiles.py [--root PATH]
```

- With no option, validate the repository containing the script, independent of the current working directory.
- `--root PATH` selects an explicit repository root. The validator still checks only the five expected paths beneath `.github/agents/`.
- The command is local and read-only. It does not start Copilot, invoke the factory CLI, or make network requests.

## Results

- Exit `0`: every expected profile passes; print a concise success message to standard output.
- Exit `1`: one or more expected profiles are missing or invalid; print each repository-relative path and useful reason to standard error.
- Exit `2`: invalid command-line usage, including an explicit root that is not a directory containing `.github/agents/`.
- Independent profile findings are aggregated in one run where possible.

## Required Checks

- All five expected profile files exist.
- Each file has delimited, syntactically valid YAML frontmatter containing non-empty string `name` and `description` values.
- The Code Reviewer has boolean `strict-tools-list: true` and exactly three unique tools: `read`, `grep`, and `glob`. Duplicates or additional/missing entries fail validation.
- Extra metadata is allowed unless it conflicts with a required condition.
