# Implementation Plan: Specialist AI Development Team

**Branch**: `002-specialist-ai-team` | **Date**: 2026-11-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-specialist-ai-team/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Deliver a working specialist team for one small, owner-approved feature without changing the existing factory CLI, runner, sandbox, or Spec Kit workflow. Add five repository-local Copilot agent profiles and one shared handoff skill. The owner selects Factory Lead in a normal interactive Copilot session; Factory Lead uses Copilot's supported native delegation for only the needed specialists. Existing Spec Kit stages and owner approval gates remain authoritative. Demonstrate specification approval, plan approval, task generation, implementation, planned checks, and review of the actual diff; record genuine delegated contributions and available runtime evidence without claiming unsupported independence. A later owner-approved, bounded amendment updates only the existing policy and pre-tool hook for profile discovery and read-only review delegation.

## Technical Context

**Language/Version**: Existing project is Python 3.11+; v1 additions are Markdown agent profiles and a Markdown skill with YAML frontmatter. The owner-approved follow-up also updates the existing Python policy evaluator, PowerShell pre-tool hook, and focused policy tests.

**Primary Dependencies**: Existing Spec Kit and GitHub Copilot CLI integration; no new runtime dependency.

**Storage**: Role profiles and the shared skill are checked-in repository files. Existing Spec Kit run state remains authoritative. Record demonstration evidence in the feature's `quickstart.md`; add no database, report subsystem, or task store.

**Testing**: Run the checks required by the approved demo feature plan. Validate profile discovery and role contracts in the supported interactive Copilot surface. The end-to-end demonstration is owner-approved and interactive; it does not certify the factory CLI, its sandbox, or other Copilot surfaces.

**Target Platform**: Windows local checkout using normal interactive GitHub Copilot CLI and its existing permission controls.

**Project Type**: Copilot customization files used alongside the existing Python factory and Spec Kit project.

**Performance Goals**: No latency target. Delegate only work with a clear benefit; avoid parallel edits to the shared checkout.

**Constraints**: Preserve the existing Spec Kit feature workflow and owner approvals. Use Copilot's supported repository-local agent profiles, native delegation, and normal interactive permission prompts. The separately approved exception is limited to allowing `list_agents`, path-scoped read-only tools, and `task` with `agent_type: code-review`; the hook rejects unknown/duplicate tools and denies write/execute requests under the bounded policy. The complete runtime tool inventory was not captured. Do not change the runner, sandbox settings, `.specify/workflows/`, or factory CLI behavior. Do not create a custom orchestrator, tracker, database, worktree requirement, or new runtime dependency. A profile selection alone is not delegation evidence. Code review is independent only when a distinct delegated context and effective read-only tools are evidenced; otherwise report it as limited. Deferred routes and factory hardening are tracked in the root `ROADMAP.md`.

**Scale/Scope**: One local owner, one feature run, five roles, one shared handoff skill. No worktrees, autonomous background runs, plugins, external services, or broad Copilot-surface compatibility claims.

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle                                     | Gate | Plan decision                                                                                                                                                                                                                            |
| --------------------------------------------- | ---- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| I. Spec Kit Remains the Foundation            | PASS | Keep native specification, plan, task, implementation, run identity, and resume stages authoritative.                                                                                                                                    |
| II. Product-Owner Authority and Approvals     | PASS | Require approval of the current demo specification and plan before implementation; owner retains final acceptance.                                                                                                                       |
| III. Roles, Delegation and Relevant Expertise | PASS | Define five bounded profiles and select only relevant specialists through supported interactive delegation.                                                                                                                              |
| IV. Evidence-Based Quality                    | PASS | Record actual task evidence, checks, review results, and limitations; do not infer independence from profile selection or prose.                                                                                                         |
| VI. Simplicity and Developer Experience       | PASS | Add only Copilot profiles and one handoff skill; no custom orchestrator, service, database, worktree, or new dependency.                                                                                                                 |
| V. Security, Provenance and Permissions       | PASS | Preserve normal interactive permission controls and do not bypass denials. The owner separately authorized a minimal, tested hook allowlist for native discovery and read-only review; write/execute requests are denied by that policy. |
| VII. Controlled Self-Improvement              | PASS | This is an owner-reviewed Spec Kit feature; it does not alter the constitution, approval rules, or grant self-modification authority.                                                                                                    |
| VIII. Traceability, Transparency and Delivery | PASS | Record Spec Kit stages, approvals, delegated contributions, changed paths, checks, review, limitations, and owner decision in the feature guide.                                                                                         |

