"""Read-only readiness check for interactive Spec Kit and specialist-team use."""

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

PASS = "PASS"
FAIL = "FAIL"
NOT_VERIFIED = "NOT VERIFIED"
INFO = "INFO"

COMPATIBILITY = {
    "specify": {"supported": {"1.0.6"}, "incompatible": set()},
    "copilot": {"supported": {"1.0.114"}, "incompatible": set()},
}
COMMAND_TIMEOUT_SECONDS = 15
POLICY_VARIABLE = "FACTORY_POLICY_PATH"
ROOT_VARIABLE = "FACTORY_REPOSITORY_ROOT"
VERDICT_NOT_READY = "not ready"
VERDICT_LIMITED = "ready with limitations"
LIMITATIONS = "authentication, live dispatch, effective sandbox enforcement"
EXECUTABLE_SUFFIXES = ("", ".exe", ".cmd", ".bat", ".com", ".ps1")

SPECKIT_FILES = (
    ".specify/memory/constitution.md",
    ".specify/templates/spec-template.md",
    ".specify/templates/plan-template.md",
    ".specify/templates/tasks-template.md",
    ".specify/workflows/speckit/workflow.yml",
)

MANIFEST_PATH = ".github/software-factory/install-manifest.json"
PREFERENCES_PATH = ".factory/model-preferences.json"
MANAGED_FILES = (
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
_FINGERPRINT_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")


def fingerprint(data):
    return "sha256:" + hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


class CheckResult:
    def __init__(self, id, status, finding, expected=None, next_step=None):
        self.id = id
        self.status = status
        self.finding = finding
        self.expected = expected
        self.next_step = next_step


def default_runner(arguments, cwd, timeout):
    arguments = list(arguments)
    environment = dict(os.environ)
    environment["PATH"] = os.pathsep.join(
        directory for directory in environment.get("PATH", "").split(os.pathsep)
        if directory and Path(directory).is_absolute()
    )
    if arguments and arguments[0] in ("git", "specify"):
        executable = make_path_lookup(environment)(arguments[0])
        if executable is None:
            raise FileNotFoundError(f"{arguments[0]} executable not found on PATH")
        arguments[0] = str(Path(executable).resolve())
    environment = {
        key: value for key, value in environment.items()
        if key.upper() not in {
            "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
            "GIT_OBJECT_DIRECTORY", "GIT_NAMESPACE",
        }
    }
    return subprocess.run(
        arguments,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        shell=False,
        check=False,
        timeout=timeout,
    )


def make_path_lookup(environment, absolute_only=False):
    """Return which(name) searching PATH from the given mapping (never runs anything)."""

    def lookup(name):
        directories = [d for d in str(environment.get("PATH", "")).split(os.pathsep) if d]
        for directory in directories:
            if absolute_only and not Path(directory).is_absolute():
                continue
            for suffix in EXECUTABLE_SUFFIXES:
                candidate = Path(directory) / f"{name}{suffix}"
                try:
                    if candidate.is_file():
                        return str(candidate)
                except OSError:
                    continue
        return None

    return lookup


_EXACT_VERSION = re.compile(r"\d+\.\d+\.\d+")
_LOOSE_VERSION = re.compile(r"v?\d+\.\d+\S*")


def _version_token(text):
    """Return the first version-looking token (may be four-part or pre-release), or None."""
    for token in (text or "").split():
        if _LOOSE_VERSION.fullmatch(token):
            return token
    return None


def _parse_version(text):
    """Return the version only when the first version-looking token is exactly x.y.z."""
    token = _version_token(text)
    if token is not None and _EXACT_VERSION.fullmatch(token):
        return token
    return None


def _is_file(path):
    try:
        return path.is_file()
    except (OSError, ValueError):
        return False


def _is_dir(path):
    try:
        return path.is_dir()
    except (OSError, ValueError):
        return False


def _inside(root, path):
    """True when path resolves to a location inside root (resolved)."""
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError, RuntimeError):
        return False
    return True


