"""`specfactory init`: guided, approval-gated installation of the interactive Software Factory.

All project writes are performed by the bundled installer engine or by an explicitly approved setup
command. This module only inspects, previews, asks, sequences and reports.
"""

import argparse
import os
from pathlib import Path
import subprocess
import sys

from . import bundle

EXIT_OK = 0
EXIT_INCOMPLETE = 1
EXIT_REFUSED = 2
EXIT_NOT_READY = 3

UV_INSTALL_URL = "https://docs.astral.sh/uv/getting-started/installation/"
SPECIFY_PACKAGE = "specify-cli==1.0.6"
MINIMUM_PYTHON = (3, 11)


def _default_query(arguments, cwd, timeout):
    readiness = bundle.load_script("check_factory_readiness")
    return readiness.default_runner(arguments, cwd, timeout)


def _default_setup(arguments, cwd):
    """Run an approved setup command with the terminal attached so its own prompts stay visible."""
    return subprocess.run(list(arguments), cwd=cwd, shell=False, check=False).returncode


def _default_script(arguments, cwd, environment):
    return subprocess.run(
        list(arguments), cwd=cwd, env=environment, capture_output=True, text=True,
        encoding="utf-8", errors="replace", shell=False, check=False,
    )


class _Inspection:
    """Read-only snapshot of the prerequisites for one target."""

    def __init__(self):
        self.git = None
        self.copilot = None
        self.python_note = None
        self.uv = None
        self.specify_result = None
        self.specify = None
        self.speckit_result = None

    @property
    def cli_missing(self):
        return self.specify is None

    @property
    def specify_broken(self):
        return self.specify is not None and self.specify_result.status == "FAIL"

    @property
    def spec_kit_ok(self):
        return self.speckit_result is not None and self.speckit_result.status == "PASS"

    @property
    def ready(self):
        return self.spec_kit_ok


