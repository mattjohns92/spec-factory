# Implementation Plan: Installation & Project Bootstrap

**Branch**: Git branch `main`; Spec Kit feature identifier `007-installation-bootstrap` | **Date**: 2026-11-22 | **Spec**: [spec.md](spec.md)

**Input**: Original local installer spec approved with amendments on 2026-11-22; public onboarding extension requested 2026-11-23.

**Status**: ORIGINAL INSTALLER PLAN IMPLEMENTED AND RECORDED. REVISED PUBLIC-DISTRIBUTION PLAN APPROVED WITH AMENDMENTS (owner, 2026-11-23); implementation authorized within scope. Accepted Feature 002–005 behavior and existing implementation evidence must be preserved. A6 and all publishing/release actions remain unauthorized.

## Final Amendments (2026-11-22)

1. **Manifest location**: `.github/software-factory/install-manifest.json`, not inside `.factory/`. Before reporting success the installer verifies with Git that it is not ignored (checked before any write as well; an ignored manifest path is refused). Personal preferences stay in `.factory/model-preferences.json`, locally excluded.
2. **Integrity**: a managed file whose fingerprint differs from the manifest is a readiness **FAIL** naming the path and next step; a modified file is never presented as an intact installation.
3. **Non-destructive writes**: final creation is exclusive and cannot overwrite a destination that appears after the conflict check; symlink or junction path conflicts are refused; if `.factory/model-preferences.json` is already tracked by Git the installer refuses with corrective guidance instead of claiming the exclude protects it. Focused tests cover each.

## Summary

The original local installer and its tests are implemented and recorded below; they remain the reusable installation engine and are not to be rewritten or replaced. The approved extension adds a small, isolated public package with a guided `init` command, versioned interactive assets, separate approval for CLI setup and factory installation, and a matching `specfactory init` command for persistent uv tool installation. The local-only provisional distribution/command name is `specfactory`; this is not a reservation or publication. It must not package or dispatch the current `src/software_factory` automated CLI/runner and must not expose the root `factory` command. Package-name ownership remains a release gate.

T001–T025 remain the completed historical record for the local installer and must not be rewritten. New public-distribution tasks are appended below as T026 onward and track only the approved extension.

Evidence behind the design is in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.11+, as in the repository.

**Primary Dependencies**: Standard library only for the local installer and installed tools. The public bootstrap package should also use the standard library unless a justified, reviewed dependency is approved. External executables: `git` (required); `uv`/`uvx` to invoke or persistently install the package; Python 3.11+ for installed tools; Specify CLI for Spec Kit detection and optional CLI installation; VS Code Copilot Chat for use.

**Storage**: Files only. Target installation remains 9 managed files and `.github/software-factory/install-manifest.json`, plus one appended line in target `.git/info/exclude`. Distribution assets are package resources with a deterministic allowlist; no user preferences are packaged.

**Testing**: `unittest`, as in the repository, with disposable Git repositories. Existing local installer coverage remains. New package tests build local artifacts and run the wheel in a clean isolated environment from the artifact only; they do not publish or fetch the Software Factory source checkout. Spec Kit prerequisite/refusal tests use injected tools; no Copilot session or registry access.

**Target Platform**: VS Code Copilot Chat primary; Copilot CLI "reasonable compatibility" as in Features 002 and 005. Windows is the verified platform (the development environment). macOS and Linux are designed for (POSIX paths in the manifest, `shell=False`, no PowerShell dependency in the tools) but unverified until run there; the delivery report must say so. The `python` command name in the profiles is accepted for v1.

**Project Type**: Existing standalone local installer plus an isolated minimal Python distribution for public onboarding. The root development package and its automated runner are not the public interactive distribution.

**Performance Goals**: None beyond local file operations on 10 files and a handful of `git`/`specify` queries (each with the 15 s timeout the readiness checker already uses).

**Constraints**: The local installation engine has no network and does not run `specify init`. Public onboarding does not run project initialization because Specify 1.0.6 requires `--force` even for a Git-only project; invalid Spec Kit state is a manual prerequisite. No `--force`, silent overwrite, cost escalation, commit, push, merge, deployment, registry upload, history exposure, hooks, policy, sandbox or automated runner. No personal model IDs. No worktrees.

**Scale/Scope**: Existing 9 managed files, 1 manifest and 1 exclude entry. The approved extension adds a minimal public package/onboarding command, its bundled asset allowlist, package metadata/build configuration, concise setup documentation and focused tests. No rewrite of the existing installer engine and no work in the excluded automated runner/policy/hook/sandbox path.