The constitution remains a draft pending explicit product-owner ratification. This plan applies its constraints without implying ratification.

### Phase 0 Gate Result

PASS for the narrowed design and subsequent owner-approved amendment. The existing feature Spec Kit workflow and owner approval gates remain unchanged. V1 adds repository-local Copilot profiles and a shared handoff skill; the only execution-policy exception is the tested pre-tool hook allowlist described under Constraints. The factory CLI, runner, sandbox, and workflow registry remain out of scope. Planning does not establish that the current interactive runtime exposes all evidence required for independent review, so the demonstration must verify this at runtime and report any evidence gap without a claim of independence.

### Post-Design Constitution Check

PASS for all principles, subject to owner approval of the amended scope. The demonstration uses existing interactive permission controls. The separately authorized hook change is least-privilege, restricted to discovery and `code-review`, and covered by focused policy and hook checks. Evidence for separate-context delegation and effective reviewer read-only tools must be checked during the authorized demo; missing evidence means the related acceptance criterion is not met.

### Interactive Delegation Evidence Gate

During the owner-approved feature demonstration, verify that Copilot actually dispatches the Engineer and Code Reviewer to separate contexts and inspect runtime-visible task evidence. Confirm the Code Reviewer has no write-capable tools before calling its result independent. The one authorized hook retest did not discover the exact repository Engineer or Code Reviewer profiles; no additional hosted run is authorized by this amendment. Do not conduct factory CLI, sandbox, or security probes. If the interactive surface cannot establish the required evidence, label the review as limited and mark the independent-review criterion incomplete.

## Project Structure

### Documentation (this feature)

```text
specs/002-specialist-ai-team/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
.github/
├── agents/
│   ├── factory-lead.agent.md
│   ├── architect.agent.md
│   ├── engineer.agent.md
│   ├── qa-engineer.agent.md
│   └── code-reviewer.agent.md
└── skills/
    └── factory-handoff/
        └── SKILL.md
```

**Structure Decision**: Add five agent profiles under `.github/agents/` and one shared handoff skill under `.github/skills/factory-handoff/`. The owner-approved follow-up changes the existing `src/software_factory/policy.py`, `scripts/factory_pre_tool_use.ps1`, and `tests/unit/test_policy.py` only; the runner, sandbox, and Spec Kit workflows remain unchanged. Capture demonstration evidence in `quickstart.md`; no report subsystem or new interface is required.

Regenerate `tasks.md` from this plan. Task generation does not approve the specification or plan and does not authorize implementation. Implementation remains blocked until the owner approves both current artifacts. The demo feature must be small, low-risk, owner-approved, and have runnable checks. Deferred routes, broader factory execution/policy changes beyond the approved hook amendment, and security/compatibility probes belong in the repository root `ROADMAP.md`.

## Complexity Tracking

**Approved amendment record**: The baseline was a fail-closed hosted `list_agents` call; the hypothesis was that a narrow allowlist for native discovery and read-only review could unblock observation without write/execute access. The owner explicitly approved the amendment after the original plan. Focused Python tests and a Windows PowerShell hook smoke test passed. Rollback is to remove `NATIVE_TASK_TOOLS` and `READ_ONLY_TASK_TYPES`, restore the pre-amendment tool list and task path handling in the hook, and remove only the T020 regression cases. No runner or sandbox changes are part of the amendment.
