# Data Model: Readiness Check

In-memory only; nothing is persisted.

## CheckResult

| Field | Description |
| --- | --- |
| `id` | Stable check identifier (e.g. `tool-copilot`, `interactive-hooks`) |
| `status` | `PASS`, `FAIL`, `NOT_VERIFIED`, or `INFO` |
| `finding` | What was observed; repository-relative paths, no secrets or environment values |
| `expected` | What a passing state requires (FAIL and NOT_VERIFIED only) |
| `next_step` | Concrete remedy or follow-up (FAIL and NOT_VERIFIED only) |

## ReadinessReport

| Field | Description |
| --- | --- |
| `results` | Ordered list of `CheckResult` |
| `verdict` | `not ready` if any `FAIL`; otherwise `ready with limitations` |
| `limitations` | The NOT_VERIFIED items, always including authentication, live dispatch, and sandbox enforcement |

## VersionClassification

Input: tool name and parsed version. Output: `PASS` (in supported set), `FAIL` (in incompatible set or tool unusable), or `NOT_VERIFIED` with a warning (any other parseable version). Exit status derives from `FAIL` only.
