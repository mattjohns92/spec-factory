---
description: "Task list for the Specialist AI Development Team feature"
---

# Tasks: Specialist AI Development Team

**Input**: Design documents from `specs/002-specialist-ai-team/`

**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, and `quickstart.md`

**Authorization**: This task list does not approve implementation. Obtain explicit owner approval of the current `spec.md` and `plan.md` before implementing profiles or running the demonstration. Obtain owner approval of the separate demonstration feature's scope, specification, and plan before that feature is implemented. No task authorizes a hosted run, security probe, factory CLI/runner change, or bypass of interactive permissions. The owner later approved the narrow hook amendment recorded in T020 and the quickstart; it does not authorize broader policy or sandbox changes.

**Tests**: Validate profile discovery and delegation interactively. Run the demonstration feature's planned checks and record actual outcomes; no new Python factory tests are in scope.

**Organization**: Tasks are grouped by the three user stories. Existing Spec Kit stages and interactive Copilot permissions remain authoritative.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Tasks that can proceed independently in different files
- **[Story]**: User story label for story-phase tasks only
- Every task names its target file or evidence record

## Phase 1: Setup

**Purpose**: Confirm the supported interactive environment and preserve a truthful evidence trail.

- [x] T001 Review existing Copilot and Spec Kit conventions in `.github/skills/` and `.specify/`; record relevant discovery paths in `specs/002-specialist-ai-team/research.md` without starting Copilot or changing existing workflow assets.

## Phase 2: Foundational Owner Approval

**Purpose**: Establish the approval gate before implementation or live delegation.

- [x] T002 Record the owner's explicit approval of the current `specs/002-specialist-ai-team/spec.md` and `specs/002-specialist-ai-team/plan.md` on 2026-11-20.

**Checkpoint**: No profile implementation or feature demonstration begins before T002 is complete.

## Phase 3: User Story 1 - Define and Select Specialist Roles (Priority: P1)

**Goal**: Provide five discoverable, bounded Copilot profiles and select only relevant specialists.

**Independent Test**: Discover all five profiles in the supported interactive Copilot surface and inspect each for its role contract, authority, inputs, outputs, and completion conditions.

### Implementation for User Story 1

- [x] T003 [US1] Create `.github/agents/factory-lead.agent.md` defining coordination, selective specialist choice, owner approval boundaries, native Spec Kit stage ownership, normal permission handling, and truthful reporting.
- [x] T004 [P] [US1] Create `.github/agents/architect.agent.md` defining bounded technical planning, relevant risks and decisions, required context, outputs, completion conditions, and no authority to expand scope or approve implementation.
- [x] T005 [P] [US1] Create `.github/agents/engineer.agent.md` defining implementation limited to owner-approved tasks, required repository context, changed-path reporting, actual verification evidence, and escalation of out-of-scope requests.
- [x] T006 [P] [US1] Create `.github/agents/qa-engineer.agent.md` defining requirement-derived checks, exact outcomes and blockers, and no authority to weaken acceptance criteria.
- [x] T007 [US1] Create `.github/agents/code-reviewer.agent.md` with a read/search-only tool list, no write or command tools, actual-diff review criteria, and actionable findings or an explicit no-findings result.
- [ ] T008 [US1] Verify all five profiles are discoverable and their role contracts are distinct in the interactive Copilot surface; record exact observations and any unsupported capability in `specs/002-specialist-ai-team/quickstart.md`.

**Checkpoint**: All five profiles are discoverable, bounded, and do not claim capabilities unsupported by the runtime.

## Phase 4: User Story 2 - Delegate and Return Evidence (Priority: P1)

**Goal**: Use native interactive Copilot delegation for bounded work and return evidence-bearing handoffs.

**Independent Test**: Dispatch a bounded, owner-approved assignment to a separate specialist context; inspect the returned result, affected paths, checks, unresolved questions, and runtime-visible task evidence. Confirm a profile-only or same-session pass is not labeled as delegation.

### Implementation for User Story 2

- [x] T009 [US2] Create `.github/skills/factory-handoff/SKILL.md` defining specialist selection criteria, assignment fields, handoff fields, delegation evidence labels, and escalation for incomplete, contradictory, or out-of-scope results.
- [ ] T010 [US2] After T003 and T009, use the supported interactive Copilot surface to delegate a bounded, non-mutating assignment; record its objective, specialist role, returned result, affected paths, checks, unresolved issues, and runtime-visible separate-context evidence in `specs/002-specialist-ai-team/quickstart.md`.
- [ ] T011 [US2] Verify that normal Copilot permission prompts are respected and any denied action is reported without retrying through another execution path; record the observed outcome or note that no denial occurred in `specs/002-specialist-ai-team/quickstart.md`.

**Checkpoint**: Delegation and handoffs are accurately evidenced; no custom dispatch or permission bypass is introduced.

## Phase 5: User Story 3 - Demonstrate an Approved Feature (Priority: P1)

**Goal**: Carry one small, owner-approved feature through the existing Spec Kit workflow, implementation, planned checks, and independent review.

**Independent Test**: Inspect the demo feature's approved Spec Kit artifacts, approval decisions, implementation diff, actual planned check results, separately delegated Engineer and Code Reviewer contributions, and final owner decision.

### Demonstration and Implementation for User Story 3

