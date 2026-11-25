import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import specialist_models  # noqa: E402  (the checkout's own helper: the source of truth for presets)
import specfactory  # noqa: E402
from specfactory import bundle, cli  # noqa: E402


READINESS = bundle.load_script("check_factory_readiness")
SPEC_KIT_FILES = READINESS.SPECKIT_FILES
MANAGED = READINESS.MANAGED_FILES
MANIFEST = READINESS.MANIFEST_PATH
PREFERENCES = READINESS.PREFERENCES_PATH
DRY_PLAN = "PLAN-SENTINEL: 9 create, 0 unchanged, 0 conflict\nDRY RUN: nothing was changed."
REAL_OK = (
    "[created]   scripts/specialist_models.py\nInstalled 10 file(s).\nInstalled readiness check:\n"
    "[PASS] speckit-config: ok\nVerdict: ready with limitations\n"
    "Limitations: authentication, live dispatch, effective sandbox enforcement\nNext steps:\n"
)
REAL_NOT_READY = "Installed 10 file(s).\nInstalled readiness check:\n[FAIL] interactive-hooks: policy missing\nVerdict: not ready\n"


class World:
    """A fake machine and project: tools on PATH, Spec Kit state, and a chronological event log."""

    def __init__(self, target, *, specify=True, spec_kit="ok", uv=True, python=True):
        self.target = str(target)
        self.tools = {"git": "/bin/git"}
        if specify:
            self.tools["specify"] = "/bin/specify"
        if uv:
            self.tools["uv"] = "/bin/uv"
        if python:
            self.tools["python"] = "/bin/python"
        self.python_version = "Python 3.11.0"
        self.toplevel = self.target
        self.events = []
        self.output = io.StringIO()
        self.integration_ok = False
        self.cli_install_status = 0
        self.cli_install_on_path = True
        self.dry = (0, DRY_PLAN)
        self.real = (0, REAL_OK)
        if spec_kit == "ok":
            self.make_spec_kit_valid()
        elif spec_kit == "incomplete":
            (Path(self.target) / ".specify").mkdir()

    def make_spec_kit_valid(self):
        for relative in SPEC_KIT_FILES:
            path = Path(self.target) / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x\n", encoding="utf-8")
        self.integration_ok = True

    def which(self, name):
        return self.tools.get(name)

    def query(self, arguments, cwd=None, timeout=None):
        arguments = list(arguments)
        self.events.append(("query", arguments))
        done = subprocess.CompletedProcess
        if arguments[:1] == ["git"]:
            return done(arguments, 0, self.toplevel + "\n", "")
        if arguments[1:] == ["--version"]:
            if arguments[0] == self.tools.get("python"):
                return done(arguments, 0, self.python_version + "\n", "")
            return done(arguments, 0, "specify 1.0.6\n", "")
        if arguments[1:] == ["integration", "status", "--json"]:
            if not self.integration_ok:
                return done(arguments, 1, "", "no integration")
            document = {
                "status": "ok", "default_integration": "copilot",
                "installed_integrations": ["copilot"], "missing_managed_files": 0,
                "modified_managed_files": 0, "invalid_manifest_paths": 0,
                "unchecked_manifests": 0, "findings": [],
            }
            return done(arguments, 0, json.dumps(document), "")
        raise AssertionError(f"unexpected query: {arguments}")

    def setup(self, arguments, cwd):
        arguments = list(arguments)
        self.events.append(("setup", arguments, cwd))
        if arguments[1:3] == ["tool", "install"]:
            if self.cli_install_status == 0 and self.cli_install_on_path:
                self.tools["specify"] = "/bin/specify"
            return self.cli_install_status
        raise AssertionError(f"unexpected setup command: {arguments}")

    def script(self, arguments, cwd, environment):
        arguments = list(arguments)
        self.events.append(("script", arguments, dict(environment)))
        done = subprocess.CompletedProcess
        script = Path(arguments[2])
        if script.name == "install_factory.py":
            assert Path(arguments[2]).parent.parent == bundle.asset_root()
            status, text = self.dry if "--dry-run" in arguments else self.real
            return done(arguments, status, text, "")
        if script.name == "specialist_models.py":
            if arguments[3] == "set-preset":
                path = Path(self.target) / PREFERENCES
                path.parent.mkdir(exist_ok=True)
                path.write_text("{}\n", encoding="utf-8")
            return done(arguments, 0, "ok\n", "")
        raise AssertionError(f"unexpected script: {arguments}")

    def commands(self, kind):
        return [event for event in self.events if event[0] == kind]

    def engine_runs(self, dry):
        return [
            event for event in self.commands("script")
            if Path(event[1][2]).name == "install_factory.py" and (("--dry-run" in event[1]) == dry)
        ]

    def helper_runs(self):
        return [e for e in self.commands("script") if Path(e[1][2]).name == "specialist_models.py"]

    def prompts(self):
        return [event for event in self.events if event[0] == "prompt"]

    def order(self):
        """Compact chronological summary of prompts, setup and engine runs."""
        summary = []
        for event in self.events:
            if event[0] == "prompt":
                summary.append("prompt")
            elif event[0] == "setup":
                summary.append("setup:" + " ".join(event[1][1:3]))
            elif event[0] == "script" and Path(event[1][2]).name == "install_factory.py":
                summary.append("engine:dry" if "--dry-run" in event[1] else "engine:real")
        return summary


class PublicCliCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.target = Path(os.path.realpath(temporary.name))

    def world(self, **options):
        return World(self.target, **options)

    def run_cli(self, world, *argv, answers=(), interactive=True, cwd=None):
        pending = list(answers)

        def ask(prompt):
            world.events.append(("prompt", prompt, world.output.getvalue()))
            if not pending and "Preset to configure now" in prompt:
                return ""  # post-install model setup is optional; tests opt in by scripting an answer
            if not pending:
                raise AssertionError(f"unexpected prompt: {prompt}")
            return pending.pop(0)

        code = cli.main(
            list(argv), stdout=world.output, environment={"PATH": "", "FACTORY_X": "1", "PYTHONPATH": "p"},
            which=world.which, query_runner=world.query, setup_runner=world.setup,
            script_runner=world.script, input_fn=ask, interactive=interactive,
            cwd=str(cwd or self.target),
        )
        self.assertEqual(pending, [], "scripted answers were not all consumed")
        return code

    def text(self, world):
        return world.output.getvalue()


class ParsingAndTargetTests(PublicCliCase):
    def test_bad_arguments_exit_2_without_any_action(self):
        import contextlib

        for argv in ([], ["factory"], ["init", "--force"]):
            world = self.world()
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()):
                code = self.run_cli(world, *argv)
            self.assertEqual(code, 2)
            self.assertEqual(world.events, [])

    def test_target_defaults_to_the_current_directory(self):
        world = self.world()
        self.assertEqual(self.run_cli(world, "init", "--dry-run"), 0)
        self.assertIn(f"Target: {self.target}", self.text(world))
        arguments = world.engine_runs(dry=True)[0][1]
        self.assertEqual(arguments[arguments.index("--target") + 1], str(self.target))

    def test_explicit_target_is_used_instead_of_the_current_directory(self):
        world = self.world()
        elsewhere = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere.cleanup)
        code = self.run_cli(world, "init", "--dry-run", "--target", str(self.target), cwd=elsewhere.name)
        self.assertEqual(code, 0)
        self.assertIn(f"Target: {self.target}", self.text(world))

    def test_missing_target_directory_is_refused(self):
        world = self.world()
        code = self.run_cli(world, "init", "--target", str(self.target / "nope"))
        self.assertEqual(code, 2)
        self.assertEqual(world.events, [])
        self.assertIn("existing directory", self.text(world))

    def test_a_subdirectory_of_a_repository_is_refused_naming_the_root(self):
        world = self.world()
        sub = self.target / "sub"
        sub.mkdir()
        world.toplevel = str(self.target)
        code = self.run_cli(world, "init", "--target", str(sub))
        self.assertEqual(code, 2)
        self.assertIn("not the Git project root", self.text(world))
        self.assertIn(str(self.target), self.text(world))
        self.assertEqual(world.commands("setup"), [])
        self.assertEqual(world.commands("script"), [])

    def test_a_directory_outside_any_repository_is_refused(self):
        world = self.world()

        def failing(arguments, cwd=None, timeout=None):
            return subprocess.CompletedProcess(arguments, 128, "", "fatal")

        world.query = failing
        code = self.run_cli(world, "init")
        self.assertEqual(code, 2)
        self.assertIn("not inside a Git working tree", self.text(world))

    def test_git_missing_is_refused(self):
        world = self.world()
        del world.tools["git"]
        self.assertEqual(self.run_cli(world, "init"), 2)
        self.assertIn("git was not found", self.text(world))

    def test_no_factory_command_alias_is_offered(self):
        parser = cli._build_parser()
        self.assertEqual(parser.prog, "specfactory")
        self.assertNotIn("factory", parser._subparsers._group_actions[0].choices)
        self.assertEqual(list(parser._subparsers._group_actions[0].choices), ["init"])


