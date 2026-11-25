import re
import sys
import tomllib
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = REPOSITORY_ROOT
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import specfactory  # noqa: E402
from specfactory import bundle  # noqa: E402

PACKAGE = PROJECT_ROOT / "src" / "specfactory"
ASSETS = PACKAGE / "assets"
CODE_FILES = ("__init__.py", "__main__.py", "bundle.py", "cli.py")
# Source files that the bundled copies must match (the accepted, tested originals).
SOURCE_FOR_ASSET = {
    name: REPOSITORY_ROOT / name for name in bundle.BUNDLED_ASSETS if name != "BUNDLE_VERSION"
}
FORBIDDEN = re.compile(
    r"software_factory|\.specify|(^|/)specs(/|$)|(^|/)tests?(/|$)|\.factory|model-preferences|"
    r"policy|hook|sandbox|settings\.local|run_engineer|speckit|\.git(/|$)|(^|/)dist(/|$)",
    re.IGNORECASE,
)


def lf(data):
    return data.replace(b"\r\n", b"\n")


def load_pyproject():
    with open(PROJECT_ROOT / "pyproject.toml", "rb") as handle:
        return tomllib.load(handle)


def disk_assets():
    return sorted(
        path.relative_to(ASSETS).as_posix()
        for path in ASSETS.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )


class BundledAssetTests(unittest.TestCase):
    def test_every_required_asset_is_present(self):
        self.assertEqual(bundle.missing_assets(ASSETS), [])

    def test_disk_matches_the_explicit_asset_list_exactly(self):
        self.assertEqual(disk_assets(), sorted(bundle.BUNDLED_ASSETS))

    def test_bundled_copies_match_the_accepted_sources(self):
        for relative, source in SOURCE_FOR_ASSET.items():
            with self.subTest(asset=relative):
                self.assertEqual(lf((ASSETS / relative).read_bytes()), lf(source.read_bytes()))

    def test_managed_files_of_the_engine_are_all_bundled(self):
        engine = bundle.load_script("install_factory")
        for relative in engine.MANAGED_FILES:
            self.assertIn(relative, bundle.BUNDLED_ASSETS)

    def test_exactly_the_engine_and_its_helpers_are_bundled_as_scripts(self):
        scripts = sorted(name for name in bundle.BUNDLED_ASSETS if name.startswith("scripts/"))
        self.assertEqual(
            scripts,
            [
                "scripts/check_factory_readiness.py",
                "scripts/install_factory.py",
                "scripts/specialist_models.py",
                "scripts/validate_specialist_profiles.py",
            ],
        )

    def test_forbidden_content_is_absent_from_the_asset_list(self):
        for relative in bundle.BUNDLED_ASSETS:
            with self.subTest(asset=relative):
                self.assertIsNone(FORBIDDEN.search(relative))
        # The only dotted directory permitted is .github (profiles and skill).
        for relative in bundle.BUNDLED_ASSETS:
            first = relative.split("/")[0]
            if first.startswith("."):
                self.assertEqual(first, ".github")

    def test_only_the_five_profiles_and_the_handoff_skill_are_under_github(self):
        github = sorted(name for name in bundle.BUNDLED_ASSETS if name.startswith(".github/"))
        self.assertEqual(
            github,
            [
                ".github/agents/architect.agent.md",
                ".github/agents/code-reviewer.agent.md",
                ".github/agents/engineer.agent.md",
                ".github/agents/factory-lead.agent.md",
                ".github/agents/qa-engineer.agent.md",
                ".github/skills/factory-handoff/SKILL.md",
            ],
        )

    def test_no_model_ids_or_personal_data_are_bundled(self):
        pattern = re.compile(rb"claude-|gpt-|gemini-|sonnet|haiku|opus", re.IGNORECASE)
        for relative in bundle.BUNDLED_ASSETS:
            with self.subTest(asset=relative):
                self.assertIsNone(pattern.search((ASSETS / relative).read_bytes()))
        self.assertFalse((ASSETS / ".factory").exists())

    def test_bundle_version_marker_matches_the_package_version(self):
        version = load_pyproject()["project"]["version"]
        self.assertEqual(specfactory.__version__, version)
        self.assertEqual((ASSETS / "BUNDLE_VERSION").read_text(encoding="utf-8"), f"specfactory-{version}\n")

    def test_bundled_engine_records_the_bundle_version_instead_of_querying_git(self):
        engine = bundle.load_script("install_factory")

        def runner(*_args, **_kwargs):
            raise AssertionError("git must not be queried for a bundled asset root")

        self.assertEqual(engine._source_revision(runner), f"specfactory-{specfactory.__version__}")
        self.assertEqual(engine.SOURCE_ROOT, ASSETS)

    def test_loading_bundled_scripts_writes_no_bytecode(self):
        bundle.load_script("check_factory_readiness")
        bundle.load_script("specialist_models")
        self.assertEqual(list(ASSETS.rglob("__pycache__")), [])


