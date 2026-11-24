# Implementation Plan: Per-Agent Model Preferences

**Branch**: Git branch `main`; Spec Kit feature identifier `005-agent-model-preferences` | **Date**: 2026-11-21 | **Spec**: [spec.md](spec.md)

**Status**: OWNER-ACCEPTED WITH DOCUMENTED EXCEPTIONS (2026-11-21) — Option B implemented as planned (per-delegation native `task` `model` argument). See [tasks.md](tasks.md#owner-acceptance-2026-11-21). Sections headed "Historical" are superseded.

## Approved plan (Option B)

Scope: one standalone stdlib script, one local gitignored config, a narrowly scoped Factory Lead and handoff-skill update, unit tests, and short user documentation. No change to specialist profiles, hooks, runner, policy, sandbox or `src/`; no personal profile copies; no router.

1. `scripts/specialist_models.py` implements the contract in [contracts/configuration.md](contracts/configuration.md): preset resolution, overrides, atomic persistence, validation, and `report` over the session `events.jsonl`.
2. [factory-lead.agent.md](../../.github/agents/factory-lead.agent.md) and the `factory-handoff` skill: before each specialist delegation run `python scripts/specialist_models.py resolve <role>` and pass the printed ID as the `task` `model` argument; on failure ask the owner, never guess or silently inherit; recommend but never silently apply escalation; record requested versus actual model (from `events.jsonl`, never specialist text).
3. Tests (`tests/unit/test_specialist_models.py`): preset maps, default Budget, override precedence and clearing, preset change changes resolved IDs, persistence and atomicity, unknown-key preservation, invalid config and IDs, unresolved exit codes, `report` over fixture events (explicit override, inherited, mismatch, missing fields, multiple delegations), and a guard that Factory Lead/skill instructions contain the resolve-and-pass contract while specialist profiles still have unchanged names, tools and reviewer restrictions.
4. Delegation: Engineer implements, QA Engineer verifies, Code Reviewer reviews the actual diff. Each delegation uses the model resolved by the feature itself, recorded in the delivery report.
5. Evidence: live delegation runs under the final configuration, then `report` output compared with the requested models.

Constitution check: Spec Kit foundation kept; owner decision recorded; roles, tools and approval gates unchanged; evidence is runtime-event based; no security infrastructure touched; simplicity retained (one script, no service). Limitation: no cost data beyond tokens and duration.

## Historical (superseded) status and plans

**Former status**: INCOMPLETE — BLOCKED on a supported, observable application path (owner decision 2026-11-21). The global personal-agent-copy helper is rejected and must not be built. The text below, including the P0 interim plan, predates Option B.

## P0 interim plan (superseded)

1. **Verify (done, one probe)**: named parent model, one delegated Engineer task, evidence read from local `events.jsonl`. Result: repository `model` frontmatter was not applied in the running session. See [research.md](research.md).
2. **If a native path is confirmed**, implement the minimum: a small `scripts/` helper with `status`, `apply --preset`, `override` and `clear`; model IDs read from a local, gitignored user config (three tiers, no bundled IDs); `apply` edits only `model` and `model-policy: preferred` on the four specialist files, lists the Git changes first and requires confirmation; `clear` restores the files; validator and unit tests extended for preserved tools, roles and instructions. Engineer implements, QA Engineer writes the tests, Code Reviewer reviews the actual diff; report reviewer independence only if separate context and read-only tools are evidenced.
3. **Blocked now**: no helper, config, presets or profile changes are implemented. Decision needed from the owner: (a) authorize a fresh-session repeat of the frontmatter probe, or (b) approve per-delegation `model` set by Factory Lead from the preset as the application path (native and recorded as `taskModelSource`, but changes the current delegation rule).

## Revised proposal: native delegated-specialist preferences

The owner corrected the product scope: Factory Lead's model is chosen in Chat; only Architect, Engineer, QA Engineer, and Code Reviewer need delegated preferences. The prior main-agent probe does not establish native `task` subagent behavior.

1. Prefer the runtime's existing per-agent subagent settings (`subagents.agents`) and existing custom agent definitions; do not generate or replace personal agent files, add an inference router, or override the task model in the Factory Lead by default. Keep all existing specialist instructions and declared tool restrictions intact.
2. Provide the three preset concepts as user-chosen model mappings across the four specialists: Budget uses the user's Budget tier for QA Engineer and Balanced tier for Architect, Engineer, and Code Reviewer; Balanced uses Balanced for all four; Quality-first uses Quality for all four. All tier names and cost/rework expectations are hypotheses, not model IDs, prices, capability claims, or hard budget controls.
3. Use native per-user configuration and the native UI/CLI where supported. For CLI, [GitHub documents](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-config-dir-reference#configuration-file-settings) per-agent entries and `/subagents`; for VS Code Chat's Copilot harness, whether that settings source is actually loaded, how to select presets without a custom helper, and actual subagent model observability remain NOT VERIFIED. Do not equate documented CLI behavior with Chat evidence.
4. A documentation-only guide for manually applying native preferences does **not** satisfy the original requirements and must not be presented as doing so; it is at most supporting documentation once an automatic, observable path exists. A guide must not claim that changing a preset automatically applies preferences. If one-action preset selection cannot be done natively, return to the owner rather than building anything that stores preferences without applying them.
5. Where a role's native `model` field is used as a repository-level default, preserve its full profile and use a preferred model, not required locking. Verify any model identifiers against the applicable runtime; user-level settings should override only where evidenced. Avoid adding unverified hardcoded identifiers or altering production profiles until approval.
6. Report requested preference, override source, session model, and actual model only where independently observable. Unavailable settings, models, fallback, model precedence and reviewer-effective permissions must be explicitly classified as NOT VERIFIED. VS Code's documented SDK conversion does not forward `strict-tools-list`; static declarations do not establish read-only enforcement.

### Verification gate (outcome recorded; no further probing authorized)

The single owner-authorized native `task` dispatch of the disposable probe succeeded, but exposed no task ID, delegated-context details or model metadata, so the actual and resolved subagent model are NOT VERIFIED. Both disposable probes have been removed. CLI documentation states that an Auto session makes subagents inherit the resolved session model regardless of the agent `model` field; the earlier UI observations were made under Auto and are therefore inconclusive, not evidence that per-agent preferences are unsupported. VS Code Chat's consumption of `subagents.agents`, model precedence, fallback and effective delegated model remain NOT VERIFIED.

Feature 005 resumes when a supported and observable application path exists (for example, documented Chat support for user-level per-subagent settings plus visible actual-model metadata), and the owner approves a new design and any live test separately. A documentation-only guide or a stored-but-unapplied preference file does not satisfy the original requirements and must not be presented as doing so. Until then, selecting a model manually in native Chat is only a per-conversation fallback.

## Summary

Budget, Balanced and Quality-first presets and persistent per-role overrides remain future requirements; they are not implemented. The proposed opt-in helper that generates complete global personal agent profiles is blocked and must not be built under this plan. As the current fallback, the user can manually select an available model in native Copilot Chat for the current conversation; this is not per-agent automatic configuration, a preset implementation, or proof of the effective execution model.

The remainder of this document preserves the previously approved design as historical context, not an instruction to implement it. A different approach requires a future owner decision; no additional model-precedence experiments are authorized.

**Compatibility result**: The owner observed the personal probe discovered in VS Code, but same-ID precedence remains unverified. After its preference was set using VS Code completion to `[model ID omitted] (copilot)`, Chat remained on Auto and the owner observed a subsequent request routed to [model ID omitted]. This did not demonstrate application of the requested preference; it does not prove which same-ID definition took precedence. Delegated-task model precedence and effective reviewer tools also remain unverified. CLI documentation is not proof of Chat behavior.

## Technical Context

**Language/Version**: Python 3.11+, matching the repository.

**Primary Dependencies**: Standard library plus the existing PyYAML validation dependency for safe frontmatter parsing and comparison; no new dependencies. Reuse existing validation logic where it can be parameterized without weakening existing checks.

**Storage**: User-selected local configuration under a user-owned per-checkout directory, outside tracked files; personal native definitions under the Copilot user agent directory. Exact path and resolution rules are in [data-model.md](data-model.md) and [contracts/configuration.md](contracts/configuration.md). No user files are changed during planning.

**Testing**: Python `unittest` with isolated temporary repository and home fixtures; test native preference output, source equivalence, drift, conflict, errors, persistence, no overwrite and partial failure. Separately report any authorized interactive checks.

**Target Platform**: VS Code Copilot Chat using the Copilot harness, and Copilot CLI; Windows-first with portable paths.

**Project Type**: Opt-in local configuration helper, not a factory CLI feature or runtime orchestrator.

**Performance Goals**: Local file operations for five roles; no network or model inference by the helper. No unmeasured latency target.

**Constraints**: No model lock, invented model IDs or price/ranking claims; no edits to hooks, automated policies, factory CLI, runner, or sandbox. No hosted session or live delegation test without separate run-specific owner authorization. Personal agents are global and may shadow same-ID agents in other checkouts: explicit notice and consent are required before applying, and existing unowned files must never be overwritten.

**Scale/Scope**: Three configurable tiers, three preset mappings, five roles, one optional model override per role; a standalone helper, focused tests and user documentation.

## Constitution Check

The constitution remains draft pending ratification; its constraints are applied without amendment.

| Principle | Gate | Assessment |
| --- | --- | --- |
| Spec Kit foundation | PASS | Existing specification, plan, later tasks and native Copilot capabilities; no parallel workflow. |
| Owner authority | PASS WITH GATE | Spec and plan approved with amendments. The bounded Chat smoke test is authorized, but a separate explicit confirmation is required before creating or modifying the personal test file; the full helper remains blocked until the test supports the design. Other hosted tests require separate run-specific authorization. |
| Roles and delegation | PASS | Architect supplied bounded planning input; implementation and review remain subject to approved scope and evidenced permissions. |
| Evidence-based quality | PASS WITH LIMITATIONS | Static tests and interactive evidence are separate. Unverified behavior cannot become a pass, and a blocked required demonstration is reported. |
| Security and permissions | PASS WITH LIMITATIONS | Helper writes only after explicit user action; no overwrites of unowned personal files or changes to security infrastructure. Static declaration does not prove effective permission enforcement. |
| Simplicity | PASS | One helper, native agent profiles, existing validator and local files. No service, router, billing or dashboard. |
| Controlled self-improvement | PASS WITH LIMITATIONS | Hypothesis, baseline, tests and rollback are described; actual cost and permission benefits require evidence, not inference. |
| Traceability | PASS | Evidence categories and Git baseline below, with limitations preserved at delivery. |

Post-test: the automatic personal-agent design did not pass its compatibility gate and is blocked. The table records the earlier design assessment, not an implementation approval or verified outcome.

## Design

### User choice and native application

1. Define user-owned model slots `budget`, `balanced`, and `quality`; each is a user-supplied runtime model identifier, initially unresolved. No model ID, price, or capability ranking is bundled.
2. Provide preset maps for all roles. Budget maps Factory Lead and QA Engineer to `budget`, and Architect, Engineer, and Code Reviewer to `balanced`; Balanced maps all roles to `balanced`; Quality-first maps all roles to `quality`. This is a documented, unvalidated rework-risk hypothesis, not a guarantee of savings or a claim that a role needs a particular model. Users can choose their own IDs and adjust role choices via overrides.
3. Default to Budget on first use. Guide users to find model identifiers available in their native Copilot environment and configure each needed tier. A role override names a user-supplied model ID and remains in effect when changing presets until explicitly cleared. Resolve each role as override first, else its selected preset's tier. Show the resolved requested value or a clear setup instruction for an unresolved value; never show an unresolved preference as applied, silently select an unavailable model, or invent prices.
4. An explicit `apply` action prepares personal `<Copilot user/session directory>` definitions from the current complete repository profiles, inserting/replacing only the `model` field. Source `model-policy: required` or other unsafe/ambiguous inputs block with guidance rather than silently changing restrictions. Use a single string for CLI compatibility. Native model selection remains user-controlled.
5. Before any writes, show the five targets, global same-ID shadowing risk and drift/conflict report; require explicit opt-in confirmation. Refuse unowned pre-existing files, symlinks, invalid profiles, unsafe paths, changed managed outputs, unresolved role models, and source inconsistencies. The tool must never adopt, overwrite, or delete an unknown personal profile automatically. Render all five and validate before writing. Record provenance separately. For partial I/O failure, report exactly which files changed and recovery steps; never claim an all-or-nothing transaction without implementing and testing one.
6. Generated personal definitions copy all source metadata and exact instruction body, with only `model` differing. Validate semantic equivalence of all other frontmatter, exact body, and all existing reviewer restrictions. Reuse the repository validator's rules for every source and generated profile; extend/reuse its interface only as needed. Fail closed on parse failures, duplicates, malformed input, unsupported metadata or source/target drift; do not silently normalize away fields.
7. Source profiles can change after generation and native runtimes may continue to load stale personal copies. The helper offers a read-only `status`/preflight that detects source and generated-output drift and instructs the user to reconcile and refresh before use. It cannot intercept native agent execution or guarantee that users perform this check. Refresh never overwrites user edits; removing a managed file requires matching provenance/content and explicit action. Recovery guidance must not destroy user data.
8. Status reports configured preset, per-role override, requested value, file ownership, source drift, target, and whether it has been applied or remains unresolved. It must label model availability, runtime selection, actual model and permission enforcement **not verified** unless directly evidenced. It cannot promise to detect provider-side unavailability offline; provide runtime picker/error guidance and disclose any observable fallback.

This design deliberately avoids hidden session commands, invoking Copilot, user profile writes on install, or a proxy. Personal definitions are global, not checkout-scoped: explicitly report their originating checkout and refuse refresh from a different checkout unless the user safely reconciles it. A user may instead manually configure native preferences while preserving full profiles; this is a documented fallback, not proof that the helper satisfied Chat integration.

### Verification and delivery

- First run the bounded Chat compatibility proof below. Do not generate implementation tasks or build the full helper unless it supports this design.
- Unit tests exercise every preset/role, default Budget, three tier mappings, override precedence and clearing, persistence, unresolved values, malformed input, profile equivalence and exact instructions, reviewer metadata, source drift, user-edited/foreign targets, two checkouts, symlinks, interrupted writes, and unchanged unrelated files. No real home profiles are used in automated tests.
- Validate the written native `model` value for all five roles and every preset, not merely the stored configuration. Test preservation of unknown metadata, the reviewer's exact tool list and strict flag, and every role body.
- Validate documentation guidance against current official references and report that provider availability cannot be proven offline. For actual environment behavior, seek separate run-specific approval for hosted/live tests; distinguish active-agent versus delegated-agent checks, requested and observed model, fallback, and runtime-effective reviewer permissions. If not authorized or observable, mark NOT VERIFIED.
- Following owner plan approval, generate Spec Kit tasks. Delegate bounded Engineer, QA Engineer, and Code Reviewer work through native task only where supported and authorized. Give review the approved spec, plan, accepted scope and actual diff. An independent review requires evidence of both a separate context and effective read-only tools; otherwise label self-review.
- The final report must preserve all four evidence categories required by FR-015 and distinguish documentation-supported, fixture-tested, live-observed, and unknown behavior. No commits, pushes, merges or deployments without separate authorization.

### Compatibility-first gate

The owner authorized one bounded, reversible VS Code Copilot Chat smoke test on 2026-11-21. The owner subsequently reported the results above and stopped this implementation approach. No further model-precedence experiments are authorized. The following paragraphs describe the historical test protocol.

After explicit confirmation, create only the exact disposable repository and personal definitions with the same ID and distinguishable harmless markers. Inspect the active Copilot Chat customization source or other runtime-visible evidence first with the repository definition and then with both definitions; record source selection, actual harness/version and the observed precedence. Where the UI visibly exposes the selected model, compare it with a user-supplied available preference; the declaration and an agent's self-report do not prove the actual model used. Remove only exact artifacts created by the test after checking they have not been independently changed; do not remove pre-existing content. If no UI/source evidence is available, mark precedence NOT VERIFIED and stop before the full helper. Personal precedence failing likewise blocks the helper. Smallest fallback: user manually selects a complete repository agent and chooses a model in Chat; this is a limitation, not fulfillment of automated per-agent presets.

VS Code's [agent file reference](https://code.visualstudio.com/docs/agents/reference/custom-agent-file-reference) states `strict-tools-list` is not forwarded when agent files are converted to SDK custom-agent configuration. Preserve the declaration, but do not claim effective read-only enforcement without runtime evidence.

### Git safeguard and baseline

At planning inspection on 2026-11-21, actual Git HEAD was `481aca7ba8e26a512461070294eae2498f731d4a` on `main`; staged and unstaged tracked changes were empty. Untracked files were this feature's `spec.md`, `checklists/requirements.md`, and the newly initialized `plan.md`; later planning artifacts are also untracked. The ignored `.specify/feature.json` was changed in the prior turn to select Feature 005 and is not shown in normal Git status.

The previous turn observed 20 staged paths. Reflog shows HEAD advanced at 13:29:02 to commit `481aca7` and the commit's changed-path list matches all 20 previously staged paths, explaining the staging-state change. All tracked files now match HEAD. The prior turn did not record staged blob IDs or a staged diff, so byte-for-byte identity of the earlier staged content with the commit cannot be independently established; do not claim stronger proof. No work was reset or discarded. Recheck all five required Git facts immediately before implementation because this is a shared checkout.

## Project Structure

### Documentation

```text
specs/005-agent-model-preferences/
  spec.md
  plan.md
  research.md
  data-model.md
  contracts/configuration.md
  quickstart.md
  checklists/requirements.md
  tasks.md                       # only after plan approval
```

### Proposed source and tests

```text
scripts/configure_specialist_models.py     # new opt-in local helper
scripts/validate_specialist_profiles.py    # reuse or narrowly extend validation
tests/unit/test_specialist_models.py       # new fixture-based tests
tests/unit/test_agent_profiles.py          # extend if validator interface changes
```

Document use in an existing appropriate user guide or a narrowly scoped new guide, without altering unrelated workflows. No agent role or security-control changes are planned.

**Structure Decision**: One standalone maintenance helper mirrors the existing profile validator and avoids changing the factory CLI. The exact command and configuration contract is in [contracts/configuration.md](contracts/configuration.md).

## Complexity Tracking

No constitution violations are proposed. Estimate: **moderate**, approximately one helper, one focused test module, possible narrow validator changes and documentation. Cross-platform safe writes, personal-file ownership, drift and runtime compatibility are the main complexity drivers. If these safeguards or native application cannot be delivered simply, return to the owner rather than weaken them.
