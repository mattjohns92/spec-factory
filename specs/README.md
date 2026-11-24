# Recovered Feature Records

These files preserve selected design, implementation, verification, and acceptance records from the original `software-factory` checkout. They are historical records, not new authorization or evidence that every proposal was implemented. No Git history was imported.

| Feature | Status recorded in the source documents |
| --- | --- |
| 002 - Specialist AI Team | Draft; incomplete. The source records unchecked tasks and a blocked hosted session. |
| 003 - Specialist Profile Validator | Draft; checked tasks do not change the recorded draft status. |
| 004 - Factory Readiness Check | Owner-accepted with an explicit review exception and documented verification limits. |
| 005 - Agent Model Preferences | Owner-accepted with documented exceptions. Preserve its limits and unresolved runtime behavior. |
| 007 - Installation Bootstrap | Final record documents the `v0.1.0` public release. A6 was not run; no real project or hosted Copilot session was used. Earlier pre-publication snapshots in the source are superseded by the final acceptance record. |

These are archival specification and acceptance statuses, not an assessment of what is currently implemented in the canonical repository. Determine current implementation from the canonical source, tests, and published release artifacts.

Feature 001, the legacy factory CLI/runner proposal, is excluded. Feature 006 is absent and deferred; it is not represented as completed. The unapproved Feature 007 license proposal is excluded.

### Migration and privacy

Historical paths and implementation references generally describe the original checkout. Its Python package path `src/software_factory` was replaced in the public product by `src/specfactory`; an old path does not imply the referenced code or behavior shipped. Missing links may point to excluded source files or records outside this repository.

Feature 005 and Feature 007 records were selectively sanitized in this copy to remove user-local paths, model identifiers, session identifiers, raw session evidence, and private telemetry. Technical decisions, task states, acceptance exceptions, test outcomes, and public release evidence were retained. The source checkout was not modified.

These documents are development records, not package inputs. Keep them outside the explicit wheel and sdist allowlists and run the public distribution tests when changing packaging.