class WorkspaceCliTests(PublicCliCase):
    def test_missing_workspace_spec_kit_gives_manual_root_setup_instructions(self):
        world = self.world(spec_kit="none")
        repositories = [
            {"path": "clients/web", "branch": "main", "head": "abc123", "clean": True, "dirty_paths": 0},
            {"path": "services/api", "branch": "main", "head": "def456", "clean": True, "dirty_paths": 0},
        ]
        with mock.patch.object(READINESS, "discover_workspace_repositories", return_value=(repositories, None)):
            code = self.run_cli(world, "init", "--workspace", "--dry-run")

        self.assertEqual(code, 2)
        self.assertIn("specify init --here --integration copilot", self.text(world))
        self.assertIn("review its merge prompt", self.text(world))
        self.assertIn("never uses --force", self.text(world))
        self.assertEqual(world.commands("script"), [])
        self.assertEqual(world.commands("setup"), [])

    def test_workspace_mode_forwards_flag_and_does_not_prompt_for_preferences(self):
        world = self.world()
        repositories = [
            {"path": "clients/web", "branch": "main", "head": "abc123", "clean": True, "dirty_paths": 0},
            {"path": "services/api", "branch": "main", "head": "def456", "clean": False, "dirty_paths": 1},
        ]
        with mock.patch.object(READINESS, "discover_workspace_repositories", return_value=(repositories, None)):
            code = self.run_cli(world, "init", "--workspace", answers=["y"])

        self.assertEqual(code, 0, self.text(world))
        self.assertEqual(len(world.prompts()), 1)
        self.assertEqual(world.helper_runs(), [])
        self.assertIn("services/api (branch main; HEAD def456; dirty (1 path(s)))", self.text(world))
        self.assertIn("child repositories were not modified", self.text(world))
        self.assertTrue(all("--workspace" in event[1] for event in world.engine_runs(dry=True)))
        self.assertTrue(all("--workspace" in event[1] for event in world.engine_runs(dry=False)))
        arguments = world.engine_runs(dry=True)[0][1]
        self.assertEqual(arguments[arguments.index("--target") + 1], str(self.target))

    def test_declining_workspace_install_never_runs_the_real_installer(self):
        world = self.world()
        repositories = [
            {"path": "clients/web", "branch": "main", "head": "abc123", "clean": True, "dirty_paths": 0},
            {"path": "services/api", "branch": "main", "head": "def456", "clean": True, "dirty_paths": 0},
        ]
        with mock.patch.object(READINESS, "discover_workspace_repositories", return_value=(repositories, None)):
            code = self.run_cli(world, "init", "--workspace", answers=["n"])

        self.assertEqual(code, 2)
        self.assertEqual(len(world.engine_runs(dry=True)), 1)
        self.assertEqual(world.engine_runs(dry=False), [])
        self.assertEqual(world.helper_runs(), [])
        self.assertIn("Declined", self.text(world))


