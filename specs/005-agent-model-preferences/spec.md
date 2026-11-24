# Feature Specification: Per-Agent Model Preferences

**Feature Branch**: `main` (existing checkout; no feature branch created)

**Created**: 2026-11-21

**Status**: OWNER-ACCEPTED WITH DOCUMENTED EXCEPTIONS (2026-11-21). Option B (per-delegation native `task` `model` argument set by Factory Lead from a local preset configuration) is implemented and runtime-verified. See [tasks.md](tasks.md#owner-acceptance-2026-11-21) for the exceptions and lessons. Everything under "Historical" headings is superseded and retained only as a record.

**Input**: Owner request for configurable specialist model preferences, cost-aware presets, and evidence of the existing Spec Kit and specialist workflow in VS Code Copilot Chat, while preserving reasonable Copilot CLI compatibility.

**Scope correction, 2026-11-21**: Model preferences apply to delegated Architect, Engineer, QA Engineer, and Code Reviewer only. The user selects Factory Lead's model in Chat; requirements below that mention five configurable roles or a Factory Lead preset mapping are superseded for this revision. Preserve Budget, Balanced, and Quality-first for the four specialists, as hypotheses rather than proven cost or quality rankings. A new design and any implementation require owner approval; no global copies of specialist profiles.

## Approved design (Option B, 2026-11-21) — current requirements

**Mechanism evidence** ([research.md](research.md)): the source records one owner-authorized, read-only delegation where the explicit native task model argument was observed in runtime evidence, while repository model frontmatter was not effective in that session. Model identifiers, session IDs, and usage telemetry are omitted from this public copy. This single-session result is not a general compatibility guarantee.

**Requirements**

- **FR-A1** Architect, Engineer, QA Engineer and Code Reviewer each resolve to an independent model ID. Factory Lead's model remains the user's Chat selection and is never configured here.
- **FR-A2** Presets: Budget (initial default: QA Engineer uses the `budget` tier; the other three use `balanced`), Balanced (all `balanced`), Quality-first (all `quality`). The user supplies the model ID for each tier; none is bundled. Tier names are cost hypotheses, not verified price or quality rankings.
- **FR-A3** Per-agent overrides persist across preset changes until cleared. Resolution: override, else the preset's tier ID, else unresolved.
- **FR-A4** Configuration is a local, gitignored file (`.factory/model-preferences.json`), read at every delegation. An invalid file is an error and is never silently rewritten.
- **FR-A5** `scripts/specialist_models.py` inspects and changes the configuration (`status`, `resolve`, `set-preset`, `set-tier`, `set-override`, `clear-override`) and reports requested versus actual models from the session `events.jsonl` (`report`).
- **FR-A6** Factory Lead runs `resolve <role>` before each specialist delegation and passes the result as the native `task` `model` argument. Changing a preset therefore changes subsequent task calls. If a role is unresolved, Factory Lead does not guess or silently use the session model; it asks the owner.
- **FR-A7** No silent escalation: Factory Lead may recommend a stronger tier or override with a reason, and applies it only on the owner's instruction.
- **FR-A8** Specialist profiles, tool restrictions, security hooks, runner, policy and sandbox are not changed. No personal profile copies or model router.
- **FR-A9** Requested and actual models are distinguished. The actual model, `taskModelSource`, `modelSelectionSource`, tokens and duration come only from runtime events, never from specialist text. If the runtime rejects or cannot honor a model, report it; do not substitute.

**Limitations to state in delivery**: the user-supplied ID must be accepted by the `task` tool (the tool lists a fixed set; an unlisted ID is rejected by the runtime, not by this feature); `assistant.usage` and price data are not in `events.jsonl`, so cost is reported as tokens and duration only; model quality and efficiency claims need observed outcomes (completion, retries, corrections), not assumptions; Code Reviewer's effective read-only enforcement is evidenced only by the runtime-reported tools list for the delegated agent.

## Historical (superseded) — earlier requirements and user stories

Everything below this heading predates the owner's Option B decision. Where it mentions five roles, a Factory Lead mapping, personal profile copies, a `model-policy` or frontmatter application path, or blocked/unverified status, it is superseded by the Approved design above.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose cost-aware preferences (Priority: P1)

As a Software Factory user, I can select Budget, Balanced, or Quality-first preferences for all five specialist roles and adjust any individual role without changing shared repository files, so I can match the team to my own priorities and available models.

**Why this priority**: Per-role choice and a useful default are the core product value.

**Independent Test**: Select each preset in turn, inspect the preference for every role, then override one role locally and verify the other four retain the selected preset's preference.

**Acceptance Scenarios**:

1. **Given** a fresh user configuration, **When** the user inspects the active preset, **Then** Budget is the default and preferences for all five roles are visible or explicitly identified as needing user configuration.
2. **Given** any of the three presets, **When** the user selects it, **Then** its preferences apply to Factory Lead, Architect, Engineer, QA Engineer, and Code Reviewer without changing their role responsibilities.
3. **Given** a selected preset, **When** the user overrides one role locally, **Then** that role's requested preference reflects the override, the other four remain unchanged, and shared repository files need not be edited.
4. **Given** a user clears an override, **When** the preference is inspected, **Then** the affected role returns to the selected preset's preference.
5. **Given** model availability and pricing differ between users, **When** users inspect the presets, **Then** the basis and limitations of each choice are explained without presenting unverified prices, model identifiers, or capability rankings as fact.
6. **Given** configured, available role preferences, **When** the user applies a preset or override using the supported path, **Then** the native Copilot agent configuration requests those preferences; recording desired values alone is insufficient.
7. **Given** a personal definition replaces a repository profile, **When** the user applies or refreshes preferences, **Then** the complete effective specialist profile is preserved and validated, including instructions and tool restrictions, with conflicts or drift surfaced before an existing definition is overwritten.

---

### User Story 2 - Understand model selection and limitations (Priority: P1)

As a user, I can tell what was requested, what is known to have run, and what to do when a preference cannot be used, without mistaking a preference for a guarantee or a spending limit.

**Why this priority**: Misleading model and cost claims would undermine the feature.

**Independent Test**: Exercise an available preference, a missing or unavailable preference, and a case where the effective model is not observable; compare the guidance with the runtime evidence.

**Acceptance Scenarios**:

1. **Given** a role has a preference, **When** a user inspects a task's selection, **Then** the requested preference is distinguishable from the actual model, and the actual model is reported only when supported by observable evidence.
2. **Given** a preference is missing, invalid, unavailable, or not supported by the selected runtime, **When** the user tries to use or configure it, **Then** the user receives a clear explanation and an actionable next step; any fallback is disclosed rather than presented as the requested model.
3. **Given** the runtime does not expose the effective model or selection precedence, **When** the user inspects the result, **Then** the unknown is explicitly labeled not verified.
4. **Given** a user selects Budget, **When** the cost guidance is consulted, **Then** it describes the goal of reducing the total cost of successful tasks, including retries, and does not promise a hard spending cap or universally lowest cost.

---

### User Story 3 - Use the existing workflow in both environments (Priority: P2)

As the owner, I can evaluate the feature through VS Code Copilot Chat and understand the compatibility of the same specialist workflow with Copilot CLI, while keeping approvals and permissions intact.

**Why this priority**: The feature is also an integration exercise, not merely a configuration change.

**Independent Test**: Inspect the recorded Chat delegation, approval decisions, implementation handoffs, QA evidence, actual-diff review, and compatibility checks; classify unsupported or unobservable behavior as a limitation rather than a pass.

**Acceptance Scenarios**:

1. **Given** this feature's specification or plan is not approved, **When** work reaches the respective gate, **Then** the team pauses for explicit owner approval and does not start implementation.
2. **Given** an approved specification and plan, **When** the team works in VS Code Copilot Chat, **Then** native delegation to Engineer, QA Engineer, and Code Reviewer is demonstrated where supported, with bounded assignments and actual returned results; unavailable capabilities are reported precisely.
3. **Given** an implementation diff exists, **When** the reviewer is assigned, **Then** the review receives the approved requirements, plan, accepted task scope, and actual diff, and reports findings or an explicit no-findings result.
4. **Given** review independence is claimed, **When** the evidence is inspected, **Then** both separate execution context and effective read-only reviewer permissions are evidenced; otherwise the review is labeled self-review with its limitation.
5. **Given** the two supported environments, **When** the owner inspects compatibility results, **Then** the report distinguishes verified behavior from documentation-only expectations and unverified behavior, including parent/session versus delegated-agent model precedence.

### Edge Cases

- A preset or role preference has no supported model for the user's entitlement, provider, or environment; identify the unresolved choice and how to remedy it.
- A model previously available is removed or renamed, or the user's access changes; do not silently claim the preference ran.
- A preset is selected after a local override exists; the override remains effective until cleared.
- User-selected parent/session model, delegated role preference, and runtime defaults conflict; document and test precedence where observable, otherwise report it as unverified.
- The runtime picks a different model or omits model identity; never infer actual model identity from the declared preference or the task result alone.
- One environment cannot support an equivalent preference or override; explain the difference and any supported user action without claiming cross-environment parity.
- The reviewer profile declares restricted tools, but runtime-effective permissions cannot be observed; do not infer enforcement from configuration alone.
- Personal agents with matching identities can shadow repository profiles; a model-only personal definition must not displace a complete role profile.
- A user-owned personal profile or generated profile differs from its tracked source; report the conflict or drift and require reconciliation rather than silently overwrite it.
- An approval, permission, or required verification is denied or unavailable; stop the affected action and report the limitation without bypassing safeguards.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to express an individual model preference for each of the five existing roles, without locking the role to a required model.
- **FR-002**: The feature MUST provide selectable Budget, Balanced, and Quality-first presets covering all five roles, with Budget selected by default for a fresh configuration. Any preference that cannot be responsibly specified MUST be visibly marked as requiring user input.
- **FR-003**: Users MUST be able to set, change, and clear individual role overrides without changing shared repository files. A role override takes precedence over its preset until cleared.
- **FR-004**: Preset guidance MUST explain the intended trade-offs and seek to reduce total cost of successful work, including expected rework, rather than simply identifying the least expensive model. It MUST NOT assert a demonstrated cost saving or optimal ranking without supporting evidence.
- **FR-005**: Model choices and guidance MUST NOT hardcode unverified identifiers, prices, or capability rankings; they MUST account for differences in provider, entitlement, model availability, and user priorities as far as the runtime permits.
- **FR-006**: The feature MUST explain the requested preference and, when observable, the actual model used. A missing effective-model observation MUST be labeled not verified; a preference or role selection alone is not proof of the effective model.
- **FR-007**: Missing, invalid, unsupported, or unavailable preferences MUST be explained with actionable guidance. Any observable fallback MUST be disclosed; unavailable evidence MUST NOT be converted into a success claim.
- **FR-008**: User guidance MUST explain that preferences are not guaranteed model selection or hard budget enforcement unless the underlying runtime actually establishes those capabilities.
- **FR-009**: The feature MUST favor native Copilot capabilities, remain provider-agnostic where practical, and avoid a custom inference gateway, model router, billing engine, orchestrator, or dashboard.
- **FR-010**: The existing specialist roles, instructions, approval gates, and tool restrictions MUST be preserved; existing security hooks, automated execution policies, runner, and sandbox MUST NOT be modified for this feature.
- **FR-011**: Compatibility findings MUST cover VS Code Copilot Chat and Copilot CLI, including supported preference fields, user override behavior, unavailable models, and parent/session versus delegated-agent selection precedence. Each finding MUST identify whether it is supported by documentation, a directly observed check, or remains unverified.
- **FR-012**: The team MUST use the existing Spec Kit artifacts and obtain separate explicit owner approval of this specification and the current implementation plan before implementation or task execution.
- **FR-013**: In VS Code Copilot Chat, Factory Lead MUST demonstrate a useful bounded native Architect research delegation during discovery and, after approvals, native Engineer, QA Engineer, and Code Reviewer delegation where supported. The record MUST include the actual invocation and returned result or the precise limitation.
- **FR-014**: QA MUST report actual checks and outcomes. Review MUST examine the actual implementation diff against the approved requirements, plan, and task scope, with reviewer permissions remaining read-only. Independent review MUST be claimed only when separate context and effective read-only permissions are both evidenced.
- **FR-015**: Delivery MUST separately identify evidence for delegation, actual model identity, separate specialist execution, and effective reviewer permissions; unsupported or unobserved claims MUST be marked not verified.
- **FR-016**: The owner retains final acceptance, and commits, pushes, merges, and deployments require separate authorization. No worktrees are required and unrelated uncommitted changes MUST be preserved.
- **FR-017**: Preset selections and per-role overrides MUST have a practical supported path to influence native Copilot agent model preferences. A configuration that merely records desired models without such a path does not satisfy this requirement. Unsupported environments MUST be identified and the smallest viable alternative explained.
- **FR-018**: Personal overrides MUST NOT replace or weaken specialist instructions or tool restrictions. If personal definitions are generated or modified, the complete effective profile MUST be preserved and validated, including all role instructions and existing fields; Code Reviewer's declared read-only configuration MUST remain intact. Existing personal definitions and profile drift MUST be handled without silent overwrites.
- **FR-019**: Before implementation, the team MUST report current Git HEAD, staged changes, unstaged changes, untracked files, and whether previously staged content remains intact, including the evidence limits of that determination. The unexpected staging-state change MUST be investigated without changing or discarding existing work.
- **FR-020**: First-run guidance MUST explain how to configure model identifiers available to the user. An unresolved model MUST provide a clear setup instruction and MUST NOT be reported as applied.
- **FR-021**: Before full helper implementation, a bounded disposable test MUST establish same-identifier personal-agent precedence in the actual VS Code Copilot Chat harness. If precedence fails or cannot be established, the team MUST stop before building the full helper and report the limitation and smallest viable Chat alternative. Creation or modification of the personal test agent requires explicit confirmation.
- **FR-022**: The Budget preset MUST map Factory Lead and QA Engineer to the Budget tier, and Architect, Engineer, and Code Reviewer to the Balanced tier. Balanced maps all roles to Balanced; Quality-first maps all roles to Quality. These mappings are hypotheses, not proven cost or quality rankings.

### Key Entities

- **Specialist role**: One of the five existing agents with a distinct responsibility and a configurable preference.
- **Preset**: A named collection of per-role preferences and the rationale and limitations associated with them.
- **User override**: A user-controlled preference for one role that supersedes the selected preset until removed.
- **Selection evidence**: A record distinguishing requested model, observed actual model, environment, source of evidence, and unknowns.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All five roles have an inspectable preference or explicit user-action-needed status under each of the three presets, with Budget selected initially.
- **SC-002**: In tests of each of the five roles, setting and clearing an override changes only the intended role's effective requested preference and requires no shared repository-file edits.
- **SC-003**: All tested missing, invalid, unsupported, and unavailable preference cases provide an actionable explanation and never identify an unobserved actual model as known.
- **SC-004**: The delivery evidence records outcomes for both environments and separately classifies all four evidence categories in FR-015, including any not-verified items.
- **SC-005**: All owner approval gates are recorded in order; no implementation begins before both approvals, and the owner makes the final acceptance decision.
- **SC-006**: For each supported native delegation requested by FR-013, a bounded assignment and returned result are recorded; each unsupported or unobservable case has a specific limitation rather than a passing claim.
- **SC-007**: For every configured role, a test verifies that applying a selected preset and an override reaches the native preference surface; recorded-only configuration does not pass.
- **SC-008**: All generated or modified personal profiles in preservation tests retain the complete source profile except for the intended preference, and all tested conflicts and drift are reported before overwriting. Reviewer read-only declarations remain intact.
- **SC-009**: Before implementation, the Git safeguard report includes the five facts required by FR-019 and identifies any uncertainty about previously staged bytes.
- **SC-010**: First-run checks show setup guidance for every unresolved model, and no unresolved choice is described as applied.
- **SC-011**: The compatibility gate records evidence of Chat's same-identifier profile precedence, or the helper remains unbuilt with the limitation and alternative reported.

## Assumptions

- Users have their own Copilot access and model availability; no specific model or price is assumed to be universally available.
- A preset expresses a preference, not a promise of selection, measured savings, or billing control. Users retain control over choices.
- The owner has authorized the bounded Architect discovery delegation requested in this session; later hosted sessions or live delegation tests still require separate run-specific authorization where applicable.
- Existing unrelated work is not part of this feature and will remain intact. Planning is authorized; implementation requires separate owner approval of the plan.
- Verification of runtime-dependent features may be limited by observable evidence and normal interactive permissions; limitations must be reported rather than worked around.

## Discovery Evidence

- The owner approved this specification with the amendments recorded in FR-017 through FR-019 on 2026-11-21 and authorized planning only. This approval does not authorize implementation.
- On 2026-11-21 the owner approved the plan with amendments recorded in FR-020 through FR-022, authorized a bounded reversible Chat compatibility test with explicit confirmation required before personal-file creation, and conditioned full helper implementation on successful compatibility evidence.
- Factory Lead is operating through the Copilot SDK in VS Code and inspected the five existing agent profiles, the specialist validator and its unit tests, the Spec Kit constitution and template, and the existing feature specifications. This establishes local project inspection, not proof of a particular Chat UI state or model.
- The repository validator currently checks profile frontmatter, required name and description, and the reviewer's strict `read`, `grep`, and `glob` declaration. Its tests cover these rules; neither the declaration nor static validation establishes runtime-effective reviewer permissions.

### Architect delegation record

A bounded delegated research handoff is recorded in the source. Session identifiers and raw handoff/session output are omitted from this public copy; the technical compatibility limitations remain documented below.
### Official documentation inspected by Factory Lead

The following are documentation findings inspected on 2026-11-21, not live verification of this session:

- The [VS Code custom-agent reference](https://code.visualstudio.com/docs/agents/reference/custom-agent-file-reference#_model-preferences) describes `model` as a string or ordered list of alternatives, with the first available model used on agent selection and the selected model used when omitted. `model-policy` defaults to preferred rather than required. The same reference distinguishes Local subagent selection behavior from other harnesses; do not assume Local rules apply to the Copilot harness.
- [VS Code custom agents](https://code.visualstudio.com/docs/copilot/customization/custom-agents) says users can choose another model unless the agent uses `model-policy: required`. [VS Code subagent guidance](https://code.visualstudio.com/docs/agents/run/subagents) identifies native `task` for the Copilot harness and cautions that harnesses differ; a read-only instruction alone does not enforce a permission boundary.
- The [GitHub custom-agents configuration reference](https://docs.github.com/en/copilot/reference/custom-agents-configuration) describes `model` as a string and says that omission inherits the default model. This differs in documented type from the VS Code reference and needs compatibility verification rather than a parity assumption.
- [GitHub's CLI custom-agent guide](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli) gives a provider-qualified local model example and explains that `model-policy: required` enforces that configured model. This feature explicitly excludes required locking.
- Parent/session versus delegated-agent model precedence in the Copilot harness, behavior for unavailable preferences in the actual environments, effective model observability, and effective reviewer permissions remain **not verified**. No live CLI or hosted-session test was performed.
