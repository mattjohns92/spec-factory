# Quickstart: Specialist AI Development Team

**Status**: Team profiles, handoff skill, and the static Feature 003 validator are implemented. One separately authorized hosted Copilot session was attempted; the repository pre-tool hook denied profile enumeration before any specialist task or review began.

## Feature 002 Artifact Approval

- Owner approval of the current team specification and plan: approved on 2026-11-20.
- Approval scope: Feature 002 only; the draft constitution is not ratified.
- The separate demonstration feature still requires its own owner-approved scope, specification, and plan before implementation.

## Local Implementation Checks

- `copilot skill list --json` discovered `factory-handoff` as an enabled project skill at `.github/skills/factory-handoff`.
- PyYAML 6.0.1 parsed all five agent profile frontmatters. The Code Reviewer has `strict-tools-list: true` and only `read`, `grep`, and `glob`; specialist `infer` is disabled.
- The project virtual environment does not include PyYAML (`uv run --no-sync python -c "import yaml"` returned `ModuleNotFoundError`).
- These are local configuration checks, not interactive profile-discovery, delegation, implementation, or demo acceptance evidence.
- At the end of the Feature 002 profile implementation, no changes were found under `src/software_factory/`, `.specify/workflows/`, `.github/hooks/`, or `scripts/`.

## T012 Demonstration Feature Scope (Owner Approved)

**Recommended feature**: Add a standalone specialist-profile integrity validator at `scripts/validate_specialist_profiles.py`, with focused tests at `tests/unit/test_agent_profiles.py`.

**Why this is useful**: The repository now relies on five YAML-frontmatter agent profiles and a shared skill. A local validator could catch missing profiles, malformed required metadata, and accidental write-capable Code Reviewer tools before someone opens Copilot.

**Approved scope**: Validate the five expected profile files, non-empty `name` and `description` metadata, and the Code Reviewer's strict tool configuration (`strict-tools-list: true` and exactly three unique entries: `read`, `grep`, and `glob`). Report repository-relative paths and useful reasons, aggregate independent findings, and return nonzero for invalid profiles. Keep it separate from `factory`, `src/software_factory/`, `.specify/workflows/`, execution policy, and sandbox behavior. PyYAML 6.0.3 is installed in the `validation` dependency group only; it is not a factory runtime dependency.

**Acceptance checks**: The validator accepts the current five profiles, rejects missing files, absent, malformed, or unclosed frontmatter, missing, empty, or wrongly typed required metadata, and missing, malformed, incomplete, duplicate, or additional reviewer tools. The 15 focused unit tests pass; the CLI validates the repository successfully. Tests do not start Copilot, invoke the factory CLI, or access the network.

**Roles**: Factory Lead coordinates; Engineer implements the validator; QA Engineer defines and runs its focused tests; Code Reviewer reviews the actual diff. Architect is involved only if the validator's contract requires a design decision.

**Decision**: The owner approved this scope, child specification, and plan on 2026-11-20. Implementation is complete and recorded below for final owner acceptance.

## Authorization Gates Still Pending

- T008 profile enumeration and T010-T011 live delegation/permission observations remain incomplete. In the authorized 2026-11-20 session, `copilot --agent "Factory Lead" --add-dir .` selected Factory Lead, but `list_agents` was denied by `.github/hooks/factory-policy.json` before the five profiles could be enumerated. Copilot reported: “A preToolUse hook (.github_hooks_factory-policy.json) denied list_agents and reported an error.” With `FACTORY_POLICY_PATH` unset, the hook code's first fail-closed reason is `Factory policy is unavailable.`; Copilot did not display that reason payload, so it is an inference from the inspected hook code, not the literal CLI message. No task was dispatched and no normal permission prompt was observed. The denial was reported; no bypass or retry occurred.
- T013: The owner explicitly approved `specs/003-specialist-profile-validator/spec.md` and `specs/003-specialist-profile-validator/plan.md` for implementation on 2026-11-20. PyYAML is approved only in the validation dependency group; it must not be added to factory runtime dependencies.
- T014: Generated `specs/003-specialist-profile-validator/tasks.md` through the native Spec Kit task setup on 2026-11-20.
- T015: The Engineer-profile assignment attempt returned blocked without changes when its offline PyYAML check failed. No separate-context Engineer implementation is evidenced; implementation was completed in this session after resolving the approved dependency.
- T016: QA ran `uv run --group validation python -m unittest tests.unit.test_agent_profiles -v` (PASS, all 15 tests) and `uv run --group validation python scripts/validate_specialist_profiles.py` (PASS, output: `All five specialist profiles are valid.`). No separate QA context was evidenced.
- T017: The Code Reviewer pass identified no findings in inspected file contents, but could not inspect the actual Git diff. A distinct context and effective read-only tool boundary were not evidenced; independent review remains incomplete.
- T018: This evidence record reconciles the approved scope, implementation, test outcomes, role-pass limitations, and outstanding acceptance items.

## 2026-11-20 Delegation Follow-up