class PreviewAndConsentTests(PublicCliCase):
    def test_dry_run_is_read_only_asks_nothing_and_runs_only_the_engine_dry_run(self):
        world = self.world()
        code = self.run_cli(world, "init", "--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(world.prompts(), [])
        self.assertEqual(world.commands("setup"), [])
        self.assertEqual(world.engine_runs(dry=False), [])
        self.assertEqual(len(world.engine_runs(dry=True)), 1)
        self.assertIn("PLAN-SENTINEL", self.text(world))
        self.assertIn("DRY RUN: nothing was changed", self.text(world))

    def test_dry_run_with_missing_prerequisites_lists_actions_but_does_nothing(self):
        world = self.world(specify=False, spec_kit="none")
        code = self.run_cli(world, "init", "--dry-run")
        text = self.text(world)
        self.assertEqual(code, 2)
        self.assertEqual(world.prompts(), [])
        self.assertEqual(world.commands("setup"), [])
        self.assertEqual(world.commands("script"), [])
        for fragment in ("uv tool install specify-cli==1.0.6", "will not run a command that requires `--force`", "Install the Software Factory"):
            self.assertIn(fragment, text)
        for path in (*MANAGED, MANIFEST):
            self.assertIn(path, text)
        self.assertIn("never overwrite", text)

    def test_preview_is_complete_before_the_first_prompt(self):
        world = self.world(specify=False, spec_kit="none")
        self.run_cli(world, "init", answers=["n"])
        prompt = world.prompts()[0]
        self.assertIn("Proposed actions", prompt[2])
        self.assertIn("uv tool install specify-cli==1.0.6", prompt[2])
        self.assertIn("will not run a command that requires `--force`", prompt[2])
        self.assertIn(MANAGED[0], prompt[2])

    def test_valid_project_has_a_single_install_prompt_after_the_engine_plan(self):
        world = self.world()
        code = self.run_cli(world, "init", answers=["y"])
        self.assertEqual(code, 0)
        self.assertEqual(world.order(), ["engine:dry", "prompt", "engine:real", "prompt"])
        self.assertIn("PLAN-SENTINEL", world.prompts()[0][2])
        self.assertEqual(world.commands("setup"), [])

    def test_declining_the_install_changes_nothing(self):
        for answer in ("n", "", "no", "maybe", "yes please"):
            world = self.world()
            with self.subTest(answer=answer):
                code = self.run_cli(world, "init", answers=[answer])
                self.assertEqual(code, 2)
                self.assertEqual(world.engine_runs(dry=False), [])
                self.assertIn("No project changes were made", self.text(world))

    def test_eof_at_a_prompt_is_a_decline(self):
        world = self.world()

        def eof(prompt):
            raise EOFError

        code = cli.main(
            ["init"], stdout=world.output, environment={"PATH": ""}, which=world.which,
            query_runner=world.query, setup_runner=world.setup, script_runner=world.script,
            input_fn=eof, interactive=True, cwd=str(self.target),
        )
        self.assertEqual(code, 2)
        self.assertEqual(world.engine_runs(dry=False), [])

    def test_installer_conflict_in_the_dry_run_stops_before_any_prompt(self):
        world = self.world()
        world.dry = (1, "[conflict]  .github/agents/engineer.agent.md: different content\nPlan: 8 create, 0 unchanged, 1 conflict")
        code = self.run_cli(world, "init")
        self.assertEqual(code, 1)
        self.assertEqual(world.prompts(), [])
        self.assertEqual(world.engine_runs(dry=False), [])

    def test_installer_refusal_exit_status_is_preserved(self):
        world = self.world()
        world.dry = (2, "Refused: .factory/model-preferences.json is already tracked by Git")
        self.assertEqual(self.run_cli(world, "init"), 2)
        self.assertEqual(world.engine_runs(dry=False), [])

    def test_engine_result_and_exit_status_are_preserved(self):
        for status in (1, 2, 3):
            world = self.world()
            world.real = (status, "installer output\n")
            with self.subTest(status=status):
                self.assertEqual(self.run_cli(world, "init", answers=["y"]), status)

    def test_engine_runs_the_bundled_script_without_bytecode_or_inherited_overrides(self):
        world = self.world()
        self.run_cli(world, "init", answers=["y"])
        for event in world.commands("script"):
            arguments, environment = event[1], event[2]
            self.assertEqual(arguments[:2], [sys.executable, "-B"])
            self.assertEqual(Path(arguments[2]), bundle.asset_root() / "scripts" / "install_factory.py")
            self.assertNotIn("PYTHONPATH", environment)
            self.assertFalse(any(key.startswith("FACTORY_") for key in environment))
            self.assertEqual(environment["PYTHONDONTWRITEBYTECODE"], "1")

    def test_prerequisite_findings_are_reported_exactly(self):
        world = self.world()
        world.tools.pop("uv")
        world.python_version = "Python 3.9.1"
        self.run_cli(world, "init", "--dry-run")
        text = self.text(world)
        self.assertIn("Specify CLI: [PASS]", text)
        self.assertIn(
            "Copilot CLI (readiness check only; VS Code Copilot Chat is the primary path): "
            "NOT FOUND on PATH; optional for installed-project readiness",
            text,
        )
        self.assertIn("Spec Kit + Copilot integration: [PASS]", text)
        self.assertIn("uv: not found", text)
        self.assertIn("older than 3.11", text)

    def test_missing_python_on_path_is_reported_as_a_finding_not_a_blocker(self):
        world = self.world(python=False)
        self.assertEqual(self.run_cli(world, "init", "--dry-run"), 0)
        self.assertIn("install Python 3.11+", self.text(world))


class SetupApprovalTests(PublicCliCase):
    def setup_commands(self, world):
        return [event[1] for event in world.commands("setup")]

    def test_missing_cli_is_approved_separately_then_invalid_project_is_refused(self):
        world = self.world(specify=False, spec_kit="none")
        code = self.run_cli(world, "init", answers=["y"])
        self.assertEqual(code, 2)
        self.assertEqual(
            world.order(),
            ["prompt", "setup:tool install"],
        )
        self.assertEqual(self.setup_commands(world), [["/bin/uv", "tool", "install", "specify-cli==1.0.6"]])
        self.assertIsNone(world.commands("setup")[0][2])
        self.assertIn("Automatic initialization is unavailable without --force", self.text(world))
        self.assertEqual(world.commands("script"), [])

    def test_no_setup_command_ever_uses_force(self):
        world = self.world(specify=False, spec_kit="none")
        self.run_cli(world, "init", answers=["y"])
        for command in self.setup_commands(world):
            self.assertFalse(any("force" in part.lower() for part in command))
        for event in world.commands("script"):
            self.assertFalse(any("force" in str(part).lower() for part in event[1]))

    def test_each_approval_applies_to_one_action_only(self):
        world = self.world(specify=False, spec_kit="none")
        code = self.run_cli(world, "init", answers=["y"])
        self.assertEqual(code, 2)
        self.assertEqual(len(self.setup_commands(world)), 1)
        self.assertEqual(world.engine_runs(dry=False), [])
        self.assertIn("initialize or repair it manually", self.text(world))
        self.assertIn("installed the Specify CLI", self.text(world))

    def test_declined_cli_installation_runs_nothing(self):
        world = self.world(specify=False, spec_kit="none")
        code = self.run_cli(world, "init", answers=["n"])
        self.assertEqual(code, 2)
        self.assertEqual(world.commands("setup"), [])
        self.assertEqual(world.commands("script"), [])
        self.assertEqual(len(world.prompts()), 1)
        self.assertIn("No project changes were made", self.text(world))

    def test_spec_kit_initialization_is_not_offered_when_only_force_would_work(self):
        world = self.world(spec_kit="none")
        readme = self.target / "README.md"
        readme.write_text("existing project content\n", encoding="utf-8")
        code = self.run_cli(world, "init")
        self.assertEqual(code, 2)
        self.assertIn("without --force in a Git project", self.text(world))
        self.assertIn("initialize or repair it manually", self.text(world))
        self.assertEqual(world.prompts(), [])
        self.assertEqual(world.commands("setup"), [])
        self.assertEqual(world.commands("script"), [])
        self.assertEqual(readme.read_text(encoding="utf-8"), "existing project content\n")

    def test_missing_specify_cli_may_be_installed_before_nonempty_project_is_refused(self):
        world = self.world(specify=False, spec_kit="none")
        readme = self.target / "README.md"
        readme.write_text("existing project content\n", encoding="utf-8")
        code = self.run_cli(world, "init", answers=["y"])
        self.assertEqual(code, 2)
        self.assertEqual(self.setup_commands(world), [["/bin/uv", "tool", "install", "specify-cli==1.0.6"]])
        self.assertIn("Automatic initialization is unavailable without --force", self.text(world))
        self.assertEqual(world.commands("script"), [])
        self.assertEqual(readme.read_text(encoding="utf-8"), "existing project content\n")

    def test_failed_cli_installation_stops_without_further_prompts(self):
        world = self.world(specify=False, spec_kit="none")
        world.cli_install_status = 1
        code = self.run_cli(world, "init", answers=["y"])
        self.assertEqual(code, 1)
        self.assertEqual(len(self.setup_commands(world)), 1)
        self.assertEqual(world.commands("script"), [])

    def test_cli_not_on_path_after_installation_stops_after_revalidation(self):
        world = self.world(specify=False, spec_kit="none")
        world.cli_install_on_path = False
        code = self.run_cli(world, "init", answers=["y"])
        self.assertEqual(code, 1)
        self.assertEqual(len(world.prompts()), 1)
        self.assertEqual(world.commands("script"), [])
        self.assertIn("still not on PATH", self.text(world))

    def test_revalidation_runs_after_each_setup_action(self):
        world = self.world(specify=False, spec_kit="none")
        self.run_cli(world, "init", answers=["y"])
        kinds = [event[0] for event in world.events]
        first = kinds.index("setup")
        after_setup = world.events[first + 1:]
        self.assertTrue(any(e[0] == "query" and e[1][1:] == ["--version"] for e in after_setup))
        self.assertTrue(
            any(e[0] == "query" and e[1][1:] == ["integration", "status", "--json"] for e in after_setup)
        )

    def test_installed_cli_over_valid_spec_kit_needs_no_initialization_prompt(self):
        world = self.world(specify=False, spec_kit="ok")
        code = self.run_cli(world, "init", answers=["y", "y"])
        self.assertEqual(code, 0)
        self.assertEqual(len(self.setup_commands(world)), 1)
        self.assertEqual(world.order().count("prompt"), 3)

    def test_incomplete_spec_kit_is_never_repaired_or_reinitialized(self):
        world = self.world(spec_kit="incomplete")
        code = self.run_cli(world, "init", answers=[])
        self.assertEqual(code, 2)
        self.assertEqual(world.commands("setup"), [])
        self.assertEqual(world.prompts(), [])
        self.assertEqual(world.commands("script"), [])
        self.assertIn("incomplete", self.text(world))
        self.assertIn("Automatic initialization is unavailable without --force", self.text(world))

    def test_missing_uv_blocks_cli_installation_with_guidance(self):
        world = self.world(specify=False, spec_kit="none", uv=False)
        code = self.run_cli(world, "init")
        self.assertEqual(code, 2)
        self.assertEqual(world.prompts(), [])
        self.assertEqual(world.commands("setup"), [])
        self.assertIn(cli.UV_INSTALL_URL, self.text(world))

    def test_unusable_specify_is_not_replaced_automatically(self):
        world = self.world()

        def broken(arguments, cwd=None, timeout=None):
            if list(arguments)[1:] == ["--version"] and arguments[0] == "/bin/specify":
                return subprocess.CompletedProcess(arguments, 1, "", "boom")
            return World.query(world, arguments, cwd, timeout)

        world.query = broken
        code = self.run_cli(world, "init")
        self.assertEqual(code, 2)
        self.assertEqual(world.prompts(), [])
        self.assertEqual(world.commands("setup"), [])
        self.assertIn("unusable", self.text(world))

    def test_setup_commands_that_try_force_are_refused_by_the_guard(self):
        world = self.world()
        onboarding = cli._Onboarding(
            str(self.target), stdout=world.output, input_fn=None, interactive=True, environment={},
            which=world.which, query=world.query, setup=world.setup, script=world.script,
        )
        with self.assertRaises(ValueError):
            onboarding.run_setup("x", ["specify", "init", "--force"], None)
        self.assertEqual(world.commands("setup"), [])


class NonInteractiveTests(PublicCliCase):
    def test_yes_requires_non_interactive(self):
        import contextlib

        world = self.world()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.run_cli(world, "init", "--yes"), 2)
        self.assertEqual(world.events, [])

    def test_yes_is_rejected_with_dry_run(self):
        import contextlib

        world = self.world()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.run_cli(world, "init", "--non-interactive", "--yes", "--dry-run"), 2)
        self.assertEqual(world.events, [])

    def test_non_interactive_without_yes_is_preview_only(self):
        world = self.world()
        code = self.run_cli(world, "init", "--non-interactive")
        self.assertEqual(code, 0)
        self.assertEqual(world.prompts(), [])
        self.assertEqual(world.commands("setup"), [])
        self.assertEqual(world.engine_runs(dry=False), [])
        self.assertIn("Preview only", self.text(world))
        self.assertIn("--non-interactive --yes", self.text(world))

    def test_non_interactive_with_missing_prerequisites_and_no_yes_changes_nothing(self):
        world = self.world(specify=False, spec_kit="none")
        code = self.run_cli(world, "init", "--non-interactive")
        self.assertEqual(code, 2)
        self.assertEqual(world.prompts(), [])
        self.assertEqual(world.commands("setup"), [])
        self.assertEqual(world.commands("script"), [])

    def test_yes_installs_only_when_prerequisites_already_pass_and_never_prompts(self):
        world = self.world()
        code = self.run_cli(world, "init", "--non-interactive", "--yes")
        self.assertEqual(code, 0)
        self.assertEqual(world.prompts(), [])
        self.assertEqual(world.commands("setup"), [])
        self.assertEqual(len(world.engine_runs(dry=False)), 1)
        self.assertEqual(world.order(), ["engine:dry", "engine:real"])

    def test_yes_never_authorizes_specify_or_spec_kit_setup(self):
        for options in ({"specify": False, "spec_kit": "none"}, {"spec_kit": "none"}, {"spec_kit": "incomplete"}):
            world = self.world(**options)
            with self.subTest(options=options):
                code = self.run_cli(world, "init", "--non-interactive", "--yes")
                self.assertEqual(code, 2)
                self.assertEqual(world.prompts(), [])
                self.assertEqual(world.commands("setup"), [])
                self.assertEqual(world.commands("script"), [])
                self.assertIn("Refused", self.text(world))
                self.assertIn("No project changes were made", self.text(world))
            shutil.rmtree(self.target / ".specify", ignore_errors=True)

    def test_yes_does_not_apply_when_the_installer_plan_has_conflicts(self):
        world = self.world()
        world.dry = (1, "[conflict] x\nPlan: 8 create, 0 unchanged, 1 conflict")
        self.assertEqual(self.run_cli(world, "init", "--non-interactive", "--yes"), 1)
        self.assertEqual(world.engine_runs(dry=False), [])

    def test_redirected_input_without_non_interactive_never_prompts_or_writes(self):
        world = self.world()
        code = self.run_cli(world, "init", interactive=False)
        self.assertEqual(code, 0)
        self.assertEqual(world.prompts(), [])
        self.assertEqual(world.engine_runs(dry=False), [])
        self.assertIn("not a terminal", self.text(world))

    def test_non_interactive_reports_model_guidance_without_prompting(self):
        world = self.world()
        self.run_cli(world, "init", "--non-interactive", "--yes")
        self.assertEqual(world.prompts(), [])
        self.assertEqual(world.helper_runs(), [])
        self.assertIn("Configure later", self.text(world))


