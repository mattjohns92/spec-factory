"""`specfactory upgrade` engine (scripts/upgrade_factory.py) and its CLI command."""

import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import check_factory_readiness as readiness  # noqa: E402
import install_factory as installer  # noqa: E402
import upgrade_factory as upgrade  # noqa: E402
from specfactory import bundle, cli  # noqa: E402
from tests.unit.test_installer import FakeReadiness, Runner, specify_on_path  # noqa: E402


MANAGED = readiness.MANAGED_FILES
MANIFEST = readiness.MANIFEST_PATH
PREFERENCES = readiness.PREFERENCES_PATH
WORKSPACE_INDEX = readiness.WORKSPACE_MANIFEST_PATH
OLD_VERSION = "specfactory-0.1.1"
BUNDLED_VERSION = "specfactory-0.1.4"


class UpgradeCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(os.path.realpath(temporary.name))
        patcher = mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CEILING_DIRECTORIES"):
            os.environ.pop(name, None)
        self.runner = Runner()
        self.readiness = FakeReadiness()
        bundled = mock.patch.object(installer, "_source_revision", return_value=BUNDLED_VERSION)
        bundled.start()
        self.addCleanup(bundled.stop)

    def git(self, *arguments, cwd=None):
        return subprocess.run(["git", *arguments], cwd=cwd, capture_output=True, text=True, check=True)

    def spec_kit(self, path):
        for relative in readiness.SPECKIT_FILES:
            file = path / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("content\n", encoding="utf-8")

    def make_repo(self, name="project"):
        path = self.base / name
        path.mkdir()
        self.git("init", "-q", str(path))
        self.spec_kit(path)
        return path

    def make_workspace(self):
        workspace = self.base / "workspace"
        workspace.mkdir()
        self.spec_kit(workspace)
        for relative in ("services/api", "clients/web"):
            child = workspace / relative
            child.mkdir(parents=True)
            self.git("init", "-q", str(child))
            (child / "tracked.txt").write_text("committed\n", encoding="utf-8")
            self.git("add", "tracked.txt", cwd=child)
            self.git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "i", cwd=child)
        return workspace

    def install_old(self, root, workspace=False):
        """Install with the current engine, then rewrite managed files and manifest as an older release."""
        code = installer.main(
            ["--target", str(root), *(["--workspace"] if workspace else [])],
            runner=self.runner, environment={"PATH": ""}, which=specify_on_path,
            stdout=io.StringIO(), readiness_runner=FakeReadiness(),
        )
        self.assertEqual(code, 0)
        manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
        for relative in MANAGED:
            data = f"old {OLD_VERSION} {relative}\n".encode()
            (root / relative).write_bytes(data)
            manifest["files"][relative] = installer.fingerprint(data)
        (root / MANIFEST).write_bytes(installer._manifest_bytes(OLD_VERSION, manifest["files"]))

    def write_preferences(self, root):
        document = {
            "version": 1, "preset": "balanced",
            "tiers": {"budget": None, "balanced": "shared-model", "quality": None},
            "overrides": {"architect": "arch-override"},
        }
        path = root / PREFERENCES
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        return path.read_bytes()

    def run_upgrade(self, root, *extra, readiness_runner=None):
        stream = io.StringIO()
        code = upgrade.main(
            ["--target", str(root), *extra], runner=self.runner, environment={"PATH": ""},
            stdout=stream, readiness_runner=readiness_runner or self.readiness,
        )
        return code, stream.getvalue()

    def snapshot(self, root, skip=(".git",)):
        found = {}
        for directory, directories, files in os.walk(root):
            directories[:] = [d for d in directories if d not in skip]
            for name in files:
                full = Path(directory, name)
                found[full.relative_to(root).as_posix()] = hashlib.sha256(full.read_bytes()).hexdigest()
        return found

    def source(self, relative):
        return (installer.SOURCE_ROOT / relative).read_bytes()

    def backups(self, root):
        if (root / WORKSPACE_INDEX).exists():
            base = root / ".factory" / "upgrade-backups"
        else:
            base = root / ".git" / "software-factory-upgrade-backups"
        return sorted(base.iterdir()) if base.is_dir() else []