## Constitution Check

| Principle | Gate | Assessment |
| --- | --- | --- |
| I Spec Kit foundation | PASS WITH GATE | Spec Kit remains the workflow; the reusable installer and public onboarding refuse invalid integration. Public onboarding may install the Specify CLI only with action-specific approval and revalidation; project initialization is manual. |
| II Owner authority | PASS WITH GATES | Spec approved. This plan, including edits to accepted files, needs approval. A6 needs the owner to name the project and authorize installation and any hosted session separately. No commit, push, merge or deploy. |
| III Roles and delegation | PASS | Implementation will use bounded Engineer, QA Engineer and Code Reviewer tasks under the existing handoff rules. Independent review is claimed only with evidence. |
| IV Evidence-based quality | PASS | Observable acceptance matrix A1–A7; the relocation test is a required gate; unverified platforms and Copilot behavior are labeled. |
| V Security and permissions | PASS WITH LIMITATIONS | Least privilege: writes only to named paths in a validated target; no network; symlinks never followed; the single permitted edit to an existing file is the disclosed exclude append. No third-party code added. Limitation: Code Reviewer read-only enforcement remains runtime-unverified as in Feature 002. |
| VI Simplicity | PASS WITH GATE | Keep the local engine and add only a minimal isolated public distribution; no registry operation or release is included without separate authorization. |
| VII Self-improvement | PASS | Changes to accepted files are listed, tested for unchanged source behavior, and approval-gated; no gate or permission is loosened. |
| VIII Traceability | PASS | The manifest records source revision and fingerprints; the acceptance record is kept in `tasks.md`. |

Re-check after design: no violation. No Complexity Tracking entries.

## Design

### 1. Standalone installation command and usage

```text
python scripts/install_factory.py --target PATH [--dry-run]
```

Run from a Software Factory checkout; the checkout is the source of the managed files. Full contract: [contracts/cli.md](contracts/cli.md). No prompts: the plan is always printed first, and `--dry-run` stops after printing it. There is no `--force`, `--update` or `--uninstall` in v1.

Order of operations (every step before step 5 is read-only):

1. **Validate target**: existing directory; `git rev-parse --show-toplevel` equals the target and it is not bare; not the source checkout; an existing manifest (if any) parses and has a supported `version`; `.factory/model-preferences.json` is not tracked by Git (`git ls-files -- .factory/model-preferences.json` is empty; otherwise refuse with guidance: `git rm --cached .factory/model-preferences.json`, commit that removal yourself, re-run); the manifest path is not ignored (`git check-ignore --no-index`; otherwise refuse and name the rule).
2. **Spec Kit gate (Q1 = A)**: reuse the readiness checker's `check_specify` and `check_speckit` with the feature pointer not required. Failure prints what is missing and directs the developer to the official existing-project guidance, then exits 2 with nothing written. No automatic init or repair is offered because Specify 1.0.6 requires `--force` even for a Git-only project root, and onboarding is prohibited from using it.
3. **Classify** each managed path (section 5) and compute the exclude disposition (section 4).
4. **Print the plan**; stop here for `--dry-run`, or when any conflict exists (exit 1, nothing written, including no exclude change).
5. **Exclude**: append the entry if needed, then verify with Git that the preferences path is ignored; failure exits 1 before any asset is written.
6. **Write** missing managed files with exclusive creation (section 5), then the manifest last.
7. **Verify and report**: re-check that the preferences path is ignored and the manifest is not (a failure here exits 1 and is not reported as success), run the installed `scripts/check_factory_readiness.py --root <target>` as a subprocess with the same interpreter, print its output and the next steps (configure model tiers, open Chat, select Factory Lead). Installed but `not ready` exits 3; the installation is not rolled back.

### 2. Installed layout and managed-file manifest

The installed layout mirrors the source, so no path rewriting or templating is needed and installed files are byte copies of source files:

```text
<target>/
  .github/agents/{factory-lead,architect,engineer,qa-engineer,code-reviewer}.agent.md
  .github/skills/factory-handoff/SKILL.md
  scripts/specialist_models.py
  scripts/validate_specialist_profiles.py
  scripts/check_factory_readiness.py
  .github/software-factory/install-manifest.json   shareable; written last
  .factory/model-preferences.json                  personal; created by the developer later; locally excluded
```

