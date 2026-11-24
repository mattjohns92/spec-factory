# Development Context

## Recovered records

- [`../../ROADMAP.md`](../../ROADMAP.md) preserves the source roadmap, including deferred work.
- [`constitution-draft.md`](constitution-draft.md) is the original unratified constitution draft. It is not active policy and must not replace the current Spec Kit constitution file without owner ratification.
- [`../../specs/README.md`](../../specs/README.md) indexes the recovered feature records and their statuses.

The source checkout was `software-factory`; its Python package path `src/software_factory` became `src/specfactory` in the public repository. References to old source paths, scripts, tests, and generated files are historical unless independently present here. Feature 001 and its experimental runner/policy/sandbox work were excluded. Feature 006 remains deferred, not completed.

## Spec Kit state at recovery

The locally installed Specify CLI is version 1.0.6. In the canonical checkout, `specify integration status --json` reported `status: ok`, and `specify workflow list` / `specify workflow info speckit` reported the Copilot `speckit` workflow at v1.0.1. The original checkout recorded workflow v1.0.2 and also contained an unapproved retry overlay; neither was copied over the canonical workflow.

The canonical checkout's `.specify/` configuration and ten `.github/skills/speckit-*` directories appeared concurrently during this work and are untracked. This recovery did not overwrite or delete them. The active `.specify/memory/constitution.md` is a generic Spec Kit template, not the recovered project constitution. Review these concurrent files before deciding what belongs in a future commit.

No `specify init --force` was run in the canonical checkout. Do not treat successful local CLI status as owner approval of generated configuration or as ratification of the constitution. No feature workflow was started as part of this recovery.

## Scope and distribution

Only records for Features 002, 003, 004, 005, and 007 were recovered, along with the roadmap and constitution draft. No history, credentials, local settings, caches, session logs, checkpoints, or experimental runner implementation were imported. Feature 007's unapproved license proposal was omitted. Feature 005 and 007 public copies have documented, narrow privacy sanitization; see [`../../specs/README.md`](../../specs/README.md).

Development documentation should remain outside the wheel and sdist. The existing explicit package allowlists were not changed.
