# Research: Specialist Profile Integrity Validator

## Decision 1: Parse Frontmatter as YAML

**Decision**: Use `yaml.safe_load` from PyYAML on the delimited YAML frontmatter.

**Rationale**: The input is YAML, and the validator must distinguish malformed syntax, wrong value types, and valid extra metadata. Python's standard library has no YAML parser. A hand-written subset would be a second parser with ambiguous behavior and weaker malformed-input handling. `safe_load` avoids constructing arbitrary Python objects from repository text.

**Alternatives considered**:

- Hand-parse the current simple fields: rejected because accepted YAML syntax would be implicit and malformed or typed values could be handled inconsistently.
- Add a frontmatter-specific package: rejected because it adds another abstraction/dependency when the required input is already a delimited YAML document.
- Add PyYAML to project runtime dependencies: rejected because neither `software_factory` nor its installed factory CLI uses this validator.

## Decision 2: Isolate the Parser Dependency

**Decision**: Declare PyYAML in a dedicated `validation` dependency group and invoke the script/tests through `uv` with that group enabled. Resolve and lock the version when implementation is approved; do not install or modify dependency files as part of this plan-only step.

**Rationale**: The repository has no runtime dependencies and uses `uv` for environment management. PyYAML 6.0.1 is available in the global Python environment, while the project virtual environment does not include it. A validation-only group makes the validator reproducible without adding the parser to factory runtime installs. Do not implement a fallback parser that silently changes validation semantics when the group is absent.

**Alternatives considered**:

- Rely on whichever YAML package happens to be globally installed: rejected as non-reproducible.
- Put PyYAML in the runtime dependency list: rejected as unnecessary for factory consumers.
- Vendor a parser or implement a custom parser: rejected as extra maintenance and weaker correctness.

## Decision 3: Keep Validation Local and Read-Only

**Decision**: Read only the five fixed `.github/agents/*.agent.md` paths, produce findings in memory, and write output only to standard streams. Make no subprocess or network calls.

**Rationale**: This directly satisfies FR-006 and avoids coupling profile validation to Copilot runtime behavior or factory execution infrastructure. An optional `--root` argument permits explicit repository and fixture selection; the default resolves from the script's location so invocation does not depend on the caller's working directory.

**Alternatives considered**:

- Discover every file in `.github/agents/`: rejected because the spec requires a fixed set of five expected profiles and discovery could hide a missing required file.
- Invoke Copilot to verify profile discovery: rejected because the feature is a local static validator and must not start Copilot.

## Existing Repository Evidence

- `pyproject.toml` requires Python 3.11+, has no project runtime dependencies, and already uses dependency groups.
- `tests/unit/` uses `unittest`.
- The current Code Reviewer frontmatter declares `strict-tools-list: true` and `tools: ["read", "grep", "glob"]`.
- Spec Kit's plan setup reports feature identifier `003-specialist-profile-validator`; it did not create or switch a Git branch.
