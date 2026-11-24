# CLI Contract: `scripts/check_factory_readiness.py`

```text
python scripts/check_factory_readiness.py [--root PATH]
```

- `--root PATH`: checkout to inspect; defaults to the repository containing the script. Must be an existing directory.

## Exit status

| Code | Meaning |
| --- | --- |
| 0 | No check FAILED; verdict "ready with limitations" |
| 1 | At least one check FAILED; verdict "not ready" |
| 2 | Usage error (invalid `--root`) |

NOT VERIFIED items, INFO items, and warnings never change the exit status.

## Output (stdout)

```text
[PASS] tool-specify: Specify CLI 1.0.6 (supported)
[NOT VERIFIED] tool-copilot: copilot executable found; version not checked (never executed)
    expected: a version documented as supported (1.0.114)
    next step: confirm the Copilot CLI version manually; not treated as a failure
[FAIL] specialist-profiles: .github/agents/architect.agent.md: 'name' must be a non-empty string
    expected: five valid specialist profiles
    next step: fix the listed profile frontmatter
[NOT VERIFIED] interactive-hooks: hook declared, locally disabled
[INFO] runner-policy: .factory/policy.json absent (not required for interactive use)
[NOT VERIFIED] authentication, live dispatch, effective sandbox enforcement
Verdict: not ready | ready with limitations
```

Guarantees: read-only; no network; no hosted session; no factory CLI invocation; the `copilot` executable is never run (presence check only); no environment variable values or secrets printed; fixed subprocess queries only (`specify --version`, `specify integration status --json`), argument lists, `shell=False`, 15 s timeout.
