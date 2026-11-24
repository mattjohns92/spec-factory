# Feature Specification: Specialist Profile Integrity Validator

**Feature Branch**: `003-specialist-profile-validator`

**Created**: 2026-11-20

**Status**: Draft

**Input**: User description: "Add a standalone validator for the five specialist Copilot agent profiles. Check the expected profile files, required frontmatter metadata, and the Code Reviewer's strict read-only tool configuration. Report useful errors and exit nonzero when profiles are invalid. Add focused unit tests. Avoid unnecessary dependencies and do not change factory infrastructure."

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Validate Specialist Profile Configuration (Priority: P1)

As a repository maintainer, I can run a local validator to catch missing or invalid specialist profile definitions before using them in Copilot.

**Why this priority**: Invalid profile metadata or an unsafe reviewer tool list can prevent discovery or undermine the intended review boundary.

**Independent Test**: Run the validator against the repository's five profiles and against focused temporary fixtures containing a missing profile, malformed frontmatter, missing required metadata, and an unsafe Code Reviewer tool list.

**Acceptance Scenarios**:

1. **Given** all five expected profile files contain valid required metadata and the Code Reviewer has strict read-only tools, **When** the maintainer runs the validator, **Then** it reports success with no invalid-profile findings and exits successfully.
2. **Given** one or more expected profile files are missing or have malformed frontmatter or missing required metadata, **When** the maintainer runs the validator, **Then** it identifies each affected path and reason and exits with a nonzero status.
3. **Given** the Code Reviewer profile does not set `strict-tools-list` to `true` or its tool list is not exactly three unique entries (`read`, `grep`, and `glob`), **When** the maintainer runs the validator, **Then** it reports the unsafe configuration and exits with a nonzero status.

### Edge Cases

- One or more profile files are missing; report the missing paths without an unhandled exception.
- Frontmatter is absent, malformed, or has an unexpected value type; report the file and validation problem.
- The Code Reviewer `strict-tools-list` value is missing, malformed, or not `true`, or its tool list is missing, malformed, contains duplicates, or is not exactly three unique entries (`read`, `grep`, and `glob`); fail validation.
- A profile has extra metadata that is not used by this validator; do not reject it unless it conflicts with a required condition.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: The validator MUST check the five expected profile files: Factory Lead, Architect, Engineer, QA Engineer, and Code Reviewer.
- **FR-002**: The validator MUST verify each profile has valid frontmatter with non-empty `name` and `description` values.
- **FR-003**: The validator MUST verify the Code Reviewer has boolean `strict-tools-list: true` and a tool list containing exactly three unique entries, `read`, `grep`, and `glob`, with no additional, duplicate, write-capable, or command-execution tools.
- **FR-004**: The validator MUST report each invalid profile with its repository-relative path and a useful reason; it MUST report multiple independent findings in one run where possible.
- **FR-005**: The validator MUST exit successfully only when all required checks pass and MUST return a nonzero status if any profile is missing or invalid.
- **FR-006**: The validator MUST be runnable locally without starting Copilot, making network requests, or invoking the factory CLI.
- **FR-007**: The feature MUST provide focused unit tests for valid profiles and invalid/missing metadata and unsafe reviewer tool configuration.
- **FR-008**: The implementation MUST NOT modify the existing factory CLI, runner, execution policies, sandbox, or Spec Kit workflow assets.

### Key Entities _(include if feature involves data)_

- **Agent profile**: A named specialist definition containing frontmatter metadata and role instructions.
- **Tool restriction**: The Code Reviewer's declared strict set of available read-only tools.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: A valid set of all five repository profiles is accepted with a successful exit status and no error findings.
- **SC-002**: A missing profile, malformed frontmatter, or missing required metadata is identified by file path and reason and produces a nonzero exit status.
- **SC-003**: A Code Reviewer profile whose strict flag is invalid or whose tool list is not exactly three unique entries (`read`, `grep`, and `glob`) is identified with a specific configuration error and produces a nonzero exit status.
- **SC-004**: Focused automated tests cover valid input and each required failure category without starting Copilot or using network access.

## Assumptions

- The five expected file paths establish profile identities. Each declared `name` must be a non-empty string, but it does not have to exactly match the filename or role title.
- Additional profile metadata may be present and is not rejected unless it invalidates a required check.
- The validator is a local maintenance tool and does not change profile discovery or Copilot permissions.
- The approved plan uses safe YAML parsing with PyYAML isolated to a validation-only dependency group.
