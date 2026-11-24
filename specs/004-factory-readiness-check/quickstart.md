# Quickstart: Readiness Check

After implementation (not yet implemented):

```powershell
uv run --group validation python scripts/check_factory_readiness.py
uv run --group validation python -m unittest tests.unit.test_readiness_check
```

Interpreting results:

- `FAIL`: fix the stated next step; exit status is 1.
- `NOT VERIFIED`: compatibility, authentication, live dispatch, sandbox enforcement, or hook behavior cannot be established offline. A live, owner-authorized session is the only way to confirm these.
- `INFO`: context only, such as a missing automated-runner policy.
- "ready with limitations" is the best verdict this check can issue.

The check does not install, repair, or modify anything and does not replace `factory doctor` (which covers the deferred automated-execution path).