- [x] T012 [US3] Obtain owner approval for the Specialist Profile Integrity Validator scope, with target files `scripts/validate_specialist_profiles.py` and `tests/unit/test_agent_profiles.py`, as recorded in `specs/002-specialist-ai-team/quickstart.md`.
- [x] T013 [US3] Complete the child Spec Kit specification and plan and record the owner's explicit approval on 2026-11-20, with artifact paths in `specs/002-specialist-ai-team/quickstart.md`.
- [x] T014 [US3] Generate the selected feature's tasks through the existing Spec Kit task-generation stage and record `specs/003-specialist-profile-validator/tasks.md` in `specs/002-specialist-ai-team/quickstart.md`; no parallel tracker was created.
- [ ] T015 [US3] Have Engineer implement only the approved tasks in the target paths recorded in `specs/002-specialist-ai-team/quickstart.md`; record changed paths and actual verification performed there.
- [x] T016 [US3] Have QA run every check required by the approved plan and record each exact command/check, outcome, skipped check, and blocker in `specs/002-specialist-ai-team/quickstart.md`.
- [ ] T017 [US3] Have Code Reviewer inspect the actual demo diff in a separate context with no write-capable tools; record findings or explicit no-findings, diff scope, and available runtime evidence in `specs/002-specialist-ai-team/quickstart.md`. If context or effective tool restrictions cannot be verified, label the review self-review, record the limitation, and leave independent-review criteria incomplete.
- [x] T018 [US3] Reconcile the demonstration record in `specs/002-specialist-ai-team/quickstart.md` against the approved requirements, actual tests, handoffs, review, limitations, and next steps; leave final acceptance to the owner.

**Checkpoint**: Report the demonstration as complete only when its approved checks and evidence criteria are met; otherwise state exactly what remains incomplete.

## Final Phase: Polish and Cross-Cutting Validation

**Purpose**: Ensure the approved first increment contains no deferred factory work and has complete evidence.

- [x] T019 Review the changed paths against `specs/002-specialist-ai-team/plan.md` and `ROADMAP.md`; confirm no factory CLI, runner, sandbox, or Spec Kit workflow changes were introduced, verify that any execution-policy change is limited to the owner-approved T020 amendment, and record scope discrepancies in `specs/002-specialist-ai-team/quickstart.md`.
- [x] T020 Apply and locally validate the owner's narrow pre-tool hook amendment for `list_agents` and path-scoped read-only review; restrict native task delegation to `code-review`, add policy/hook regression coverage, and record hosted limitations without marking T015 or T017 complete.

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 records existing Copilot/Spec Kit discovery paths and configuration conventions without starting Copilot.
- **Foundational (Phase 2)**: T002 requires explicit approval of the current team specification and plan; it blocks profile implementation and all live delegation.
- **User Story 1 (Phase 3)**: Depends on T002. T004-T006 may be authored in parallel; T003 and T007 establish the coordinating and review roles; T008 validates all profiles after they exist.
- **User Story 2 (Phase 4)**: Depends on T002 and the Factory Lead profile. T009 defines shared handoffs; T010 follows T003 and T009 and validates native delegation/evidence; T011 records how interactive permissions behaved.
- **User Story 3 (Phase 5)**: Depends on T002-T011. T012 requires owner selection and approval of the demo scope. T013 requires the existing Spec Kit feature stages and owner approval of the child spec and plan. T014 precedes implementation; T015 precedes QA and review; T016 and T017 may be performed independently after implementation; T018 follows both.
- **Polish (Final Phase)**: T019 follows all changed paths and demonstration evidence.

### User Story Dependencies

- **US1 (P1)**: Defines and validates five specialist profiles after team spec/plan approval.
- **US2 (P1)**: Depends on the Factory Lead profile; provides handoffs and observed native interactive delegation.
- **US3 (P1)**: Depends on US1 and US2; demonstrates the roles on a separately owner-approved feature using existing Spec Kit stages.

### Parallel Opportunities

- **US1**: T004, T005, and T006 edit distinct profile files and can proceed in parallel. T003 and T007 should be completed before T008 validates the full set.
- **US3**: After T015, QA checks (T016) and review (T017) can proceed independently against the same completed diff, provided review remains read-only.

## Parallel Example: User Story 1

```text
Task T004: Create .github/agents/architect.agent.md
Task T005: Create .github/agents/engineer.agent.md
Task T006: Create .github/agents/qa-engineer.agent.md
```

## Implementation Strategy

### MVP First

1. Obtain owner approval of the team specification and plan.
2. Add and validate the five role profiles and shared handoff skill.
3. Demonstrate one separately delegated, bounded contribution with available runtime evidence.
4. Carry one separately approved small feature through existing Spec Kit stages, implementation, actual planned checks, and evidence-backed review.

### Incremental Delivery

1. Complete role definitions and validate interactive profile discovery.
2. Validate native delegation and handoff behavior without factory runner changes; any policy exception must remain within owner-approved T020.
3. Complete the owner-approved feature demonstration and record actual outcomes.
4. Keep deferred routes, factory execution/policy work, and security probes on the roadmap for separately approved increments.

## Notes

- `[P]` tasks edit different files and have no dependency on unfinished tasks.
- `[USn]` maps each task to a user story in `specs/002-specialist-ai-team/spec.md`.
- All tasks remain unchecked until performed; task generation and artifact approval do not authorize implementation.
- Do not claim a test, delegated task, or independent review unless its actual outcome and available evidence are recorded.
- No task authorizes changes to the factory CLI, runner, sandbox, or Spec Kit workflow registry. T020 is the only authorization for the narrow pre-tool hook amendment; it does not authorize broader execution-policy changes.