class _Onboarding:
    def __init__(self, target, *, stdout, input_fn, interactive, environment, which,
                 query, setup, script, workspace=False):
        self.target = target
        self.workspace = workspace
        self.workspace_repositories = []
        self.stdout = stdout
        self.input_fn = input_fn
        self.interactive = interactive
        self.environment = environment
        self.which = which
        self.query = query
        self.setup = setup
        self.script = script
        self.changes = []
        self.readiness = bundle.load_script("check_factory_readiness")

    def emit(self, text=""):
        print(text, file=self.stdout)

    # inspection ---------------------------------------------------------------------------------

    def inspect(self):
        found = _Inspection()
        root = Path(self.target)
        found.git = self.which("git")
        found.copilot = self.which("copilot") or self.which("copilot.ps1")
        found.uv = self.which("uv")
        found.python_note = self._python_note(root)
        found.specify_result, found.specify = self.readiness.check_specify(
            root, self.query, self.which
        )
        if found.specify is not None and found.specify_result.status != "FAIL":
            found.speckit_result = self.readiness.check_speckit(
                root, self.query, found.specify, require_pointer=False
            )
        return found

    def _python_note(self, root):
        python = self.which("python")
        if python is None:
            return "not found on PATH; the installed profiles run `python scripts/...`, so install Python 3.11+"
        completed, error = self.readiness._query(self.query, [python, "--version"], str(root))
        token = self.readiness._version_token(completed.stdout) if completed else None
        parts = (token or "").lstrip("v").split(".")
        try:
            version = (int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            return f"found at {python}; version could not be read ({error or 'unrecognized output'})"
        if version < MINIMUM_PYTHON:
            return f"{token} at {python} is older than 3.11; the installed profiles need Python 3.11+"
        return None

    def report(self, found):
        self.emit("Prerequisites:")
        self.emit(f"  git: {found.git or 'NOT FOUND on PATH'}")
        copilot_status = found.copilot or "NOT FOUND on PATH; optional for installed-project readiness"
        self.emit(
            "  Copilot CLI (readiness check only; VS Code Copilot Chat is the primary path): "
            + copilot_status
        )
        self.emit(f"  python (running specfactory): {sys.version.split()[0]}")
        self.emit(
            "  python (on PATH for the installed profiles): "
            + (found.python_note or "ok")
        )
        self.emit(f"  uv: {found.uv or 'not found (only needed to install the Specify CLI)'}")
        if found.cli_missing:
            self.emit("  Specify CLI: NOT FOUND on PATH")
        else:
            self.emit(f"  Specify CLI: [{found.specify_result.status}] {found.specify_result.finding}")
        if found.speckit_result is not None:
            self.emit(
                f"  Spec Kit + Copilot integration: [{found.speckit_result.status}] "
                f"{found.speckit_result.finding}"
            )
        elif found.cli_missing:
            self.emit("  Spec Kit + Copilot integration: not checked (Specify CLI unavailable)")
        else:
            self.emit("  Spec Kit + Copilot integration: not checked (Specify CLI unusable)")
        if self.workspace:
            self.emit("  Child repositories:")
            for repository in self.workspace_repositories:
                state = "clean" if repository["clean"] else f"dirty ({repository['dirty_paths']} path(s))"
                head = repository["head"] or "no commits"
                self.emit(
                    f"    {repository['path']} (branch {repository['branch']}; HEAD {head}; {state})"
                )

    def blocker(self, found):
        """Return text explaining why no approved action can fix the current state, else None."""
        if found.git is None:
            return "git was not found on PATH. Install Git, then re-run."
        if found.specify_broken:
            return (
                f"the Specify CLI is present but unusable ({found.specify_result.finding}). "
                "Repair or reinstall it yourself, then re-run."
            )
        if found.cli_missing and found.uv is None:
            return (
                "the Specify CLI is missing and uv is not available to install it. Install uv "
                f"({UV_INSTALL_URL}) or install the Specify CLI yourself, then re-run."
            )
        if found.speckit_result is not None and not found.spec_kit_ok:
            if self.workspace:
                return (
                    "the workspace root has no valid Spec Kit Copilot integration "
                    f"({found.speckit_result.finding}). Initialize Spec Kit interactively at the "
                    "workspace root with `specify init --here --integration copilot`, review its "
                    "merge prompt, then re-run; Spec Factory never uses --force or initializes "
                    "child repositories."
                )
            return (
                "Spec Kit is absent, incomplete or lacks a valid Copilot integration "
                f"({found.speckit_result.finding}). Automatic initialization is unavailable "
                "without --force in a Git project; review Specify's existing-project guidance, "
                "initialize or repair it manually, then re-run."
            )
        return None

    # preview ------------------------------------------------------------------------------------

    def proposed_actions(self, found):
        actions = []
        if found.cli_missing:
            actions.append(("install-specify-cli", self._cli_command(found)))
        actions.append(("install-software-factory", None))
        return actions

    def _cli_command(self, found):
        return [found.uv or "uv", "tool", "install", SPECIFY_PACKAGE]

    def preview(self, found):
        self.emit(f"Target: {self.target}")
        self.report(found)
        self.emit("Proposed actions (each needs its own approval; nothing has been changed):")
        for index, (action, command) in enumerate(self.proposed_actions(found), start=1):
            self.emit(f"  {index}. {self._describe(action, command)}")
        if found.ready:
            return self.preview_engine()
        self.emit("Software Factory plan: the per-path plan is shown after the prerequisites pass.")
        self.emit("  It will create these files if absent and never overwrite an existing file:")
        readiness = self.readiness
        paths = (*readiness.MANAGED_FILES, readiness.MANIFEST_PATH)
        if self.workspace:
            paths += (readiness.WORKSPACE_MANIFEST_PATH,)
        for path in paths:
            self.emit(f"    {path}")
        if self.workspace:
            self.emit("  Child repositories are inspected only; no child files or Git metadata are changed.")
        else:
            self.emit(f"  and append '/{readiness.PREFERENCES_PATH}' to the project's .git/info/exclude.")
        return None

    def preview_engine(self):
        """Show the installer's own read-only plan (its --dry-run) and return its exit status."""
        plan = self.run_engine(dry_run=True)
        self.emit("Software Factory plan (from the installer; dry run):")
        self.emit(plan.stdout.rstrip("\n") if plan.stdout else "(no output)")
        if plan.stderr:
            print(plan.stderr.rstrip("\n"), file=sys.stderr)
        return plan.returncode

    def _describe(self, action, command):
        if action == "install-specify-cli":
            return (
                f"Install the Specify CLI: `{' '.join(command)}`. Environment-level change on this "
                "machine (uv tool environment); installs the official PyPI `specify-cli` package "
                "from uv's configured index; no project file changes. After rechecking, if Spec "
                "Kit setup is needed, review Specify's existing-project guidance and initialize "
                "manually; onboarding will not run a command that requires `--force`."
            )
        if self.workspace:
            return (
                "Install the Software Factory files once at this Gitless workspace root, create a "
                "workspace repository index, leave child repositories unchanged, then run readiness."
            )
        return (
            "Install the Software Factory files with the bundled installer: creates the managed "
            "files and a manifest that do not yet exist, appends one line to .git/info/exclude, "
            "never overwrites, then runs readiness."
        )

    # execution ----------------------------------------------------------------------------------

    def engine_arguments(self, dry_run):
        engine = bundle.asset_root() / "scripts" / "install_factory.py"
        arguments = [sys.executable, "-B", str(engine), "--target", self.target]
        if self.workspace:
            arguments.append("--workspace")
        if dry_run:
            arguments.append("--dry-run")
        return arguments

    def _child_environment(self):
        env = {
            key: value
            for key, value in self.environment.items()
            if not key.upper().startswith("FACTORY_") and key.upper() != "PYTHONPATH"
        }
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env

    def run_engine(self, dry_run):
        return self.script(self.engine_arguments(dry_run), self.target, self._child_environment())

    def approve(self, question):
        try:
            answer = self.input_fn(f"{question} [y/N]: ")
        except (EOFError, KeyboardInterrupt):
            answer = ""
        return str(answer).strip().lower() in ("y", "yes")

    def stop(self, code, text):
        self.emit(text)
        if self.changes:
            self.emit("Changes made so far: " + "; ".join(self.changes) + ".")
        else:
            self.emit("No project changes were made.")
        return code

    def run_setup(self, label, command, cwd):
        if any(part.lower().startswith("--force") for part in command):
            raise ValueError("setup commands must never use --force")
        self.emit(f"Running: {' '.join(command)}")
        try:
            status = self.setup(command, cwd)
        except OSError as error:
            self.emit(f"{label} failed to start ({type(error).__name__}).")
            return False
        if status != 0:
            self.emit(f"{label} failed (exit status {status}).")
            return False
        return True

    def setup_prerequisites(self, found):
        """Ask for and run each needed setup action; return (found, None) or (found, exit code)."""
        if found.cli_missing:
            command = self._cli_command(found)
            self.emit(f"Action 1: {self._describe('install-specify-cli', command)}")
            if not self.approve("Install the Specify CLI now?"):
                return found, self.stop(EXIT_REFUSED, "Declined. The Specify CLI was not installed.")
            if not self.run_setup("Specify CLI installation", command, None):
                return found, self.stop(EXIT_INCOMPLETE, "Stopped: the Specify CLI installation did not succeed.")
            self.changes.append("installed the Specify CLI")
            found = self.inspect()
            self.report(found)
            if found.cli_missing:
                return found, self.stop(
                    EXIT_INCOMPLETE,
                    "Stopped: the Specify CLI is still not on PATH. Run `uv tool update-shell`, "
                    "restart the terminal, then re-run.",
                )
            blocked = self.blocker(found)
            if blocked:
                return found, self.stop(EXIT_REFUSED, f"Stopped: {blocked}")
        return found, None

    # install and report -------------------------------------------------------------------------

    def install(self):
        result = self.run_engine(dry_run=False)
        if result.stdout:
            self.emit(result.stdout.rstrip("\n"))
        if result.stderr:
            print(result.stderr.rstrip("\n"), file=sys.stderr)
        code = result.returncode
        verdict, limitations = self._readiness_lines(result.stdout or "")
        self.emit("Result:")
        if code == EXIT_OK:
            self.emit("  Software Factory is installed.")
        elif code == EXIT_NOT_READY:
            self.emit("  Software Factory files are installed, but readiness is NOT READY (nothing was rolled back).")
        elif code == EXIT_INCOMPLETE:
            self.emit("  The installation is INCOMPLETE. See the installer messages above and re-run to finish.")
        else:
            self.emit("  The installer refused to run; nothing was written.")
        if code in (EXIT_OK, EXIT_NOT_READY):
            self.emit(f"  Readiness verdict: {verdict or 'not reported'}")
            if limitations:
                self.emit(f"  Limitations: {limitations}")
            if self.workspace:
                self.emit("  The Gitless workspace root remains Gitless; child repositories were not modified.")
                self.emit("  Review current service state with `python scripts/check_factory_readiness.py`.")
                self.emit("  Model preferences are not prompted for in workspace mode.")
            else:
                self.emit("  Installed files are uncommitted; review them with `git status`.")
                self.model_guidance()
            self.vscode_guidance()
        return code

    @staticmethod
    def _readiness_lines(text):
        verdict = limitations = None
        for line in text.splitlines():
            if line.startswith("Verdict:"):
                verdict = line[len("Verdict:"):].strip()
            elif line.startswith("Limitations:"):
                limitations = line[len("Limitations:"):].strip()
        return verdict, limitations

    def model_guidance(self):
        models = bundle.load_script("specialist_models")
        self.emit("Model setup (nothing is configured unless you choose it; no model IDs are bundled):")
        for name, mapping in models.PRESETS.items():
            roles = ", ".join(f"{role}={tier}" for role, tier in mapping.items())
            marker = " (helper default)" if name == models.DEFAULT_PRESET else ""
            self.emit(f"  {name}{marker}: {roles}")
        self.emit(f"  Tiers: {', '.join(models.TIERS)}. 'quality-first' uses the 'quality' tier for every role and may cost more.")
        self.emit("  Each tier needs a model ID you choose from the models available to you.")
        preferences = Path(self.target) / self.readiness.PREFERENCES_PATH
        if preferences.exists():
            self.emit("  Existing preferences were found and are left unchanged; review them with")
            self.emit("  `python scripts/specialist_models.py status`.")
            return
        if self.interactive:
            self._configure_models(models)
        else:
            self.emit("  Configure later: `python scripts/specialist_models.py set-preset <preset>` and")
            self.emit("  `python scripts/specialist_models.py set-tier <tier> <model-id>`.")

    def _configure_models(self, models):
        choice = self._ask_text(
            f"Preset to configure now ({', '.join(models.PRESETS)}; Enter to skip)"
        )
        if not choice:
            self.emit("  Model setup skipped. Until configured, Factory Lead will ask you which model to use.")
            return
        if choice not in models.PRESETS:
            self.emit(f"  '{choice}' is not a preset; model setup skipped.")
            return
        needed = []
        for tier in models.TIERS:
            if tier in models.PRESETS[choice].values():
                needed.append(tier)
        chosen = {}
        for tier in needed:
            value = self._ask_text(
                f"Model ID or display name for tier '{tier}' (one available to you; Enter to leave unset)"
            )
            if not value:
                continue
            if models.MODEL_ID_PATTERN.fullmatch(value) is None:
                self.emit(f"  '{value}' is not a valid model ID; it was ignored.")
                continue
            chosen[tier] = value
        if not chosen:
            self.emit("  No model IDs entered; preferences were not created.")
            return
        listing = ", ".join(f"{tier}={value}" for tier, value in chosen.items())
        if not self.approve(
            f"Write preset '{choice}' and {listing} to .factory/model-preferences.json "
            "(local, excluded from Git)?"
        ):
            self.emit("  Declined; preferences were not created.")
            return
        helper = str(Path(self.target) / "scripts" / "specialist_models.py")
        commands = [["set-preset", choice]] + [["set-tier", tier, value] for tier, value in chosen.items()]
        for command in commands:
            outcome = self.script([sys.executable, "-B", helper, *command], self.target, self._child_environment())
            if outcome.returncode != 0:
                self.emit(f"  `{' '.join(command[:2])}` failed: {(outcome.stderr or outcome.stdout or '').strip()}")
                return
        self.emit("  Preferences written. Check them with `python scripts/specialist_models.py status`.")

    def _ask_text(self, question):
        try:
            return str(self.input_fn(f"{question}: ")).strip()
        except (EOFError, KeyboardInterrupt):
            return ""

    def vscode_guidance(self):
        self.emit("Next steps in VS Code:")
        label = "workspace root" if self.workspace else "project folder"
        self.emit(f"  1. Open this {label} in VS Code (`code \"{self.target}\"`).")
        self.emit("  2. Open Copilot Chat, open the agent picker and select 'Factory Lead'.")
        self.emit("  3. Ask it to work on a feature; it stops for your approval of each specification and plan.")
        self.emit("  Not verified: that Chat lists Factory Lead and its delegation work in your project; no Copilot session was run.")


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="specfactory",
        description="Guided installation of the interactive Software Factory.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser(
        "init",
        help="install into the project in the current directory (or --target)",
        description="Inspect the project, show every planned change, then install after separate approvals.",
    )
    init.add_argument("--target", help="project root (default: current directory)")
    init.add_argument(
        "--workspace", action="store_true",
        help="install once at a Gitless workspace root containing multiple child Git repositories",
    )
    init.add_argument("--dry-run", action="store_true", help="read-only preview; no prompts, setup or writes")
    init.add_argument(
        "--non-interactive", action="store_true",
        help="never prompt; preview only unless --yes is also given",
    )
    init.add_argument(
        "--yes", action="store_true",
        help="with --non-interactive: authorize only the Software Factory install when prerequisites pass",
    )
    return parser