def _classify(tool, version):
    table = COMPATIBILITY[tool]
    if version in table["incompatible"]:
        return FAIL
    if version in table["supported"]:
        return PASS
    return NOT_VERIFIED


def _query(runner, arguments, cwd):
    """Run a fixed local query; return (completed, error_text)."""
    try:
        completed = runner(arguments, cwd=cwd, timeout=COMMAND_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return None, f"timed out after {COMMAND_TIMEOUT_SECONDS} seconds"
    except OSError as error:
        return None, f"could not run: {type(error).__name__}"
    if completed.returncode != 0:
        return None, f"exited with status {completed.returncode}"
    return completed, None


def _query_status(runner, arguments, cwd):
    """Run a fixed local query; return (returncode, error_text) without treating nonzero as an error."""
    try:
        completed = runner(arguments, cwd=cwd, timeout=COMMAND_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return None, f"timed out after {COMMAND_TIMEOUT_SECONDS} seconds"
    except OSError as error:
        return None, f"could not run: {type(error).__name__}"
    return completed.returncode, None


def check_specify(root, runner, which):
    executable = which("specify")
    supported = ", ".join(sorted(COMPATIBILITY["specify"]["supported"]))
    expected = f"specify on PATH at a supported version ({supported})"
    if executable is None:
        return CheckResult(
            "tool-specify", FAIL, "specify executable not found on PATH", expected,
            "install the Specify CLI",
        ), None
    completed, error = _query(runner, [executable, "--version"], root)
    if error:
        return CheckResult(
            "tool-specify", FAIL, f"specify --version {error}", expected,
            "repair the Specify CLI installation",
        ), executable
    version = _parse_version(completed.stdout)
    loose = _version_token(completed.stdout)
    if version is None and loose is not None:
        return CheckResult(
            "tool-specify", NOT_VERIFIED,
            f"Specify CLI version '{loose}' is not an exact x.y.z version; "
            "compatibility not established",
            expected, "use a supported version or confirm compatibility manually",
        ), executable
    if version is None:
        return CheckResult(
            "tool-specify", FAIL, "specify --version output has no parseable version",
            expected, "repair the Specify CLI installation",
        ), executable
    status = _classify("specify", version)
    if status == PASS:
        return CheckResult("tool-specify", PASS, f"Specify CLI {version} (supported)"), executable
    if status == FAIL:
        return CheckResult(
            "tool-specify", FAIL, f"Specify CLI {version} is known incompatible", expected,
            "install a supported version",
        ), executable
    return CheckResult(
        "tool-specify", NOT_VERIFIED,
        f"Specify CLI {version} is not in the supported set; compatibility not established",
        expected, "use a supported version or confirm compatibility manually",
    ), executable


def check_copilot(which, installed=False):
    supported = ", ".join(sorted(COMPATIBILITY["copilot"]["supported"]))
    found = which("copilot") or which("copilot.ps1")
    if found is None:
        if installed:
            return CheckResult(
                "tool-copilot", INFO,
                "copilot executable not found; use VS Code Copilot Chat (Copilot CLI is optional)",
                "Copilot CLI only when using its terminal workflow",
                "use VS Code Copilot Chat; install the Copilot CLI only if you need it",
            )
        return CheckResult(
            "tool-copilot", FAIL, "copilot executable not found on PATH",
            f"copilot on PATH (documented supported version {supported})",
            "install the Copilot CLI",
        )
    return CheckResult(
        "tool-copilot", NOT_VERIFIED,
        "copilot executable found; version not checked (never executed)",
        f"a version documented as supported ({supported})",
        "confirm the Copilot CLI version manually; not treated as a failure",
    )


def _speckit_findings(root, runner, specify_executable, require_pointer=True):
    findings = []
    for relative in SPECKIT_FILES:
        if not _is_file(root / relative):
            findings.append(f"{relative}: missing")

    feature_path = root / ".specify" / "feature.json"
    if _is_file(feature_path):
        try:
            data = json.loads(feature_path.read_text(encoding="utf-8"))
            directory = data.get("feature_directory") if isinstance(data, dict) else None
        except (OSError, UnicodeError, ValueError):
            directory = None
        if not isinstance(directory, str) or not directory.strip():
            findings.append(".specify/feature.json: 'feature_directory' must be a non-empty string")
        else:
            feature_directory = root / directory.replace("\\", "/")
            if not _inside(root, feature_directory):
                findings.append(".specify/feature.json: feature_directory is outside the repository")
            elif not _is_dir(feature_directory):
                findings.append(".specify/feature.json: feature_directory does not exist")
    else:
        if require_pointer:
            findings.append(".specify/feature.json: missing")

    if specify_executable is None:
        findings.append("specify integration status: not queried (specify unavailable)")
        return findings
    completed, error = _query(
        runner, [specify_executable, "integration", "status", "--json"], root
    )
    if error:
        findings.append(f"specify integration status --json {error}")
        return findings
    try:
        status = json.loads(completed.stdout)
    except (ValueError, TypeError):
        status = None
    if not isinstance(status, dict):
        findings.append("specify integration status: output is not a valid JSON object")
        return findings
    if status.get("status") != "ok":
        findings.append("specify integration status: status is not ok")
    installed = status.get("installed_integrations")
    if (
        status.get("default_integration") != "copilot"
        or not isinstance(installed, list)
        or "copilot" not in installed
    ):
        findings.append("specify integration status: Copilot integration is not registered")
    for key in (
        "missing_managed_files",
        "modified_managed_files",
        "invalid_manifest_paths",
        "unchecked_manifests",
    ):
        value = status.get(key)
        if type(value) is not int or value != 0:
            findings.append(f"specify integration status: {key} is not the integer 0")
    if status.get("findings") != []:
        findings.append("specify integration status: reports managed-file findings")
    return findings


def check_speckit(root, runner, specify_executable, require_pointer=True):
    findings = _speckit_findings(root, runner, specify_executable, require_pointer)
    if findings:
        return CheckResult(
            "speckit-config", FAIL, "; ".join(findings),
            "Spec Kit memory, templates, feature pointer, workflow and Copilot integration intact",
            "restore the listed items (for example with specify integration commands)",
        )
    return CheckResult("speckit-config", PASS, "Spec Kit configuration is intact")


def check_profiles(root):
    expected = "five valid specialist profiles and the factory-handoff skill"
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        try:
            validator = importlib.import_module("validate_specialist_profiles")
        finally:
            sys.path.pop(0)
    except Exception as error:  # broken validator module
        return _validator_broken(expected, error)
    try:
        return _profile_result(root, validator, expected)
    except AttributeError as error:
        return _validator_broken(expected, error)


def _validator_broken(expected, error):
    return CheckResult(
        "specialist-profiles", FAIL,
        "scripts/validate_specialist_profiles.py is missing, broken, or lacks the expected "
        f"interface ({type(error).__name__}: {error}); profiles were not validated",
        expected, "restore or repair scripts/validate_specialist_profiles.py",
    )


def _profile_result(root, validator, expected):
    findings = list(validator.validate_profiles(root))
    skill = ".github/skills/factory-handoff/SKILL.md"
    skill_path = root / skill
    if not _is_file(skill_path):
        findings.append(f"{skill}: missing")
    else:
        sink = []
        try:
            metadata = validator._frontmatter(
                skill_path.read_text(encoding="utf-8"), skill, sink
            )
        except (OSError, UnicodeError):
            metadata = None
            sink.append(f"{skill}: unable to read")
        findings.extend(sink)
        if metadata is not None:
            for field in ("name", "description"):
                value = metadata.get(field)
                if not isinstance(value, str) or not value.strip():
                    findings.append(f"{skill}: '{field}' must be a non-empty string")
    if findings:
        return CheckResult(
            "specialist-profiles", FAIL, "; ".join(findings), expected,
            "fix the listed profile or skill files",
        )
    return CheckResult("specialist-profiles", PASS, "five specialist profiles and skill are valid")


def _managed_file_problem(root, relative, recorded):
    path = root / relative
    try:
        regular = _is_file(path) and not path.is_symlink() and _inside(root, path)
    except OSError:
        regular = False
    if not regular:
        return f"{relative}: missing or not a regular file"
    try:
        actual = fingerprint(path.read_bytes())
    except OSError:
        return f"{relative}: unreadable"
    if actual != recorded:
        return f"{relative}: differs from the installed fingerprint"
    return None


def check_install_manifest(root, runner):
    expected = (
        "an intact install manifest, unmodified managed files, and a locally ignored "
        "preferences file"
    )
    try:
        manifest = json.loads((root / MANIFEST_PATH).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        manifest = None
    files = manifest.get("files") if isinstance(manifest, dict) else None
    version = manifest.get("version") if isinstance(manifest, dict) else None
    if (
        type(version) is not int
        or version != 1
        or not isinstance(files, dict)
        or set(files) != set(MANAGED_FILES)
        or any(
            not isinstance(value, str) or not _FINGERPRINT_PATTERN.fullmatch(value)
            for value in files.values()
        )
    ):
        return CheckResult(
            "install-manifest", FAIL, f"{MANIFEST_PATH}: not a valid install manifest", expected,
            "restore the manifest or re-run the installer",
        )

    problems = [
        problem
        for problem in (_managed_file_problem(root, relative, files[relative]) for relative in MANAGED_FILES)
        if problem
    ]
    code, error = _query_status(
        runner,
        ["git", "-C", str(root), "check-ignore", "-q", "--no-index", PREFERENCES_PATH],
        root,
    )
    ignore_problem = None
    if code == 1:
        ignore_problem = f"{PREFERENCES_PATH} is not ignored by Git"
    elif code != 0:
        detail = error or f"git check-ignore exited with status {code}"
        ignore_problem = f"{PREFERENCES_PATH}: ignore state could not be verified ({detail})"

    if problems:
        steps = [
            "restore the file from the Software Factory source, or move your edit elsewhere, "
            "then re-run the installer"
        ]
        if ignore_problem:
            steps.append("re-run the installer to add the local exclude")
        return CheckResult(
            "install-manifest", FAIL, "; ".join(problems + ([ignore_problem] if ignore_problem else [])),
            expected, "; ".join(steps),
        )
    if ignore_problem:
        return CheckResult(
            "install-manifest", NOT_VERIFIED, ignore_problem, expected,
            "re-run the installer to add the local exclude",
        )
    return CheckResult(
        "install-manifest", PASS,
        f"{len(MANAGED_FILES)} managed files match the install manifest; "
        f"{PREFERENCES_PATH} is ignored",
    )


_SCRIPT_EXTENSIONS = r"(?:ps1|sh|py|cmd|bat)"
_QUOTED_SCRIPT = re.compile(r"""(["'])([^"'\r\n]+?\.""" + _SCRIPT_EXTENSIONS + r""")\1""", re.IGNORECASE)
_SCRIPT_PATTERN = re.compile(r"[\w./\\-]+\." + _SCRIPT_EXTENSIONS, re.IGNORECASE)
_HOOK_COMMAND_KEYS = ("powershell", "bash", "command", "windows", "linux", "osx")


def _script_reference(command):
    quoted = _QUOTED_SCRIPT.search(command)
    if quoted:
        return quoted.group(2).strip()
    match = _SCRIPT_PATTERN.search(command)
    return match.group(0) if match else None


def _hook_defects(root):
    """Return (declared, defects, script_texts, notes)."""
    hook_dir = root / ".github" / "hooks"
    try:
        files = sorted(hook_dir.glob("*.json")) if hook_dir.is_dir() else []
    except OSError:
        files = []
    defects, texts, notes = [], [], []
    for hook_file in files:
        relative = f".github/hooks/{hook_file.name}"
        try:
            data = json.loads(hook_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            defects.append(f"{relative}: malformed JSON")
            continue
        hooks = data.get("hooks") if isinstance(data, dict) else None
        if not isinstance(hooks, dict):
            defects.append(f"{relative}: missing 'hooks' structure")
            continue
        for event, entries in hooks.items():
            if not isinstance(entries, list):
                defects.append(f"{relative}: hooks.{event} must be a list")
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    defects.append(f"{relative}: hooks.{event} entry must be an object")
                    continue
                cwd = entry.get("cwd") if isinstance(entry.get("cwd"), str) else "."
                cwd_path = root / cwd.replace("\\", "/")
                cwd_inside = _inside(root, cwd_path)
                if not cwd_inside:
                    defects.append(f"{relative}: hooks.{event} cwd '{cwd}' is outside the repository")
                for key in _HOOK_COMMAND_KEYS:
                    command = entry.get(key)
                    if not isinstance(command, str):
                        continue
                    reference = _script_reference(command)
                    if reference is None:
                        notes.append(
                            f"{relative}: hooks.{event}.{key} names no recognizable script; "
                            "its behavior was not inspected"
                        )
                        continue
                    script_relative = reference.replace("\\", "/")
                    if not cwd_inside:
                        continue
                    if Path(script_relative).is_absolute() or re.match(r"^[A-Za-z]:", script_relative):
                        defects.append(
                            f"{relative}: hooks.{event}.{key} script {script_relative} "
                            "is outside the repository"
                        )
                        continue
                    script = cwd_path / script_relative
                    if not _inside(root, script):
                        defects.append(
                            f"{relative}: hooks.{event}.{key} script {script_relative} "
                            "is outside the repository"
                        )
                        continue
                    if not _is_file(script):
                        defects.append(f"{relative}: referenced script {script_relative} is missing")
                        continue
                    try:
                        texts.append(script.read_text(encoding="utf-8", errors="replace"))
                    except OSError:
                        defects.append(f"{relative}: referenced script {script_relative} unreadable")
    return bool(files), defects, texts, notes


def check_hooks(root, environment):
    declared, defects, texts, notes = _hook_defects(root)
    if not declared:
        return CheckResult("interactive-hooks", PASS, "no repository hooks declared")
    if defects:
        return CheckResult(
            "interactive-hooks", FAIL, "; ".join(defects + notes),
            "well-formed hook declarations referencing existing scripts inside the repository",
            "fix the hook declaration or restore the script",
        )
    settings = root / ".github" / "copilot" / "settings.local.json"
    if _is_file(settings):
        try:
            data = json.loads(settings.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            data = None
        if not isinstance(data, dict):
            notes.append(
                "settings.local.json unreadable or not a JSON object; "
                "treated as hooks not disabled"
            )
        elif data.get("disableAllHooks") is True:
            return CheckResult(
                "interactive-hooks", NOT_VERIFIED,
                "; ".join(
                    ["hooks declared but locally disabled; whether Copilot honors this cannot "
                     "be established without a live session"] + notes
                ),
                "hooks either enforced or intentionally disabled, confirmed in a live session",
                "confirm hook behavior in a live Copilot session",
            )
    requires = any(POLICY_VARIABLE in t or ROOT_VARIABLE in t for t in texts)
    policy_value = environment.get(POLICY_VARIABLE)
    policy_ok = False
    if isinstance(policy_value, str) and policy_value:
        try:
            policy_ok = Path(policy_value).is_file()
        except OSError:
            policy_ok = False
    if requires and not policy_ok:
        return CheckResult(
            "interactive-hooks", FAIL,
            "; ".join(["hook is presumed active and requires a policy path that is not "
            "available in the current shell/launching environment (it would deny every tool "
            "request); this does not assume other Copilot environments are configured "
            "identically"] + notes),
            f"{POLICY_VARIABLE} set to an existing file in the environment that launches Copilot, "
            "or hooks locally disabled",
            f"set {POLICY_VARIABLE} and {ROOT_VARIABLE} when launching, or disable hooks locally",
        )
    return CheckResult(
        "interactive-hooks", NOT_VERIFIED,
        "; ".join(
            ["hook preconditions are met in this environment; effective permission decisions "
             "cannot be established without a live session"] + notes
        ),
        "hook enforcement confirmed in a live session",
        "confirm hook behavior in a live Copilot session",
    )


def check_policy(root):
    if (root / ".factory" / "policy.json").is_file():
        return CheckResult("runner-policy", INFO, ".factory/policy.json present")
    return CheckResult(
        "runner-policy", INFO,
        ".factory/policy.json absent (not required for interactive use)",
    )


def check_git(root):
    if (root / ".git").exists():
        return CheckResult("git-state", INFO, "Git repository detected; working tree not inspected")
    return CheckResult("git-state", INFO, "not a Git repository root")


def check_unverifiable():
    return CheckResult(
        "unverifiable", NOT_VERIFIED, LIMITATIONS,
        "confirmation in a live session",
        "verify authentication, dispatch and sandbox enforcement manually",
    )


def _guarded(check_id, function, *arguments):
    try:
        return function(*arguments)
    except Exception as error:  # noqa: BLE001 - a broken check must not hide the report
        return CheckResult(
            check_id, FAIL, f"check raised unexpected {type(error).__name__}",
            "the check completes without error", "investigate the readiness check or environment",
        )


def run_checks(root, runner=default_runner, environment=None, which=None):
    root = Path(root)
    environment = os.environ if environment is None else environment
    installed = _is_file(root / MANIFEST_PATH)
    which = which or make_path_lookup(environment, absolute_only=installed)
    try:
        specify_result, specify_executable = check_specify(root, runner, which)
    except Exception as error:  # noqa: BLE001
        specify_result = CheckResult(
            "tool-specify", FAIL, f"check raised unexpected {type(error).__name__}",
            "the check completes without error", "investigate the readiness check or environment",
        )
        specify_executable = None
    results = [
        specify_result,
        _guarded("tool-copilot", check_copilot, which, installed),
        _guarded(
            "speckit-config", check_speckit, root, runner, specify_executable, not installed
        ),
        _guarded("specialist-profiles", check_profiles, root),
    ]
    if installed:
        results.append(_guarded("install-manifest", check_install_manifest, root, runner))
    results += [
        _guarded("interactive-hooks", check_hooks, root, environment),
        _guarded("runner-policy", check_policy, root),
        _guarded("git-state", check_git, root),
        _guarded("unverifiable", check_unverifiable),
    ]
    return results


def verdict_for(results):
    if any(result.status == FAIL for result in results):
        return VERDICT_NOT_READY
    return VERDICT_LIMITED


def render(results):
    lines = []
    for result in results:
        lines.append(f"[{result.status}] {result.id}: {result.finding}")
        if result.status in (FAIL, NOT_VERIFIED):
            lines.append(f"    expected: {result.expected}")
            lines.append(f"    next step: {result.next_step}")
    verdict = verdict_for(results)
    lines.append(f"Verdict: {verdict}")
    if verdict == VERDICT_LIMITED:
        lines.append(f"Limitations: {LIMITATIONS}")
    return "\n".join(lines)


def main(argv=None, runner=default_runner, environment=None, which=None, stdout=None):
    stdout = stdout or sys.stdout
    parser = argparse.ArgumentParser(description="Check factory readiness (read-only).")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="checkout to inspect (defaults to the repository containing this script)",
    )
    try:
        arguments = parser.parse_args(argv)
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    root = arguments.root.expanduser()
    if not root.is_dir():
        print(f"error: --root must be an existing directory: {root}", file=sys.stderr)
        return 2
    results = run_checks(root, runner, environment, which)
    print(render(results), file=stdout)
    return 1 if verdict_for(results) == VERDICT_NOT_READY else 0


if __name__ == "__main__":
    raise SystemExit(main())