The explicit list of managed files is one constant, `MANAGED_FILES`, in the installer; the installer refuses to run if a listed source file is missing. The installed manifest ([data-model.md](data-model.md)) records `version`, `source_revision` (the source's `git rev-parse HEAD`, or `unknown`) and a fingerprint per managed file: SHA-256 of the content with CRLF normalized to LF, so Git `autocrlf` checkouts compare as identical. It contains no absolute paths or personal data. The manifest supports readiness drift detection and removal instructions; it is not an updater.

Why `scripts/` rather than a factory-owned directory: the profiles, skill, tests and accepted Feature 005 behavior all use `python scripts/specialist_models.py`, and the three scripts already derive their default root and preferences path from `Path(__file__).parent.parent`, which is correct in the target. A collision with a developer's identically named script is reported as a conflict and never overwritten. Moving the scripts would change accepted Feature 003–005 files and tests for no functional gain. If a real project shows collisions in practice, that is feedback for a later feature.

### 3. Minimal portability changes to accepted Features 002–005

Each change leaves source-checkout behavior and existing tests passing unless stated. All are submitted for approval with this plan.

| File | Feature | Change | Why |
| --- | --- | --- | --- |
| `scripts/validate_specialist_profiles.py` | 003 | `import yaml` becomes optional. With PyYAML present, behavior is unchanged. Without it, a built-in parser for the exact subset these files use is used: `key: scalar`, booleans, and inline `["a", "b"]` lists. Any other line yields a finding ("unsupported frontmatter syntax; install PyYAML to validate"), never a silent pass. | FR-009: targets do not have PyYAML. |
| `scripts/check_factory_readiness.py` | 004 | (a) Remove the "PyYAML is missing" FAIL branch, now unreachable. (b) `check_speckit` gains `require_pointer` (default true; false when the install manifest exists, and for the installer's gate): an absent `.specify/feature.json` is then acceptable because a fresh `specify init` project has none, while a present but invalid pointer still fails. (c) New `install-manifest` check, run only when `.github/software-factory/install-manifest.json` exists (so source-checkout output is unchanged): manifest valid; every managed file present (FAIL if missing) and matching its recorded fingerprint (**FAIL** if it differs, naming the path, with next step "restore the file from the Software Factory source, or move your edit elsewhere, then re-run the installer"; a modified file is never reported as an intact installation); preferences path ignored per `git check-ignore --no-index` (NOT VERIFIED with "re-run the installer" if not, since a teammate's clone lacks the local exclude). (d) Export `fingerprint()` used by the installer. | FR-018. Hook, policy and Git checks are reused unchanged. |
| `scripts/specialist_models.py` | 005 | **No change.** Default preferences path already resolves to `<root>/.factory/model-preferences.json`. | — |
| `.github/agents/factory-lead.agent.md` | 002/005 | Wording only; tools, `strict-tools-list`, approval gates and the helper command are unchanged. See below. | FR-008: no source-repo-specific text. |
| `.github/skills/factory-handoff/SKILL.md` | 002/005 | One phrase, see below. | Same. |
| the other four profiles | 002 | **No change** (checked: no source-specific references). | — |

Proposed wording edits (current text to replacement):

- Factory Lead, paragraph 1: "coordinate specialist work for this repository" to "coordinate specialist work for this project".
- Factory Lead, paragraph 2: "For a demonstration feature, also require owner approval of that feature's scope, specification, and plan. Approval of this team's Feature 002 artifacts does not approve the demonstration feature or any future feature." to "Approval of one feature, or of the factory's installation, does not approve any other feature; require owner approval of each feature's scope, specification, and plan."
- Factory Lead, last paragraph: "Do not use or modify this repository's factory CLI, runner, execution policies, or sandbox for this feature." to "Do not use or modify any factory CLI, automated runner, execution policy, or sandbox; work only through the normal interactive Copilot experience."
- `factory-handoff`, Review and Permissions: "or use the factory CLI, runner, policy, or sandbox as a workaround" to "or use any automated runner, execution policy, or sandbox as a workaround".

Existing assertions in `tests/unit/test_specialist_models.py` (the `scripts/specialist_models.py resolve` text) and `tests/unit/test_agent_profiles.py` stay valid. One test is intentionally updated: `test_readiness_check.py::test_pyyaml_missing_fails` (the branch is removed; replaced by a test that profile validation passes without PyYAML).

**Approved follow-up compatibility amendment (2026-11-23)**: after the original local-installer scope, the owner approved accepting the Copilot runtime's display-name values in Feature 005 model preferences. `MODEL_ID_PATTERN` allows internal ASCII spaces and parentheses while retaining the 1–200 character limit, alphanumeric first character, safe character allowlist and no trailing space. The helper and bundled copy share the same validator; requested model values remain user-selected, and runtime availability/effective model identity remain unverified outside the bounded delegation evidence.

### 4. Local Git exclude behavior

Entry: `/.factory/model-preferences.json` (anchored to the repository root). Target file: `git -C <target> rev-parse --git-path info/exclude`, resolved against the target.

- **Already ignored**: `git check-ignore -v --no-index .factory/model-preferences.json` exits 0 (any rule, including an existing exclude line). The preview prints "already ignored by <rule>" and nothing is written. `--no-index` keeps the answer independent of tracked files.
- **Otherwise** the preview prints `[exclude] append '/.factory/model-preferences.json' to <path>` and says whether the file or its `info/` directory will be created.
- **Write**: create the directory and file if absent; if the existing content is non-empty and lacks a trailing newline, add one `\n`; append the entry and `\n` with a single append write. Existing bytes are never rewritten. A line already equal to the entry is never appended again.
- **Verify**: re-run `check-ignore --no-index`. Exit 0 is required. Exit 1 (still not ignored, for example because of a later negation rule) or 128/timeout stops the run with exit 1 before any asset is written; an appended line, if any, is reported and left in place.
- **Dry run** performs only the read-only queries; the exclude file is never created or opened for writing.
- **Warn** (does not block) when `git check-ignore --no-index` reports that a managed path other than the manifest is ignored by the target's rules, since it would not be shared. An ignored manifest path is not a warning: it is refused (section 1, step 1).
- **Tracked preferences**: if `.factory/model-preferences.json` is already tracked, the exclude cannot protect it; the run is refused before any write (exit 2) with the `git rm --cached` guidance above. The exclude file itself, if it is a symlink, is refused as in section 5.
- Tests: see section 9.

### 5. Conflict detection, repeat installation and partial-write recovery

Per managed path (and for the manifest), comparing LF-normalized fingerprints and never following symlinks:

| State | Disposition |
| --- | --- |
| Absent | `create` |
| Regular file, same fingerprint | `unchanged` |
| Regular file, different content | `conflict` (different content) |
| The path is a symlink (including a dangling one), a directory or another non-regular file | `conflict` (not a regular file) |
| An ancestor inside the target is a file, a symlink or a junction (its real path is not the expected path under the target's real path) | `conflict` (blocked path) |

The manifest follows the same rules: absent is `create`; present with the same `files` map is `unchanged`; present otherwise is `conflict`.

- **Any conflict means no writes at all** (not even the exclude entry). The run exits 1 listing each conflict with a manual resolution step (compare, merge or move your file, re-run). This avoids a half-installed team.
- **Repeat installation**: with every path `unchanged` and the ignore state satisfied, the run reports "already installed", writes nothing and exits 0 (it still runs readiness). A deleted managed file is recreated alone; a missing exclude entry is re-added.
- **Exclusive creation (no silent overwrite, including races)**: content is first written to a temp file `.<name>.sf-tmp` created with `O_CREAT|O_EXCL` in the destination directory, then published with `os.link(temp, destination)`, which fails with `FileExistsError` if anything (including a symlink) appeared at the destination after the conflict check; the temp is then removed. If the filesystem cannot hard-link, the fallback is `os.open(destination, O_CREAT|O_EXCL|O_WRONLY|O_NOFOLLOW where available)`, writing the content and `fsync`; a failure after creating removes that partial file. `os.replace` is never used on a managed destination. A destination that appears mid-run is reported as `conflict (appeared during installation)`, is left untouched, and ends the run with exit 1; already created paths are listed.
- **Partial-write recovery**: on any error the temp file is removed, the paths already created are listed, and the run exits 1. Because created files then count as `unchanged`, re-running completes the rest. The manifest is written last, so a missing manifest means "incomplete; re-run". Leftover `.<name>.sf-tmp` files for managed names are removed on the next run. Created directories are not rolled back.
- Existing files are never modified (the sole exception is section 4).
- **Hard-crash caveat**: with the no-hard-link fallback, a power loss mid-write could leave a truncated managed file; the next run reports it as a conflict (different content) and never treats it as installed.
- **Reversal**: `git status` shows what was added; the manifest lists the nine files plus itself; to uninstall, delete them and the one exclude line ([quickstart.md](quickstart.md)).

### 6. How the installed readiness checker validates the target

The installed `scripts/check_factory_readiness.py` is the Feature 004 checker with the section 3 changes. It defaults `--root` to the repository containing it, which is the target. It runs the existing checks (Specify and Copilot integration, Spec Kit configuration via `specify integration status --json`, the five profiles and the skill via the validator, hooks, policy information, Git information, unverifiable limitations) against the target's files, plus the `install-manifest` check. The Copilot CLI is optional in installed-project mode because VS Code Copilot Chat is the primary workflow; its absence is informational and does not hide any other failure. Source-checkout behavior remains unchanged. It imports the validator from its own directory; both are installed together, and neither needs PyYAML, `src/software_factory`, `.factory/policy.json` or any `FACTORY_*` variable. Verdict vocabulary, exit codes (0/1/2), the read-only guarantee and the permanent "ready with limitations" ceiling are unchanged. The target's own hooks are checked exactly as before, since a malformed or unsatisfiable target hook genuinely obstructs interactive use.

### 7. Dependencies and supported environments

| Need | Where | Notes |
| --- | --- | --- |
| Python 3.11+ | public bootstrap environment and target | `uvx` must resolve a supported Python for the package; the installed profiles/helpers still require the target's `python` command. Missing/older target Python is reported before install. |
| `uv` / `uvx` | public invocation and persistent install | Public use prerequisite; quickstart links to official installers/package-manager options. Local source-checkout installer remains independent of uv. |
| `git` | target; source only for local installer | Target validation and ignore checks; public manifest revision is package-version based, not checkout-dependent. |
| Specify CLI | target, at detection/readiness; CLI installation optional | 1.0.6 verified. Missing/incomplete project integration is a manual prerequisite because initialization of an existing Git root requires `--force`; onboarding never uses it. Other versions: readiness reports NOT VERIFIED, as in Feature 004. |
| PyYAML | not required | Optional in this repository for the validator. |
| VS Code Copilot Chat | target | Primary workflow; discoverability is proven only by A6. |
| Copilot CLI | target | Optional in installed-project mode; absence is informational with VS Code Copilot Chat guidance. Source-checkout behavior remains as in Feature 004. |
| Operating system | — | Windows verified; macOS and Linux unverified. |

### 8. Separate-project acceptance test (A6)

Not started and not authorized. Prerequisites: all automated tests and A1–A5 and A7 pass; the owner names the project and gives separate written authorization for installation into it and for any hosted Copilot session or live delegation. Procedure:

1. Dry run on the named project; the owner reviews the preview (including the exclude line) and confirms; real install; record the output and `git status` (installed files remain uncommitted).
2. Open the project in VS Code Copilot Chat; confirm Factory Lead and the four specialists are listed.
3. Ask Factory Lead a read-only question that requires inspecting the project's own code and Spec Kit state; record the answer and the files it read.
4. Request a small feature; confirm it follows the Spec Kit specify and plan approval gates and stops for owner approval.
5. After the owner sets model tiers (`python scripts/specialist_models.py set-tier ...`) and approves a bounded task, confirm a native `task` delegation to an installed specialist and record `python scripts/specialist_models.py report` (requested versus actual model, tokens, duration).
6. Classify each result as evidenced or NOT VERIFIED; the owner decides acceptance. Nothing is committed.

### 9. Verification (tests)

New `tests/unit/test_installer.py` and `tests/integration/test_install_workflow.py`, plus additions to existing test files:

- **Installer unit (injected `git`/`specify` runner)**: target validation (not a directory, not a repository root, bare, source checkout); Spec Kit refusal without writes; classification table; no writes on conflict; dry-run immutability; temp-file cleanup and re-run recovery after an injected write failure; manifest content and conflict rules; line-ending equivalence; excluded assets never installed (`MANAGED_FILES` guard); no source paths in installed files.
- **Exclude**: appended once; existing bytes preserved; missing trailing newline; absent file and directory created; already ignored by another rule (nothing written); existing duplicate line not re-added; verification failure stops before assets; dry run leaves the file byte-identical.
- **Validator**: parser parity (PyYAML and fallback give identical results for all six shipped files), fallback rejects unsupported syntax, reviewer tool rules still enforced without PyYAML.
- **Readiness**: absent pointer tolerated only in an installed project; manifest missing-file FAIL, fingerprint drift FAIL (path and next step named; verdict `not ready`), preferences-ignore NOT VERIFIED; missing Copilot CLI informational only in installed-project mode; source-checkout behavior unchanged.
- **Amendment tests (focused)**: manifest at `.github/software-factory/install-manifest.json`; ignored manifest path refused before any write and again verified at the end; tracked `.factory/model-preferences.json` refused with guidance and nothing written (also when only staged); destination created after classification is not overwritten (injected race via a hook between classification and write; also for the no-hard-link fallback); symlink at a managed path, dangling symlink, symlinked or junctioned ancestor directory, and symlinked exclude file are refused with the target's pre-existing files untouched (symlink tests skip with a stated reason if the OS denies creating symlinks); modified managed file makes readiness FAIL.
- **Integration (real `git` and real offline `specify init --here --force --non-interactive --integration copilot` in disposable repositories)**: A1, A1b, A2, A3, A4, A5 and **A7 relocation**: install from a temporary copy of the source, delete that copy, then run the installed validator, readiness checker and helper (`status`, `resolve`) as subprocesses with `FACTORY_*` and `PYTHONPATH` removed and `yaml` blocked; compare with the pre-move results and assert that no source path appears in installed files or output.
- **Regression**: the existing suite passes; a before/after diff confirms only the listed files changed.

The delivery report separates fixture-tested, directly observed and unverified items (non-Windows platforms, Chat discoverability and delegation before A6, Copilot CLI behavior).

## 10. Public distribution and guided onboarding (approved local implementation; release unauthorized)

### Distribution boundary

- Keep `scripts/install_factory.py` as the single reusable installation engine. Add only an adapter that supplies bundled assets and maps the public command's validated target to the engine; do not duplicate conflict, exclude, manifest, exclusive-write or readiness logic.
- Recommended structure: an isolated `distributions/interactive/pyproject.toml` with a small `software_factory_onboarding` package and an `assets/` subtree containing the reusable `scripts/install_factory.py`, its required readiness/helper scripts, and the five profiles plus handoff skill at their mirrored paths. Invoke the bundled installer as a subprocess so its current `SOURCE_ROOT`/sibling-script contract remains valid; only its existing nine managed assets are copied into a target. Use package-resource APIs, never checkout-relative paths. The implementation may adjust this structure after a focused prototype, but must keep the same artifact boundary.
- Build the minimal distribution target with explicit Hatchling wheel and sdist file selection containing only the bootstrap modules and the versioned interactive assets. The release wheel and sdist must not include source Git history, `specs/`, tests, `.specify/`, user configuration, `.factory/`, `.github/copilot/settings.local.json`, hooks, policy, sandbox, experimental runner, or the root automated CLI.
- The desired `software-factory` PyPI project is owned by another project (`stratonext/software-factory`) and is unavailable. Use `specfactory` as a provisional local-only distribution name and primary executable. The durable clean-artifact test installs the built wheel into a temporary venv; a local-wheel `uvx --from` invocation was also smoke-tested. Persistent `uv tool install <wheel>` is documented but not independently verified. A PyPI 404 was observed on 2026-11-23 but does not reserve the name. Verify ownership immediately before any separately approved release; do not reserve/register/publish under this or any other name without separate approval.
- Do not alter the existing root `[project.scripts] factory = software_factory.cli:main` behavior or expose a `factory` script from the public package. The public package exposes only the distinct `specfactory` command for onboarding. Test its `uvx` and persistent `uv tool install` behavior; no command resolution should reach the experimental automated runner.
- Use package resources rather than paths into the checkout. The adapter passes the package asset root or an explicit source mapping into the existing engine. Preserve deterministic manifest fingerprints and source revision semantics: for wheel installs, use the public package version as the recorded source revision or introduce an explicit version field without writing checkout paths or machine-specific build metadata. Decide and test the exact mapping before implementation.
- Pin/build from a reviewed versioned source artifact; the user's runtime install must not fetch scripts or assets from GitHub. Runtime network access is only that required by `uvx` to obtain the package and, when explicitly approved, to install the official Specify CLI.

### First-run flow and consent

1. Parse `init`, preview/read-only, explicit target, non-interactive and apply authorization options. Default target is the current directory; reject non-Git roots, subdirectories, bare repos, unsupported Python and unsafe symlink paths before planning writes.
2. Detect uv/Python, Git, Specify CLI, Spec Kit state, Copilot integration, existing managed paths, local preferences tracking/ignore state, and package/installer compatibility. Print exact findings and a complete Software Factory installation plan before asking for approval.
3. If the Specify CLI is absent, offer the verified official PyPI `specify-cli==1.0.6` package through `uv tool install specify-cli==1.0.6` as an explicit environment-level action; identify uv's configured index as the source and do not install it in non-interactive mode. Revalidate after installation. If the project integration is missing or incomplete, do not offer automatic initialization: Specify 1.0.6 requires `--force` even for a Git-only project root, and this flow is prohibited from using it. Direct the user to review the official existing-project guidance and complete setup manually. A refusal, preview, unavailable network/tool or failure stops without invoking the installer. Existing/incomplete Spec Kit state must not be force-reset or overwritten.
4. Ask separately for approval to install the Software Factory managed assets. Reuse the installer, showing the same per-path plan and retaining its all-conflict preflight, local exclude exception, exclusive file creation, manifest-last behavior and installed readiness check. The installer remains responsible for fail-closed writes.
5. After successful install, explain the existing Feature 005 preset mapping: `budget` maps most roles to balanced and QA to budget; `balanced` maps all roles to balanced; `quality-first` maps all roles to quality. Explain that each configured tier requires a model ID selected by the user from models available to that user. Offer the existing helper to set a preset/tier only after explicit approval; do not preselect or invent IDs. Show resulting status without exposing secrets or copying preferences into the project/package.
6. Report actual readiness output, limitations and the next VS Code action: open this project, open Copilot Chat, choose Factory Lead. Do not claim hosted delegation or Chat discoverability verified without A6.

### Preview and automation contract

- Interactive default: inspection and plan first; separate approvals for Specify CLI installation and Software Factory installation. Invalid Spec Kit is a manual prerequisite.
- `--dry-run`/`--preview`: always read-only with respect to the target; no write-triggering prompts, no `.git/info/exclude` change and no Spec Kit initialization/write command. Read-only prerequisite queries may run. The existing installer may be invoked only with its `--dry-run` option to show the authoritative per-path plan; write mode is never invoked.
- `--non-interactive`: no prompts and preview-only by default. The explicit `--yes` switch authorizes only the Software Factory install when all prerequisites already pass. It never authorizes or triggers Spec Kit initialization; missing/incomplete Spec Kit is a refusal. Preview and apply flags cannot be combined ambiguously.
- Preserve existing installer exit guarantees and explain which action failed. A failure during approved Specify CLI installation is reported; onboarding must rerun detection and may not continue based on an assumed success.

### Distribution verification and release gates

- Build wheel and sdist from the new explicit distribution target. Inspect archive members against an allowlist and denylist before execution.
- In tests, copy only the built wheel and a disposable target fixture into a clean temporary location. Install/run using an isolated environment or `uvx --from <wheel-path>`; set cwd to the disposable Git project, remove checkout-related `PYTHONPATH` and `FACTORY_*`, and ensure the child cannot resolve/import the repository. Assert `module.__file__` and every asset source are within the installed distribution, then run end-to-end install, readiness and source-relocation behavior.
- Test both the wheel and sdist build; wheel is the required clean runtime artifact. Sdist must build the same wheel from included sources without requiring `.git`, private files or history.
- Verify local package build is offline after dependencies are provisioned; no test publishes to PyPI or GitHub. Do not treat package installation from a public registry as authorized.
- Before any public release, separately obtain owner authorization after a dedicated audit of repository/history exposure, package and console-script ownership, file allowlist, dependency provenance/licenses, secrets and personal data, supported platform metadata, versioning, reproducible build/SBOM or equivalent provenance, and release credentials/permissions. No remote publication, push, merge, deployment, or registry upload is in this plan's authorized actions.

### Additional focused tests

- Packaging: wheel/sdist build from the minimal distribution target; allowlist and denylist checks; metadata/entrypoint inspection; no `.git`, `.specify`, `specs`, tests, personal data or excluded automation; package version captured in deterministic install metadata.
- Clean runtime: invoke the built wheel from a clean isolated environment outside the checkout; assert import and asset paths resolve only inside the installed distribution; `specfactory init --help` returns successfully; exercise actual B1 installation with the checkout absent from working directory and import paths.
- Onboarding: current-directory root detection; invalid target refusal; exact preflight findings; prompt order and refusal; Specify CLI installation consent; missing/incomplete Spec Kit refusal with manual setup guidance; separate install consent; no `--force`; existing Spec Kit conflicts never overwritten; readiness result and VS Code guidance. Use injected command runners for environment setup actions; automated tests do not install Specify or access a package registry.
- Preview/automation: byte-for-byte target and Git state snapshots for preview, declined prompts and noninteractive-without-authorization; `--yes` applies only to valid preflight and never bootstraps Spec Kit; no prompt under redirected stdin; contradictory options rejected.
- Model guidance: preset mappings match `specialist_models.PRESETS`; configuration asks for user-selected IDs; no IDs/preferences in package, logs, manifest or target until the user explicitly configures them; no model tier escalation.
- Preserve and rerun all existing installer tests and the 333-test regression baseline; record new totals and platform-specific skips separately. A6 remains separately owner-authorized and is not part of local package tests.

## Git Safeguard

Historical baseline for the original local-installer work is preserved in the Acceptance Record: HEAD `54f2ded`, with the original spec directory as the sole untracked item at that time. The accepted implementation remains uncommitted in the worktree and must not be reset or overwritten. At the start of this public-onboarding revision, `.specify/feature.json` pointed to `specs/007-installation-bootstrap`; the worktree already contained the original implementation changes. Recheck the current feature pointer, HEAD, staged, unstaged and untracked state immediately before any separately approved implementation. No commit, push, merge, publish or deploy is authorized.

## Project Structure

### Documentation

```text
specs/007-installation-bootstrap/
  spec.md  plan.md  research.md  data-model.md  quickstart.md
  contracts/cli.md
  checklists/requirements.md
```

### Implemented public-distribution layout

```text
distributions/interactive/
  pyproject.toml                 isolated metadata and console scripts
  src/specfactory/
    __init__.py
    __main__.py
    bundle.py
    cli.py                       public CLI and onboarding adapter
    assets/.github/...           allowlisted interactive profiles and skill
    assets/scripts/...           existing reusable installer and helpers
tests/unit/test_public_package.py
tests/unit/test_public_cli.py
tests/integration/test_public_distribution.py
```

The exact paths and whether the minimal target is a separate subproject or a narrowly configured build target are implementation choices; the artifact allowlist and separation from the root automated CLI are requirements.

### Source (new and changed)

```text
scripts/install_factory.py                      new
scripts/validate_specialist_profiles.py         edit (optional PyYAML; fallback parser)
scripts/check_factory_readiness.py              edit (installed mode; fingerprint export)
.github/agents/factory-lead.agent.md            wording only
.github/skills/factory-handoff/SKILL.md         wording only
tests/unit/test_installer.py                    new
tests/unit/test_agent_profiles.py               add fallback and parity tests
tests/unit/test_readiness_check.py              update one test; add installed-mode tests
tests/integration/test_install_workflow.py      new
```

## Risks and Limitations

- The fallback frontmatter parser only accepts a narrow subset and rejects everything else, but a profile valid to the fallback yet invalid as full YAML is possible in theory. The parity test limits this to the shipped files; stated in delivery.
- Wording edits change accepted profile text; they are listed above for approval and covered by the unchanged-contract tests.
- `scripts/` name collisions become conflicts that stop installation (by design); the developer must resolve them manually.
- The local exclude is not shared: a teammate's clone needs its own run of the installer (or an equivalent ignore rule), and readiness reports this as NOT VERIFIED.
- Managed-file integrity is strict: an intentionally customized managed file makes readiness FAIL until restored; customization support is not in v1.
- Readiness treats a project as installed only when the manifest exists. If the manifest is missing after an interrupted install, readiness runs in source mode (a fresh Spec Kit project then reports the missing feature pointer); the installer's own output says to re-run it, and a re-run completes the install.
- Only the destination file is protected against swaps after classification; ancestor directories could in theory be replaced by links between classification and write. Accepted for a local, single-developer tool (Constitution VI).
- Negation rules: a `.gitignore` rule that un-ignores the preferences path makes an exclude entry ineffective; this is detected at plan time and refused (dry run and real run agree).
- Upgrading to a newer factory revision is out of scope; differing files are conflicts.
- Chat discoverability and delegation in a real project are unproven until A6.
- The owner identifies `software-factory` as owned by `stratonext/software-factory`; it must not be used. `specfactory` returned 404 during research but remains provisional and can be claimed by another party; exact release ownership must be rechecked under separate approval.
- The existing global `factory` command belongs to the experimental root package and must not be changed or shipped by this feature; use only the distinct provisional `specfactory` executable.
- Specify 1.0.6 requires `--force` to initialize a Git project, including a Git-only root; onboarding refuses invalid integration and provides manual guidance. Reassess only if a future supported upstream command offers safe non-force initialization.
- Runtime package retrieval by `uvx` uses the selected package index; tests must use local built artifacts only, and release approval must separately cover registry ownership, provenance, source/history exposure and package contents.
- The clean-artifact test proves wheel contents and runtime independence, not public registry availability, PyPI ownership, GitHub release integrity, or A6 Copilot behavior.