class ModelGuidanceTests(PublicCliCase):
    def test_every_preset_mapping_matches_the_helper(self):
        world = self.world()
        self.run_cli(world, "init", answers=["y", ""])
        text = self.text(world)
        for name, mapping in specialist_models.PRESETS.items():
            line = f"{name}" + (" (helper default)" if name == specialist_models.DEFAULT_PRESET else "") + ": "
            line += ", ".join(f"{role}={tier}" for role, tier in mapping.items())
            self.assertIn(line, text)
        self.assertIn("Tiers: budget, balanced, quality", text)
        self.assertIn("may cost more", text)

    def test_bundled_helper_presets_equal_the_checkouts(self):
        bundled = bundle.load_script("specialist_models")
        self.assertEqual(bundled.PRESETS, specialist_models.PRESETS)
        self.assertEqual(bundled.TIERS, specialist_models.TIERS)
        self.assertEqual(bundled.DEFAULT_PRESET, specialist_models.DEFAULT_PRESET)

    def test_skipping_creates_no_preferences_and_no_model_ids(self):
        world = self.world()
        self.run_cli(world, "init", answers=["y", ""])
        self.assertEqual(world.helper_runs(), [])
        self.assertFalse((self.target / PREFERENCES).exists())
        self.assertEqual(len(world.prompts()), 2)

    def test_unknown_preset_name_configures_nothing(self):
        world = self.world()
        self.run_cli(world, "init", answers=["y", "turbo"])
        self.assertEqual(world.helper_runs(), [])
        self.assertIn("not a preset", self.text(world))

    def test_budget_asks_only_for_the_tiers_it_uses_and_needs_consent(self):
        world = self.world()
        code = self.run_cli(world, "init", answers=["y", "budget", "model-b", "model-a", "y"])
        self.assertEqual(code, 0)
        tier_prompts = [p[1] for p in world.prompts() if "Model ID or display name for tier" in p[1]]
        self.assertEqual(len(tier_prompts), 2)
        self.assertIn("'budget'", tier_prompts[0])
        self.assertIn("'balanced'", tier_prompts[1])
        self.assertFalse(any("'quality'" in prompt for prompt in tier_prompts))
        commands = [event[1][3:] for event in world.helper_runs()]
        self.assertEqual(
            commands,
            [["set-preset", "budget"], ["set-tier", "budget", "model-b"], ["set-tier", "balanced", "model-a"]],
        )

    def test_quality_first_does_not_prompt_for_lower_tiers(self):
        world = self.world()
        self.run_cli(world, "init", answers=["y", "quality-first", "big-model", "y"])
        tier_prompts = [p[1] for p in world.prompts() if "Model ID or display name for tier" in p[1]]
        self.assertEqual(len(tier_prompts), 1)
        self.assertIn("'quality'", tier_prompts[0])
        self.assertEqual(
            [event[1][3:] for event in world.helper_runs()],
            [["set-preset", "quality-first"], ["set-tier", "quality", "big-model"]],
        )

    def test_blank_ids_are_not_invented(self):
        world = self.world()
        self.run_cli(world, "init", answers=["y", "balanced", ""])
        self.assertEqual(world.helper_runs(), [])
        self.assertFalse((self.target / PREFERENCES).exists())
        self.assertIn("No model IDs entered", self.text(world))

    def test_declining_the_final_consent_writes_nothing(self):
        world = self.world()
        self.run_cli(world, "init", answers=["y", "balanced", "some-model", "n"])
        self.assertEqual(world.helper_runs(), [])
        self.assertFalse((self.target / PREFERENCES).exists())

    def test_invalid_model_id_is_ignored(self):
        world = self.world()
        self.run_cli(world, "init", answers=["y", "balanced", "--bad"])
        self.assertEqual(world.helper_runs(), [])
        self.assertIn("not a valid model ID", self.text(world))

    def test_existing_preferences_are_left_alone_and_nothing_is_asked(self):
        world = self.world()
        path = self.target / PREFERENCES
        path.parent.mkdir()
        path.write_text('{"keep": true}\n', encoding="utf-8")
        self.run_cli(world, "init", answers=["y"])
        self.assertEqual(world.helper_runs(), [])
        self.assertEqual(path.read_text(encoding="utf-8"), '{"keep": true}\n')
        self.assertIn("left unchanged", self.text(world))

    def test_no_model_guidance_when_the_installer_did_not_install(self):
        world = self.world()
        world.real = (1, "conflict\n")
        self.run_cli(world, "init", answers=["y"])
        self.assertNotIn("Model setup", self.text(world))


