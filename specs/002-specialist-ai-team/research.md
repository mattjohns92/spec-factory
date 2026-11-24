# Research: Specialist AI Development Team

**Feature**: [spec.md](spec.md)
**Date**: 2026-11-20

## Decisions

### Keep the existing Spec Kit feature workflow

**Decision**: Use the repository's existing Spec Kit feature workflow for specification, plan, task generation, and implementation. Do not create another workflow engine or modify factory CLI routing.

**Rationale**: The requested first increment demonstrates collaboration within the current product workflow. Custom bug-fix and idea-assessment routes are deferred.

### Use repository-local Copilot profiles and one handoff skill

**Decision**: Define Factory Lead, Architect, Engineer, QA Engineer, and Code Reviewer under `.github/agents/`. Add `.github/skills/factory-handoff/SKILL.md` for bounded assignments, evidence-bearing handoffs, and accurate delegation labels.

**Rationale**: Copilot's repository customization mechanism provides reusable agent profiles and skills without new orchestration or dependencies. Existing Spec Kit skills continue to own their stages.

### Delegate through the interactive Copilot runtime

**Decision**: The owner starts Factory Lead in a supported interactive Copilot surface. The lead uses native agent delegation as needed and respects normal permission prompts and denials. Do not enable delegation through the factory runner. A separately owner-approved follow-up narrowly updates the existing pre-tool policy for `list_agents`, path-scoped reads, and `task` restricted to `code-review`; write/execute requests are denied by the bounded review policy. The complete runtime tool inventory was not captured.

**Rationale**: The user requested a first demonstration in the native interactive experience and explicitly deferred factory CLI, runner, and sandbox changes. The owner later approved only the bounded hook-policy exception recorded in the plan and quickstart.

### Require evidence for delegation and independent review

**Decision**: A selected profile or same-session role pass is not separate-context delegation. Record available runtime evidence for delegated work. Call review independent only when the reviewer ran in a separate context and had no write-capable tools; otherwise report it as limited.

**Rationale**: The demo must substantiate the collaboration claims. If the surface does not expose adequate evidence, disclose the gap instead of inferring it from agent-authored prose.

### Keep owner approvals explicit

**Decision**: Do not implement the demo feature until the owner approves the current team specification and plan. Select and approve the small demonstration feature and its scope through its own normal feature workflow before its implementation.

**Rationale**: Planning artifacts do not authorize implementation, and the specialist team must not decide its own acceptance or expand scope.

## Deferred Scope

Bug-fix and idea-assessment routes, factory CLI/runner changes, broader execution-policy expansion, separately authorized security and compatibility probes, and related infrastructure are not v1 requirements. Track them in the repository root `ROADMAP.md`.

## Sources

- Repository feature workflow and Spec Kit skills under `.github/skills/`.
- Existing Copilot customization conventions under `.github/agents/` and `.github/skills/`.
- GitHub Copilot CLI documentation: [Creating and using custom agents](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli) and [Command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference).

## Verification Status

This document records design decisions, not runtime validation. At initial research time no Copilot delegation, hosted inference, security probe, factory CLI run, or implementation test had been executed. The later owner-approved hosted follow-up and its limits are recorded in `quickstart.md`.

## T001 Static Convention Check

- `.github/skills/` contains the repository's existing `speckit-*` skills; there were no repository custom agents under `.github/agents/` before this implementation.
- `.specify/init-options.json` and `.specify/integration.json` configure Copilot integration and skills for Spec Kit 1.0.6. Existing workflow assets were not changed.
- Current Copilot CLI documentation identifies `.github/agents/*.agent.md` and `.github/skills/<skill>/SKILL.md` as project discovery locations. Agent profiles support `include-custom-instructions`, `infer`, and explicit `tools`; `strict-tools-list: true` can prevent default tools from being added to a restricted list.
- This was static inspection only. No Copilot session, profile discovery, hosted request, or delegation was started.
