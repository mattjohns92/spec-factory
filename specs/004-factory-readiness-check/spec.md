# Feature Specification: Software Factory Setup & Readiness Check

**Feature Branch**: `004-factory-readiness-check`

**Created**: 2026-11-21

**Status**: Implemented; owner-accepted 2026-11-21 with an explicit review exception (independent review waived for this feature only; review recorded as self-review, independence unverified). See `tasks.md` Acceptance Record.

**Input**: User description: "Software Factory Setup & Readiness Check — let a maintainer confirm, locally and read-only, that a checkout is correctly set up to use the interactive Spec Kit and specialist-team workflow, with clear guidance for anything missing."

## Background (existing state observed)

- `factory doctor` already runs static preflight checks, but it is tied to the deferred automated-execution path: it requires a local execution-policy file (`.factory/policy.json`) and pinned Specify/Copilot versions. In the current checkout it reports `BLOCKED` solely because that policy file is absent, and it stops before reporting anything else.
- Feature 003 provides a standalone specialist-profile validator.
- Spec Kit configuration (`.specify/`: integration, constitution, templates, feature pointer) and the five specialist profiles plus the `factory-handoff` skill are present but are not checked together by any single command.
- Interactive development (Features 002 and 003) does not depend on the automated runner or its execution policy.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - One-command readiness verdict for interactive use (Priority: P1)

As the product owner or a maintainer, I can run one local command and learn whether this checkout is ready for the interactive Spec Kit and specialist-team workflow, with each check listed as pass, fail, or not verified.

**Why this priority**: Setup problems (missing tools, missing profiles, broken Spec Kit configuration) currently surface midway through work. A single verdict prevents that.

**Independent Test**: Run the check against the repository and against temporary fixture checkouts each missing one prerequisite; confirm the verdict, per-check result, and exit status.

**Acceptance Scenarios**:

1. **Given** all required prerequisites are present and valid, **When** the maintainer runs the readiness check, **Then** every check is reported as passed or not verified with its limitation, the overall verdict is "ready with limitations" (a plain "ready" is never issued because authentication, live dispatch, and sandbox enforcement are always not verified), and the exit status is successful.
2. **Given** one or more required prerequisites are missing or invalid, **When** the check runs, **Then** every failing check is listed in one run (not just the first), the verdict is "not ready", and the exit status is nonzero.
3. **Given** a check cannot be performed locally (for example authentication or live agent dispatch), **When** the check runs, **Then** it is reported as "not verified" and never as passed.

---

### User Story 2 - Actionable guidance for each failure (Priority: P2)

As a maintainer, for each failed check I see what was expected, what was found, and the concrete next step, so I can fix setup without reading source code.

**Why this priority**: A bare failure list still leaves the maintainer to diagnose.

**Independent Test**: For each failure category in the fixtures, confirm the output names the affected path or tool, the expectation, and a suggested remedy.

**Acceptance Scenarios**:

1. **Given** a required tool is not installed or has an unsupported version, **When** the check runs, **Then** the output names the tool, the required and detected versions, and how to resolve it.
2. **Given** a specialist profile, Spec Kit file, or the active feature pointer is missing or invalid, **When** the check runs, **Then** the output gives its repository-relative path and the reason.

---

### User Story 3 - Safe, read-only, local operation (Priority: P2)

As the product owner, I can run the readiness check with confidence that it changes nothing, uses no network or credentials, and does not start any agent session.

**Why this priority**: The constitution requires least-privilege behavior and forbids unapproved external actions.

**Independent Test**: Run the check on a fixture checkout and confirm no files change, and with tool execution limited to local version queries.

**Acceptance Scenarios**:

1. **Given** any checkout state, **When** the check runs, **Then** no repository file is created, modified, or deleted.
2. **Given** the check runs, **When** it completes, **Then** no hosted Copilot session, delegation, network request, or authentication attempt has occurred.

### Edge Cases