class ReadinessAndGuidanceTests(PublicCliCase):
    def test_ready_result_reports_the_verdict_limitations_and_vscode_steps(self):
        world = self.world()
        code = self.run_cli(world, "init", "--non-interactive", "--yes")
        text = self.text(world)
        self.assertEqual(code, 0)
        self.assertIn("Software Factory is installed.", text)
        self.assertIn("Readiness verdict: ready with limitations", text)
        self.assertIn("Limitations: authentication, live dispatch, effective sandbox enforcement", text)
        self.assertIn("Copilot Chat", text)
        self.assertIn("'Factory Lead'", text)
        self.assertIn("Open this project folder in VS Code", text)
        self.assertIn("git status", text)

    def test_guidance_does_not_claim_chat_verification(self):
        world = self.world()
        self.run_cli(world, "init", "--non-interactive", "--yes")
        text = self.text(world)
        self.assertIn("Not verified", text)
        self.assertIn("no Copilot session was run", text)
        self.assertNotIn("verified in Chat", text)

    def test_not_ready_is_reported_without_claiming_success_or_rollback(self):
        world = self.world()
        world.real = (3, REAL_NOT_READY)
        code = self.run_cli(world, "init", "--non-interactive", "--yes")
        text = self.text(world)
        self.assertEqual(code, 3)
        self.assertIn("Readiness verdict: not ready", text)
        self.assertIn("NOT READY", text)
        self.assertIn("nothing was rolled back", text)
        self.assertNotIn("Software Factory is installed.", text)
        self.assertNotIn("Limitations:", text.split("Result:")[1])
        self.assertIn("Next steps in VS Code", text)

    def test_incomplete_install_gives_no_vscode_launch_guidance(self):
        world = self.world()
        world.real = (1, "[conflict]  x: appeared during installation\n")
        code = self.run_cli(world, "init", "--non-interactive", "--yes")
        text = self.text(world)
        self.assertEqual(code, 1)
        self.assertIn("INCOMPLETE", text)
        self.assertNotIn("Next steps in VS Code", text)
        self.assertNotIn("Software Factory is installed.", text)

    def test_missing_verdict_is_reported_as_not_reported(self):
        world = self.world()
        world.real = (0, "Installed 10 file(s).\n")
        self.run_cli(world, "init", "--non-interactive", "--yes")
        self.assertIn("Readiness verdict: not reported", self.text(world))

    def test_installer_output_is_shown_verbatim(self):
        world = self.world()
        self.run_cli(world, "init", "--non-interactive", "--yes")
        self.assertIn(REAL_OK.rstrip("\n"), self.text(world))