class SingleRepositoryUpgradeTests(UpgradeCase):
    def setUp(self):
        super().setUp()
        self.root = self.make_repo()
        self.install_old(self.root)
        self.preferences = self.write_preferences(self.root)

    def test_upgrade_replaces_managed_files_and_updates_the_manifest(self):
        before = self.snapshot(self.root)
        code, output = self.run_upgrade(self.root)

        self.assertEqual(code, 0, output)
        for relative in MANAGED:
            self.assertEqual((self.root / relative).read_bytes(), self.source(relative))
        manifest = json.loads((self.root / MANIFEST).read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_revision"], installer._source_revision(self.runner))
        self.assertEqual(
            manifest["files"], {r: installer.fingerprint(self.source(r)) for r in MANAGED}
        )
        self.assertIn(f"Installed: {OLD_VERSION}", output)
        self.assertIn("Plan: 9 replace, 0 add, 0 unchanged, 0 locally modified, 0 conflict", output)
        self.assertEqual(self.readiness.calls, [str(self.root)])
        changed = {p for p, h in self.snapshot(self.root).items() if before.get(p) != h}
        outside = {p for p in changed if not p.startswith(".factory/upgrade-backups/")}
        self.assertEqual(outside, {*MANAGED, MANIFEST})

    def test_model_preferences_and_overrides_are_preserved(self):
        exclude = self.root / ".git" / "info" / "exclude"
        exclude_before = exclude.read_bytes()

        code, output = self.run_upgrade(self.root)

        self.assertEqual(code, 0, output)
        self.assertEqual((self.root / PREFERENCES).read_bytes(), self.preferences)
        self.assertEqual(exclude.read_bytes(), exclude_before)
        self.assertIn(f"{PREFERENCES}: never modified", output)
        resolved = {
            role: subprocess.run(
                [sys.executable, "-B", str(self.root / "scripts" / "specialist_models.py"), "resolve", role],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
            for role in ("architect", "engineer")
        }
        self.assertEqual(resolved, {"architect": "arch-override", "engineer": "shared-model"})

    def test_dry_run_changes_nothing_and_skips_readiness(self):
        before = self.snapshot(self.root)
        code, output = self.run_upgrade(self.root, "--dry-run")

        self.assertEqual(code, 0, output)
        self.assertEqual(self.snapshot(self.root), before)
        self.assertEqual(self.readiness.calls, [])
        self.assertEqual(self.backups(self.root), [])
        self.assertIn("DRY RUN: nothing was changed.", output)
        self.assertIn("[replace]", output)

    def test_second_run_is_up_to_date_and_makes_no_backup(self):
        self.assertEqual(self.run_upgrade(self.root)[0], 0)
        backups = self.backups(self.root)
        before = self.snapshot(self.root)

        code, output = self.run_upgrade(self.root)

        self.assertEqual(code, 0, output)
        self.assertIn("already up to date", output)
        self.assertEqual(self.snapshot(self.root), before)
        self.assertEqual(self.backups(self.root), backups)

    def test_backup_holds_the_previous_files_and_is_marked_complete(self):
        self.assertEqual(self.run_upgrade(self.root)[0], 0)
        (backup,) = self.backups(self.root)
        for relative in (*MANAGED, MANIFEST):
            self.assertEqual(
                (backup / "files" / relative).read_text(encoding="utf-8").startswith(("old", "{")), True
            )
        record = json.loads((backup / "upgrade-record.json").read_text(encoding="utf-8"))
        self.assertEqual((record["status"], record["from"]), ("complete", OLD_VERSION))

    def test_single_repository_backups_stay_out_of_the_working_tree(self):
        self.assertEqual(self.run_upgrade(self.root)[0], 0)
        status = self.git("status", "--porcelain", "--untracked-files=all", cwd=self.root).stdout
        self.assertNotIn("upgrade-backups", status)
        self.assertEqual(len(self.backups(self.root)), 1)
        self.assertTrue(str(self.backups(self.root)[0]).startswith(str(self.root / ".git")))

    def test_line_ending_only_differences_are_not_local_customization(self):
        relative = MANAGED[0]
        text = (self.root / relative).read_bytes().replace(b"\n", b"\r\n")
        (self.root / relative).write_bytes(text)

        code, output = self.run_upgrade(self.root)

        self.assertEqual(code, 0, output)
        self.assertEqual((self.root / relative).read_bytes(), self.source(relative))

    def test_locally_modified_file_blocks_the_whole_upgrade(self):
        custom = self.root / MANAGED[0]
        custom.write_text("my customized lead\n", encoding="utf-8")
        before = self.snapshot(self.root)

        for extra in ((), ("--dry-run",)):
            code, output = self.run_upgrade(self.root, *extra)
            self.assertEqual(code, 1, output)
            self.assertIn(f"[modified]  {MANAGED[0]}", output)
            self.assertIn(f"--replace {MANAGED[0]}", output)
            self.assertIn("Nothing was written", output)
        self.assertEqual(self.snapshot(self.root), before)
        self.assertEqual(self.readiness.calls, [])

    def test_approved_replacement_keeps_a_backup_of_the_customized_file(self):
        custom = self.root / MANAGED[0]
        custom.write_text("my customized lead\n", encoding="utf-8")

        code, output = self.run_upgrade(self.root, "--replace", MANAGED[0])

        self.assertEqual(code, 0, output)
        self.assertEqual(custom.read_bytes(), self.source(MANAGED[0]))
        (backup,) = self.backups(self.root)
        self.assertEqual((backup / "files" / MANAGED[0]).read_text(encoding="utf-8"), "my customized lead\n")
        self.assertIn("replacement approved", output)

    def test_approval_covers_only_the_named_file(self):
        (self.root / MANAGED[0]).write_text("custom one\n", encoding="utf-8")
        (self.root / MANAGED[1]).write_text("custom two\n", encoding="utf-8")
        before = self.snapshot(self.root)

        code, output = self.run_upgrade(self.root, "--replace", MANAGED[0])

        self.assertEqual(code, 1, output)
        self.assertEqual(self.snapshot(self.root), before)

    def test_replace_accepts_only_managed_files(self):
        before = self.snapshot(self.root)
        for path in (PREFERENCES, MANIFEST, "README.md"):
            code, output = self.run_upgrade(self.root, "--replace", path)
            self.assertEqual(code, 2, output)
        self.assertEqual(self.snapshot(self.root), before)

    def test_unrecorded_existing_file_is_treated_as_customized(self):
        manifest = json.loads((self.root / MANIFEST).read_text(encoding="utf-8"))
        del manifest["files"][MANAGED[2]]
        (self.root / MANIFEST).write_bytes(installer._manifest_bytes(OLD_VERSION, manifest["files"]))

        code, output = self.run_upgrade(self.root)

        self.assertEqual(code, 1, output)
        self.assertIn("not recorded in the manifest", output)

    def test_missing_managed_file_is_restored(self):
        (self.root / MANAGED[3]).unlink()

        code, output = self.run_upgrade(self.root)

        self.assertEqual(code, 0, output)
        self.assertIn("[add]", output)
        self.assertEqual((self.root / MANAGED[3]).read_bytes(), self.source(MANAGED[3]))

    def test_symlinked_managed_file_is_a_conflict(self):
        link = self.root / MANAGED[0]
        target = self.root / "elsewhere.txt"
        target.write_text("outside\n", encoding="utf-8")
        link.unlink()
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        before = self.snapshot(self.root)

        code, output = self.run_upgrade(self.root)

        self.assertEqual(code, 1, output)
        self.assertIn("[conflict]", output)
        self.assertEqual(self.snapshot(self.root), before)
        self.assertEqual(target.read_text(encoding="utf-8"), "outside\n")

    def test_unrelated_readiness_failure_keeps_the_upgrade(self):
        failing = FakeReadiness(returncode=1)

        code, output = self.run_upgrade(self.root, readiness_runner=failing)

        self.assertEqual(code, 3, output)
        self.assertIn("unrelated to the files this upgrade wrote", output)
        self.assertEqual((self.root / MANAGED[0]).read_bytes(), self.source(MANAGED[0]))


class RefusalTests(UpgradeCase):
    def test_a_project_without_a_manifest_is_not_an_installation(self):
        root = self.make_repo()
        before = self.snapshot(root)
        code, output = self.run_upgrade(root)
        self.assertEqual(code, 2, output)
        self.assertIn("specfactory init", output)
        self.assertEqual(self.snapshot(root), before)

    def test_unsupported_manifests_are_refused_without_writes(self):
        root = self.make_repo()
        self.install_old(root)
        good = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
        variants = {
            "bad json": b"{not json",
            "wrong version": json.dumps({**good, "version": 2}).encode(),
            "unknown path": json.dumps({**good, "files": {**good["files"], "scripts/other.py": "sha256:" + "0" * 64}}).encode(),
            "bad fingerprint": json.dumps({**good, "files": {**good["files"], MANAGED[0]: "nope"}}).encode(),
        }
        for label, data in variants.items():
            with self.subTest(label):
                (root / MANIFEST).write_bytes(data)
                before = self.snapshot(root)
                code, output = self.run_upgrade(root)
                self.assertEqual(code, 2, output)
                self.assertEqual(self.snapshot(root), before)

    def test_downgrade_is_refused(self):
        root = self.make_repo()
        self.install_old(root)
        manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
        (root / MANIFEST).write_bytes(installer._manifest_bytes("specfactory-99.0.0", manifest["files"]))
        before = self.snapshot(root)
        code, output = self.run_upgrade(root)
        self.assertEqual(code, 2, output)
        self.assertIn("downgrades are not supported", output)
        self.assertEqual(self.snapshot(root), before)

    def test_subdirectory_of_a_repository_and_the_source_checkout_are_refused(self):
        root = self.make_repo()
        self.install_old(root)
        sub = root / "sub"
        sub.mkdir()
        self.assertEqual(self.run_upgrade(sub)[0], 2)
        self.assertEqual(self.run_upgrade(REPOSITORY_ROOT)[0], 2)

    def test_missing_target_is_refused(self):
        self.assertEqual(self.run_upgrade(self.base / "nope")[0], 2)

    def test_workspace_index_without_a_workspace_manifest_entry_is_refused(self):
        root = self.make_repo()
        self.install_old(root)
        (root / WORKSPACE_INDEX).parent.mkdir(exist_ok=True)
        (root / WORKSPACE_INDEX).write_text("{}\n", encoding="utf-8")
        code, output = self.run_upgrade(root)
        self.assertEqual(code, 2, output)


class RollbackTests(UpgradeCase):
    def setUp(self):
        super().setUp()
        self.root = self.make_repo()
        self.install_old(self.root)
        self.preferences = self.write_preferences(self.root)
        self.before = self.snapshot(self.root)

    def fail_on(self, relative, error=OSError("simulated failure")):
        def hook(path):
            if path == relative:
                raise error
        return mock.patch.object(upgrade, "_before_apply", hook)

    def assert_restored(self):
        now = self.snapshot(self.root)
        outside = {p: h for p, h in now.items() if not p.startswith(".factory/upgrade-backups/")}
        self.assertEqual(outside, {p: h for p, h in self.before.items()})

    def test_failure_midway_restores_every_file_and_the_old_manifest(self):
        with self.fail_on(MANAGED[3]):
            code, output = self.run_upgrade(self.root)

        self.assertEqual(code, 1, output)
        self.assertIn("Rolled back", output)
        self.assert_restored()
        self.assertEqual(self.readiness.calls, [])
        (backup,) = self.backups(self.root)
        record = json.loads((backup / "upgrade-record.json").read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "rolled-back")

    def test_failure_while_writing_the_manifest_restores_everything(self):
        with self.fail_on(MANIFEST):
            code, output = self.run_upgrade(self.root)
        self.assertEqual(code, 1, output)
        self.assert_restored()

    def test_added_files_are_removed_by_rollback(self):
        (self.root / MANAGED[0]).unlink()
        self.before = self.snapshot(self.root)
        with self.fail_on(MANIFEST):
            code, _ = self.run_upgrade(self.root)
        self.assertEqual(code, 1)
        self.assertFalse((self.root / MANAGED[0]).exists())
        self.assert_restored()

    def test_backup_failure_changes_nothing(self):
        with mock.patch.object(installer, "_create_exclusive", side_effect=OSError("disk full")):
            code, output = self.run_upgrade(self.root)
        self.assertEqual(code, 1, output)
        self.assertIn("backup could not be written", output)
        self.assert_restored()

    def test_a_file_changed_after_planning_is_not_overwritten(self):
        relative = MANAGED[1]

        def hook(path):
            pass

        real_inspect = upgrade._inspect
        calls = {"count": 0}

        def sneaky(root, path):
            result = real_inspect(root, path)
            if path == relative:
                calls["count"] += 1
                if calls["count"] == 1:
                    (Path(root) / path).write_text("edited during planning\n", encoding="utf-8")
            return result

        with mock.patch.object(upgrade, "_inspect", sneaky):
            code, output = self.run_upgrade(self.root)

        self.assertEqual(code, 1, output)
        self.assertIn("changed during planning", output)
        self.assertEqual((self.root / relative).read_text(encoding="utf-8"), "edited during planning\n")
        self.assertEqual(self.backups(self.root), [])

    def test_interrupted_upgrade_is_refused_until_recovered(self):
        with mock.patch.object(upgrade, "_restore", side_effect=OSError("crash")), self.fail_on(MANAGED[2]):
            code, output = self.run_upgrade(self.root)
        self.assertEqual(code, 1, output)
        self.assertIn("rollback did not complete", output)
        self.assertNotEqual({p: h for p, h in self.snapshot(self.root).items() if not p.startswith(".factory/upgrade-backups/")}, self.before)

        code, output = self.run_upgrade(self.root)
        self.assertEqual(code, 2, output)
        self.assertIn("--recover", output)

        code, output = self.run_upgrade(self.root, "--recover", "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertNotEqual(
            {p: h for p, h in self.snapshot(self.root).items() if not p.startswith(".factory/upgrade-backups/")}, self.before
        )

        code, output = self.run_upgrade(self.root, "--recover")
        self.assertEqual(code, 0, output)
        self.assert_restored()

        code, output = self.run_upgrade(self.root)
        self.assertEqual(code, 0, output)
        self.assertEqual((self.root / MANAGED[0]).read_bytes(), self.source(MANAGED[0]))

    def test_recover_with_nothing_to_recover_is_harmless(self):
        code, output = self.run_upgrade(self.root, "--recover")
        self.assertEqual(code, 0, output)
        self.assertIn("nothing to recover", output)
        self.assert_restored()


class WorkspaceUpgradeTests(UpgradeCase):
    def setUp(self):
        super().setUp()
        self.root = self.make_workspace()
        self.install_old(self.root, workspace=True)
        self.preferences = self.write_preferences(self.root)
        self.children = [self.root / "services/api", self.root / "clients/web"]

    def child_state(self):
        return {str(path): self.snapshot(path, skip=()) for path in self.children}

    def test_workspace_upgrade_preserves_index_models_and_child_repositories(self):
        index = (self.root / WORKSPACE_INDEX).read_bytes()
        children = self.child_state()

        code, output = self.run_upgrade(self.root)

        self.assertEqual(code, 0, output)
        self.assertIn("Mode: Gitless workspace", output)
        for relative in MANAGED:
            self.assertEqual((self.root / relative).read_bytes(), self.source(relative))
        self.assertEqual((self.root / WORKSPACE_INDEX).read_bytes(), index)
        self.assertEqual((self.root / PREFERENCES).read_bytes(), self.preferences)
        self.assertEqual(self.child_state(), children)
        self.assertFalse((self.root / ".git").exists())
        manifest = json.loads((self.root / MANIFEST).read_text(encoding="utf-8"))
        self.assertEqual(manifest["files"][WORKSPACE_INDEX], installer.fingerprint(index))
        self.assertEqual(set(manifest["files"]), {*MANAGED, WORKSPACE_INDEX})
        self.assertEqual(self.readiness.calls, [str(self.root)])
        self.assertIn(f"{WORKSPACE_INDEX}: never modified", output)

    def test_workspace_dry_run_and_customization_gate(self):
        before = self.snapshot(self.root)
        self.assertEqual(self.run_upgrade(self.root, "--dry-run")[0], 0)
        self.assertEqual(self.snapshot(self.root), before)

        (self.root / MANAGED[0]).write_text("custom\n", encoding="utf-8")
        before = self.snapshot(self.root)
        code, output = self.run_upgrade(self.root)
        self.assertEqual(code, 1, output)
        self.assertEqual(self.snapshot(self.root), before)

    def test_a_changed_workspace_index_is_left_alone_and_not_re_recorded(self):
        (self.root / WORKSPACE_INDEX).write_text('{"version": 1, "repositories": ["only/one"]}\n', encoding="utf-8")
        changed = (self.root / WORKSPACE_INDEX).read_bytes()
        recorded = json.loads((self.root / MANIFEST).read_text(encoding="utf-8"))["files"][WORKSPACE_INDEX]

        code, output = self.run_upgrade(self.root)

        self.assertEqual(code, 0, output)
        self.assertEqual((self.root / WORKSPACE_INDEX).read_bytes(), changed)
        self.assertEqual(json.loads((self.root / MANIFEST).read_text(encoding="utf-8"))["files"][WORKSPACE_INDEX], recorded)

    def test_missing_workspace_index_is_refused(self):
        (self.root / WORKSPACE_INDEX).unlink()
        before = self.snapshot(self.root)
        code, output = self.run_upgrade(self.root)
        self.assertEqual(code, 2, output)
        self.assertEqual(self.snapshot(self.root), before)


class StubReadiness:
    def __init__(self, stdout, returncode=0, error=None):
        self.stdout, self.returncode, self.error, self.calls = stdout, returncode, error, 0

    def __call__(self, target, environment):
        self.calls += 1
        if self.error:
            raise self.error
        return subprocess.CompletedProcess([], self.returncode, self.stdout, "")


LIMITED = (
    "[PASS] tool-specify: ok\n[NOT VERIFIED] tool-copilot: not found\n"
    "[PASS] specialist-profiles: five specialist profiles and skill are valid\n"
    "[PASS] install-manifest: 9 managed files match the install manifest\n"
    "[NOT VERIFIED] unverifiable: authentication, live dispatch, effective sandbox enforcement\n"
    "    expected: confirmation in a live session\n"
    "Verdict: ready with limitations\nLimitations: authentication, live dispatch, effective sandbox enforcement\n"
)


def not_ready(*lines):
    return "\n".join(lines) + "\nVerdict: not ready\n"


class ReadinessVerificationTests(UpgradeCase):
    """A failed check of the files this upgrade wrote rolls it back; other outcomes do not."""

    def setUp(self):
        super().setUp()
        self.root = self.make_repo()
        self.install_old(self.root)
        self.preferences = self.write_preferences(self.root)
        self.before = self.snapshot(self.root)

    def state(self):
        return {p: h for p, h in self.snapshot(self.root).items() if not p.startswith(".factory/upgrade-backups/")}

    def record_status(self):
        (backup,) = self.backups(self.root)
        return json.loads((backup / "upgrade-record.json").read_text(encoding="utf-8"))["status"]

    def assert_rolled_back(self, code, output):
        self.assertEqual(code, 1, output)
        self.assertIn("Post-upgrade verification FAILED", output)
        self.assertIn("Rolled back", output)
        self.assertEqual(self.state(), self.before)
        self.assertEqual(self.record_status(), "rolled-back")
        self.assertEqual(json.loads((self.root / MANIFEST).read_text(encoding="utf-8"))["source_revision"], OLD_VERSION)

    def assert_kept(self, code, output, expected_code):
        self.assertEqual(code, expected_code, output)
        self.assertNotIn("Rolled back", output)
        for relative in MANAGED:
            self.assertEqual((self.root / relative).read_bytes(), self.source(relative))
        self.assertEqual(self.record_status(), "complete")

    def test_ready_with_limitations_is_never_rolled_back(self):
        code, output = self.run_upgrade(self.root, readiness_runner=StubReadiness(LIMITED, 0))
        self.assert_kept(code, output, 0)
        self.assertEqual((self.root / PREFERENCES).read_bytes(), self.preferences)

    def test_failed_manifest_integrity_check_rolls_back_to_the_previous_files(self):
        report = not_ready(
            "[PASS] tool-specify: ok",
            f"[FAIL] install-manifest: {MANAGED[0]}: differs from the installed fingerprint",
        )
        code, output = self.run_upgrade(self.root, readiness_runner=StubReadiness(report, 1))
        self.assert_rolled_back(code, output)
        self.assertIn(f"install-manifest: {MANAGED[0]}", output)

    def test_failed_profile_validation_rolls_back(self):
        report = not_ready(f"[FAIL] specialist-profiles: {MANAGED[4]}: invalid")
        code, output = self.run_upgrade(self.root, readiness_runner=StubReadiness(report, 1))
        self.assert_rolled_back(code, output)

    def test_invalid_manifest_finding_rolls_back(self):
        report = not_ready(f"[FAIL] install-manifest: {MANIFEST}: not a valid install manifest")
        code, output = self.run_upgrade(self.root, readiness_runner=StubReadiness(report, 1))
        self.assert_rolled_back(code, output)

    def test_unrelated_failures_keep_the_upgrade_and_say_so(self):
        report = not_ready(
            "[FAIL] tool-specify: not found", "[FAIL] speckit-config: missing",
            "[FAIL] interactive-hooks: broken", "[FAIL] git-state: dirty",
        )
        code, output = self.run_upgrade(self.root, readiness_runner=StubReadiness(report, 1))
        self.assert_kept(code, output, 3)
        self.assertIn("unrelated to the files this upgrade wrote", output)

    def test_report_without_a_verdict_cannot_verify_but_keeps_the_upgrade(self):
        code, output = self.run_upgrade(self.root, readiness_runner=StubReadiness("Traceback...\n", 1))
        self.assert_kept(code, output, 3)
        self.assertIn("could not be verified", output)

    def test_readiness_that_cannot_run_keeps_the_verified_upgrade_and_says_so(self):
        runner = StubReadiness("", error=subprocess.TimeoutExpired("readiness", 1))
        code, output = self.run_upgrade(self.root, readiness_runner=runner)
        self.assert_kept(code, output, 3)
        self.assertIn("could not run", output)
        self.assertIn("byte-for-byte", output)

    def test_failed_rollback_leaves_an_interrupted_record_that_recover_restores(self):
        report = not_ready(f"[FAIL] install-manifest: {MANAGED[0]}: differs from the installed fingerprint")
        with mock.patch.object(upgrade, "_restore", side_effect=OSError("disk error")):
            code, output = self.run_upgrade(self.root, readiness_runner=StubReadiness(report, 1))
        self.assertEqual(code, 1, output)
        self.assertIn("rollback did not complete", output)
        self.assertEqual(self.record_status(), "applying")
        self.assertNotEqual(self.state(), self.before)

        self.assertEqual(self.run_upgrade(self.root)[0], 2)
        code, output = self.run_upgrade(self.root, "--recover")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.state(), self.before)

    def test_rollback_that_does_not_match_the_backup_is_not_reported_as_success(self):
        report = not_ready(f"[FAIL] install-manifest: {MANAGED[0]}: differs from the installed fingerprint")
        real_restore = upgrade._restore

        def restore_and_corrupt(root, directory, record):
            real_restore(root, directory, record)
            (Path(root) / MANAGED[1]).write_text("corrupted after restore\n", encoding="utf-8")

        with mock.patch.object(upgrade, "_restore", restore_and_corrupt):
            code, output = self.run_upgrade(self.root, readiness_runner=StubReadiness(report, 1))
        self.assertEqual(code, 1, output)
        self.assertNotIn("Rolled back: every file", output)
        self.assertIn("does not match its backup", output)
        self.assertEqual(self.record_status(), "applying")

    def test_real_readiness_failure_on_a_written_file_triggers_rollback(self):
        def tamper_then_check(target, environment):
            (Path(target) / MANAGED[0]).write_text("tampered after the upgrade\n", encoding="utf-8")
            return installer._run_readiness(target, dict(os.environ))

        code, output = self.run_upgrade(self.root, readiness_runner=tamper_then_check)
        self.assert_rolled_back(code, output)
        self.assertIn("differs from the installed fingerprint", output)

    def test_real_readiness_passes_on_an_untampered_upgrade_and_keeps_it(self):
        def real(target, environment):
            return installer._run_readiness(target, dict(os.environ))

        code, output = self.run_upgrade(self.root, readiness_runner=real)
        self.assertIn(code, (0, 3), output)
        self.assertNotIn("Rolled back", output)
        self.assertNotIn("Post-upgrade verification FAILED", output)
        for relative in MANAGED:
            self.assertEqual((self.root / relative).read_bytes(), self.source(relative))

    def test_workspace_index_drift_alone_does_not_roll_back(self):
        workspace = self.make_workspace()
        self.install_old(workspace, workspace=True)
        before = self.snapshot(workspace)
        report = not_ready(f"[FAIL] install-manifest: {WORKSPACE_INDEX}: differs from the installed fingerprint")
        code, output = self.run_upgrade(workspace, readiness_runner=StubReadiness(report, 1))
        self.assertEqual(code, 3, output)
        self.assertNotIn("Rolled back", output)
        self.assertNotEqual(self.snapshot(workspace), before)

    def test_workspace_managed_file_failure_rolls_back_and_preserves_children(self):
        workspace = self.make_workspace()
        self.install_old(workspace, workspace=True)
        self.write_preferences(workspace)
        before = self.snapshot(workspace)
        children = {p: self.snapshot(workspace / p, skip=()) for p in ("services/api", "clients/web")}
        report = not_ready(f"[FAIL] specialist-profiles: {MANAGED[0]}: invalid")
        code, output = self.run_upgrade(workspace, readiness_runner=StubReadiness(report, 1))
        self.assertEqual(code, 1, output)
        self.assertIn("Rolled back", output)
        after = {p: h for p, h in self.snapshot(workspace).items() if not p.startswith(".factory/upgrade-backups/")}
        self.assertEqual(after, {p: h for p, h in before.items() if not p.startswith(".factory/upgrade-backups/")})
        self.assertEqual({p: self.snapshot(workspace / p, skip=()) for p in children}, children)


class FakeEngine:
    """Stands in for the engine subprocess and records each invocation."""

    def __init__(self, dry=(0, "Plan: 9 replace\nDRY RUN: nothing was changed.\n"), real=(0, "Upgraded 9 file(s).\n")):
        self.dry = dry
        self.real = real
        self.calls = []

    def __call__(self, arguments, cwd, environment):
        arguments = list(arguments)
        self.calls.append(arguments)
        assert Path(arguments[2]) == bundle.asset_root() / "scripts" / "upgrade_factory.py"
        status, text = self.dry if "--dry-run" in arguments else self.real
        if callable(status):
            status, text = status(arguments)
        return subprocess.CompletedProcess(arguments, status, text, "")

    def dry_calls(self):
        return [c for c in self.calls if "--dry-run" in c]

    def real_calls(self):
        return [c for c in self.calls if "--dry-run" not in c]


class UpgradeCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.target = Path(os.path.realpath(temporary.name))
        self.output = io.StringIO()
        self.prompts = []

    def run_cli(self, engine, *argv, answers=(), interactive=True):
        pending = list(answers)

        def ask(prompt):
            self.prompts.append(prompt)
            if not pending:
                raise AssertionError(f"unexpected prompt: {prompt}")
            return pending.pop(0)

        code = cli.main(
            list(argv), stdout=self.output, environment={"PATH": "", "FACTORY_X": "1", "PYTHONPATH": "p"},
            script_runner=engine, input_fn=ask, interactive=interactive, cwd=str(self.target),
        )
        self.assertEqual(pending, [], "scripted answers were not all consumed")
        return code

    def test_the_upgrade_command_is_offered_next_to_init(self):
        self.assertEqual(list(cli._build_parser()._subparsers._group_actions[0].choices), ["init", "upgrade"])

    def test_dry_run_runs_only_the_engine_dry_run_and_never_asks(self):
        engine = FakeEngine()
        self.assertEqual(self.run_cli(engine, "upgrade", "--dry-run"), 0)
        self.assertEqual(len(engine.dry_calls()), 1)
        self.assertEqual(engine.real_calls(), [])
        self.assertEqual(self.prompts, [])
        self.assertIn("DRY RUN: nothing was changed", self.output.getvalue())
        call = engine.calls[0]
        self.assertEqual(call[call.index("--target") + 1], str(self.target))

    def test_non_interactive_without_yes_is_preview_only(self):
        engine = FakeEngine()
        self.assertEqual(self.run_cli(engine, "upgrade", "--non-interactive"), 0)
        self.assertEqual(engine.real_calls(), [])
        self.assertIn("re-run with --non-interactive --yes", self.output.getvalue())

    def test_not_a_terminal_without_yes_never_writes(self):
        engine = FakeEngine()
        self.assertEqual(self.run_cli(engine, "upgrade", interactive=False), 0)
        self.assertEqual(engine.real_calls(), [])
        self.assertEqual(self.prompts, [])

    def test_yes_applies_without_prompting(self):
        engine = FakeEngine()
        self.assertEqual(self.run_cli(engine, "upgrade", "--non-interactive", "--yes"), 0)
        self.assertEqual(len(engine.real_calls()), 1)
        self.assertEqual(self.prompts, [])
        self.assertIn("The upgrade is complete", self.output.getvalue())

    def test_interactive_consent_gates_the_real_run(self):
        engine = FakeEngine()
        self.assertEqual(self.run_cli(engine, "upgrade", answers=["n"]), 2)
        self.assertEqual(engine.real_calls(), [])
        self.assertIn("Declined. Nothing was changed.", self.output.getvalue())

        engine = FakeEngine()
        self.assertEqual(self.run_cli(engine, "upgrade", answers=["y"]), 0)
        self.assertEqual(len(engine.real_calls()), 1)
        self.assertEqual(engine.calls[0][:1], engine.calls[-1][:1])
        self.assertLess(engine.calls.index(engine.dry_calls()[0]), engine.calls.index(engine.real_calls()[0]))

    def test_interactive_customized_files_need_per_file_approval(self):
        path = ".github/agents/factory-lead.agent.md"

        def dry(arguments):
            if "--replace" in arguments:
                return 0, "Plan: 9 replace\nDRY RUN: nothing was changed.\n"
            return 1, f"[modified]  {path}: locally modified\nNothing was written.\n"

        engine = FakeEngine(dry=(dry, ""))
        self.assertEqual(self.run_cli(engine, "upgrade", answers=["y", "y"]), 0)
        real = engine.real_calls()
        self.assertEqual(len(real), 1)
        self.assertEqual(real[0][real[0].index("--replace") + 1], path)
        self.assertIn("A backup of your version is kept", self.prompts[0])

        engine = FakeEngine(dry=(dry, ""))
        self.output = io.StringIO()
        self.prompts = []
        self.assertEqual(self.run_cli(engine, "upgrade", answers=["n"]), 1)
        self.assertEqual(engine.real_calls(), [])
        self.assertIn("Nothing was changed.", self.output.getvalue())

    def test_replace_flags_are_forwarded_and_conflicts_stop_non_interactive_runs(self):
        path = ".github/skills/factory-handoff/SKILL.md"
        engine = FakeEngine(dry=(1, f"[modified]  {path}: locally modified\n"))
        code = self.run_cli(engine, "upgrade", "--non-interactive", "--yes", "--replace", path)
        self.assertEqual(code, 1)
        self.assertEqual(engine.real_calls(), [])
        self.assertTrue(all(c[c.index("--replace") + 1] == path for c in engine.calls))

    def test_up_to_date_and_refusals_do_not_prompt_or_write(self):
        engine = FakeEngine(dry=(0, "already up to date: nothing to change.\n"))
        self.assertEqual(self.run_cli(engine, "upgrade"), 0)
        self.assertEqual(engine.real_calls(), [])
        engine = FakeEngine(dry=(2, "Refused: no manifest.\n"))
        self.assertEqual(self.run_cli(engine, "upgrade", "--non-interactive", "--yes"), 2)
        self.assertEqual(engine.real_calls(), [])
        self.assertEqual(self.prompts, [])

    def test_engine_exit_codes_are_reported_honestly(self):
        for code, fragment in (
            (3, "readiness did not pass for reasons unrelated to them"),
            (1, "did not complete"),
        ):
            with self.subTest(code=code):
                self.output = io.StringIO()
                engine = FakeEngine(real=(code, ""))
                self.assertEqual(self.run_cli(engine, "upgrade", "--non-interactive", "--yes"), code)
                self.assertIn(fragment, self.output.getvalue())

    def test_recover_requires_consent(self):
        engine = FakeEngine(dry=(0, "Would restore 3 file(s).\n"))
        self.assertEqual(self.run_cli(engine, "upgrade", "--recover", answers=["n"]), 2)
        self.assertEqual(engine.real_calls(), [])
        engine = FakeEngine(dry=(0, "Would restore 3 file(s).\n"))
        self.assertEqual(self.run_cli(engine, "upgrade", "--recover", answers=["y"]), 0)
        self.assertIn("--recover", engine.real_calls()[0])

    def test_conflicting_flags_are_rejected(self):
        engine = FakeEngine()
        import contextlib

        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.run_cli(engine, "upgrade", "--yes"), 2)
            self.assertEqual(self.run_cli(engine, "upgrade", "--non-interactive", "--yes", "--dry-run"), 2)
        self.assertEqual(engine.calls, [])


if __name__ == "__main__":
    unittest.main()
