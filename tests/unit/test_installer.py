import errno
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import check_factory_readiness as readiness  # noqa: E402
import install_factory as installer  # noqa: E402


ENTRY = "/.factory/model-preferences.json"
PREFERENCES = ".factory/model-preferences.json"
MANIFEST = ".github/software-factory/install-manifest.json"
EXPECTED_MANAGED = (
    ".github/agents/factory-lead.agent.md",
    ".github/agents/architect.agent.md",
    ".github/agents/engineer.agent.md",
    ".github/agents/qa-engineer.agent.md",
    ".github/agents/code-reviewer.agent.md",
    ".github/skills/factory-handoff/SKILL.md",
    "scripts/specialist_models.py",
    "scripts/validate_specialist_profiles.py",
    "scripts/check_factory_readiness.py",
)
INTEGRATION_OK = {
    "status": "ok",
    "default_integration": "copilot",
    "installed_integrations": ["copilot"],
    "missing_managed_files": 0,
    "modified_managed_files": 0,
    "invalid_manifest_paths": 0,
    "unchecked_manifests": 0,
    "findings": [],
}


class Runner:
    """Real git, fake Specify CLI; `git_hook` may override a git call's result."""

    def __init__(self):
        self.integration = dict(INTEGRATION_OK)
        self.git_hook = None
        self.git_calls = []

    def __call__(self, arguments, cwd=None, timeout=None):
        arguments = list(arguments)
        if arguments[0] == "git":
            self.git_calls.append(arguments)
            if self.git_hook is not None:
                override = self.git_hook(arguments)
                if override is not None:
                    return override
            return readiness.default_runner(arguments, cwd=cwd, timeout=timeout)
        if arguments[1:] == ["--version"]:
            return subprocess.CompletedProcess(arguments, 0, "specify 1.0.6\n", "")
        if arguments[1:] == ["integration", "status", "--json"]:
            return subprocess.CompletedProcess(arguments, 0, json.dumps(self.integration), "")
        raise AssertionError(f"unexpected command: {arguments}")


class FakeReadiness:
    def __init__(self, returncode=0):
        self.returncode = returncode
        self.calls = []

    def __call__(self, target, environment):
        self.calls.append(str(target))
        return subprocess.CompletedProcess([], self.returncode, "Verdict: ready with limitations\n", "")


def specify_on_path(name):
    return "/bin/specify" if name == "specify" else None


class InstallerTestCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(os.path.realpath(temporary.name))
        patcher = mock.patch.dict(
            os.environ, {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CEILING_DIRECTORIES"):
            os.environ.pop(name, None)
        self.runner = Runner()
        self.readiness = FakeReadiness()
        self.which = specify_on_path
        self.target = self.make_repo("target")
        self.exclude = self.target / ".git" / "info" / "exclude"

    # helpers
    def git(self, *arguments, cwd=None):
        return subprocess.run(
            ["git", *arguments], cwd=cwd, capture_output=True, text=True, check=True
        )

    def make_repo(self, name, spec_kit=True):
        path = self.base / name
        path.mkdir()
        self.git("init", "-q", str(path))
        if spec_kit:
            for relative in readiness.SPECKIT_FILES:
                file = path / relative
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("content\n", encoding="utf-8")
        return path

    def run_install(self, target=None, *extra, runner=None, readiness_runner=None, which=None):
        stream = io.StringIO()
        code = installer.main(
            ["--target", str(self.target if target is None else target), *extra],
            runner=runner or self.runner,
            environment={"PATH": ""},
            which=which or self.which,
            stdout=stream,
            readiness_runner=readiness_runner or self.readiness,
        )
        return code, stream.getvalue()

    def tree_hash(self, root):
        entries = []
        for directory, directories, files in os.walk(root):
            directories.sort()
            for name in directories + files:
                full = os.path.join(directory, name)
                relative = os.path.relpath(full, root)
                if os.path.islink(full):
                    entries.append((relative, "L", os.readlink(full)))
                elif os.path.isdir(full):
                    entries.append((relative, "D", ""))
                else:
                    with open(full, "rb") as handle:
                        entries.append((relative, "F", hashlib.sha256(handle.read()).hexdigest()))
        return hashlib.sha256(repr(sorted(entries)).encode()).hexdigest()

    def installed_files(self, root=None):
        root = Path(root or self.target)
        found = set()
        for directory, directories, files in os.walk(root):
            directories[:] = [d for d in directories if d not in (".git", ".specify")]
            for name in files:
                found.add(Path(directory, name).relative_to(root).as_posix())
        return found

    def source_bytes(self, relative):
        return (installer.SOURCE_ROOT / relative).read_bytes()

    def write_target(self, relative, data, target=None):
        path = (target or self.target) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def entry_lines(self):
        return [
            line for line in self.exclude.read_bytes().decode("utf-8", "replace").splitlines()
            if line.strip() == ENTRY
        ]

    def is_ignored(self, path=PREFERENCES):
        return subprocess.run(
            ["git", "-C", str(self.target), "check-ignore", "-q", "--no-index", path],
            capture_output=True,
        ).returncode == 0

    def assert_refused_without_writing(self, target, *extra, **kwargs):
        before = self.tree_hash(target) if Path(target).exists() else None
        code, output = self.run_install(target, *extra, **kwargs)
        self.assertEqual(code, 2, output)
        self.assertIn("Refused:", output)
        if before is not None:
            self.assertEqual(self.tree_hash(target), before)
        self.assertEqual(self.readiness.calls, [])
        return output


class TargetValidationTests(InstallerTestCase):
    def test_nonexistent_directory_is_refused(self):
        missing = self.base / "missing"
        self.assert_refused_without_writing(missing)
        self.assertFalse(missing.exists())

    def test_target_that_is_a_file_is_refused(self):
        file = self.base / "file.txt"
        file.write_text("x", encoding="utf-8")
        self.assert_refused_without_writing(file)

    def test_plain_directory_that_is_not_a_repository_is_refused(self):
        plain = self.base / "plain"
        plain.mkdir()
        (plain / "keep.txt").write_text("x", encoding="utf-8")
        output = self.assert_refused_without_writing(plain)
        self.assertIn("Git working tree", output)
        self.assertEqual(sorted(p.name for p in plain.iterdir()), ["keep.txt"])

    def test_subdirectory_of_a_repository_is_refused(self):
        sub = self.target / "nested"
        sub.mkdir()
        before = self.tree_hash(self.target)
        output = self.assert_refused_without_writing(sub)
        self.assertIn("Git working tree", output)
        self.assertEqual(self.tree_hash(self.target), before)

    def test_bare_repository_is_refused(self):
        bare = self.base / "bare.git"
        self.git("init", "--bare", "-q", str(bare))
        self.assert_refused_without_writing(bare)

    def test_source_checkout_is_refused(self):
        source = self.make_repo("source", spec_kit=True)
        for relative in EXPECTED_MANAGED:
            self.write_target(relative, self.source_bytes(relative), target=source)
        with mock.patch.object(installer, "SOURCE_ROOT", source):
            output = self.assert_refused_without_writing(source)
        self.assertIn("source checkout", output)

    def test_bundled_engine_refuses_factory_source_checkout_layout(self):
        (self.target / "pyproject.toml").write_text("[project]\nname = 'specfactory'\n")
        (self.target / "src" / "specfactory").mkdir(parents=True)
        scripts = self.target / "scripts"
        scripts.mkdir()
        (scripts / "install_factory.py").write_text("# source checkout marker\n")
        before = self.tree_hash(self.target)
        output = self.assert_refused_without_writing(self.target)
        self.assertIn("source checkout", output)
        self.assertEqual(self.tree_hash(self.target), before)

    def test_canonical_source_checkout_is_refused_as_install_target(self):
        output = self.assert_refused_without_writing(REPOSITORY_ROOT)
        self.assertIn("Software Factory source checkout", output)

    def test_dry_run_validation_failures_also_exit_2(self):
        plain = self.base / "plain"
        plain.mkdir()
        self.assert_refused_without_writing(plain, "--dry-run")

    def test_unknown_option_is_usage_error(self):
        with mock.patch("sys.stderr", new=io.StringIO()):
            code = installer.main(["--bogus"], runner=self.runner, environment={"PATH": ""})
        self.assertEqual(code, 2)

    def test_missing_target_option_is_usage_error(self):
        with mock.patch("sys.stderr", new=io.StringIO()):
            code = installer.main([], runner=self.runner, environment={"PATH": ""})
        self.assertEqual(code, 2)


class SpecKitGateTests(InstallerTestCase):
    def assert_spec_kit_refusal(self, target, *extra, **kwargs):
        output = self.assert_refused_without_writing(target, *extra, **kwargs)
        self.assertIn("Review the official existing-project guidance", output)
        self.assertIn("initialize or repair Spec Kit manually", output)
        self.assertIn("Nothing was written", output)
        self.assertEqual(self.installed_files(target), set())
        return output

    def test_repository_without_spec_kit_files_is_refused(self):
        bare_repo = self.make_repo("no-speckit", spec_kit=False)
        self.assert_spec_kit_refusal(bare_repo)
        self.assertFalse((bare_repo / ".github").exists())
        self.assertFalse((bare_repo / "scripts").exists())

    def test_missing_specify_executable_is_refused(self):
        self.assert_spec_kit_refusal(self.target, which=lambda name: None)

    def test_unhealthy_integration_status_is_refused(self):
        self.runner.integration = dict(INTEGRATION_OK, installed_integrations=[])
        self.assert_spec_kit_refusal(self.target)

    def test_refusal_applies_to_dry_run(self):
        self.assert_spec_kit_refusal(self.make_repo("no-speckit", spec_kit=False), "--dry-run")

    def test_absent_feature_pointer_is_accepted_by_the_gate(self):
        self.assertFalse((self.target / ".specify" / "feature.json").exists())
        code, output = self.run_install(self.target, "--dry-run")
        self.assertEqual(code, 0, output)

    def test_present_but_invalid_feature_pointer_is_refused(self):
        self.write_target(".specify/feature.json", b'{"feature_directory": "specs/nope"}')
        self.assert_spec_kit_refusal(self.target)


class PlanAndClassificationTests(InstallerTestCase):
    def line(self, state, relative):
        return f"[{state}]".ljust(12) + relative

    def test_fresh_target_plan_lists_every_path_as_create(self):
        code, output = self.run_install(self.target, "--dry-run")
        self.assertEqual(code, 0, output)
        lines = output.splitlines()
        for relative in EXPECTED_MANAGED + (MANIFEST,):
            self.assertIn(self.line("create", relative), lines)
        self.assertIn("Plan: 10 create, 0 unchanged, 0 conflict", lines)
        self.assertIn("DRY RUN: nothing was changed.", lines)

    def test_identical_files_are_unchanged_and_others_created(self):
        for relative in EXPECTED_MANAGED[:2]:
            self.write_target(relative, self.source_bytes(relative))
        code, output = self.run_install(self.target, "--dry-run")
        self.assertEqual(code, 0, output)
        lines = output.splitlines()
        self.assertIn(self.line("unchanged", EXPECTED_MANAGED[0]), lines)
        self.assertIn(self.line("unchanged", EXPECTED_MANAGED[1]), lines)
        self.assertIn(self.line("create", EXPECTED_MANAGED[2]), lines)
        self.assertIn("Plan: 8 create, 2 unchanged, 0 conflict", lines)

    def test_different_content_is_a_conflict(self):
        path = self.write_target("scripts/specialist_models.py", b"# my own script\n")
        code, output = self.run_install(self.target, "--dry-run")
        self.assertEqual(code, 1, output)
        lines = output.splitlines()
        self.assertIn("[conflict]  scripts/specialist_models.py: different content", lines)
        self.assertIn("Plan: 9 create, 0 unchanged, 1 conflict", lines)
        self.assertIn("Nothing was written.", output)
        self.assertEqual(path.read_bytes(), b"# my own script\n")

    def test_conflict_means_no_writes_at_all(self):
        self.write_target("scripts/specialist_models.py", b"# my own script\n")
        self.write_target(EXPECTED_MANAGED[0], b"my profile\n")
        before = self.tree_hash(self.target)
        exclude_before = self.exclude.read_bytes()
        code, output = self.run_install(self.target)
        self.assertEqual(code, 1, output)
        self.assertEqual(self.tree_hash(self.target), before)
        self.assertEqual(self.exclude.read_bytes(), exclude_before)
        self.assertFalse(self.is_ignored())
        self.assertEqual(self.readiness.calls, [])
        self.assertIn("scripts/specialist_models.py", output)
        self.assertIn(EXPECTED_MANAGED[0], output)
        self.assertIn("Plan: 8 create, 0 unchanged, 2 conflict", output)

    def test_existing_manifest_with_different_files_is_a_conflict(self):
        path = self.write_target(MANIFEST, json.dumps({"version": 1, "files": {}}).encode())
        before = self.tree_hash(self.target)
        code, output = self.run_install(self.target)
        self.assertEqual(code, 1, output)
        self.assertIn(f"[conflict]  {MANIFEST}: different content", output)
        self.assertEqual(self.tree_hash(self.target), before)
        self.assertTrue(path.exists())

    def test_unsupported_existing_manifest_is_refused(self):
        for content in (b"{not json", b"[]", json.dumps({"version": 2, "files": {}}).encode()):
            with self.subTest(content=content):
                self.write_target(MANIFEST, content)
                self.assert_refused_without_writing(self.target)

    def test_dry_run_leaves_the_target_byte_identical(self):
        before = self.tree_hash(self.target)
        exclude_before = self.exclude.read_bytes()
        code, output = self.run_install(self.target, "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.tree_hash(self.target), before)
        self.assertEqual(self.exclude.read_bytes(), exclude_before)
        self.assertEqual(self.readiness.calls, [])
        self.assertIn("append '/.factory/model-preferences.json'", output)

    def test_dry_run_does_not_create_missing_exclude_file_or_directory(self):
        shutil.rmtree(self.target / ".git" / "info")
        before = self.tree_hash(self.target)
        code, output = self.run_install(self.target, "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.tree_hash(self.target), before)
        self.assertFalse((self.target / ".git" / "info").exists())

    def test_dry_run_of_an_installed_target_changes_nothing(self):
        self.assertEqual(self.run_install(self.target)[0], 0)
        before = self.tree_hash(self.target)
        code, output = self.run_install(self.target, "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertIn("Plan: 0 create, 10 unchanged, 0 conflict", output)
        self.assertEqual(self.tree_hash(self.target), before)

    def test_crlf_difference_alone_is_unchanged(self):
        crlf = {}
        for relative in EXPECTED_MANAGED:
            lf = self.source_bytes(relative).replace(b"\r\n", b"\n")
            crlf[relative] = lf.replace(b"\n", b"\r\n")
            self.write_target(relative, crlf[relative])
        code, output = self.run_install(self.target)
        self.assertEqual(code, 0, output)
        self.assertIn("Plan: 1 create, 9 unchanged, 0 conflict", output)
        for relative in EXPECTED_MANAGED:
            self.assertEqual((self.target / relative).read_bytes(), crlf[relative])

    def test_lf_target_against_crlf_source_content_is_unchanged(self):
        for relative in EXPECTED_MANAGED:
            lf = self.source_bytes(relative).replace(b"\r\n", b"\n")
            self.write_target(relative, lf)
        code, output = self.run_install(self.target, "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertIn("Plan: 1 create, 9 unchanged, 0 conflict", output)

    def test_repeat_install_is_a_byte_identical_no_op(self):
        self.assertEqual(self.run_install(self.target)[0], 0)
        before = self.tree_hash(self.target)
        code, output = self.run_install(self.target)
        self.assertEqual(code, 0, output)
        self.assertIn("already installed", output)
        self.assertEqual(self.tree_hash(self.target), before)
        self.assertEqual(len(self.readiness.calls), 2)


class InstallResultTests(InstallerTestCase):
    def install(self, target=None):
        code, output = self.run_install(target)
        self.assertEqual(code, 0, output)
        return output

    def test_readiness_subprocess_does_not_write_bytecode(self):
        completed = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.object(installer.subprocess, "run", return_value=completed) as run:
            installer._run_readiness(self.target, {"PATH": "", "FACTORY_X": "1", "PYTHONPATH": "src"})
        command = run.call_args.args[0]
        env = run.call_args.kwargs["env"]
        self.assertIn("-B", command[:2])
        self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertNotIn("FACTORY_X", env)
        self.assertNotIn("PYTHONPATH", env)

    def test_managed_file_list_is_exactly_the_nine_assets(self):
        self.assertEqual(tuple(installer.MANAGED_FILES), EXPECTED_MANAGED)
        self.assertEqual(installer.MANIFEST_PATH, MANIFEST)
        for relative in EXPECTED_MANAGED:
            self.assertTrue((installer.SOURCE_ROOT / relative).is_file(), relative)

    def test_installed_files_are_exact_copies_of_the_source(self):
        output = self.install()
        for relative in EXPECTED_MANAGED:
            self.assertEqual((self.target / relative).read_bytes(), self.source_bytes(relative))
            self.assertIn(f"[created]   {relative}", output)
        self.assertIn(f"[created]   {MANIFEST}", output)
        self.assertIn("Installed 10 file(s).", output)

    def test_only_managed_files_and_manifest_are_installed(self):
        specify_before = self.tree_hash(self.target / ".specify")
        self.install()
        self.assertEqual(self.installed_files(), set(EXPECTED_MANAGED) | {MANIFEST})
        self.assertEqual(self.tree_hash(self.target / ".specify"), specify_before)

    def test_excluded_assets_are_never_installed(self):
        self.install()
        for relative in (
            "src",
            "specs",
            "tests",
            ".github/hooks",
            ".github/copilot",
            ".factory/policy.json",
            ".factory/model-preferences.json",
            ".factory",
            "scripts/factory_pre_tool_use.ps1",
            "scripts/run_engineer_delegation_test.ps1",
        ):
            with self.subTest(relative=relative):
                self.assertFalse(os.path.lexists(self.target / relative))
        self.assertEqual(
            sorted(p.name for p in (self.target / ".specify").iterdir()),
            sorted({Path(r).parts[1] for r in readiness.SPECKIT_FILES}),
        )

    def test_no_source_root_path_appears_in_any_installed_file(self):
        output = self.install()
        needles = {str(installer.SOURCE_ROOT), installer.SOURCE_ROOT.as_posix()}
        needles = {n.lower() for n in needles} | {n for n in needles}
        for relative in self.installed_files():
            text = (self.target / relative).read_bytes().decode("utf-8", errors="replace")
            for needle in needles:
                with self.subTest(relative=relative, needle=needle):
                    self.assertNotIn(needle, text)
                    self.assertNotIn(needle, text.lower())
        for needle in needles:
            self.assertNotIn(needle, output)

    def test_manifest_content(self):
        self.install()
        data = (self.target / MANIFEST).read_bytes()
        document = json.loads(data.decode("utf-8"))
        self.assertEqual(set(document), {"version", "source_revision", "files"})
        self.assertIs(type(document["version"]), int)
        self.assertEqual(document["version"], 1)
        self.assertEqual(tuple(sorted(document["files"])), tuple(sorted(EXPECTED_MANAGED)))
        self.assertEqual(len(document["files"]), 9)
        for relative, value in document["files"].items():
            self.assertEqual(value, installer.fingerprint(self.source_bytes(relative)))
            self.assertRegex(value, r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(document["source_revision"], r"^(unknown|[0-9a-f]{40,64})$")

    def test_manifest_contains_no_absolute_paths_or_local_locations(self):
        self.install()
        text = (self.target / MANIFEST).read_text(encoding="utf-8")
        document = json.loads(text)
        for relative in document["files"]:
            self.assertFalse(os.path.isabs(relative), relative)
            self.assertNotIn("\\", relative)
            self.assertFalse(re.match(r"^[A-Za-z]:", relative), relative)
        for needle in (
            str(self.target), self.target.as_posix(), str(installer.SOURCE_ROOT),
            installer.SOURCE_ROOT.as_posix(), str(self.base),
        ):
            self.assertNotIn(needle, text)

    def test_manifest_is_deterministic_across_targets(self):
        self.install()
        second = self.make_repo("second")
        self.install(second)
        first_bytes = (self.target / MANIFEST).read_bytes()
        self.assertEqual((second / MANIFEST).read_bytes(), first_bytes)
        document = json.loads(first_bytes.decode("utf-8"))
        self.assertEqual(first_bytes, (json.dumps(document, indent=2, sort_keys=True) + "\n").encode())

    def test_manifest_is_written_last(self):
        created = []
        original = installer._create_exclusive

        def spy(path, data):
            created.append(Path(path).relative_to(self.target).as_posix())
            return original(path, data)

        with mock.patch.object(installer, "_create_exclusive", spy):
            self.install()
        self.assertEqual(created[-1], MANIFEST)
        self.assertEqual(set(created[:-1]), set(EXPECTED_MANAGED))

    def test_manifest_is_not_ignored_and_preferences_are_after_install(self):
        self.install()
        self.assertFalse(self.is_ignored(MANIFEST))
        self.assertTrue(self.is_ignored(PREFERENCES))

    def test_installed_readiness_check_runs_once_against_the_target(self):
        output = self.install()
        self.assertEqual(self.readiness.calls, [str(self.target)])
        self.assertIn("Installed readiness check:", output)
        self.assertIn("Verdict: ready with limitations", output)
        self.assertIn("Next steps:", output)

    def test_not_ready_installed_check_exits_3_without_rollback(self):
        self.readiness.returncode = 1
        code, output = self.run_install(self.target)
        self.assertEqual(code, 3, output)
        self.assertEqual(self.installed_files(), set(EXPECTED_MANAGED) | {MANIFEST})

    def test_deleted_managed_file_is_recreated_alone(self):
        self.install()
        victim = self.target / EXPECTED_MANAGED[6]
        victim.unlink()
        other = self.target / EXPECTED_MANAGED[0]
        before = other.read_bytes()
        code, output = self.run_install(self.target)
        self.assertEqual(code, 0, output)
        self.assertEqual(victim.read_bytes(), self.source_bytes(EXPECTED_MANAGED[6]))
        self.assertEqual(other.read_bytes(), before)
        self.assertIn("Installed 1 file(s).", output)


class ExcludeTests(InstallerTestCase):
    def seed_exclude(self, data):
        self.exclude.parent.mkdir(parents=True, exist_ok=True)
        self.exclude.write_bytes(data)

    def install_ok(self):
        code, output = self.run_install(self.target)
        self.assertEqual(code, 0, output)
        return output

    def test_entry_is_appended_once_and_takes_effect(self):
        seed = b"# local rules\n"
        self.seed_exclude(seed)
        output = self.install_ok()
        self.assertEqual(self.exclude.read_bytes(), seed + ENTRY.encode() + b"\n")
        self.assertEqual(self.entry_lines(), [ENTRY])
        self.assertTrue(self.is_ignored())
        self.assertIn(f"[appended]  {ENTRY}", output)

    def test_existing_bytes_are_preserved_exactly(self):
        seed = b"# mine\r\n*.log\r\n# caf\xe9\n\n\n"
        self.seed_exclude(seed)
        self.install_ok()
        after = self.exclude.read_bytes()
        self.assertTrue(after.startswith(seed))
        self.assertEqual(after[len(seed):], ENTRY.encode() + b"\n")

    def test_missing_trailing_newline_gets_exactly_one_newline(self):
        self.seed_exclude(b"*.log")
        self.install_ok()
        self.assertEqual(self.exclude.read_bytes(), b"*.log\n" + ENTRY.encode() + b"\n")

    def test_absent_exclude_file_is_created(self):
        self.exclude.unlink()
        self.install_ok()
        self.assertEqual(self.exclude.read_bytes(), ENTRY.encode() + b"\n")
        self.assertTrue(self.is_ignored())

    def test_absent_info_directory_and_file_are_created(self):
        shutil.rmtree(self.target / ".git" / "info")
        code, output = self.run_install(self.target, "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertIn("creates info directory and file", output)
        self.assertFalse((self.target / ".git" / "info").exists())
        self.install_ok()
        self.assertEqual(self.exclude.read_bytes(), ENTRY.encode() + b"\n")
        self.assertTrue(self.is_ignored())

    def test_path_already_ignored_through_gitignore_leaves_exclude_untouched(self):
        for index, rule in enumerate((".factory/\n", ".factory/model-preferences.json\n")):
            with self.subTest(rule=rule):
                self.target = self.make_repo(f"ignored{index}")
                self.exclude = self.target / ".git" / "info" / "exclude"
                self.write_target(".gitignore", rule.encode())
                seed = b"# keep me"
                self.seed_exclude(seed)
                output = self.install_ok()
                self.assertEqual(self.exclude.read_bytes(), seed)
                self.assertIn("already ignored by", output)
                self.assertIn(".gitignore", output)
                self.assertNotIn("[appended]", output)
                self.assertTrue(self.is_ignored())

    def test_entry_already_present_is_not_duplicated_across_runs(self):
        seed = b"# rules\n" + ENTRY.encode() + b"\n"
        self.seed_exclude(seed)
        self.install_ok()
        self.assertEqual(self.exclude.read_bytes(), seed)
        self.install_ok()
        self.install_ok()
        self.assertEqual(self.exclude.read_bytes(), seed)
        self.assertEqual(self.entry_lines(), [ENTRY])

    def test_repeat_runs_after_append_never_duplicate_the_entry(self):
        self.install_ok()
        once = self.exclude.read_bytes()
        self.install_ok()
        self.install_ok()
        self.assertEqual(self.exclude.read_bytes(), once)
        self.assertEqual(self.entry_lines(), [ENTRY])

    def test_entry_present_without_trailing_newline_is_not_duplicated(self):
        seed = ENTRY.encode()
        self.seed_exclude(seed)
        self.install_ok()
        self.assertEqual(self.exclude.read_bytes(), seed)

    def test_entry_negated_by_a_later_rule_exits_1_before_any_asset(self):
        negated_exclude = f"{ENTRY}\n!{ENTRY}\n".encode()
        self.seed_exclude(negated_exclude)
        before = self.tree_hash(self.target)
        code, output = self.run_install(self.target)
        self.assertEqual(code, 1, output)
        self.assertEqual(self.tree_hash(self.target), before)
        self.assertEqual(self.installed_files(), set())
        self.assertFalse(self.is_ignored())
        self.assertEqual(self.readiness.calls, [])
        self.assertIn("would not take effect", output)

    def test_entry_negated_through_gitignore_exits_1_before_any_asset(self):
        self.seed_exclude(ENTRY.encode() + b"\n")
        self.write_target(".gitignore", f"!{PREFERENCES}\n".encode())
        self.assertFalse(self.is_ignored())
        before = self.tree_hash(self.target)
        code, output = self.run_install(self.target)
        self.assertEqual(code, 1, output)
        self.assertEqual(self.tree_hash(self.target), before)
        self.assertEqual(self.readiness.calls, [])

    def test_dry_run_leaves_existing_exclude_byte_identical(self):
        seed = b"*.log"
        self.seed_exclude(seed)
        before = self.tree_hash(self.target)
        code, output = self.run_install(self.target, "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.exclude.read_bytes(), seed)
        self.assertEqual(self.tree_hash(self.target), before)

    def test_dry_run_leaves_absent_exclude_absent(self):
        self.exclude.unlink()
        code, output = self.run_install(self.target, "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertFalse(self.exclude.exists())
        self.assertIn("creates file", output)

    def test_symlinked_exclude_file_is_refused(self):
        outside = self.base / "outside-exclude"
        outside.write_bytes(b"# outside\n")
        self.exclude.unlink()
        try:
            os.symlink(outside, self.exclude)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"this OS or account cannot create symlinks: {error}")
        before = self.tree_hash(self.target)
        code, output = self.run_install(self.target)
        self.assertEqual(code, 1, output)
        self.assertIn("symlink", output)
        self.assertEqual(outside.read_bytes(), b"# outside\n")
        self.assertTrue(self.exclude.is_symlink())
        self.assertEqual(self.tree_hash(self.target), before)
        self.assertEqual(self.installed_files(), set())

    def test_exclude_is_applied_before_any_asset_is_written(self):
        seen = []
        original = installer._create_exclusive

        def spy(path, data):
            if not seen:
                seen.append(ENTRY.encode() in self.exclude.read_bytes())
            return original(path, data)

        with mock.patch.object(installer, "_create_exclusive", spy):
            self.install_ok()
        self.assertEqual(seen, [True])

    def test_failed_exclude_verification_stops_before_any_asset(self):
        preference_checks = []

        def hook(arguments):
            if "check-ignore" in arguments and arguments[-1] == PREFERENCES:
                preference_checks.append(arguments)
                if len(preference_checks) >= 2:
                    return subprocess.CompletedProcess(arguments, 1, "", "")
            return None

        self.runner.git_hook = hook
        code, output = self.run_install(self.target)
        self.assertEqual(code, 1, output)
        self.assertGreaterEqual(len(preference_checks), 2)
        self.assertEqual(self.installed_files(), set())
        self.assertFalse((self.target / ".github").exists())
        self.assertFalse((self.target / "scripts").exists())
        self.assertIn("still not ignored", output)
        self.assertIn("no assets were written", output)
        self.assertEqual(self.readiness.calls, [])
        # The appended line is reported as left in place.
        self.assertEqual(self.entry_lines(), [ENTRY])

    def test_unestablishable_ignore_state_writes_nothing(self):
        def hook(arguments):
            if "check-ignore" in arguments and arguments[-1] == PREFERENCES:
                return subprocess.CompletedProcess(arguments, 128, "", "fatal")
            return None

        self.runner.git_hook = hook
        before = self.tree_hash(self.target)
        code, output = self.run_install(self.target)
        self.assertEqual(code, 1, output)
        self.assertEqual(self.tree_hash(self.target), before)


class AmendmentTestCase(InstallerTestCase):
    def commit(self, repo):
        self.git(
            "-c", "user.name=tester", "-c", "user.email=tester@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "-q", "-m", "baseline", cwd=repo,
        )

    def fresh_target(self, name):
        self.target = self.make_repo(name)
        self.exclude = self.target / ".git" / "info" / "exclude"
        return self.target

    def leftover_temps(self):
        return sorted(p for p in self.installed_files() if p.endswith(".sf-tmp"))

    def file_hashes(self, relatives):
        return {
            relative: hashlib.sha256((self.target / relative).read_bytes()).hexdigest()
            for relative in relatives
        }

    def assert_installed_exactly(self):
        for relative in EXPECTED_MANAGED:
            self.assertEqual((self.target / relative).read_bytes(), self.source_bytes(relative))
        self.assertTrue((self.target / MANIFEST).is_file())
        self.assertEqual(self.leftover_temps(), [])


class ManifestIgnoreTests(AmendmentTestCase):
    def test_ignored_manifest_is_refused_before_any_write_naming_the_rule(self):
        cases = (
            (".gitignore", ".github/software-factory/"),
            (".gitignore", "install-manifest.json"),
            (".gitignore", "*.json"),
            (".git/info/exclude", "install-manifest.json"),
        )
        for index, (source, pattern) in enumerate(cases):
            with self.subTest(source=source, pattern=pattern):
                self.fresh_target(f"ignored{index}")
                if source == ".gitignore":
                    self.write_target(".gitignore", (pattern + "\n").encode())
                else:
                    self.exclude.write_bytes(self.exclude.read_bytes() + (pattern + "\n").encode())
                exclude_before = self.exclude.read_bytes()
                output = self.assert_refused_without_writing(self.target)
                self.assertIn(MANIFEST, output)
                self.assertIn(pattern, output)
                self.assertIn(source if source == ".gitignore" else "exclude", output)
                self.assertIn("Nothing was written", output)
                self.assertEqual(self.exclude.read_bytes(), exclude_before)
                self.assertEqual(self.installed_files() - {".gitignore"}, set())

    def test_ignored_manifest_is_refused_in_dry_run_too(self):
        self.write_target(".gitignore", b"install-manifest.json\n")
        output = self.assert_refused_without_writing(self.target, "--dry-run")
        self.assertIn(".gitignore:1:install-manifest.json", output)

    def test_negated_manifest_rule_is_not_an_ignore(self):
        self.write_target(".gitignore", b"install-manifest.json\n!install-manifest.json\n")
        code, output = self.run_install(self.target)
        self.assertEqual(code, 0, output)
        self.assertTrue((self.target / MANIFEST).is_file())

    def test_manifest_becoming_ignored_after_write_is_not_reported_as_success(self):
        calls = []

        def hook(arguments):
            if "check-ignore" in arguments and arguments[-1] == MANIFEST:
                calls.append(arguments)
                if len(calls) >= 2:
                    return subprocess.CompletedProcess(
                        arguments, 0, f".gitignore:1:*.json\t{MANIFEST}\n", ""
                    )
            return None

        self.runner.git_hook = hook
        code, output = self.run_install(self.target)
        self.assertEqual(code, 1, output)
        self.assertGreaterEqual(len(calls), 2)
        self.assertIn("final verification failed", output)
        self.assertIn("not verified as shareable", output)
        self.assertNotIn("Installed", output)
        self.assertNotIn("already installed", output)
        self.assertEqual(self.readiness.calls, [])
        self.assertEqual(self.installed_files(), set(EXPECTED_MANAGED) | {MANIFEST})

    def test_manifest_that_is_a_symlink_is_a_conflict_not_a_refusal(self):
        link = self.target / MANIFEST
        link.parent.mkdir(parents=True)
        try:
            os.symlink(self.base / "missing-manifest-target", link)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"this OS or account cannot create symlinks: {error}")
        before = self.tree_hash(self.target)
        code, output = self.run_install(self.target)
        self.assertEqual(code, 1, output)
        self.assertIn(f"[conflict]  {MANIFEST}: not a regular file (symlink)", output)
        self.assertIn("Nothing was written", output)
        self.assertEqual(self.tree_hash(self.target), before)
        self.assertFalse((self.base / "missing-manifest-target").exists())

    def test_manifest_that_is_a_directory_is_a_conflict_not_a_refusal(self):
        blocker = self.target / MANIFEST
        blocker.mkdir(parents=True)
        (blocker / "inside.txt").write_text("user data\n", encoding="utf-8")
        for extra in ((), ("--dry-run",)):
            with self.subTest(extra=extra):
                before = self.tree_hash(self.target)
                code, output = self.run_install(self.target, *extra)
                self.assertEqual(code, 1, output)
                self.assertIn(f"[conflict]  {MANIFEST}: not a regular file", output)
                self.assertNotIn("Refused:", output)
                self.assertEqual(self.tree_hash(self.target), before)
        self.assertEqual(self.installed_files() - {MANIFEST + "/inside.txt"}, set())
        self.assertEqual(self.readiness.calls, [])


class TrackedPreferencesTests(AmendmentTestCase):
    def track(self, stage_only, excluded_first=False):
        if excluded_first:
            self.exclude.write_bytes(self.exclude.read_bytes() + ENTRY.encode() + b"\n")
        self.write_target(PREFERENCES, b'{"version": 1}\n')
        self.git("add", "-f", PREFERENCES, cwd=self.target)
        if not stage_only:
            self.commit(self.target)

    def test_tracked_preferences_are_refused_with_guidance_and_nothing_written(self):
        cases = (
            ("committed", False, False),
            ("staged only via git add -f", True, False),
            ("staged via git add -f although already excluded", True, True),
        )
        for index, (label, stage_only, excluded_first) in enumerate(cases):
            with self.subTest(label):
                self.fresh_target(f"tracked{index}")
                self.track(stage_only, excluded_first)
                exclude_before = self.exclude.read_bytes()
                output = self.assert_refused_without_writing(self.target)
                self.assertIn("already tracked by Git", output)
                self.assertIn(f"git rm --cached {PREFERENCES}", output)
                self.assertIn("Nothing was written", output)
                self.assertEqual(self.exclude.read_bytes(), exclude_before)
                self.assertEqual((self.target / PREFERENCES).read_bytes(), b'{"version": 1}\n')
                self.assertFalse((self.target / "scripts").exists())
                self.assertFalse((self.target / ".github").exists())

    def test_tracked_preferences_are_refused_in_dry_run_too(self):
        self.track(stage_only=True)
        output = self.assert_refused_without_writing(self.target, "--dry-run")
        self.assertIn("git rm --cached", output)


class ExclusiveCreationTests(AmendmentTestCase):
    PLANTED = b"planted by someone else after the conflict check\n"

    def plant_hook(self, relative):
        destination = self.target / relative
        seen = []

        def hook(path):
            seen.append(Path(path))
            if Path(path) == destination:
                destination.write_bytes(self.PLANTED)

        return hook, seen

    def user_files(self):
        self.write_target("scripts/mine.py", b"print('mine')\n")
        self.write_target(".github/agents/custom.agent.md", b"custom\n")
        return self.file_hashes(("scripts/mine.py", ".github/agents/custom.agent.md"))

    def assert_planted_destination_survives(self, link_patch):
        relative = EXPECTED_MANAGED[2]
        users = self.user_files()
        hook, seen = self.plant_hook(relative)
        with mock.patch.object(installer, "_before_publish", hook), link_patch as link:
            code, output = self.run_install(self.target)
        self.assertEqual(code, 1, output)
        self.assertGreaterEqual(link.call_count, 1)
        self.assertEqual((self.target / relative).read_bytes(), self.PLANTED)
        self.assertIn(f"[conflict]  {relative}: appeared during installation", output)
        self.assertIn("Created: " + ", ".join(EXPECTED_MANAGED[:2]), output)
        self.assertIn("Existing files were not modified", output)
        self.assertEqual(self.leftover_temps(), [])
        for later in EXPECTED_MANAGED[3:]:
            self.assertFalse((self.target / later).exists(), later)
        self.assertFalse((self.target / MANIFEST).exists())
        self.assertEqual(self.file_hashes(users), users)
        self.assertEqual(self.readiness.calls, [])

        # Re-run while the planted file is still there: reported, nothing more written.
        before = self.tree_hash(self.target)
        code, output = self.run_install(self.target)
        self.assertEqual(code, 1, output)
        self.assertIn(f"[conflict]  {relative}: different content", output)
        self.assertEqual(self.tree_hash(self.target), before)
        self.assertEqual((self.target / relative).read_bytes(), self.PLANTED)

        # Removing the planted file lets the re-run complete the installation.
        (self.target / relative).unlink()
        code, output = self.run_install(self.target)
        self.assertEqual(code, 0, output)
        self.assert_installed_exactly()
        self.assertEqual(self.file_hashes(users), users)

    def test_destination_created_before_publish_is_not_overwritten_with_hard_links(self):
        self.assert_planted_destination_survives(mock.patch.object(os, "link", wraps=os.link))

    def test_destination_created_before_publish_is_not_overwritten_without_hard_links(self):
        no_links = mock.patch.object(os, "link", side_effect=OSError(errno.EPERM, "no hard links"))
        self.assert_planted_destination_survives(no_links)

    def test_install_completes_through_the_no_hard_link_fallback(self):
        with mock.patch.object(os, "link", side_effect=OSError(errno.EPERM, "no hard links")) as link:
            code, output = self.run_install(self.target)
        self.assertEqual(code, 0, output)
        self.assertEqual(link.call_count, 10)
        self.assert_installed_exactly()

    def test_hook_runs_once_per_created_file_before_publication(self):
        paths = []
        with mock.patch.object(installer, "_before_publish", lambda path: paths.append(path)):
            code, output = self.run_install(self.target)
        self.assertEqual(code, 0, output)
        relatives = [Path(p).relative_to(self.target).as_posix() for p in paths]
        self.assertEqual(relatives, list(EXPECTED_MANAGED) + [MANIFEST])


class JunctionMixin:
    def make_junction(self, link, destination):
        if os.name != "nt":
            self.skipTest("directory junctions exist only on Windows")
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(destination)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            self.skipTest(f"could not create a junction: {result.stdout} {result.stderr}")
        self.addCleanup(self.remove_junction, link)

    @staticmethod
    def remove_junction(link):
        try:
            os.rmdir(link)  # removes only the junction, never its contents
        except (FileNotFoundError, NotADirectoryError):
            pass


class LinkConflictTests(JunctionMixin, AmendmentTestCase):
    def make_symlink(self, link, destination, directory=False):
        link.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.symlink(destination, link, target_is_directory=directory)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"this OS or account cannot create symlinks: {error}")

    def assert_blocked(self, expected_lines, untouched=()):
        before = self.tree_hash(self.target)
        exclude_before = self.exclude.read_bytes()
        outside_before = [self.tree_hash(path) for path in untouched]
        code, output = self.run_install(self.target)
        self.assertEqual(code, 1, output)
        for line in expected_lines:
            self.assertIn(line, output)
        self.assertIn("Nothing was written", output)
        self.assertEqual(self.tree_hash(self.target), before)
        self.assertEqual(self.exclude.read_bytes(), exclude_before)
        self.assertEqual([self.tree_hash(path) for path in untouched], outside_before)
        self.assertEqual(self.readiness.calls, [])
        return output

    def test_junctioned_github_directory_is_a_blocked_path(self):
        outside = self.base / "outside-github"
        outside.mkdir()
        (outside / "keep.md").write_text("user file\n", encoding="utf-8")
        self.make_junction(self.target / ".github", outside)
        self.assert_blocked(
            [
                f"[conflict]  {EXPECTED_MANAGED[2]}: blocked path (junction)",
                f"[conflict]  {MANIFEST}: blocked path (junction)",
            ],
            untouched=[outside],
        )
        self.assertEqual(os.listdir(outside), ["keep.md"])
        self.assertFalse((self.target / "scripts").exists())

    def test_junctioned_scripts_directory_is_a_blocked_path(self):
        outside = self.base / "outside-scripts"
        outside.mkdir()
        self.make_junction(self.target / "scripts", outside)
        self.assert_blocked(
            [f"[conflict]  {EXPECTED_MANAGED[6]}: blocked path (junction)"], untouched=[outside]
        )
        self.assertEqual(os.listdir(outside), [])
        self.assertFalse((self.target / ".github").exists())

    def test_file_symlink_at_a_managed_path_is_refused(self):
        outside = self.base / "outside.py"
        outside.write_bytes(b"# not the factory's file\n")
        self.make_symlink(self.target / EXPECTED_MANAGED[6], outside)
        self.write_target(".github/agents/custom.agent.md", b"custom\n")
        self.assert_blocked(
            [f"[conflict]  {EXPECTED_MANAGED[6]}: not a regular file (symlink)"], untouched=[]
        )
        self.assertEqual(outside.read_bytes(), b"# not the factory's file\n")
        self.assertTrue((self.target / EXPECTED_MANAGED[6]).is_symlink())
        self.assertEqual((self.target / ".github/agents/custom.agent.md").read_bytes(), b"custom\n")

    def test_dangling_symlink_at_a_managed_path_is_refused_and_not_written_through(self):
        missing = self.base / "does-not-exist.py"
        self.make_symlink(self.target / EXPECTED_MANAGED[6], missing)
        self.assert_blocked([f"[conflict]  {EXPECTED_MANAGED[6]}: not a regular file (symlink)"])
        self.assertFalse(os.path.lexists(missing))
        self.assertTrue((self.target / EXPECTED_MANAGED[6]).is_symlink())

    def test_symlinked_ancestor_directory_is_a_blocked_path(self):
        outside = self.base / "outside-scripts"
        outside.mkdir()
        self.make_symlink(self.target / "scripts", outside, directory=True)
        self.assert_blocked(
            [f"[conflict]  {EXPECTED_MANAGED[6]}: blocked path (symlink)"], untouched=[outside]
        )
        self.assertEqual(os.listdir(outside), [])

    def test_symlinked_ancestor_of_the_agents_is_a_blocked_path(self):
        outside = self.base / "outside-agents"
        outside.mkdir()
        self.make_symlink(self.target / ".github" / "agents", outside, directory=True)
        self.assert_blocked(
            [f"[conflict]  {EXPECTED_MANAGED[0]}: blocked path (symlink)"], untouched=[outside]
        )
        self.assertEqual(os.listdir(outside), [])


class PartialWriteTests(AmendmentTestCase):
    def failing_write(self, fail_on):
        original = installer._write_all
        calls = {"count": 0}

        def write(fd, data):
            calls["count"] += 1
            if calls["count"] == fail_on:
                os.close(fd)
                raise OSError(errno.EIO, "injected write failure")
            return original(fd, data)

        return mock.patch.object(installer, "_write_all", write)

    def user_files(self):
        self.write_target("scripts/mine.py", b"print('mine')\n")
        self.write_target(".github/agents/custom.agent.md", b"custom\n")
        return self.file_hashes(("scripts/mine.py", ".github/agents/custom.agent.md"))

    def test_write_failure_on_the_third_file_leaves_existing_files_and_rerun_completes(self):
        users = self.user_files()
        with self.failing_write(3):
            code, output = self.run_install(self.target)
        self.assertEqual(code, 1, output)
        self.assertIn(f"error: {EXPECTED_MANAGED[2]} could not be written", output)
        self.assertIn("Created: " + ", ".join(EXPECTED_MANAGED[:2]), output)
        self.assertIn("Existing files were not modified", output)
        self.assertEqual(self.file_hashes(users), users)
        self.assertEqual(self.leftover_temps(), [])
        self.assertFalse((self.target / EXPECTED_MANAGED[2]).exists())
        self.assertFalse((self.target / MANIFEST).exists())
        self.assertEqual(self.readiness.calls, [])
        for relative in EXPECTED_MANAGED[:2]:
            self.assertEqual((self.target / relative).read_bytes(), self.source_bytes(relative))

        code, output = self.run_install(self.target)
        self.assertEqual(code, 0, output)
        self.assertIn(f"[unchanged] {EXPECTED_MANAGED[0]}", output)
        self.assertIn("Installed 8 file(s).", output)
        self.assert_installed_exactly()
        self.assertEqual(self.file_hashes(users), users)
        self.assertEqual(self.entry_lines(), [ENTRY])

    def test_write_failure_in_the_fallback_removes_the_partial_destination(self):
        users = self.user_files()
        no_links = mock.patch.object(os, "link", side_effect=OSError(errno.EPERM, "no hard links"))
        # Writes per file without hard links: temp file, then the destination itself.
        with no_links, self.failing_write(6):
            code, output = self.run_install(self.target)
        self.assertEqual(code, 1, output)
        self.assertIn("Created: " + ", ".join(EXPECTED_MANAGED[:2]), output)
        self.assertFalse(os.path.lexists(self.target / EXPECTED_MANAGED[2]))
        self.assertEqual(self.leftover_temps(), [])
        self.assertEqual(self.file_hashes(users), users)

        code, output = self.run_install(self.target)
        self.assertEqual(code, 0, output)
        self.assert_installed_exactly()

    def test_write_failure_on_the_manifest_leaves_it_missing_and_rerun_completes(self):
        with self.failing_write(10):
            code, output = self.run_install(self.target)
        self.assertEqual(code, 1, output)
        self.assertIn(f"error: {MANIFEST} could not be written", output)
        self.assertIn("Created: " + ", ".join(EXPECTED_MANAGED), output)
        self.assertFalse((self.target / MANIFEST).exists())
        self.assertEqual(self.leftover_temps(), [])

        code, output = self.run_install(self.target)
        self.assertEqual(code, 0, output)
        self.assertIn("Installed 1 file(s).", output)
        self.assert_installed_exactly()

    def test_unmodified_preinstalled_files_keep_bytes_and_mtimes_after_a_failed_run(self):
        for relative in EXPECTED_MANAGED[:2]:
            self.write_target(relative, self.source_bytes(relative))
        before = {r: (self.target / r).stat().st_mtime_ns for r in EXPECTED_MANAGED[:2]}
        with self.failing_write(2):
            code, output = self.run_install(self.target)
        self.assertEqual(code, 1, output)
        self.assertEqual(
            {r: (self.target / r).stat().st_mtime_ns for r in EXPECTED_MANAGED[:2]}, before
        )
        self.assertIn("Created: " + EXPECTED_MANAGED[2], output)


class LeftoverTempTests(AmendmentTestCase):
    LEFTOVER = ".github/agents/.engineer.agent.md.sf-tmp"

    def test_leftover_temp_file_is_removed_by_the_next_real_run_only(self):
        leftover = self.write_target(self.LEFTOVER, b"half written")
        before = self.tree_hash(self.target)
        code, output = self.run_install(self.target, "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.tree_hash(self.target), before)
        self.assertEqual(leftover.read_bytes(), b"half written")

        code, output = self.run_install(self.target)
        self.assertEqual(code, 0, output)
        self.assertFalse(os.path.lexists(leftover))
        self.assertEqual(self.installed_files(), set(EXPECTED_MANAGED) | {MANIFEST})
        self.assert_installed_exactly()

    def test_leftover_temp_file_beside_an_installed_file_is_removed(self):
        self.assertEqual(self.run_install(self.target)[0], 0)
        leftover = self.write_target(self.LEFTOVER, b"junk")
        before = {r: (self.target / r).stat().st_mtime_ns for r in EXPECTED_MANAGED}
        code, output = self.run_install(self.target)
        self.assertEqual(code, 0, output)
        self.assertFalse(os.path.lexists(leftover))
        self.assertIn("already installed", output)
        self.assertEqual({r: (self.target / r).stat().st_mtime_ns for r in EXPECTED_MANAGED}, before)

    def test_leftover_temp_that_is_not_a_regular_file_is_a_conflict(self):
        directory = self.target / self.LEFTOVER
        directory.mkdir(parents=True)
        (directory / "inside.txt").write_text("x", encoding="utf-8")
        before = self.tree_hash(self.target)
        code, output = self.run_install(self.target)
        self.assertEqual(code, 1, output)
        self.assertIn("temporary file", output)
        self.assertIn("Nothing was written", output)
        self.assertEqual(self.tree_hash(self.target), before)


class RepeatInstallTests(AmendmentTestCase):
    def test_repeat_install_is_a_byte_identical_no_op_with_stable_mtimes(self):
        self.assertEqual(self.run_install(self.target)[0], 0)
        before = self.tree_hash(self.target)
        mtimes = {r: (self.target / r).stat().st_mtime_ns for r in self.installed_files()}
        code, output = self.run_install(self.target)
        self.assertEqual(code, 0, output)
        self.assertIn("already installed", output)
        self.assertNotIn("[created]", output)
        self.assertNotIn("[appended]", output)
        self.assertEqual(self.tree_hash(self.target), before)
        self.assertEqual({r: (self.target / r).stat().st_mtime_ns for r in self.installed_files()}, mtimes)

    def test_deleted_managed_file_is_recreated_alone_leaving_other_bytes_and_mtimes(self):
        self.assertEqual(self.run_install(self.target)[0], 0)
        for victim in (EXPECTED_MANAGED[6], MANIFEST):
            with self.subTest(victim=victim):
                (self.target / victim).unlink()
                others = self.installed_files()
                mtimes = {r: (self.target / r).stat().st_mtime_ns for r in others}
                hashes = self.file_hashes(others)
                exclude_before = self.exclude.read_bytes()
                code, output = self.run_install(self.target)
                self.assertEqual(code, 0, output)
                self.assertEqual(output.count("[created]"), 1, output)
                self.assertIn(f"[created]   {victim}", output)
                self.assertEqual(
                    {r: (self.target / r).stat().st_mtime_ns for r in others}, mtimes
                )
                self.assertEqual(self.file_hashes(others), hashes)
                self.assertEqual(self.exclude.read_bytes(), exclude_before)
                self.assertTrue((self.target / victim).is_file())
        self.assert_installed_exactly()


class ExcludeLinkTests(JunctionMixin, AmendmentTestCase):
    """The exclude file's directory chain is checked like any other ancestor (finding 1)."""

    def junction_info_to(self, outside):
        shutil.rmtree(self.target / ".git" / "info")
        self.make_junction(self.target / ".git" / "info", outside)

    def outside_info(self):
        outside = self.base / "outside-info"
        outside.mkdir()
        (outside / "exclude").write_bytes(b"# someone else's exclude\n")
        return outside

    def test_junctioned_info_directory_is_a_blocked_path_for_dry_and_real_runs(self):
        outside = self.outside_info()
        self.junction_info_to(outside)
        outside_before = self.tree_hash(outside)
        for extra in (("--dry-run",), ()):
            with self.subTest(extra=extra):
                before = self.tree_hash(self.target)
                code, output = self.run_install(self.target, *extra)
                self.assertEqual(code, 1, output)
                self.assertIn("blocked path (junction)", output)
                self.assertIn("Nothing was written", output)
                self.assertNotIn("[exclude]   append", output)
                self.assertEqual(self.tree_hash(self.target), before)
                self.assertEqual(self.tree_hash(outside), outside_before)
        self.assertEqual(self.installed_files() - {".git/info/exclude"}, set())
        self.assertEqual(self.readiness.calls, [])

    def test_info_directory_replaced_by_a_junction_after_planning_is_not_appended_to(self):
        outside = self.outside_info()
        outside_before = self.tree_hash(outside)
        original = installer._plan_exclude

        def plan_then_swap(runner, target):
            plan = original(runner, target)
            self.junction_info_to(outside)
            return plan

        with mock.patch.object(installer, "_plan_exclude", plan_then_swap):
            code, output = self.run_install(self.target)
        self.assertEqual(code, 1, output)
        self.assertIn("could not update the exclude file", output)
        self.assertIn("no assets were written", output)
        self.assertEqual(self.tree_hash(outside), outside_before)
        self.assertEqual(self.installed_files() - {".git/info/exclude"}, set())
        self.assertEqual(self.readiness.calls, [])

    def test_append_exclude_refuses_a_path_that_no_longer_resolves_to_the_expected_one(self):
        outside = self.outside_info()
        self.junction_info_to(outside)
        outside_before = self.tree_hash(outside)
        with self.assertRaises(OSError):
            installer._append_exclude(str(self.exclude))
        self.assertEqual(self.tree_hash(outside), outside_before)

    def test_append_exclude_refuses_a_non_regular_exclude_path(self):
        self.exclude.unlink()
        self.exclude.mkdir()
        with self.assertRaises(OSError):
            installer._append_exclude(str(self.exclude))
        self.assertEqual(os.listdir(self.exclude), [])


class NegatedPreferencesTests(AmendmentTestCase):
    """A rule that negates the preferences path cannot be fixed by an exclude entry (finding 2)."""

    RULE = f".gitignore:1:!{PREFERENCES}"

    def test_negating_gitignore_rule_is_cannot_establish_for_dry_and_real_runs(self):
        self.write_target(".gitignore", f"!{PREFERENCES}\n".encode())
        results = {}
        for label, extra in (("dry", ("--dry-run",)), ("real", ())):
            before = self.tree_hash(self.target)
            exclude_before = self.exclude.read_bytes()
            code, output = self.run_install(self.target, *extra)
            results[label] = (code, output)
            self.assertEqual(code, 1, output)
            self.assertIn(self.RULE, output)
            self.assertIn("would not take effect", output)
            self.assertNotIn("[exclude]   append", output)
            self.assertNotIn("[created]", output)
            self.assertEqual(self.tree_hash(self.target), before)
            self.assertEqual(self.exclude.read_bytes(), exclude_before)
        self.assertEqual(self.readiness.calls, [])
        plan = lambda text: text.split("Plan:")[0]
        self.assertEqual(plan(results["dry"][1]), plan(results["real"][1]))

    def test_negation_after_a_wildcard_rule_is_also_cannot_establish(self):
        self.write_target(".gitignore", b".factory/*\n!.factory/model-preferences.json\n")
        code, output = self.run_install(self.target, "--dry-run")
        self.assertEqual(code, 1, output)
        self.assertIn(f"!{PREFERENCES}", output)
        self.assertIn("would not take effect", output)
        code, output = self.run_install(self.target)
        self.assertEqual(code, 1, output)
        self.assertEqual(self.installed_files() - {".gitignore"}, set())


class LeftoverCleanupDisclosureTests(AmendmentTestCase):
    """The preview names every leftover temporary file the real run will delete (finding 3)."""

    LEFTOVERS = (
        ".github/agents/.engineer.agent.md.sf-tmp",
        "scripts/.specialist_models.py.sf-tmp",
        ".github/software-factory/.install-manifest.json.sf-tmp",
    )

    def cleanup_lines(self, output):
        return sorted(line for line in output.splitlines() if line.startswith("[cleanup]"))

    def expected_lines(self):
        return sorted(
            f"[cleanup]   {leftover}: remove leftover temporary file" for leftover in self.LEFTOVERS
        )

    def test_dry_run_and_real_run_disclose_each_leftover_and_only_the_real_run_removes_it(self):
        for leftover in self.LEFTOVERS:
            self.write_target(leftover, b"half written")
        before = self.tree_hash(self.target)
        code, dry = self.run_install(self.target, "--dry-run")
        self.assertEqual(code, 0, dry)
        self.assertEqual(self.cleanup_lines(dry), self.expected_lines())
        self.assertEqual(self.tree_hash(self.target), before)

        code, real = self.run_install(self.target)
        self.assertEqual(code, 0, real)
        self.assertEqual(self.cleanup_lines(real), self.expected_lines())
        for leftover in self.LEFTOVERS:
            self.assertFalse(os.path.lexists(self.target / leftover), leftover)

    def test_no_cleanup_line_without_a_leftover(self):
        code, output = self.run_install(self.target, "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertNotIn("[cleanup]", output)

    def test_cleanup_is_not_announced_when_a_conflict_means_nothing_is_removed(self):
        leftover = self.write_target(self.LEFTOVERS[0], b"half written")
        self.write_target("scripts/specialist_models.py", b"# my own script\n")
        code, output = self.run_install(self.target)
        self.assertEqual(code, 1, output)
        self.assertNotIn("[cleanup]", output)
        self.assertEqual(leftover.read_bytes(), b"half written")


class SubprocessEnvironmentTests(InstallerTestCase):
    def test_git_environment_overrides_never_reach_a_subprocess(self):
        seen = []

        def recording(arguments, cwd=None, timeout=None):
            seen.append({name: os.environ.get(name) for name in installer.SCRUBBED_GIT_VARIABLES})
            return self.runner(arguments, cwd=cwd, timeout=timeout)

        bogus = {name: str(self.base / "bogus") for name in installer.SCRUBBED_GIT_VARIABLES}
        self.assertEqual(
            set(bogus),
            {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
             "GIT_OBJECT_DIRECTORY", "GIT_NAMESPACE"},
        )
        with mock.patch.dict(os.environ, bogus):
            code, output = self.run_install(self.target, "--dry-run", runner=recording)
            restored = {name: os.environ.get(name) for name in bogus}
        self.assertEqual(code, 0, output)
        self.assertGreater(len(seen), 5)
        for values in seen:
            self.assertEqual(values, {name: None for name in bogus})
        self.assertEqual(restored, bogus)

        completed = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.object(installer.subprocess, "run", return_value=completed) as run:
            installer._run_readiness(self.target, {"PATH": "", **bogus, "git_dir": "x"})
        env = run.call_args.kwargs["env"]
        self.assertEqual([name for name in env if name.upper() in bogus], [])


class ExcludeEntryMatchingTests(InstallerTestCase):
    def test_has_entry_compares_the_right_stripped_line_only(self):
        self.assertTrue(installer._has_entry(ENTRY.encode() + b"\n"))
        self.assertTrue(installer._has_entry(b"# x\r\n" + ENTRY.encode() + b"  \r\n"))
        self.assertFalse(installer._has_entry(b"  " + ENTRY.encode() + b"\n"))
        self.assertFalse(installer._has_entry(b"\t" + ENTRY.encode() + b"\n"))

    def test_an_indented_entry_is_not_an_entry_so_the_real_one_is_appended(self):
        seed = b"  " + ENTRY.encode() + b"\n"
        self.exclude.write_bytes(seed)
        self.assertFalse(self.is_ignored())
        code, output = self.run_install(self.target)
        self.assertEqual(code, 0, output)
        self.assertEqual(self.exclude.read_bytes(), seed + ENTRY.encode() + b"\n")
        self.assertTrue(self.is_ignored())


class ReportingAndPlanTests(AmendmentTestCase):
    def test_ignored_managed_path_is_a_warning_and_the_installation_continues(self):
        self.write_target(".gitignore", b"scripts/specialist_models.py\n")
        before_exclude = self.exclude.read_bytes()
        code, output = self.run_install(self.target)
        self.assertEqual(code, 0, output)
        self.assertIn(
            "[warning]   scripts/specialist_models.py is ignored by "
            ".gitignore:1:scripts/specialist_models.py; it will not be shared",
            output,
        )
        self.assertEqual(output.count("[warning]"), 1)
        self.assertNotIn("Refused:", output)
        self.assertEqual(
            (self.target / "scripts" / "specialist_models.py").read_bytes(),
            self.source_bytes("scripts/specialist_models.py"),
        )
        self.assertTrue((self.target / MANIFEST).is_file())
        self.assertNotEqual(self.exclude.read_bytes(), before_exclude)

    def test_ancestor_that_is_a_regular_file_is_a_blocked_path_conflict(self):
        agents = self.write_target(".github/agents", b"I am a file, not a directory\n")
        for extra in (("--dry-run",), ()):
            with self.subTest(extra=extra):
                before = self.tree_hash(self.target)
                code, output = self.run_install(self.target, *extra)
                self.assertEqual(code, 1, output)
                for relative in EXPECTED_MANAGED[:5]:
                    self.assertIn(f"[conflict]  {relative}: blocked path (not a directory)", output)
                self.assertIn("Nothing was written", output)
                self.assertEqual(self.tree_hash(self.target), before)
        self.assertEqual(agents.read_bytes(), b"I am a file, not a directory\n")
        self.assertFalse((self.target / "scripts").exists())
        self.assertEqual(self.readiness.calls, [])

    def test_dry_run_whose_ignore_state_cannot_be_established_exits_1(self):
        def hook(arguments):
            if "check-ignore" in arguments and arguments[-1] == PREFERENCES:
                return subprocess.CompletedProcess(arguments, 128, "", "fatal")
            return None

        self.runner.git_hook = hook
        before = self.tree_hash(self.target)
        code, output = self.run_install(self.target, "--dry-run")
        self.assertEqual(code, 1, output)
        self.assertIn("cannot establish the ignore state", output)
        self.assertIn("DRY RUN: nothing was changed.", output)
        self.assertEqual(self.tree_hash(self.target), before)

    def test_dry_run_with_a_git_runner_that_always_times_out_is_not_a_success(self):
        def hook(arguments):
            if "check-ignore" in arguments and arguments[-1] == PREFERENCES:
                raise subprocess.TimeoutExpired(arguments, 15)
            return None

        self.runner.git_hook = hook
        code, output = self.run_install(self.target, "--dry-run")
        self.assertEqual(code, 1, output)
        self.assertIn("timed out", output)


if __name__ == "__main__":
    unittest.main()
