---
description: "Task list for the Specialist Profile Integrity Validator"
---

# Tasks: Specialist Profile Integrity Validator

**Input**: Design documents from `specs/003-specialist-profile-validator/`

**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/cli.md`, and `quickstart.md`

**Authorization**: The owner approved the current child specification and plan on 2026-11-20. Implement only this scope. Do not change factory CLI, runner, execution policy, sandbox, or Spec Kit workflow code. PyYAML belongs only in the `validation` dependency group, not project runtime dependencies. Do not start a hosted Copilot session, make network requests for tests, run a security probe, deploy, or perform external repository actions.

**Tests**: Focused `unittest` cases are explicitly required by the specification. Tests and the validator must be runnable locally without Copilot or network access.

## Phase 1: Setup

**Purpose**: Add the approved parser dependency without changing factory runtime dependencies.

- [x] T001 Add PyYAML to a `validation` dependency group in `pyproject.toml` and resolve the corresponding `uv.lock` entries without adding PyYAML to `[project].dependencies`.

## Phase 2: User Story 1 - Validate Specialist Profile Configuration (Priority: P1)

**Goal**: Validate the five required agent profiles locally, report actionable findings, and reject unsafe or duplicate Code Reviewer tools.

**Independent Test**: The focused unit suite accepts all valid profiles and rejects missing files, malformed frontmatter, invalid required metadata, invalid strict-tool configuration, additional tools, and duplicate tools with nonzero CLI status.

### Tests for User Story 1

- [x] T002 [P] [US1] Add focused unit tests in `tests/unit/test_agent_profiles.py` for valid profiles, missing profiles, malformed or non-mapping frontmatter, missing/wrong-type/empty `name` and `description`, invalid `strict-tools-list`, extra reviewer tools, duplicate reviewer tools, aggregated findings, and CLI exit status.

### Implementation for User Story 1

- [x] T003 [US1] Implement `scripts/validate_specialist_profiles.py` to safely parse frontmatter, validate the fixed five paths, require exactly three unique reviewer tools (`read`, `grep`, `glob`), aggregate repository-relative findings, and implement the documented CLI exit behavior without subprocess or network access.
- [x] T004 [US1] Run the focused suite with `uv run --group validation python -m unittest tests.unit.test_agent_profiles -v` and validate the repository profiles with `uv run --group validation python scripts/validate_specialist_profiles.py`; record actual outcomes in the completion report.

## Dependencies & Execution Order

- T001 and T002 touch separate files and may proceed in parallel.
- T003 depends on T002's test cases and T001's dependency definition.
- T004 depends on T001 through T003.

## Parallel Opportunities

- T001 and T002 are independent file changes and may be performed in parallel.

## Implementation Strategy

Complete T001 and T002, implement T003, then run T004. Stop if dependency resolution requires unauthorized network access; do not silently substitute an unpinned global package or add PyYAML to runtime dependencies.
