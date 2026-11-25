# Roadmap

This roadmap records work intentionally excluded from the interactive specialist-team first increment. Items require separate scope and owner approval before planning or implementation.

## Deferred After the Interactive Demonstration

- Add dedicated bug-fix assessment and idea-assessment routes while preserving the existing Spec Kit feature workflow and owner approval boundaries.
- Integrate specialist delegation with the factory CLI and runner, if the interactive demonstration establishes a useful need and a supportable design.
- Evaluate any factory execution-policy changes for delegated tasks, including role/phase constraints, child-operation scope, fail-closed behavior, and reviewer tool restrictions.
- Conduct separately authorized Copilot task-payload, Windows sandbox, and compatibility probes before relying on new automated execution paths. Do not treat interactive demonstration evidence as factory-runner or sandbox certification.
- Consider additional reporting or evidence infrastructure only if the existing Spec Kit artifacts and concise delivery record prove insufficient.

## Reliability Backlog from Real-World Use

Source: a deployment rollback feature trial in another application (server and client deployment, rollback, health checks). Spec Factory created specifications, obtained approvals, delegated implementation and invoked Code Reviewer, but the trial exposed workflow reliability gaps. Session evidence is not copied here. Goal: fewer repeated failures per real task, using the smallest instruction and test changes. No new execution engine or orchestration. Items are proposals only; each needs owner approval before implementation.

Status compares the observation with the instructions shipped in v0.1.2: **Exists, not followed** (text already present), **Partial**, or **Missing**. All of these are instruction-level; none is runtime-enforced.

### P0

1. **Delegation completion gate** (Lead marked tasks complete while Engineer was still running). Missing. Lead has `list_agents`/`read_agent`, and specialists return an Outcome state, but nothing says when Lead may mark a task `[X]`; the Spec Kit implement skill only says to mark completed tasks. Change: Lead and `factory-handoff` mark a task complete only after the specialist has finished, its result and changed paths are inspected against the task scope, and verification evidence exists; otherwise record partial or blocked.
2. **Evidence-based review inputs** (Code Reviewer did not inspect the specification or plan). Exists, not followed: Lead already requires giving the reviewer requirements, plan, scope and diff. Gap: nothing requires proof. Change: the reviewer returns the artifacts and diff it actually read and returns blocked if any is missing; Lead does not count a review that omits them. Lead records the independent or self-review label and its evidence (already required) in the delivery report.
3. **Re-review after changes** (Lead edited implementation files after review). Missing. Change: Lead records the reviewed state (changed paths and diff identity); any later change to those files makes the review stale and requires a re-review or an owner-approved exception. Lead's own implementation edits count as changes.

### P1

4. **Task decomposition**. Partial: bounded objective and completion condition exist; nothing says to split by concern. Change: split broad work into independently verifiable units, each with its own completion condition (for example server deployment, client deployment, rollback, health checks), without numeric limits.
5. **QA verification** (QA Engineer never invoked, absence not treated as an exception). Missing; "smallest set of specialists" can be read as permission to skip it. Change: a feature is not reported complete without a QA verification step or an owner-approved exception recorded in the report. Reports separate checks executed from checks planned (the QA profile already separates pass, fail, skipped and unavailable).
6. **Existing-work protection** (pre-existing `.github`/`.specify` changes flagged only at the end). Missing. Change: before the first implementation delegation Lead captures `git status --porcelain` and HEAD (per child repository in workspaces), shows non-empty baselines to the owner, tells specialists those paths are out of scope, never uses broad staging (`git add -A`, `git add .`, `git commit -a`), compares against the baseline at each handoff, and reports unexpected changes immediately.
7. **Permission and approval evidence** (session reported Allow All). Partial: Lead respects prompts and v0.1.2 says permission events do not prove a visible prompt. Missing: conversational approval is not runtime enforcement. Change: state that distinction, report the permission mode when known, and never claim enforcement or isolation without evidence. Optional small helper change: `specialist_models.py report` also summarizes observed `permissionMode` and `agentMode` from permission events.

### Order and verification

- Items 1-6 and the wording in 7 are edits to `.github/agents/factory-lead.agent.md`, `code-reviewer.agent.md`, and `.github/skills/factory-handoff/SKILL.md` (plus bundled copies), guarded by phrase tests in a new unit test file. Guard tests prove the instructions are present, not that they are followed.
- Effectiveness is checked on the next real task against these seven observations.
- Status: items 1-7 and the optional report change are implemented as instruction, helper and test changes in the v0.1.3 release candidate. Phrase tests guard the wording only; whether agents follow it remains to be observed on real tasks.
- Out of scope: runtime enforcement (hooks, policy engines, sandboxing), covered by the deferred execution-policy item above; and removing Lead's `edit` tool, which is an owner decision.

## Ordering and Gates

1. Complete and review the owner-approved interactive first increment, including actual tests, review findings, and disclosed evidence limitations.
2. Reassess the deferred routes and factory integration as separate features with their own specifications, plans, approval gates, and security review.
3. Run security or compatibility probes only with their own explicit authorization and isolated test scope.

Nothing in this roadmap authorizes implementation, hosted runs, policy changes, security probes, or external actions.
