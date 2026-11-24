# Feature Specification: Installation & Project Bootstrap

**Feature Branch**: `main` (existing checkout; no feature branch created)

**Created**: 2026-11-22

**Status**: ORIGINAL LOCAL-INSTALLER SCOPE IMPLEMENTED AND RECORDED; PUBLIC-DISTRIBUTION EXTENSION IMPLEMENTED PROVISIONALLY; FINAL-DIFF REVIEW AND OWNER ACCEPTANCE PENDING. Public release and A6 remain unauthorized.

**Input**: Owner request "Simplify Public Installation" (P0): make the interactive Software Factory installable from a public Python distribution, with guided and non-destructive onboarding inside an existing project, so users do not need the development checkout or manual file copying.

**Numbering**: This is Feature 007. Feature 006 is reserved for QA Reliability & Token Efficiency.

## Owner Decisions (2026-11-22)

- **Q1 — Missing Spec Kit for the local installer: Option A remains unchanged.** The reusable local installation engine refuses before writing if the target lacks a valid Spec Kit Copilot integration. Public onboarding may offer project setup only when it can do so without `--force`; the tested Specify 1.0.6 refuses initialization even in a Git-only project root without that flag. Therefore the current onboarding gives manual setup guidance and refuses to install until validation passes.
- **Q2 — Personal model configuration: Option B.** The installer excludes `.factory/model-preferences.json` through the target's local `.git/info/exclude`: the entry is disclosed in the preview, existing content is preserved, entries are never duplicated, dry runs change nothing, the ignore state is verified before setup is reported complete, failure is safe, and no model ID is created or copied. This is the only permitted modification of an existing file (see FR-016).
- **Portability is a mandatory acceptance gate.** An installed project must operate after the source repository is moved or unavailable, with no reliance on source paths, imports, environment variables or dependencies the target lacks (FR-009, A7).

## Public Installation Revision (2026-11-23)

- **Owner priority**: favor the simplest experience for the developer even when packaging and onboarding require additional implementation work.
- `software-factory` is unavailable: the owner identifies it as another project's PyPI distribution with provenance pointing to `stratonext/software-factory`. Use `specfactory` as a provisional local distribution and primary executable. Run local artifacts with `uvx --from <wheel> specfactory init`; bare `uvx specfactory init` requires a separately approved release. A PyPI 404 was observed for that candidate on 2026-11-23, but this is not a reservation or guarantee of availability. Verify name ownership again before any release. Do not publish, reserve or register a name without separate approval.
- The public command must work from a built distribution without access to this development checkout. The existing installer remains the reusable engine; the new layer provides packaging, onboarding, explicit approval prompts and a guided first-run flow.
- The current source distribution's `factory` command invokes the separate automated factory CLI. The public minimal distribution must neither replace it nor expose it. The provisional package uses the matching `specfactory` executable and provides `uv tool install specfactory` followed by `specfactory init` as the persistent option.
- No PyPI or GitHub publication, repository exposure, push, merge, deployment, or A6 real-project installation is authorized. A separate provenance/security/history audit and explicit owner approval are required before any public release.

## Background (observed in this checkout, 2026-11-22)

- The interactive factory is a set of project files, not an installed package: five agent profiles (`.github/agents/*.agent.md`), the `factory-handoff` skill, `scripts/specialist_models.py` (Feature 005), `scripts/validate_specialist_profiles.py` (Feature 003) and `scripts/check_factory_readiness.py` (Feature 004). The three scripts use only the Python standard library, except the profile validator, which imports PyYAML.
- Spec Kit artifacts (`.specify/**`, `.github/skills/speckit-*`) belong to the Spec Kit Copilot integration, which is a prerequisite for Factory Lead rather than something the factory authors.
- Source-checkout couplings that break portability:
  - `specialist_models.py`, `validate_specialist_profiles.py` and `check_factory_readiness.py` derive their default root or config path from the script's own location.
  - Factory Lead and `factory-handoff` call `python scripts/specialist_models.py resolve <role>`, a path in the target's own `scripts/` namespace.
  - Factory Lead's text refers to "this repository's factory CLI", "this team's Feature 002 artifacts" and a "demonstration feature". These are accurate only in the source repository.
  - The readiness checker needs PyYAML (validation dependency group), and its hook and policy checks are specific to the source's `FACTORY_POLICY_PATH` hook.
  - `.factory/model-preferences.json` is personal and gitignored here; `.github/copilot/settings.local.json` disables hooks locally.
- Features 002–005 explicitly keep the factory CLI, runner, policy hook and sandbox out of the interactive path. Feature 004 (Q1) set the precedent that new capabilities are standalone commands rather than factory CLI changes.