- The earlier same-session Engineer pass ran `uv run --offline --no-project --with 'PyYAML>=6' python -c "import yaml; print('PyYAML', yaml.__version__)"`. Its recorded result was: “a usable PyYAML package was unavailable offline.” Raw `uv` stderr was not retained. The failure is attributable to local offline package availability, not permissions, profile configuration, or a dispatched task; no separate Engineer task context existed.
- Local Copilot CLI is version 1.0.114. Its help documents `--agent` and `--add-dir <directory>` loading `.github/agents`; the authorized launch displayed Factory Lead as active. All five profile files exist and pass the static validator, but runtime enumeration was blocked.
- Factory Lead declares `list_agents`, `read_agent`, and `task`. During the hosted attempt it reported `task` in its tool list, but did not invoke it because `list_agents` was denied. No Engineer task ID or return exists.
- The pre-tool config invokes `scripts/factory_pre_tool_use.ps1`. That script requires `FACTORY_POLICY_PATH` and `FACTORY_REPOSITORY_ROOT`; both were unset in the direct CLI launch. The existing runner supplies those variables, but its execution-policy allowlist excludes `list_agents`, `read_agent`, and `task`; it allows `view` rather than the Code Reviewer's `read` tool. The hook also requires target paths for non-PowerShell tools. No environment, policy, hook, or runner changes were made.
- Code Reviewer was not invoked. No actual diff was reviewed in the hosted session; T017 remains incomplete.

## 2026-11-20 Owner-Approved Policy Follow-up

- The owner explicitly authorized one narrow update to the existing policy and pre-tool hook, followed by one hosted retest. The amendment permits `list_agents`, permits pathless `task` only for `agent_type: code-review`, accepts the CLI's read-only `view` tool, and rejects unknown or duplicate policy tools. The hook denies write/execute requests under the bounded policy; the complete runtime tool inventory was not captured. It does not change the runner, sandbox, or normal permission prompts.
- Local checks passed: `uv run --offline --group validation python -m unittest tests.unit.test_policy` (13 tests), plus a Windows PowerShell smoke test showing discovery and `code-review` delegation allowed, `general-purpose` delegation and `edit` denied, `view` path-scoped, and unknown policy tools rejected.
- The hosted CLI started as Factory Lead. `list_agents` did not enumerate the repository's five custom profiles; it listed built-in agent types and reported no exact `Engineer` or `Code Reviewer` profile. The repository profile files exist under `.github/agents`. No Engineer task was dispatched, so there is no task ID or Engineer result; T015 remains incomplete.
- A separate native `code-review` task ran read-only. It used `view` on the exact named files and read the approved spec and task list; the task ID was not recorded. It identified four issues in the initial patch: scope conflict, unrestricted task types, missing hook tool validation, and test gaps. The owner then amended the scope; task types were restricted, hook validation and focused tests were expanded. The reviewer did not review those final edits.
- The workspace contains no tracked baseline: the repository files are untracked, so Git could not provide an actual demo diff. The reviewer did not inspect the plan or quickstart, run tests, or report its complete effective tool inventory. It was the built-in `code-review` task type, not the missing repository `Code Reviewer` profile. Independent-review criteria are not established; T017 remains incomplete.
- No further hosted run was authorized or performed after the final local policy tightening. T026, T028, and deferred security work were not resumed.

## Prerequisites

- Owner approval of the current team `spec.md` and `plan.md` was recorded on 2026-11-20.
- The five repository-local profile files and shared handoff skill are present. Interactive Copilot discovery remains unverified and was not needed for the static validator.
- The child specification and plan were separately approved before implementation on 2026-11-20.
- Normal Copilot permissions remain enabled; permission denials are respected and reported.

## Demonstration Flow

1. Start an interactive Copilot session with Factory Lead selected. Confirm the session uses the existing repository Spec Kit feature workflow.
2. Complete the demo feature's specification and plan. Obtain explicit owner approval of the current specification and plan before implementation.
3. Generate tasks through the existing Spec Kit workflow. Select only specialists needed for those approved tasks.
4. Delegate bounded work using Copilot's native agent delegation. Record the role, objective, context, constraints, expected deliverable, and completion condition for each assignment.
5. Implement only the approved tasks. Record changed paths and actual checks performed.
6. Have QA run the checks required by the approved plan and report exact outcomes, including unavailable or skipped checks.
7. Have Code Reviewer inspect the actual diff against approved requirements. Claim independent review only if a separate context and no write-capable reviewer tools are evidenced.
8. Record runtime-visible delegation evidence, specialist handoffs, test results, review findings, limitations, and the next action. The owner makes final acceptance.

## Evidence Record

Use this section during the authorized demo; do not prefill anticipated outcomes as if they occurred.

- Demo feature and approved scope:
- Approved Spec Kit specification and plan:
- Owner approval decisions:
- Delegated roles and bounded objectives:
- Runtime evidence for separate-context tasks:
- Changed paths:
- Checks run and exact outcomes:
- Diff reviewed and review findings:
- Evidence of reviewer context and effective tools:
- Skipped checks, blockers, and limitations:
- Owner's final acceptance decision:

If the runtime cannot establish separate-context contribution or the reviewer's effective read-only tools, label the review self-review, state the limitation, and mark the independent-review criterion incomplete. Do not bypass normal permissions or use the factory CLI/sandbox path to manufacture a passing result.

## Validation

Run the demo feature's approved checks in the normal interactive workflow. No additional repository-wide test command is prescribed by this feature because the v1 additions are Copilot Markdown profiles and a skill, not changes to the Python factory package.

## Explicitly Deferred

Bug-fix and idea-assessment routes, factory CLI/runner changes, broader execution-policy expansion beyond the approved hook amendment, separately authorized security or compatibility probes, and sandbox certification are not part of this guide. See the repository root `ROADMAP.md`.
