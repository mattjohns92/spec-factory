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

Keep assignments efficient: state the repository and paths in scope, ask specific questions, point to the relevant source files before any broad repository search, ask for concise evidence-backed findings, and tell the specialist to stop once it has sufficient evidence. Do not set arbitrary numeric limits that would block a necessary investigation.

Break substantial implementations into independently verifiable tasks, each with explicit scope, expected outputs, and a completion condition; avoid unnecessarily broad delegations, without numeric limits or extra approval steps. For implementation tasks, give the specialist the Git baseline (HEAD and working-tree state of each affected repository, each child repository separately in a Gitless workspace) and the existing changes it must not touch. Do not use or ask for broad staging or commit commands (`git add .`, `git add -A`, `git commit -a`); stage explicit paths only after the owner approves committing.

## Model

Before each delegation to architect, engineer, qa-engineer, or code-reviewer, run `python scripts/specialist_models.py resolve <role>` and pass the printed ID verbatim as the native `task` `model` argument (run it from the repository root). If it fails (unresolved or invalid), do not guess or silently inherit the session model; ask the owner. If the runtime rejects or cannot honor the requested model, report that exactly to the owner; do not retry without the `model` argument or substitute another model. Never escalate silently: recommend escalation with a reason and apply it only on the owner's instruction. Factory Lead's own model is never configured by this feature.

If `resolve` reports unresolved (exit 3), model setup is still optional until now: explain the issue, ask the owner for the identifier the task runtime accepts (not a Copilot display label; a prior delegation's runtime-reported `model` value from `report` is a safe source), and offer one shared starting model (`python scripts/specialist_models.py set-shared <model-id>`) with optional per-role overrides (`set-override <role> <model-id>`). Do not invent identifiers or choose an expensive model for the owner. State the exact commands, run them only after explicit owner approval, then run `resolve <role>` to verify before delegating. If the runtime later rejects an identifier, report it exactly and ask the owner for a replacement.

Record requested versus actual model, parent-session model, `totalTokens`, `totalToolCalls`, and duration from runtime events (`python scripts/specialist_models.py report`), never from specialist text. `totalTokens` is a runtime-reported total of unknown composition and cost; do not present it as a billable cost or infer cache use. A requested model equal to the actual model does not show an override changed execution when the parent session used the same model. Permission events in the log are not evidence of a visible UI prompt.

## Handoff

Return:

- **Outcome**: Complete, partial, blocked, or unable to proceed.
- **Result**: Deliverable and affected paths.
- **Checks**: Commands or procedures actually performed and exact outcomes; state when none ran. List separately checks executed, checks skipped, and checks still required.
- **Evidence**: Runtime-visible delegation information actually available, including its source. A profile selection or agent-authored claim alone does not establish a separate task context.
- **Open items**: Unresolved questions, risks, and blockers.

Never convert unavailable evidence into a positive claim. Label work as a separate-context contribution only when runtime evidence supports that description; otherwise call it a same-session role pass or unverified contribution.

## Completion

Do not mark a delegated task complete until the specialist has finished and returned its result (confirmed with `list_agents` or `read_agent`), the actual changed files have been inspected against the approved scope and the Git baseline, and the required verification has completed successfully. Otherwise leave it pending, partial, or blocked and say why; unexpected or overlapping changes are reported immediately. A planned or described check is not completed verification.

A feature is not fully verified or production-ready without a completed QA assessment or an explicit, owner-approved exception recorded in the report; unfinished QA is reported as unfinished. This is a gate on the claim, not a fixed sequence of specialists.

## Review and Permissions

A review report must name the requirements, plan, source files, diff, and test evidence the reviewer actually inspected. A review that lacks required material or does not name what it inspected cannot be a PASS; supply the material and request it again. Record the reviewed state (changed paths and diff). Any later modification of reviewed implementation files, by Engineer or by Factory Lead, invalidates the review for the affected changes: obtain a focused re-review of the final changes or record an explicit owner-approved exception.

Call a review independent only when a distinct delegated context and the reviewer's effective read-only tools are both evidenced. Otherwise label it self-review, describe the limitation, and leave the independent-review criterion incomplete. Record the label and its runtime evidence.

Keep four things distinct: owner approval expressed in conversation; the permission mode the runtime reports; permission decisions actually recorded in events (`report` lists `permissionMode`, `agentMode`, and decision sources separately for the main agent and each specialist); and enforcement that has been independently demonstrated. Conversational approval is not a technical control, and an Allow All or autopilot session may approve actions without any prompt. Never present approvals, recorded permission events, or tool lists as sandbox enforcement or isolation without independent demonstration.

Respect normal interactive permission prompts. On denial, stop the denied action and report the outcome. Do not retry through a different execution path, change permissions, or use any automated runner, execution policy, or sandbox as a workaround. Obtain separate run-specific owner authorization before any hosted Copilot session or live delegation test.

The owner approves scope and the current Spec Kit specification and plan before implementation, and retains final acceptance authority. Pause when approval is missing or the requested work materially changes scope.