## Portable Asset Inventory

**Installed into the target (managed files)**

| Asset | Why it is necessary | Required adaptation |
|-------|---------------------|---------------------|
| `.github/agents/factory-lead.agent.md`, `architect`, `engineer`, `qa-engineer`, `code-reviewer` (five profiles) | Discoverable team in Chat and CLI; tool restrictions (Code Reviewer read-only) and approval-gate behavior live in these files | Remove source-repo-specific wording (Feature 002 reference, "this repository's factory CLI", demonstration-feature clause) while keeping approval gates, tool lists and strict-tools settings; helper path must resolve in the target |
| `.github/skills/factory-handoff/SKILL.md` | Handoff, evidence and model-resolution rules the profiles depend on | Same helper-path adaptation |
| Model-preference helper (Feature 005) | Factory Lead must resolve a model before every delegation | Default preferences location must be the target's own, not derived from the script's checkout; unchanged behavior otherwise |
| Profile validator (Feature 003) and readiness checker (Feature 004) | Verify the install; reuse required by the request | Default root must be the target; no PyYAML dependency in the target; hook and policy checks must not assume the source's policy hook |
| Install manifest | Small explicit list of managed files, with content fingerprints and the factory source revision, supporting repeat runs, conflict detection and manual removal | New |

**Not installed (excluded)**

| Asset | Reason |
|-------|--------|
| `src/software_factory/*` (factory CLI, runner, policy, preflight, report), `pyproject.toml`, `uv.lock`, `dist/` | Deferred automated-execution path; the interactive workflow does not use it |
| `scripts/factory_pre_tool_use.ps1`, `.github/hooks/factory-policy.json`, `.factory/policy.json`, `.github/copilot/settings.local.json` | Policy hooks, sandbox and one developer's local settings (explicitly out of scope) |
| `scripts/run_engineer_delegation_test.ps1` | Source-repo live-delegation probe |
| `.factory/model-preferences.json` | One developer's personal model IDs; each project creates its own |
| `.specify/**`, `.github/skills/speckit-*` | Owned by Spec Kit and version/integration specific; the target's own constitution, templates and feature pointer must be used. Detected, never copied |
| `.specify/workflows/overlays/speckit/speckit-approval-retry.yml` | Applies to `specify workflow` runs, not interactive Chat; Factory Lead's profile supplies the approval gates. Planning must confirm this classification |
| `specs/**`, `tests/**`, `ROADMAP.md` | Source-repo history and development material |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Install into another repository and use Factory Lead (Priority: P1)

As a developer with an existing Git repository that already has Spec Kit's Copilot integration, I run one documented local command that installs the factory, and then I can pick Factory Lead in VS Code Copilot Chat and have it inspect my project, follow Spec Kit approval gates and delegate a bounded task to the installed specialists.

**Why this priority**: This is the product objective; everything else makes it safe.

**Independent Test**: Install into a disposable Git repository with Spec Kit, open it (not the source checkout) in VS Code, and run the discovery, inspection, approval-gate and delegation checks in the Acceptance Test Matrix.

**Acceptance Scenarios**:

1. **Given** a valid Git repository with Spec Kit and its Copilot integration, **When** the developer runs the install command, **Then** the managed assets are created in that repository, the readiness check runs against it and reports its verdict, and nothing outside the managed assets changes.
2. **Given** the install completed, **When** the repository is opened in VS Code Copilot Chat, **Then** Factory Lead and the four specialists are discoverable by name.
3. **Given** the installed team, **When** Factory Lead is asked to work on a feature, **Then** it uses the target's own Spec Kit artifacts, stops for owner approval of the specification and plan before implementation, and resolves a specialist model from the target's own preferences before each delegation.
4. **Given** the source checkout is moved, renamed or deleted after installation, **When** the installed workflow is used, **Then** it continues to work.

---

### User Story 2 - Preview first, never overwrite silently (Priority: P1)

As a developer, I can see exactly what installation would create, skip or refuse before anything changes, and existing files are never overwritten.

**Why this priority**: The target is someone's real project; trust depends on predictable, non-destructive behavior.

**Independent Test**: Run a dry run against repositories in each state in the Acceptance Test Matrix and confirm the repository is byte-for-byte unchanged afterwards; then run a real install over conflicting files and confirm those files are untouched.

**Acceptance Scenarios**:

1. **Given** any target, **When** the developer runs the preview (dry run), **Then** every managed path is listed with its disposition (create, already identical, conflict) and the target is unchanged, including no manifest or temporary files.
2. **Given** a managed path already exists with different content (for example a developer's own `engineer.agent.md` or a skill of the same name), **When** installation runs, **Then** that file is not modified, the conflict is reported with its path and the reason, other non-conflicting assets are not half-written in a way that breaks the team, and the outcome is reported as incomplete with the next step.
3. **Given** the target has uncommitted changes, existing Spec Kit artifacts, other agents or skills, or its own scripts, **When** installation runs, **Then** all of them are preserved and installation does not stage, commit, reset or otherwise alter Git state.

---

### User Story 3 - Repeatable installation and verification (Priority: P2)

As a developer, I can run installation again at any time and get a safe no-op or a clear report, and I can verify the installed project with the readiness check.

**Why this priority**: Real adoption involves re-runs, partial failures and teammates cloning the repository.

**Independent Test**: Install twice and compare file bytes; delete one managed file and reinstall; modify one managed file and reinstall; run the installed readiness check in a repository without the source checkout.

**Acceptance Scenarios**:

1. **Given** a completed installation, **When** the install command runs again, **Then** nothing changes, no asset is duplicated or reordered, and the outcome says everything is already installed.
2. **Given** a managed file is missing, **When** installation runs again, **Then** only the missing file is created.
3. **Given** a managed file differs from what would be installed (edited by the developer or from another factory revision), **When** installation runs again, **Then** it is reported as a conflict and not overwritten.
4. **Given** the installed project, **When** the readiness check runs from it, **Then** it checks the installed profiles, skill, helper, manifest and Spec Kit configuration, does not require the factory source layout, treats absence of Copilot CLI as informational with VS Code Copilot Chat guidance, and reports `ready with limitations` or `not ready` for other blocking findings.

---

### User Story 4 - Project-local model preferences (Priority: P2)

As a developer, I configure specialist models for this project only, and nothing from the factory author's personal setup is copied.

**Why this priority**: Model availability differs by user; Feature 005 requires preferences to stay local.

**Independent Test**: Install into two repositories, configure different tiers in each, and confirm neither affects the other nor the source checkout; confirm a fresh install resolves nothing until configured.

**Acceptance Scenarios**:

1. **Given** a fresh installation, **When** the developer inspects preferences, **Then** no model ID is preconfigured and the output explains how to set one; an unresolved role makes Factory Lead ask the owner rather than guess.
2. **Given** the developer sets tiers or overrides, **When** Factory Lead next delegates, **Then** it uses that project's file, and changes in one repository do not appear in another.
3. **Given** the preferences file exists, **When** the developer reviews Git status, **Then** it is not presented as a shareable project file, because installation excluded it through the target's local `.git/info/exclude`.
4. **Given** the exclude entry cannot be written or verified, **When** installation runs, **Then** it stops before writing any managed asset and reports how to fix it.

---

### User Story 5 - Public guided installation (Priority: P1)

As a developer in an existing Git project, I can run the Software Factory command from a local or published package, inspect prerequisites and planned changes, separately approve environment setup and factory installation, complete any required Spec Kit project setup manually, and finish with model and VS Code launch guidance.

**Why this priority**: Public distribution and a low-friction first run are required for Feature 007 to be complete.

**Independent Test**: Build the distribution locally, install/run it in an isolated environment from the built artifact only, and exercise guided consent, preview, non-interactive refusal, manual Spec Kit prerequisite, asset install, model guidance and readiness paths in disposable repositories.

**Acceptance Scenarios**:

1. **Given** an existing Git project with valid Spec Kit Copilot integration, **When** the user runs the published command from that project, **Then** it discovers the project root and prerequisites, presents a complete change plan, asks for explicit approval, and invokes the reusable installer using bundled versioned assets without reading the development checkout.
2. **Given** the Specify CLI or its Copilot integration is missing, **When** onboarding inspects the environment and project, **Then** it explains the specific gap, offers the official CLI installation only after separate approval, and directs the user to manual project setup when needed; no installer invocation occurs until validation passes and installation is separately approved. The installer remains independently strict and never installs or initializes Spec Kit itself.
3. **Given** the user approves Specify CLI installation, **When** that action completes, **Then** onboarding rechecks the CLI and project integration; if Spec Kit is still invalid, it stops with manual setup guidance and does not use `--force`, silently repair files, or continue to factory installation.
4. **Given** the user chooses Budget, Balanced or Quality-first guidance, **When** onboarding explains model configuration, **Then** it explains which role tiers the preset uses, requests or documents only user-selected model IDs, does not embed personal IDs in the distribution, and does not silently select a more costly model.
5. **Given** a successful install, **When** onboarding finishes, **Then** it runs installed readiness, reports the result and limitations, and gives concise steps to open the existing project in VS Code Copilot Chat and select Factory Lead.
6. **Given** `--dry-run` or preview mode, **When** onboarding runs, **Then** it detects prerequisites and prints every proposed repository action but changes no project file, Spec Kit state, Git index or refs, and asks no write-triggering follow-up.
7. **Given** automation invokes non-interactive mode, **When** no explicit apply authorization is present, **Then** the command performs a read-only preview and exits without writes. With explicit apply authorization, it may install only when prerequisites already pass; missing or incomplete Spec Kit state is refused with guidance rather than initialized or repaired automatically.
8. **Given** an installed public distribution, **When** the user inspects its commands, **Then** it provides only the distinct `specfactory` onboarding command and neither exposes `factory` nor invokes or bundles the unrelated automated runner from the development checkout.

---

### Edge Cases

- Target path is not a directory, is not a Git working tree root (including a subdirectory of one), or is a bare repository: refuse before any change, naming the problem.
- Target is the Software Factory source checkout itself: refuse; it already contains the assets.
- Local installer: Spec Kit is absent or incomplete, or is installed for a different coding-agent integration only (no valid Copilot integration): refuse before writing anything, report precisely what is missing and give setup instructions; never run `specify` and never modify existing Spec Kit files.
- Public onboarding: missing or incomplete Spec Kit is explained with manual setup guidance. If the Specify CLI is missing, its official installation may be offered as a separate approved environment action; the factory installer is not invoked until the integration validates. Existing Spec Kit files are not overwritten or force-reinitialized.
- A freshly initialized Spec Kit project has no active feature pointer (`.specify/feature.json` is created by the first specification); that is valid, not a failure.
- The target already ignores `.factory/model-preferences.json` through another rule: no exclude entry is added and the preview says so. The target ignores the manifest path `.github/software-factory/install-manifest.json`: refuse before writing, naming the rule. `.factory/model-preferences.json` is already tracked by Git: refuse with corrective guidance (`git rm --cached`), because an exclude rule does not protect tracked files.
- A managed path, its parent directory, or the exclude file is a symlink or junction: report a conflict and never write through it. A destination that appears between the conflict check and the write is never overwritten.
- The local exclude file is missing, lacks a trailing newline, or already holds the entry: create it, preserve existing bytes, or leave it unchanged, respectively.
- Existing files differ from installed files only in line endings (for example after Git `autocrlf`): treated as identical.
- Spec Kit version is outside the readiness checker's documented-supported set: NOT VERIFIED with a warning, not an automatic failure (Feature 004 rule).
- Python is not available on the PATH under the name the profiles use, or is older than the supported minimum: report it as an install-time finding with a next step. Public command execution also requires a supported uv/Python environment; the prerequisite guide must cover installing uv without assuming Python is preinstalled.
- Target has its own `scripts/` directory or a script with a colliding name: the helper's location must not cause a collision with or overwrite of developer scripts.
- `.github/agents` or `.github/skills` do not exist: create them; if they exist with unrelated files: leave those files untouched.
- Target has its own `.github/hooks` or local Copilot settings: left untouched; the installer neither adds hooks nor weakens existing ones.
- File write fails partway (permissions, locked file, full disk): stop, report which paths were written, leave existing files unmodified, and make a re-run complete the remainder.
- Existing manifest is malformed or unsupported: report it and make no changes.
- Windows and POSIX path separators, line endings and read-only files: installed files work on both without changing the developer's existing files.
- Installing into a OneDrive or otherwise synchronized folder: no assumption about file locking beyond ordinary failure reporting.
- Public package name is already claimed, ambiguous, or cannot be verified: do not publish or imply availability; record a proposed alternative name and explicit `uvx --from` invocation for owner approval.
- Built distribution lacks any managed asset, contains personal configuration or unrelated experimental infrastructure, or imports code from the source checkout: fail package verification before a release is considered.
- User declines Specify CLI installation or Software Factory installation: stop cleanly and report no project changes. Invalid Spec Kit is a manual prerequisite.

## Requirements *(mandatory)*

### Functional Requirements

**Command and preview**

- **FR-001**: A single documented local command, run from a Software Factory checkout with an explicit target path, MUST install the interactive factory into a local Git repository. The target MUST NOT need the factory CLI, runner, package or source checkout installed, and the install MUST NOT require network access.
- **FR-002**: The command MUST offer a preview (dry run) that lists every managed path and its disposition and makes no change to the target, including no files, manifest, directories or Git state.
- **FR-003**: Without the preview, the command MUST show the same plan, then perform it, and report each path as created, unchanged or conflict. It MUST NOT silently overwrite, delete, rename or merge any existing file or directory; the only existing file it may change is the local `.git/info/exclude`, by appending one disclosed entry (FR-016, FR-017).
- **FR-004**: The local installation engine MUST validate the target before any change: existing local directory, Git working tree root, not the source checkout, a valid Spec Kit Copilot integration (FR-005), and a readable, supported manifest if one exists. Public onboarding MUST perform its own read-only prerequisite inspection first and MUST NOT invoke the engine until those conditions pass. A failed validation changes nothing and says why.

**Detection**

- **FR-005**: The local installation engine MUST detect Spec Kit state in the target (constitution, templates, workflow, Copilot integration registered with no missing or modified managed files) without modifying it. If the target lacks a valid Spec Kit Copilot integration, the engine MUST refuse before writing any file. Public onboarding MUST report the gap and provide manual setup guidance; it may offer only the separately approved Specify CLI installation described in FR-028. An absent feature pointer is not a defect.
- **FR-006**: The command MUST report existing agents, skills and scripts that collide with managed paths and MUST treat unrelated existing agents and skills as out of scope.

**Assets**

- **FR-007**: The command MUST install exactly the managed assets in the Portable Asset Inventory and MUST NOT install any asset listed as excluded, including the factory CLI, runner, policy hooks, sandbox, probe scripts, personal settings and Spec Kit-owned files.
- **FR-008**: Installed profiles and the skill MUST preserve the source profiles' roles, tool lists, `strict-tools-list` settings, approval gates and evidence rules, including Code Reviewer's exact `read`, `grep`, `glob` tool set, and MUST contain no reference to the Software Factory source repository, its feature numbering or its factory CLI.
- **FR-009**: Installed files MUST work from the target alone: every command they instruct or contain, every default path and every import MUST resolve relative to the target repository root and MUST NOT depend on where the source checkout is or was. The installed tooling MUST run with only the Python standard library and Spec Kit's `specify` where the readiness checker already uses it. After the source repository is moved, renamed or deleted, the installed profiles, skill, helper, validator and readiness checker MUST work unchanged, with no source path, import, environment variable or non-standard-library package (including PyYAML) required.
- **FR-010**: The model-preference helper MUST behave as in Feature 005 when installed, with its preferences file located in the target. The installed workflow MUST NOT collide with a developer's existing script paths.
- **FR-011**: The command MUST write a small manifest listing each managed file, a content fingerprint and the source revision. The manifest MUST be shareable project content at `.github/software-factory/install-manifest.json` and MUST NOT contain personal data, model IDs or absolute paths. The command MUST verify with Git that the manifest path is not ignored, before writing and again before reporting success, and MUST NOT report success if it is ignored.

**Conflict handling and repeatability**

- **FR-012**: When a managed path exists with identical content it MUST be left unchanged; when it exists with different content it MUST be reported as a conflict and left unchanged; when absent it MUST be created. A missing managed file in an otherwise complete installation is recreated without touching other files.
- **FR-013**: When any conflict exists the outcome MUST be reported as incomplete with a nonzero exit status, naming each conflicting path, the difference in kind (different content), and a manual resolution step. The command MUST NOT offer or perform automatic overwrite, backup-and-replace or merge in this version.
- **FR-014**: Running the command repeatedly against the same target and unchanged source MUST produce a byte-identical target after the first run and report no changes.
- **FR-015**: A failure partway through MUST leave every pre-existing file unmodified and MUST be recoverable by re-running the command; new files MUST be written so that an interrupted run cannot leave a truncated managed file that later reads as complete.

**Preservation**

- **FR-016**: The local installation engine MUST preserve all existing project code, Spec Kit artifacts, agent definitions, skills, hooks, local settings, tracked ignore files (`.gitignore`), uncommitted changes and Git history, index and refs. It MUST NOT stage, commit, push, reset, create worktrees or branches, or run network operations. Public onboarding may retrieve its own approved package through `uvx` and may retrieve/install the Specify CLI only after the user separately approves that action; it MUST NOT transmit target project content, and this exception does not authorize publishing. Installation MUST be reversible with ordinary Git practices; the manifest identifies what to remove.
  - **Sole exception**: the target's local `.git/info/exclude` MAY be created or appended to, exactly as FR-017 describes. Existing content of that file is preserved byte-for-byte, and no other existing file may be modified.

**Local preferences**

- **FR-017**: Installation MUST NOT create or copy a model-preferences file or any model ID. It MUST make `.factory/model-preferences.json` ignored by appending one entry for it to the target's local `.git/info/exclude`:
  - the exact entry, and the file it will go in, MUST be shown in the preview (or the preview MUST state the path is already ignored and which rule ignores it);
  - existing exclude content MUST be preserved and the entry MUST NOT be duplicated, including on repeat runs;
  - a dry run MUST NOT create or alter the exclude file;
  - the command MUST verify with Git that the path is ignored before any managed asset is written and before reporting setup complete, and MUST stop without writing assets if the ignore state cannot be established.

**Readiness in the installed project**

- **FR-018**: The Feature 004 readiness check MUST be runnable from an installed project and MUST verify the installed profiles (via the Feature 003 rules), skill, helper, manifest consistency (a missing managed file, or one that differs from its recorded fingerprint, is a FAIL naming the path with a next step, never an intact installation) and Spec Kit configuration without requiring the source layout, PyYAML, `src/software_factory`, `.factory/policy.json` or the source's policy hook. In installed-project mode only, absence of the Copilot CLI MUST be informational with explicit VS Code Copilot Chat guidance; other readiness failures remain blocking. Its verdict vocabulary, read-only behavior, other per-check guidance, unverifiable-limitations list and exit semantics MUST be preserved. Source-checkout readiness MUST retain Feature 004 behavior and pass its existing tests.
- **FR-019**: After a real install, the command MUST run the installed readiness check and report its result; a `not ready` result MUST be reported without rolling back the install.

**Compatibility**

- **FR-020**: The installed workflow MUST work in VS Code Copilot Chat as the primary path. The profiles, skill and helper MUST remain usable from Copilot CLI to the extent already established by Features 002 and 005; any CLI difference MUST be stated as verified, documented or unverified, never assumed.

**Boundaries**

- **FR-021**: The local installation engine and interactive workflow MUST NOT modify or invoke the existing automated factory CLI/runner, policy, pre-tool-use hook or sandbox, or install any experimental/deferred automation. The public distribution MAY add only the minimal package and onboarding entry points required by FR-025–FR-033; it MUST NOT operate a package registry or publish/upload artifacts under this approval. This feature does not add a GUI, update service, auto-updater, plugin mechanism, upgrade or uninstall command. Existing Feature 005 behavior in the source checkout MUST be preserved except for approved portability changes, and the existing root `factory` entry point MUST not be silently repointed to the public interactive package.

**Verification and documentation**

- **FR-022**: Automated tests MUST cover, using disposable repositories and no Copilot session or network: clean repository with fresh Spec Kit, Spec Kit absent or lacking the Copilot integration (refusal, nothing written), Spec Kit present, conflicting agent and skill files, repeat install, missing-file repair, dry-run immutability, invalid targets, partial-write failure, the local-exclude behavior (entry disclosed, appended once, existing content and missing trailing newline preserved, absent file created, already-ignored path, unverifiable ignore state, dry run untouched, repeat run without duplication) and relocation (the installed tooling runs with the source checkout moved or deleted and PyYAML unavailable). Tests MUST assert that excluded assets are absent and that the target's pre-existing files and Git state are unchanged, with `.git/info/exclude` the only pre-existing file permitted to change and only by appending the one entry.
- **FR-023**: Documentation MUST give the install command, preview usage, conflict resolution, post-install steps (configure model tiers, open Chat, select Factory Lead, run readiness), what is and is not installed, and how to remove the installation.
- **FR-024**: Delivery MUST separately report verified behavior, documented expectations and unverified behavior, per Constitution IV and VIII.

**Public distribution and onboarding**

- **FR-025**: The feature MUST provide a package command for guided setup from the target project's working directory. For isolated local build testing, use the provisional distribution/primary executable `specfactory` from the local artifact with `uvx --from <wheel> specfactory init`; bare `uvx specfactory init` requires a separately approved release. The name is not reserved or approved for publication. The final package and executable names MUST be verified for registry availability and collision risk before release, and must match where practical. Public execution MUST NOT require cloning, mounting or manually copying from the Software Factory development checkout.
- **FR-026**: The public distribution MUST bundle the versioned interactive assets and the reusable installer engine, with a deterministic allowlist. It MUST exclude personal configuration/model IDs, Spec Kit-owned target artifacts, source history, repository development tests/specs, and unrelated experimental CLI, runner, hooks, policy and sandbox infrastructure. It MUST NOT expose or replace the existing `factory` command; the provisional executable is `specfactory`.
- **FR-027**: Public onboarding MUST inspect the current directory or an explicit target, validate Git/Python/uv/Spec Kit/Copilot prerequisites and report the exact detected state before proposing writes. It MUST call the same safe installation engine as the local installer; the engine's no-overwrite, conflict, symlink, manifest, `.git/info/exclude`, readiness and recovery guarantees remain authoritative.
- **FR-028**: If the Specify CLI is unavailable, public onboarding MAY offer its official PyPI installation. It MUST describe the command, source and expected environment change, obtain explicit approval, revalidate afterward, and request a separate approval before installing Software Factory. Missing or incomplete Spec Kit/Copilot integration MUST be explained with manual setup guidance; onboarding MUST NOT attempt project initialization when the supported CLI requires `--force`, and MUST never use `--force`, overwrite existing Spec Kit/project files, or treat approval for one action as approval for the next. Non-interactive mode MUST refuse rather than install or initialize Spec Kit. The existing installer MUST continue to refuse invalid Spec Kit state without attempting remediation.
- **FR-029**: Public onboarding MUST provide a fully read-only preview of all proposed project changes. Non-interactive mode MUST never prompt and MUST default to preview-only; applying the Software Factory install requires an explicit command-line authorization (proposed `--yes`, accepted only with `--non-interactive` and not with `--dry-run`). That authorization applies only to the Software Factory install, never Specify CLI installation or Spec Kit initialization. Non-interactive mode MUST refuse missing/incomplete Spec Kit state rather than bootstrap it implicitly. Preview MUST not change target files, Spec Kit state, Git index or refs.
- **FR-030**: Onboarding MUST guide the user through the existing Budget, Balanced and Quality-first presets and explain the role-to-tier mapping. It MUST NOT invent, embed, or silently apply model IDs, select a more costly tier/model without user choice, or alter existing preferences without explicit approval. User-specific preference data MUST remain out of the distribution.
- **FR-031**: After installation, onboarding MUST run readiness against the target, show its actual verdict and limitations, and explain how to open the project in VS Code Copilot Chat and select Factory Lead. Readiness failure MUST be reported without claiming success or silently rolling back installed files.
- **FR-032**: Documentation MUST include supported uv installation/setup paths for users who do not have uv, required Git/Python/Spec Kit/VS Code prerequisites, the public command, exact preview and non-interactive syntax, model setup, troubleshooting, and installation removal. Documentation MUST distinguish the public package path from the local source-checkout installer.
- **FR-033**: Automated package tests MUST build local wheel and source-distribution artifacts and exercise the wheel in a clean isolated environment from the artifact only, with the Software Factory checkout absent from the child process's import/search paths and working directory. Tests MUST prove all required assets are bundled and usable and that personal configuration, source history, tests/specs and excluded runner/policy/hook/sandbox files are absent. They MUST NOT publish or install from a registry.
- **FR-034**: Before any public release, the owner MUST separately approve a provenance/security/history audit and release plan covering distribution ownership/name, packaged contents and dependencies, licenses/provenance, secrets and personal data, build reproducibility, versioning, and release credentials. No name reservation/registration, GitHub publication, PyPI release/upload, push, merge, deployment, or development-repository exposure is authorized by this feature approval.

### Acceptance Test Matrix

Each row MUST be run against a disposable Git repository (except the real project) and its actual outcome recorded in the task record.

| # | Target state | Required outcome |
|---|--------------|------------------|
| A1 | Clean separate Git repository, freshly initialized with Spec Kit's Copilot integration | Assets and exclude entry created; readiness verdict reported and not failed for a missing feature pointer |
| A1b | Git repository without a valid Spec Kit Copilot integration | Refused before any write (including the exclude file) with setup instructions |
| A2 | Existing repository with Spec Kit and Copilot integration, with uncommitted changes | Assets created; Spec Kit files, code and Git state byte-identical; only `.git/info/exclude` appended; readiness verdict reported |
| A3 | Repository with conflicting agent and skill files, and unrelated agents and skills | Conflicts reported, conflicting files untouched, unrelated files untouched, incomplete outcome and nonzero exit |
| A4 | Repeat installation (also after deleting one managed file) | Byte-identical no-op; missing file only is recreated |
| A5 | Dry run on A1–A4 states | Target (including `.git/info/exclude`) byte-for-byte unchanged; report matches what a real run then does |
| A6 | Separate real-world project in VS Code Copilot Chat | See below |
| A7 | **Relocation gate (required)**: after installing into an A2-state repository, move and then delete the source checkout, with no `FACTORY_*` variables, no extra `PYTHONPATH` and PyYAML unavailable | Installed validator, readiness checker and helper run and give the same results as before the move; no reference to the source path appears in any installed file or output |
| B1 | Build wheel and run its public CLI in a clean isolated environment outside the checkout | CLI starts from packaged code/assets; source checkout is not importable or on `sys.path`; no clone or manual copying is used |
| B2 | Valid Spec Kit Copilot project, guided public install | Full plan shown; separately approved actions run; shared installer produces expected result and readiness report |
| B3 | Missing Spec Kit/Copilot integration; run preview or guided onboarding | No target write or installer call; manual setup instructions are shown |
| B4 | Missing Spec Kit/Copilot integration; approve CLI installation if needed | CLI installation is the only setup action; project integration remains a manual prerequisite; no factory install occurs until it validates |
| B5 | Non-interactive without apply authorization; with authorization and valid prerequisites; with missing Spec Kit | Preview-only without authorization; install only when explicitly authorized and prerequisites pass; missing prerequisites fail closed with no writes |
| B6 | Existing Software Factory path conflict, local preferences and all three model presets | Conflicts are preserved; no model ID is bundled or escalated; preset/tier guidance matches Feature 005 |
| B7 | Inspect built wheel and sdist contents and run from wheel outside source | Required versioned assets included; personal config, tests/specs, history and excluded experimental components absent; no registry upload |
| B8 | Specify CLI absent; decline or approve its installation in an isolated test | Decline invokes no installer and changes no project file; approval invokes only the disclosed environment setup action, then rechecks prerequisites; invalid Spec Kit remains a manual prerequisite |

**A6 (real-project acceptance)** requires the owner to name the project and give separate, explicit written authorization for the install and for any hosted Copilot session or live delegation. No real external project is modified before then. It MUST demonstrate, with runtime-visible evidence where available and an explicit "not verified" otherwise:

1. Factory Lead and the four specialists are discoverable in Chat.
2. Factory Lead inspects that project's own code and Spec Kit artifacts.
3. It pauses at the specification and plan approval gates and does not implement without owner approval.
4. It resolves a model from that project's preferences and delegates one bounded task to an installed specialist, with the delegation recorded as in Feature 005 (requested versus actual model, tokens, duration from runtime events).

### Key Entities

- **Managed asset**: A file the factory installs and owns, identified by a repository-relative path.
- **Install manifest**: The explicit, shareable list of managed assets with fingerprints and source revision.
- **Installation plan**: The per-path disposition (create, unchanged, conflict) produced by validation and shown by the preview before anything is written.
- **Target project**: The developer's existing Git repository, which owns every file not in the manifest.
- **Project-local preferences**: The per-project, personal model configuration created by the developer after installation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In A2, a developer goes from the documented install command to Factory Lead selectable in Chat in under 10 minutes, including reading the preview.
- **SC-002**: In every dry run in A1–A4 (including the local exclude file), the target is byte-for-byte identical before and after, and the preview's dispositions match the real run's outcomes for 100% of paths.
- **SC-003**: Across A2–A4, 0 pre-existing files other than the local `.git/info/exclude` are modified, deleted or reordered, that file changes only by one appended entry, and Git HEAD, index and unrelated working-tree changes are identical before and after.
- **SC-004**: A repeat install in a completed target produces zero file changes in 100% of repetitions tested.
- **SC-005**: With the source checkout moved and then deleted (A7), the installed readiness check, helper and profile validation all run in the target and produce the same findings as before the move, in 100% of relocation runs.
- **SC-006**: Excluded assets are present in 0 target repositories in all matrix rows.
- **SC-007**: A6 completes with all four demonstrations evidenced or explicitly labelled not verified, and the owner accepts or rejects the result.
- **SC-008**: The source checkout's existing test suite still passes unchanged, apart from tests intentionally updated for approved portability changes.
- **SC-009**: In B1, 100% of public CLI startup and install behavior uses the locally built artifact, with no source-checkout path available to the child process.
- **SC-010**: In B2–B5, 100% of target-repository writes occur only after the user approves that specific action; previews and declined/unauthorized non-interactive runs produce zero target changes.
- **SC-011**: The built distribution includes every required interactive asset and zero personal configuration, source history, development tests/specifications, or excluded automated runner/policy/hook/sandbox files.
- **SC-012**: No publication, push, merge, deployment or development-repository exposure occurs before separate owner approval and completion of the release audit.

## Assumptions

- The local source-checkout installer remains available for development and requires Python 3.11+, Git, and a valid target Spec Kit Copilot integration. The public command additionally requires uv (which manages its isolated Python environment) and will validate that target-side `python` meets the installed profiles' requirement; the prerequisite guide covers uv installation options.
- The target path is given explicitly and is the repository root; one target per invocation.
- Installed files are left uncommitted in the target working tree for the developer to review and commit; this feature never commits.
- The public distribution uses a minimal packaging/onboarding entry point separate from the existing automated runner package surface. Exact wheel contents and executable names are plan decisions subject to the exclusion requirements and name-availability gate.
- Where installed files live (for example whether the helper lives under `scripts/` or a factory-owned directory) is a plan decision subject to FR-009 and FR-010.
- Upgrading installed files to a newer factory revision is out of scope; differing content is a conflict and is resolved manually (FR-013).
- Interactive Copilot permission prompts are unchanged; the installer asks for no special permissions beyond writing to the target.