def _snapshot(root):
    entries = {}
    for directory, directories, files in os.walk(root):
        for name in directories:
            entries[os.path.relpath(os.path.join(directory, name), root)] = "D"
        for name in files:
            full = os.path.join(directory, name)
            with open(full, "rb") as handle:
                entries[os.path.relpath(full, root)] = hashlib.sha256(handle.read()).hexdigest()
    return entries


def _force_remove(function, path, _info):
    os.chmod(path, stat.S_IWRITE)
    function(path)


class RealEngineSmokeTests(unittest.TestCase):
    """The bundled engine, unmodified, run from the asset root against a real Specify project."""

    @classmethod
    def setUpClass(cls):
        if shutil.which("git") is None:
            raise RuntimeError("git is required for the real-engine acceptance fixture")
        if shutil.which("specify") is None:
            raise unittest.SkipTest("specify is absent; the optional real-Specify fixture cannot run")
        cls.base = Path(os.path.realpath(tempfile.mkdtemp()))
        cls.template = cls.base / "template"
        cls.template.mkdir()
        subprocess.run(["git", "init", "-q", str(cls.template)], check=True, capture_output=True)
        # Test fixture only: --force lets Specify initialize a pre-existing empty repository offline.
        subprocess.run(
            ["specify", "init", "--here", "--force", "--non-interactive", "--integration", "copilot"],
            cwd=cls.template, check=True, capture_output=True,
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, onerror=_force_remove)

    def setUp(self):
        self.project = self.base / self._testMethodName
        shutil.copytree(self.template, self.project, symlinks=True)

    def run_init(self, *argv):
        out = io.StringIO()
        environment = {k: v for k, v in os.environ.items() if not k.upper().startswith("FACTORY_")
                       and k.upper() not in ("PYTHONPATH", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
        code = cli.main(["init", "--target", str(self.project), *argv], stdout=out, environment=environment,
                        interactive=False)
        return code, out.getvalue()

    def test_dry_run_and_non_interactive_preview_leave_the_project_byte_identical(self):
        before = _snapshot(self.project)
        for argv in (["--dry-run"], ["--non-interactive"], []):
            code, text = self.run_init(*argv)
            self.assertEqual(code, 0, text)
            self.assertIn("create", text)
            self.assertEqual(_snapshot(self.project), before)
        self.assertEqual(list(bundle.asset_root().rglob("__pycache__")), [])

    def test_yes_installs_with_the_bundled_assets_and_reports_readiness(self):
        code, text = self.run_init("--non-interactive", "--yes")
        self.assertEqual(code, 0, text)
        for relative in (*MANAGED, MANIFEST):
            self.assertTrue((self.project / relative).is_file(), relative)
        manifest = json.loads((self.project / MANIFEST).read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_revision"], f"specfactory-{specfactory.__version__}")
        self.assertIn("Readiness verdict:", text)
        self.assertFalse((self.project / PREFERENCES).exists())
        self.assertEqual(list(bundle.asset_root().rglob("__pycache__")), [])
        self.assertFalse((self.project / "scripts" / "__pycache__").exists())
        code, text = self.run_init("--non-interactive", "--yes")
        self.assertEqual(code, 0, text)
        self.assertIn("already installed", text)


if __name__ == "__main__":
    unittest.main()