class EngineFallbackTests(unittest.TestCase):
    def test_checkout_engine_without_marker_still_uses_git_revision(self):
        sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))
        try:
            import install_factory as checkout_engine
        finally:
            sys.path.pop(0)
        self.assertFalse(checkout_engine.BUNDLE_VERSION_FILE.exists())
        calls = []

        def runner(arguments, cwd=None, timeout=None):
            calls.append(list(arguments))
            raise OSError("no git")

        self.assertEqual(checkout_engine._source_revision(runner), "unknown")
        self.assertTrue(calls and calls[0][-2:] == ["rev-parse", "HEAD"])


class DistributionMetadataTests(unittest.TestCase):
    def test_only_the_specfactory_entry_point_is_declared(self):
        scripts = load_pyproject()["project"]["scripts"]
        self.assertEqual(scripts, {"specfactory": "specfactory.cli:main"})
        self.assertNotIn("factory", scripts)

    def test_the_module_for_the_entry_point_exists(self):
        from specfactory import cli

        self.assertTrue(callable(cli.main))

    def test_name_python_and_dependencies(self):
        project = load_pyproject()["project"]
        self.assertEqual(project["name"], "specfactory")
        self.assertEqual(project["requires-python"], ">=3.11")
        self.assertEqual(project["dependencies"], [])
        self.assertEqual(project["readme"], "README.md")
        self.assertEqual(project["license"], "MIT")
        self.assertEqual(project["license-files"], ["LICENSE"])
        self.assertNotIn("urls", project)

    def test_root_project_is_the_public_specfactory_package(self):
        root = load_pyproject()["project"]
        self.assertEqual(root["name"], "specfactory")
        self.assertEqual(root["scripts"], {"specfactory": "specfactory.cli:main"})

    def test_wheel_and_sdist_allowlists_are_explicit_and_complete(self):
        targets = load_pyproject()["tool"]["hatch"]["build"]["targets"]
        self.assertIn(".gitignore", targets["sdist"]["only-include"])
        expected = sorted(
            [f"src/specfactory/{name}" for name in CODE_FILES]
            + [f"src/specfactory/assets/{name}" for name in bundle.BUNDLED_ASSETS]
        )
        self.assertEqual(sorted(targets["wheel"]["only-include"]), expected)
        self.assertEqual(
            sorted(targets["sdist"]["only-include"]),
            sorted(expected + [".gitignore", "pyproject.toml", "README.md", "build-constraints.txt", "LICENSE"]),
        )
        self.assertEqual(targets["wheel"]["sources"], ["src"])
        for path in expected:
            with self.subTest(path=path):
                self.assertTrue((PROJECT_ROOT / path).is_file())
                self.assertIsNone(FORBIDDEN.search(path.replace("src/specfactory/assets/.github", "")))

    def test_package_directory_holds_only_allowlisted_files(self):
        found = sorted(
            path.relative_to(PACKAGE).as_posix()
            for path in PACKAGE.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        )
        self.assertEqual(
            found, sorted(list(CODE_FILES) + [f"assets/{name}" for name in bundle.BUNDLED_ASSETS])
        )

    def test_interactive_product_is_not_nested_under_a_distribution_directory(self):
        self.assertFalse((PROJECT_ROOT / "distributions" / "interactive").exists())
        self.assertTrue((PROJECT_ROOT / "scripts" / "install_factory.py").is_file())
        self.assertTrue((PROJECT_ROOT / "tests" / "unit" / "test_installer.py").is_file())

    def test_release_readme_uses_the_versioned_github_wheel(self):
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("uvx --from", readme)
        self.assertIn(
            "github.com/mattjohns92/spec-factory/releases/download/v0.1.0/"
            "specfactory-0.1.0-py3-none-any.whl",
            readme,
        )
        self.assertIn("specfactory init --dry-run", readme)

    def test_approved_license_is_packaged_but_internal_release_checklist_is_not(self):
        targets = load_pyproject()["tool"]["hatch"]["build"]["targets"]
        self.assertIn("LICENSE", targets["sdist"]["only-include"])
        for target in ("wheel", "sdist"):
            self.assertNotIn("RELEASE.md", targets[target]["only-include"])


if __name__ == "__main__":
    unittest.main()
