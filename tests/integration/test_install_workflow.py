import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


FACTORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FACTORY_ROOT / "scripts"))

import check_factory_readiness as readiness  # noqa: E402


INSTALLER = FACTORY_ROOT / "scripts" / "install_factory.py"
ENTRY = "/.factory/model-preferences.json"
PREFERENCES = ".factory/model-preferences.json"
MANIFEST = readiness.MANIFEST_PATH
MANAGED = tuple(readiness.MANAGED_FILES)
INSTALLED = set(MANAGED) | {MANIFEST}
SPECIFY_INIT = ["specify", "init", "--here", "--force", "--non-interactive", "--integration", "copilot"]
FAIL_LINE = re.compile(r"^\[FAIL\]\s+(\S+?):", re.MULTILINE)
BLOCK_YAML = (
    "import os, runpy, sys\n"
    "sys.modules['yaml'] = None\n"
    "script = sys.argv[1]\n"
    "sys.argv = sys.argv[1:]\n"
    "sys.path.insert(0, os.path.dirname(os.path.abspath(script)))\n"
    "runpy.run_path(script, run_name='__main__')\n"
)
IDENTITY = ["-c", "user.name=tester", "-c", "user.email=tester@example.invalid", "-c", "commit.gpgsign=false"]

TEMPLATE = None
_TEMPLATE_DIRECTORY = None


