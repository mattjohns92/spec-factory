# Data Model: Specialist AI Development Team

This feature adds Copilot customization files and demonstration records only. It adds no database, factory run state, or parallel workflow model.

## Entities

### Specialist Role

A Copilot agent profile with a distinct purpose, authority, required context, expected output, and completion conditions. The five roles are Factory Lead, Architect, Engineer, QA Engineer, and Code Reviewer. Factory Lead coordinates; specialist participation is selective and bounded.

### Handoff Skill

Reusable instructions in `.github/skills/factory-handoff/SKILL.md` describing assignment fields, result fields, evidence labels, and escalation of unresolved questions. It does not own Spec Kit stages or workflow state.

### Delegated Assignment

A bounded objective given by Factory Lead to one specialist.

Required information:

- Role/profile identifier
- Objective and relevant Spec Kit artifact or phase
- Relevant context and repository paths
- Constraints, including approved scope and owner gates
- Expected deliverable
- Completion condition

### Specialist Handoff

The specialist's return to Factory Lead.

Required information:

- Role and assignment outcome
- Deliverable and affected paths or artifacts
- Evidence and checks actually performed
- Unresolved questions, risks, and blockers
- Delegation label: observed separate-context task, same-session role pass, or unverified

### Delegation Evidence

Runtime-visible information supporting that a distinct task was dispatched and returned. Record the evidence source and fields available in the interactive surface. Do not invent a stable audit schema or infer separate-context work from profile selection or agent-authored claims.

### Approval Decision

The owner's explicit decision on the current team specification, plan, and separate demonstration-feature scope. A decision applies only to the artifact version or scope presented. Pending or rejected approval blocks the corresponding implementation.

### Review Record

A review of the actual implementation against approved requirements and scope. It includes the reviewer role, findings or explicit no-findings result, diff reviewed, available delegation evidence, and classification as independent or self-review. `Independent` requires a separate context and evidence that the reviewer had no write-capable tools. When these conditions are not established, label the review self-review and describe the limitation.

### Demonstration Record

The feature's evidence collected in `quickstart.md`: approved scope, Spec Kit stages and decisions, actual delegated assignments and handoffs, changed paths, executed checks and results, review result, limitations, and owner acceptance decision.

## Relationships and Validation

- Each demonstration uses the existing Spec Kit feature workflow; its native artifacts remain authoritative.
- The owner approves the current specification and plan before team implementation begins and separately approves the demo feature scope before that feature is implemented.
- A delegated assignment targets one role and records its result or blocker. Only actually performed checks may appear in its handoff.
- A same-session role pass is never counted as a separate-context delegation.
- An independent review requires both separate-context and effective read-only evidence. Otherwise the review is labeled limited.
- Test results identify the actual command/check and outcome. Skipped or unavailable checks are not reported as passing.
- Sensitive prompts, credentials, and raw transcripts are not copied into persistent demonstration records.