- A required executable is absent from the search path: report a failed check, not an unhandled error.
- A version query hangs or exits nonzero: report a failed check for that item and continue the others.
- The execution-policy file used by the deferred automated runner is absent: the check must not fail interactive readiness for that reason alone (see FR-009).
- The feature pointer references a directory that does not exist, or is absent: report it and continue.
- The checkout is not a Git repository, or has uncommitted changes: report the Git state as information; uncommitted changes alone do not make the checkout "not ready".
- Output must not include secrets or environment variable values.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: The check MUST be runnable locally from a repository checkout in a single command and produce a per-check result (passed, failed, or not verified) plus one overall verdict.
- **FR-002**: The check MUST verify that the required local tools (Spec Kit CLI and Copilot CLI) are available and classify each detected version without requiring exact equality: a missing executable or a version documented as incompatible is FAIL; a version documented as supported is PASS; a newer or otherwise unknown version whose compatibility is not established is NOT VERIFIED with a warning, never an automatic failure and never reported as compatible merely because it is newer.
- **FR-003**: The check MUST verify Spec Kit configuration: the Copilot integration is registered with no missing or modified managed files, the constitution and spec/plan/tasks templates exist, and the active feature pointer refers to an existing feature directory.
- **FR-004**: The check MUST verify the five specialist profiles and the `factory-handoff` skill are present and valid, including the Code Reviewer's strict read-only tool configuration, by reusing the Feature 003 validation rules rather than duplicating them.
- **FR-005**: The check MUST report all independent failures in one run and MUST continue after an individual check fails.
- **FR-006**: For each failed check the output MUST state the expectation, the finding, and a suggested next step, identifying paths relative to the repository root.
- **FR-007**: The check MUST list checks it cannot perform locally (authentication, live dispatch, effective sandbox enforcement) as "not verified" and MUST NOT claim they passed.
- **FR-008**: The check MUST be read-only and MUST NOT make network requests, start hosted Copilot sessions or delegations, require credentials, or modify any file.
- **FR-009**: The check MUST NOT treat the absence of the automated-runner execution policy as an interactive-readiness failure when it is not required for the selected interactive mode; it MAY report its status as informational.
- **FR-014**: The check MUST include a lightweight, read-only interactive-hook readiness check. When the repository declares a factory policy hook but the runtime policy configuration that hook needs is unavailable, the check MUST classify the situation as either BLOCKING (a genuinely blocking configuration, e.g. a malformed hook declaration or a hook that would apply but cannot be satisfied) or NOT VERIFIED (effective behavior cannot be established without a live session), and MUST state which and why.
- **FR-015**: The check MUST NOT report fully verified interactive readiness while effective hook or permission behavior remains unknown; the overall verdict MUST then be "ready with limitations", with the limitation stated explicitly.
- **FR-016**: The check MUST NOT modify or disable hooks, policies, or sandbox configuration, and MUST NOT launch a live session to probe their effect.
- **FR-010**: The check MUST exit successfully only when no check has failed, and MUST exit nonzero otherwise.
- **FR-011**: The feature MUST NOT modify the factory security infrastructure (execution policy, runner, pre-tool-use hook, sandbox) or resume the deferred automated-execution work.
- **FR-012**: The feature MUST include focused automated tests covering the ready case, each failure category, the not-verified reporting, the missing-policy-file case, and the read-only guarantee, without starting Copilot or using the network.
- **FR-013**: The check's documentation MUST describe what it verifies, what it does not verify, and how to interpret each result.

### Key Entities _(include if feature involves data)_

- **Readiness check item**: A single named prerequisite with a result (passed, failed, not verified), expectation, finding, and suggested remedy.
- **Readiness report**: The ordered set of check items and the overall verdict.

## Product-Owner Decisions (2026-11-21)

- **Q1 — Standalone command**: The readiness check is a standalone command. `factory doctor`, the factory CLI, the runner, and automated-execution infrastructure are not modified.
- **Q2 — Version compatibility**: Exact version equality is not required. Missing executable or known-incompatible version: FAIL. Documented-supported version: PASS. Newer version with unestablished compatibility: NOT VERIFIED with a warning.
- **Additional requirement — Interactive hook readiness**: see FR-014 to FR-016.
- **Plan-stage decisions (2026-11-21)**: The `copilot` executable is never run (it may perform a network lookup); its presence is checked and its version is NOT VERIFIED. An active factory hook whose required policy configuration is unavailable in the checked environment is NOT READY, scoped to the current shell/launching environment; locally disabled hooks or undeterminable enforcement are NOT VERIFIED.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: On a correctly set-up checkout, the maintainer gets an overall "ready with limitations" verdict, the limitations listed, and a successful exit with a single command.
- **SC-002**: With any one prerequisite removed or broken, the verdict is "not ready", the nonzero exit occurs, and the output identifies that prerequisite with its path or tool name and a next step (verified for every failure category in tests).
- **SC-003**: With several simultaneous problems, all of them are reported in one run.
- **SC-004**: Authentication, live dispatch, and sandbox enforcement are never shown as passed (verified in tests).
- **SC-005**: A run leaves the repository byte-for-byte unchanged and performs no network access or hosted session (verified in tests).
- **SC-006**: A checkout lacking only the automated-runner policy file is not failed for that reason; because hook behavior cannot be established offline, its verdict is "ready with limitations", not fully verified.
- **SC-007**: Missing executable and known-incompatible versions fail; documented-supported versions pass; newer unestablished versions are NOT VERIFIED with a warning and are never reported as compatible (verified in tests).
- **SC-008**: A declared-but-unsatisfiable hook is classified BLOCKING or NOT VERIFIED with a stated reason, and an "all verified ready" verdict is never produced while effective hook/permission behavior is unknown (verified in tests).

## Assumptions

- The audience is the single product owner/maintainer on Windows using the standard repository checkout, per the constitution.
- Documented-supported versions are those already recorded by the repository (Specify CLI 1.0.6, Copilot CLI 1.0.114, speckit workflow 1.0.2); known-incompatible versions are only those the repository explicitly documents as such.
- Feature 003's profile validation rules are reusable as-is; this feature does not change them.
- Out of scope: installing or repairing tools, auto-fixing files, authentication or hosted/live-dispatch probes, sandbox certification, bug-fix/idea-assessment routes, and any factory CLI/runner/policy/hook changes (see ROADMAP.md).
- Existing uncommitted changes to the factory policy and agent profiles in the working tree belong to earlier work and are not part of this feature.