def clean_environment():
    """Process environment without FACTORY_*, PYTHONPATH, or caller Git overrides."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("FACTORY_")
        and key.upper() not in (
            "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "GIT_DIR", "GIT_WORK_TREE",
            "GIT_INDEX_FILE", "GIT_CEILING_DIRECTORIES",
        )
    }
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    return environment


def run(arguments, cwd=None, environment=None):
    return subprocess.run(
        [str(argument) for argument in arguments],
        cwd=None if cwd is None else str(cwd),
        env=clean_environment() if environment is None else environment,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        shell=False, check=False, timeout=300,
    )


def git(repo, *arguments):
    result = run(["git", *arguments], cwd=repo)
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(arguments)} failed: {result.stdout}{result.stderr}")
    return result.stdout


def _force_remove(function, path, _info):
    os.chmod(path, stat.S_IWRITE)
    function(path)


def remove_tree(path):
    shutil.rmtree(path, onerror=_force_remove)


def snapshot(root):
    """Map every path under root (including .git) to its kind and content hash."""
    entries = {}
    root = str(root)
    for directory, directories, files in os.walk(root):
        for name in directories:
            entries[os.path.relpath(os.path.join(directory, name), root).replace("\\", "/")] = "D"
        for name in files:
            full = os.path.join(directory, name)
            with open(full, "rb") as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
            entries[os.path.relpath(full, root).replace("\\", "/")] = digest
    return entries


def only_files(entries):
    return {path: value for path, value in entries.items() if value != "D"}


def setUpModule():
    global TEMPLATE, _TEMPLATE_DIRECTORY
    if shutil.which("specify") is None:
        raise unittest.SkipTest("the specify CLI is not on PATH; real Spec Kit initialization is required")
    if shutil.which("git") is None:
        raise RuntimeError("git is required for the real installer acceptance suite")
    _TEMPLATE_DIRECTORY = os.path.realpath(tempfile.mkdtemp())
    TEMPLATE = Path(_TEMPLATE_DIRECTORY) / "template"
    TEMPLATE.mkdir()
    git(TEMPLATE, "init", "-q", str(TEMPLATE))
    result = run(SPECIFY_INIT, cwd=TEMPLATE)
    if result.returncode != 0:
        remove_tree(_TEMPLATE_DIRECTORY)
        raise RuntimeError(f"specify init failed: {result.stdout}{result.stderr}")


def tearDownModule():
    if _TEMPLATE_DIRECTORY is not None:
        remove_tree(_TEMPLATE_DIRECTORY)


class WorkflowCase(unittest.TestCase):
    def setUp(self):
        self.base = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(remove_tree, self.base)

    def spec_kit_repo(self, name="repo"):
        path = self.base / name
        shutil.copytree(TEMPLATE, path, symlinks=True)
        return path

    def plain_repo(self, name="plain"):
        path = self.base / name
        path.mkdir()
        git(path, "init", "-q", str(path))
        return path

    def install(self, repo, *extra, installer=INSTALLER):
        return run([sys.executable, installer, "--target", repo, *extra])

    def commit(self, repo, message="baseline"):
        git(repo, *IDENTITY, "commit", "-q", "-m", message)

    def source_bytes(self, relative):
        return (FACTORY_ROOT / relative).read_bytes()

    def plan_block(self, output):
        lines = output.splitlines()
        start = next(i for i, line in enumerate(lines) if line.startswith("Target:"))
        end = next(i for i, line in enumerate(lines) if line.startswith("Plan:"))
        return lines[start:end + 1]

    def dispositions(self, output, labels):
        pattern = re.compile(r"^\[(%s)\]\s+(\S+)" % "|".join(labels))
        return sorted(m.groups() for m in map(pattern.match, output.splitlines()) if m)

    def assert_install_ok(self, result):
        """A clean installed project is ready for the primary VS Code Copilot Chat workflow."""
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertEqual(FAIL_LINE.findall(result.stdout), [], output)

    def assert_readiness_ok(self, output, returncode):
        self.assertEqual(returncode, 0, output)
        fails = FAIL_LINE.findall(output)
        self.assertEqual(fails, [], output)

    def is_ignored(self, repo, path):
        return run(["git", "-C", repo, "check-ignore", "-q", "--no-index", path]).returncode == 0


class InstallScenarioTests(WorkflowCase):
    def test_a1_fresh_spec_kit_repository_installs_and_reports_ready_with_limitations(self):
        repo = self.spec_kit_repo()
        self.assertFalse((repo / ".specify" / "feature.json").exists())
        result = self.install(repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for relative in MANAGED:
            self.assertEqual((repo / relative).read_bytes(), self.source_bytes(relative))
        self.assertTrue((repo / MANIFEST).is_file())
        exclude = (repo / ".git" / "info" / "exclude").read_text(encoding="utf-8").splitlines()
        self.assertEqual([line for line in exclude if line.strip() == ENTRY], [ENTRY])
        self.assertTrue(self.is_ignored(repo, PREFERENCES))
        self.assertFalse(self.is_ignored(repo, MANIFEST))
        self.assertIn("Installed readiness check:", result.stdout)
        self.assertIn("Verdict: ready with limitations", result.stdout)
        self.assertNotIn("[FAIL]", result.stdout)

        installed = run([sys.executable, repo / "scripts" / "check_factory_readiness.py"], cwd=repo)
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        self.assertIn("[PASS] speckit-config", installed.stdout)
        self.assertNotIn("[FAIL]", installed.stdout)
        self.assertIn("Verdict: ready with limitations", installed.stdout)

    def test_a1b_repository_without_spec_kit_is_refused_and_nothing_is_written(self):
        repo = self.plain_repo()
        before = snapshot(repo)
        result = self.install(repo)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Review the official existing-project guidance", result.stdout)
        self.assertIn("Nothing was written", result.stdout)
        self.assertEqual(snapshot(repo), before)
        self.assertFalse((repo / ".github").exists())
        self.assertFalse((repo / "scripts").exists())
        self.assertFalse((repo / ".factory").exists())

    def test_a2_spec_kit_repository_with_uncommitted_user_files_changes_only_managed_paths(self):
        repo = self.spec_kit_repo()
        (repo / "README.md").write_bytes(b"readme\n")
        git(repo, "add", "README.md")
        self.commit(repo)
        (repo / "README.md").write_bytes(b"readme edited, uncommitted\n")
        (repo / "notes.txt").write_bytes(b"untracked notes\n")
        (repo / "src").mkdir()
        (repo / "src" / "staged.py").write_bytes(b"print('staged')\n")
        git(repo, "add", "src/staged.py")

        before = snapshot(repo)
        head = git(repo, "rev-parse", "HEAD")
        log = git(repo, "log", "--format=%H %s")
        index = (repo / ".git" / "index").read_bytes()

        result = self.install(repo)
        self.assert_install_ok(result)
        after = snapshot(repo)

        before_files, after_files = only_files(before), only_files(after)
        # scripts/__pycache__ is excluded here; test_a2_install_creates_no_unmanaged_files covers it.
        added = {p for p in set(after_files) - set(before_files) if "__pycache__" not in p.split("/")}
        changed = {p for p, v in before_files.items() if p in after_files and after_files[p] != v}
        removed = set(before_files) - set(after_files)
        self.assertEqual(added, INSTALLED)
        self.assertEqual(changed, {".git/info/exclude"})
        self.assertEqual(removed, set())

        exclude_now = (repo / ".git" / "info" / "exclude").read_bytes()
        template_exclude = (TEMPLATE / ".git" / "info" / "exclude").read_bytes()
        self.assertTrue(exclude_now.startswith(template_exclude))
        self.assertEqual(exclude_now[len(template_exclude):].strip(), ENTRY.encode())
        self.assertEqual(exclude_now.count(ENTRY.encode()), 1)

        self.assertEqual(git(repo, "rev-parse", "HEAD"), head)
        self.assertEqual(git(repo, "log", "--format=%H %s"), log)
        self.assertEqual((repo / ".git" / "index").read_bytes(), index)
        self.assertEqual((repo / "README.md").read_bytes(), b"readme edited, uncommitted\n")
        self.assertEqual((repo / "notes.txt").read_bytes(), b"untracked notes\n")
        self.assertEqual((repo / "src" / "staged.py").read_bytes(), b"print('staged')\n")

    def test_a2_install_creates_no_unmanaged_files(self):
        repo = self.spec_kit_repo()
        before = only_files(snapshot(repo))
        result = self.install(repo)
        self.assert_install_ok(result)
        added = set(only_files(snapshot(repo))) - set(before)
        self.assertEqual(added, INSTALLED)

    def test_a3_conflicting_agent_and_skill_are_refused_and_nothing_is_written(self):
        repo = self.spec_kit_repo()
        files = {
            ".github/agents/engineer.agent.md": b"my own engineer profile\n",
            ".github/skills/factory-handoff/SKILL.md": b"my own handoff skill\n",
            ".github/agents/unrelated.agent.md": b"unrelated agent\n",
            ".github/skills/unrelated/SKILL.md": b"unrelated skill\n",
        }
        for relative, data in files.items():
            path = repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        before = snapshot(repo)
        result = self.install(repo)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("[conflict]  .github/agents/engineer.agent.md: different content", result.stdout)
        self.assertIn("[conflict]  .github/skills/factory-handoff/SKILL.md: different content", result.stdout)
        self.assertIn("Nothing was written", result.stdout)
        self.assertEqual(snapshot(repo), before)
        for relative, data in files.items():
            self.assertEqual((repo / relative).read_bytes(), data)
        self.assertFalse((repo / "scripts").exists())
        self.assertFalse((repo / MANIFEST).exists())

    def test_a3_same_named_skill_directory_is_refused_and_nothing_is_written(self):
        repo = self.spec_kit_repo()
        blocker = repo / ".github" / "skills" / "factory-handoff" / "SKILL.md"
        blocker.mkdir(parents=True)
        (blocker / "inside.txt").write_bytes(b"user data\n")
        before = snapshot(repo)
        result = self.install(repo)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("[conflict]  .github/skills/factory-handoff/SKILL.md: not a regular file", result.stdout)
        self.assertEqual(snapshot(repo), before)

    def test_a3b_tracked_preferences_file_is_refused_with_guidance(self):
        repo = self.spec_kit_repo()
        (repo / PREFERENCES).parent.mkdir(parents=True)
        (repo / PREFERENCES).write_bytes(b'{"version": 1}\n')
        git(repo, "add", "-f", PREFERENCES)
        self.commit(repo)
        before = snapshot(repo)
        result = self.install(repo)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(f"git rm --cached {PREFERENCES}", result.stdout)
        self.assertIn("Nothing was written", result.stdout)
        self.assertEqual(snapshot(repo), before)

    def test_a3b_staged_only_preferences_file_is_refused(self):
        repo = self.spec_kit_repo()
        (repo / PREFERENCES).parent.mkdir(parents=True)
        (repo / PREFERENCES).write_bytes(b'{"version": 1}\n')
        git(repo, "add", "-f", PREFERENCES)
        before = snapshot(repo)
        result = self.install(repo)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("git rm --cached", result.stdout)
        self.assertEqual(snapshot(repo), before)

    def test_a3b_ignored_manifest_path_is_refused_naming_the_rule(self):
        repo = self.spec_kit_repo()
        (repo / ".gitignore").write_bytes(b"install-manifest.json\n")
        before = snapshot(repo)
        result = self.install(repo)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(".gitignore:1:install-manifest.json", result.stdout)
        self.assertIn(MANIFEST, result.stdout)
        self.assertEqual(snapshot(repo), before)

    def test_a4_repeat_install_is_a_no_op_and_a_deleted_file_is_recreated_alone(self):
        repo = self.spec_kit_repo()
        first = self.install(repo)
        self.assert_install_ok(first)
        after_first = snapshot(repo)

        second = self.install(repo)
        self.assert_install_ok(second)
        self.assertIn("already installed", second.stdout)
        self.assertNotIn("[created]", second.stdout)
        self.assertEqual(snapshot(repo), after_first)

        victim = "scripts/specialist_models.py"
        (repo / victim).unlink()
        others = sorted(INSTALLED - {victim})
        mtimes = {r: (repo / r).stat().st_mtime_ns for r in others}
        hashes = {r: after_first[r] for r in others}
        exclude = (repo / ".git" / "info" / "exclude").read_bytes()

        third = self.install(repo)
        self.assert_install_ok(third)
        self.assertEqual(self.dispositions(third.stdout, ["created"]), [("created", victim)])
        self.assertIn("Installed 1 file(s).", third.stdout)
        self.assertEqual((repo / victim).read_bytes(), self.source_bytes(victim))
        after_third = snapshot(repo)
        for relative in others:
            self.assertEqual(after_third[relative], hashes[relative])
            self.assertEqual((repo / relative).stat().st_mtime_ns, mtimes[relative])
        self.assertEqual((repo / ".git" / "info" / "exclude").read_bytes(), exclude)

    def test_a4b_edited_managed_file_makes_installed_readiness_fail_naming_the_path(self):
        repo = self.spec_kit_repo()
        result = self.install(repo)
        self.assert_install_ok(result)
        edited = ".github/agents/code-reviewer.agent.md"
        with open(repo / edited, "ab") as handle:
            handle.write(b"\nLocal edit that is not part of the installed fingerprint.\n")
        check = run([sys.executable, repo / "scripts" / "check_factory_readiness.py"], cwd=repo)
        self.assertEqual(check.returncode, 1, check.stdout + check.stderr)
        failing = [line for line in check.stdout.splitlines() if "FAIL" in line and edited in line]
        self.assertTrue(failing, check.stdout)
        self.assertIn("next step:", check.stdout)
        self.assertIn("Verdict: not ready", check.stdout)


class DryRunTests(WorkflowCase):
    def prepare(self, state):
        repo = self.spec_kit_repo(state)
        if state == "installed" or state == "partial":
            result = self.install(repo)
            self.assert_install_ok(result)
        if state == "partial":
            (repo / "scripts" / "check_factory_readiness.py").unlink()
        if state == "conflict":
            path = repo / ".github" / "agents" / "engineer.agent.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"my own engineer profile\n")
        return repo

    def test_a5_dry_run_changes_nothing_and_matches_the_later_real_run(self):
        for state, expected_code in (("fresh", 0), ("conflict", 1), ("installed", 0), ("partial", 0)):
            with self.subTest(state=state):
                repo = self.prepare(state)
                before = snapshot(repo)
                dry = self.install(repo, "--dry-run")
                self.assertEqual(dry.returncode, expected_code, dry.stdout + dry.stderr)
                self.assertIn("DRY RUN: nothing was changed.", dry.stdout)
                self.assertEqual(snapshot(repo), before)

                real = self.install(repo)
                self.assertEqual(real.returncode, expected_code, real.stdout + real.stderr)
                self.assertEqual(self.plan_block(real.stdout), self.plan_block(dry.stdout))
                planned = [path for _, path in self.dispositions(dry.stdout, ["create"])]
                created = [path for _, path in self.dispositions(real.stdout, ["created"])]
                # A conflict means no writes at all, so nothing planned is created.
                self.assertEqual(created, [] if state == "conflict" else planned)
                if state == "conflict":
                    self.assertEqual(snapshot(repo), before)

    def test_a5_negated_preferences_path_is_cannot_establish_for_dry_and_real_runs(self):
        repo = self.spec_kit_repo()
        (repo / ".gitignore").write_bytes(f"!{PREFERENCES}\n".encode())
        before = snapshot(repo)
        outputs = []
        for extra in (("--dry-run",), ()):
            result = self.install(repo, *extra)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn(f".gitignore:1:!{PREFERENCES}", result.stdout)
            self.assertIn("would not take effect", result.stdout)
            self.assertEqual(snapshot(repo), before)
            outputs.append(result.stdout)
        self.assertEqual(self.plan_block(outputs[0]), self.plan_block(outputs[1]))

    def test_a5_leftover_temporary_files_are_disclosed_by_dry_and_real_runs(self):
        repo = self.spec_kit_repo()
        leftover = repo / ".github" / "agents" / ".engineer.agent.md.sf-tmp"
        leftover.parent.mkdir(parents=True)
        leftover.write_bytes(b"half written")
        line = "[cleanup]   .github/agents/.engineer.agent.md.sf-tmp: remove leftover temporary file"
        before = snapshot(repo)
        dry = self.install(repo, "--dry-run")
        self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
        self.assertIn(line, dry.stdout.splitlines())
        self.assertEqual(snapshot(repo), before)
        real = self.install(repo)
        self.assertIn(line, real.stdout.splitlines())
        self.assertEqual(self.plan_block(real.stdout), self.plan_block(dry.stdout))
        self.assertFalse(leftover.exists())

class RelocationTests(WorkflowCase):
    """A7: installed tools keep working after the source checkout is moved and deleted."""

    def make_source(self, root):
        for relative in MANAGED + ("scripts/install_factory.py",):
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(FACTORY_ROOT / relative, destination)
        git(root, "init", "-q", str(root))
        git(root, "add", "-A")
        self.commit(root, "source snapshot")
        return git(root, "rev-parse", "HEAD").strip()

    def normalize(self, text, target):
        for form in (str(target), target.as_posix(), json.dumps(str(target))[1:-1]):
            text = text.replace(form, "<TARGET>")
        return text

    def tool_runs(self, target, blocked):
        scripts = target / "scripts"
        commands = {
            "validator": [scripts / "validate_specialist_profiles.py"],
            "readiness": [scripts / "check_factory_readiness.py"],
            "status": [scripts / "specialist_models.py", "status", "--json"],
            "resolve-engineer": [scripts / "specialist_models.py", "resolve", "engineer"],
            "resolve-architect": [scripts / "specialist_models.py", "resolve", "architect"],
            "resolve-qa": [scripts / "specialist_models.py", "resolve", "qa-engineer"],
        }
        results = {}
        for name, command in commands.items():
            launch = [sys.executable, "-c", BLOCK_YAML, *command] if blocked else [sys.executable, *command]
            completed = run(launch, cwd=target)
            results[name] = (
                completed.returncode,
                self.normalize(completed.stdout, target),
                self.normalize(completed.stderr, target),
            )
        return results

    def source_path_needles(self, *paths):
        needles = set()
        for path in paths:
            for form in (str(path), Path(path).as_posix(), json.dumps(str(path))[1:-1]):
                needles.add(form.lower())
        return needles

    def assert_no_needles(self, needles, data, label):
        lowered = data.lower() if isinstance(data, bytes) else data.lower().encode("utf-8", "replace")
        for needle in needles:
            self.assertNotIn(needle.encode("utf-8"), lowered, f"source path found in {label}")

    def test_yaml_block_launcher_really_blocks_yaml(self):
        probe = self.base / "probe.py"
        probe.write_text("import yaml\n", encoding="utf-8")
        blocked = run([sys.executable, "-c", BLOCK_YAML, probe])
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("yaml", blocked.stderr)

    def test_a7_installed_tools_work_after_the_source_is_moved_and_deleted(self):
        source_base = self.base / "source-base"
        source_base.mkdir()
        source = source_base / "source"
        source.mkdir()
        revision = self.make_source(source)
        target = self.spec_kit_repo("target")
        (target / "README.md").write_bytes(b"readme\n")
        git(target, "add", "README.md")
        self.commit(target)
        user_files = {
            "README.md": b"readme edited, uncommitted\n",
            "notes.txt": b"untracked notes\n",
            "src/staged.py": b"print('staged')\n",
        }
        (target / "src").mkdir()
        for relative, data in user_files.items():
            (target / relative).write_bytes(data)
        git(target, "add", "src/staged.py")
        head = git(target, "rev-parse", "HEAD")
        staged = git(target, "diff", "--cached", "--name-only")
        self.assertEqual(staged.strip(), "src/staged.py")

        install = self.install(target, installer=source / "scripts" / "install_factory.py")
        self.assert_install_ok(install)
        self.assertIn("Verdict: ready with limitations", install.stdout)
        manifest = json.loads((target / MANIFEST).read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_revision"], revision)

        set_tier = run(
            [sys.executable, target / "scripts" / "specialist_models.py", "set-tier", "balanced", "test-model"],
            cwd=target,
        )
        self.assertEqual(set_tier.returncode, 0, set_tier.stdout + set_tier.stderr)

        before = self.tool_runs(target, blocked=False)
        self.assertEqual(before["validator"][0], 0, before["validator"])
        self.assertEqual(before["resolve-engineer"][1].strip(), "test-model")
        self.assertEqual(before["resolve-qa"][0], 3)
        self.assert_readiness_ok(before["readiness"][1], before["readiness"][0])

        moved = source_base / "relocated-source"
        shutil.move(str(source), str(moved))
        self.assertFalse(source.exists())
        self.assertTrue((moved / "scripts" / "install_factory.py").is_file())
        remove_tree(moved)
        self.assertFalse(moved.exists())

        after = self.tool_runs(target, blocked=True)
        self.assertEqual(after, before)
        self.assertEqual(after["validator"][0], 0)
        self.assertIn("All five specialist profiles are valid.", after["validator"][1])
        self.assertIn("[PASS] speckit-config", after["readiness"][1])
        self.assert_readiness_ok(after["readiness"][1], after["readiness"][0])
        self.assertIn("Verdict: ready with limitations", after["readiness"][1])
        self.assertNotIn("[FAIL]", after["readiness"][1])
        self.assertEqual(after["resolve-engineer"], (0, "test-model\n", ""))
        self.assertEqual(after["resolve-architect"][1].strip(), "test-model")
        self.assertEqual(json.loads(after["status"][1])["roles"]["engineer"]["model"], "test-model")

        profile = (target / ".github" / "agents" / "factory-lead.agent.md").read_text(encoding="utf-8")
        self.assertIn("python scripts/specialist_models.py resolve", profile)

        needles = self.source_path_needles(source, moved, source_base)
        outputs = [install.stdout, install.stderr]
        for results in (before, after):
            for returncode, stdout, stderr in results.values():
                outputs.extend((stdout, stderr))
        for index, text in enumerate(outputs):
            self.assert_no_needles(needles, text, f"tool output {index}")
        scanned = 0
        for directory, directories, files in os.walk(target):
            if ".git" in directories:
                directories.remove(".git")
            for name in files:
                full = Path(directory, name)
                self.assert_no_needles(needles, full.read_bytes(), str(full.relative_to(target)))
                scanned += 1
        self.assertGreaterEqual(scanned, 10)

        for relative, data in user_files.items():
            self.assertEqual((target / relative).read_bytes(), data, relative)
        self.assertEqual(git(target, "rev-parse", "HEAD"), head)
        self.assertEqual(git(target, "diff", "--cached", "--name-only"), staged)


if __name__ == "__main__":
    unittest.main()
