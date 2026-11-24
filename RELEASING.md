# Build and Release

Spec Factory is developed and packaged from this repository root. The root `pyproject.toml` is authoritative; keep `src/specfactory/assets/BUNDLE_VERSION` equal to `specfactory-<project version>`.

## Local Verification

Run the product unit tests:

```text
python -m unittest tests.unit.test_installer tests.unit.test_agent_profiles tests.unit.test_readiness_check tests.unit.test_specialist_models tests.unit.test_public_package tests.unit.test_public_cli
```

The disposable installer workflow needs the `specify` CLI on `PATH` and otherwise skips. Distribution tests require `uv`, Git, and the pinned build dependencies available locally; they build the wheel and source distribution, install the wheel in a clean virtual environment, test without the source checkout, and exercise installation only in disposable projects.

## Candidate Build

Use a new empty output directory outside the checkout for each candidate. Build offline with the pinned, hash-checked requirements:

```text
uv build --offline --wheel --sdist --require-hashes --build-constraint ./build-constraints.txt --out-dir <empty-output-directory> .
```

Run the full product and distribution suite before release:

```text
python -m unittest discover -s tests -t .
```

Inspect both archives against the tests' explicit file allowlists, record their SHA-256 hashes and build environment, and verify that the sdist can rebuild the same wheel without the checkout. Do not include tests, development-only files, local paths, personal configuration, or the internal release notes in either artifact.

## Publishing

The public `v0.1.0` tag, release assets, and download URLs are immutable. Never replace or republish them. Increment the project version and matching bundle marker for every release candidate; publish only a new version and tag after the owner separately authorizes the reviewed commit and release. This document does not authorize commits, pushes, or publication.