def _resolve_target(given, cwd):
    path = Path(given).expanduser() if given else Path(cwd)
    if not path.is_dir():
        return None, f"Refused: the target must be an existing directory: {path}"
    return os.path.realpath(os.path.abspath(path)), None


def main(
    argv=None, *, stdin=None, stdout=None, environment=None, which=None, query_runner=None,
    setup_runner=None, script_runner=None, input_fn=None, interactive=None, cwd=None,
):
    stdout = stdout or sys.stdout
    environment = os.environ if environment is None else environment
    parser = _build_parser()
    try:
        arguments = parser.parse_args(argv)
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else EXIT_REFUSED
    if arguments.yes and not arguments.non_interactive:
        print("error: --yes is accepted only together with --non-interactive.", file=sys.stderr)
        return EXIT_REFUSED
    if arguments.yes and arguments.dry_run:
        print("error: --yes cannot be combined with --dry-run.", file=sys.stderr)
        return EXIT_REFUSED

    def emit(text):
        print(text, file=stdout)

    missing = bundle.missing_assets()
    if missing:
        emit("Refused: this installation of specfactory is missing bundled files: " + ", ".join(missing))
        return EXIT_REFUSED

    target, problem = _resolve_target(arguments.target, cwd or os.getcwd())
    if problem:
        emit(problem)
        return EXIT_REFUSED

    readiness = bundle.load_script("check_factory_readiness")
    which = which or readiness.make_path_lookup(environment, absolute_only=True)
    query = query_runner or _default_query
    if interactive is None:
        stream = stdin or sys.stdin
        interactive = bool(getattr(stream, "isatty", lambda: False)())
    interactive = interactive and not arguments.non_interactive

    onboarding = _Onboarding(
        target, stdout=stdout, input_fn=input_fn or input, interactive=interactive,
        environment=environment, which=which, query=query,
        setup=setup_runner or _default_setup, script=script_runner or _default_script,
        workspace=arguments.workspace,
    )

    root_problem = _root_problem(onboarding, target, workspace=arguments.workspace)
    if root_problem:
        emit(f"Refused: {root_problem} No project changes were made.")
        return EXIT_REFUSED

    found = onboarding.inspect()
    # Prompts happen only on a real terminal; --yes (with --non-interactive) is the only other way to apply.
    preview_only = arguments.dry_run or not (interactive or (arguments.non_interactive and arguments.yes))
    plan_shown = found.ready
    engine_code = onboarding.preview(found)
    blocker = onboarding.blocker(found)

    if preview_only:
        if arguments.dry_run:
            emit("DRY RUN: nothing was changed; no setup command and no installer run was started.")
        elif arguments.non_interactive:
            emit("Preview only: nothing was changed. To apply, re-run with --non-interactive --yes.")
        else:
            emit("Preview only: input is not a terminal, so nothing was asked or changed. "
                 "Run interactively to approve changes, or use --non-interactive --yes.")
        if blocker:
            emit(f"Not ready to install: {blocker}")
            return EXIT_REFUSED
        if not found.ready:
            emit("Not ready to install: the setup actions above are needed first (run interactively to approve them).")
            return EXIT_REFUSED
        return engine_code if engine_code else EXIT_OK

    if arguments.non_interactive:
        # --yes authorizes only the Software Factory install, never Specify CLI or Spec Kit setup.
        if blocker or not found.ready:
            return onboarding.stop(
                EXIT_REFUSED,
                f"Refused: {blocker or 'Spec Kit setup is needed.'}\n"
                "Prerequisites must already pass; install the Specify CLI if needed and complete "
                "Spec Kit setup manually, then re-run.",
            )
        if engine_code not in (0, None):
            return engine_code
        return onboarding.install()

    if blocker:
        return onboarding.stop(EXIT_REFUSED, f"Stopped: {blocker}")
    found, code = onboarding.setup_prerequisites(found)
    if code is not None:
        return code
    if not plan_shown:
        engine_code = onboarding.preview_engine()
    if engine_code not in (0, None):
        return engine_code
    if not onboarding.approve("Install the Software Factory files into this project now?"):
        return onboarding.stop(EXIT_REFUSED, "Declined. Software Factory was not installed.")
    return onboarding.install()


def _root_problem(onboarding, target, *, workspace=False):
    if onboarding.which("git") is None:
        return "git was not found on PATH."
    if workspace:
        repositories, error = bundle.load_script("check_factory_readiness").discover_workspace_repositories(
            target, onboarding.query
        )
        if error:
            return f"workspace mode requires a Gitless root and at least two independent child Git repositories ({error})."
        onboarding.workspace_repositories = repositories
        return None
    completed, error = onboarding.readiness._query(
        onboarding.query, ["git", "-C", target, "rev-parse", "--show-toplevel"], target
    )
    if error:
        return f"{target} is not inside a Git working tree ({error}); run `git init` first or use --target."
    top = completed.stdout.strip()
    try:
        same = os.path.samefile(top, target)
    except OSError:
        same = False
    if not same:
        return f"{target} is not the Git project root (the root is {top}); use --target with the root."
    return None
