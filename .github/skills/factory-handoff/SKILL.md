---
name: factory-handoff
description: Standardizes selective specialist assignments, evidence-bearing handoffs, and accurate delegation and review claims.
---

# Factory Handoff

Use this skill when Factory Lead selects a specialist, delegates a bounded task, or records a specialist result.

## Select

Choose a specialist only when its expertise is needed for an approved task. Do not invoke every role as a fixed sequence. Do not delegate work that is out of scope or blocked by an owner approval gate.

## Assignment

Include:

- **Role**: The selected profile.
- **Objective**: One bounded outcome.
- **Context**: Relevant approved requirements, Spec Kit artifact, and repository paths.
- **Constraints**: Scope limits, approval state, permissions, and prohibited actions.
- **Deliverable**: The result or artifact to return.
- **Completion condition**: Observable evidence that the assignment is done.

## Model

Before each delegation to architect, engineer, qa-engineer, or code-reviewer, run `python scripts/specialist_models.py resolve <role>` and pass the printed ID verbatim as the native `task` `model` argument (run it from the repository root). If it fails (unresolved or invalid), do not guess or silently inherit the session model; ask the owner. If the runtime rejects or cannot honor the requested model, report that exactly to the owner; do not retry without the `model` argument or substitute another model. Never escalate silently: recommend escalation with a reason and apply it only on the owner's instruction. Factory Lead's own model is never configured by this feature. Record requested versus actual model, tokens, and duration from runtime events (`python scripts/specialist_models.py report`), never from specialist text.

## Handoff

Return:

- **Outcome**: Complete, partial, blocked, or unable to proceed.
- **Result**: Deliverable and affected paths.
- **Checks**: Commands or procedures actually performed and exact outcomes; state when none ran.
- **Evidence**: Runtime-visible delegation information actually available, including its source. A profile selection or agent-authored claim alone does not establish a separate task context.
- **Open items**: Unresolved questions, risks, and blockers.

Never convert unavailable evidence into a positive claim. Label work as a separate-context contribution only when runtime evidence supports that description; otherwise call it a same-session role pass or unverified contribution.

## Review and Permissions

Call a review independent only when a distinct delegated context and the reviewer's effective read-only tools are both evidenced. Otherwise label it self-review, describe the limitation, and leave the independent-review criterion incomplete.

Respect normal interactive permission prompts. On denial, stop the denied action and report the outcome. Do not retry through a different execution path, change permissions, or use any automated runner, execution policy, or sandbox as a workaround. Obtain separate run-specific owner authorization before any hosted Copilot session or live delegation test.

The owner approves scope and the current Spec Kit specification and plan before implementation, and retains final acceptance authority. Pause when approval is missing or the requested work materially changes scope.
