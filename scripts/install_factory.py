"""Install the Software Factory specialist team into another Git repository."""

import argparse
import importlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

_DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(_DIRECTORY))
try:
    readiness = importlib.import_module("check_factory_readiness")
finally:
    sys.path.pop(0)

MANAGED_FILES = readiness.MANAGED_FILES
MANIFEST_PATH = readiness.MANIFEST_PATH
PREFERENCES_PATH = readiness.PREFERENCES_PATH
fingerprint = readiness.fingerprint

SOURCE_ROOT = _DIRECTORY.parent
EXCLUDE_ENTRY = "/" + PREFERENCES_PATH
READINESS_TIMEOUT_SECONDS = 120
_O_BINARY = getattr(os, "O_BINARY", 0)
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_RULE_PATTERN = re.compile(r"^(.+?):(\d+):(.*)$")
_REVISION_PATTERN = re.compile(r"[0-9a-f]{40,64}")
_BUNDLE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,63}")
BUNDLE_VERSION_FILE = SOURCE_ROOT / "BUNDLE_VERSION"
SCRUBBED_GIT_VARIABLES = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY", "GIT_NAMESPACE",
)

CONFLICT_STEPS = {
    "different content": (
        "compare it with the Software Factory source file, merge or move your version "
        "elsewhere, then re-run"
    ),
    "not a regular file": (
        "remove or rename it (symlinks and junctions are never followed), then re-run"
    ),
    "blocked path": (
        "remove or rename the blocking file, symlink or junction (never followed), then re-run"
    ),
}


class _Appeared(Exception):
    """A destination appeared between classification and publication."""


class _Blocked(Exception):
    """A leftover temporary path is not a regular file."""


def _before_publish(path):
    """Test seam: called immediately before each file is published."""


def _temp_name(path):
    directory, name = os.path.split(path)
    return os.path.join(directory, f".{name}.sf-tmp")


def _write_all(fd, data):
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _remove_leftover_temp(temp):
    try:
        mode = os.lstat(temp).st_mode
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(mode):
        raise _Blocked(temp)
    os.unlink(temp)
    return True


def _publish_fallback(path, data):
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | _O_NOFOLLOW | _O_BINARY
    try:
        fd = os.open(path, flags, 0o666)
    except FileExistsError:
        raise _Appeared(path) from None
    try:
        _write_all(fd, data)
    except BaseException:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


def _create_exclusive(path, data):
    """Create path with data; never overwrite anything that exists at path."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = _temp_name(path)
    _remove_leftover_temp(temp)
    fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | _O_BINARY, 0o666)
    try:
        _write_all(fd, data)
        _before_publish(Path(path))
        try:
            os.link(temp, path)
        except FileExistsError:
            raise _Appeared(path) from None
        except OSError:
            _publish_fallback(path, data)
    finally:
        try:
            os.unlink(temp)
        except OSError:
            pass


def _scrubbed(runner):
    """Wrap a runner so repository-selecting Git variables never reach its subprocess."""

    def run(arguments, cwd=None, timeout=None):
        saved = {name: os.environ.pop(name) for name in SCRUBBED_GIT_VARIABLES if name in os.environ}
        try:
            return runner(arguments, cwd=cwd, timeout=timeout)
        finally:
            os.environ.update(saved)

    return run


def _ancestor_problem(path):
    """Return None for a real directory, "absent" when missing, else a blocked-path reason."""
    try:
        mode = os.lstat(path).st_mode
    except FileNotFoundError:
        return "absent"
    except OSError as error:
        return f"blocked path ({type(error).__name__})"
    if stat.S_ISLNK(mode):
        return "blocked path (symlink)"
    if not stat.S_ISDIR(mode):
        return "blocked path (not a directory)"
    if os.path.normcase(os.path.realpath(path)) != os.path.normcase(path):
        return "blocked path (junction)"
    return None


def _classify(root, relative, matches):
    """Return (state, reason) for a path under the real target root without following links."""
    parts = relative.split("/")
    current = root
    for part in parts[:-1]:
        current = os.path.join(current, part)
        problem = _ancestor_problem(current)
        if problem == "absent":
            return "create", None
        if problem:
            return "conflict", problem
    path = os.path.join(current, parts[-1])
    try:
        mode = os.lstat(path).st_mode
    except FileNotFoundError:
        return _check_temp(path)
    except OSError as error:
        return "conflict", f"blocked path ({type(error).__name__})"
    if stat.S_ISLNK(mode):
        return "conflict", "not a regular file (symlink)"
    if not stat.S_ISREG(mode):
        return "conflict", "not a regular file"
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError:
        return "conflict", "not a regular file (unreadable)"
    return ("unchanged", None) if matches(data) else ("conflict", "different content")


def _check_temp(path):
    temp = _temp_name(path)
    try:
        mode = os.lstat(temp).st_mode
    except OSError:
        return "create", None
    if stat.S_ISREG(mode):
        return "create", None
    return "conflict", f"blocked path (temporary file {os.path.basename(temp)} is not a regular file)"


def _has_leftover_temp(root, relative):
    try:
        mode = os.lstat(_temp_name(os.path.join(root, *relative.split("/")))).st_mode
    except OSError:
        return False
    return stat.S_ISREG(mode)


def _git_status(runner, target, *arguments):
    """Run git in target; a nonzero exit status is returned, not treated as an error."""
    try:
        completed = runner(
            ["git", "-C", str(target), *arguments],
            cwd=str(target),
            timeout=readiness.COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return None, f"timed out after {readiness.COMMAND_TIMEOUT_SECONDS} seconds"
    except OSError as error:
        return None, f"could not run git ({type(error).__name__})"
    return completed, None


def _git_query(runner, target, *arguments):
    return readiness._query(runner, ["git", "-C", str(target), *arguments], str(target))


def _parse_rule(output):
    """Return (description, is_negation) from the first `check-ignore -v` line."""
    lines = (output or "").strip().splitlines()
    if not lines:
        return None, False
    match = _RULE_PATTERN.match(lines[0].split("\t", 1)[0])
    if not match:
        return None, False
    return match.group(0), match.group(3).startswith("!")


def _ignored(runner, target, path):
    """Return (ignored, rule, error); `ignored` is None when it cannot be established."""
    completed, error = _git_status(runner, target, "check-ignore", "-v", "--no-index", "--", path)
    if error:
        return None, None, error
    if completed.returncode == 0:
        rule, negation = _parse_rule(completed.stdout)
        # With -v git reports a negating ("!") match with exit 0 although the path is not ignored.
        return (not negation), rule, None
    if completed.returncode == 1:
        return False, None, None
    return None, None, f"git check-ignore exited with status {completed.returncode}"


def _ignored_managed_paths(runner, target):
    paths = [path for path in MANAGED_FILES]
    completed, error = _git_status(runner, target, "check-ignore", "-v", "--no-index", "--", *paths)
    if error or completed.returncode not in (0, 1):
        return None
    found = []
    for line in (completed.stdout or "").splitlines():
        meta, _, path = line.partition("\t")
        match = _RULE_PATTERN.match(meta)
        if match and not match.group(3).startswith("!") and path.strip() in MANAGED_FILES:
            found.append((path.strip(), match.group(0)))
    return found


def _plan_exclude(runner, target):
    ignored, rule, error = _ignored(runner, target, PREFERENCES_PATH)
    if error:
        return {"state": "cannot-establish", "message": error}
    if ignored:
        return {"state": "already-ignored", "rule": rule}
    if rule:
        return {
            "state": "cannot-establish",
            "message": f"{rule} negates {PREFERENCES_PATH}, so an exclude entry would not take effect",
        }
    completed, error = _git_query(runner, target, "rev-parse", "--git-path", "info/exclude")
    raw = completed.stdout.strip() if completed else ""
    if error or not raw:
        return {"state": "cannot-establish", "message": error or "git returned no exclude path"}
    path = os.path.normpath(os.path.join(str(target), raw))
    root, parts = _exclude_chain(str(target), path)
    creates = []
    current = root
    for part in parts:
        current = os.path.join(current, part)
        problem = _ancestor_problem(current)
        if problem == "absent":
            creates.append("info directory")
            break
        if problem:
            return {"state": "blocked", "file": path, "reason": problem}
    expected = os.path.join(root, *parts, os.path.basename(path))
    existing = b""
    try:
        mode = os.lstat(path).st_mode
    except FileNotFoundError:
        mode = None
        creates.append("file")
    except OSError as error:
        return {"state": "blocked", "file": path, "reason": f"blocked path ({type(error).__name__})"}
    if mode is not None:
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            kind = "symlink" if stat.S_ISLNK(mode) else "not a regular file"
            return {"state": "blocked", "file": path, "reason": f"blocked path ({kind})"}
        try:
            with open(path, "rb") as handle:
                existing = handle.read()
        except OSError:
            return {"state": "blocked", "file": path, "reason": "blocked path (unreadable)"}
        if _has_entry(existing):
            return {
                "state": "blocked", "file": path,
                "reason": f"{EXCLUDE_ENTRY} is present but does not take effect (a later rule overrides it)",
            }
    return {"state": "append", "file": path, "expected": expected, "creates": creates}


def _exclude_chain(target, path):
    """Return (root, parts): directories below root that lead to the exclude file."""
    info = os.path.dirname(path)
    try:
        relative = os.path.relpath(info, target)
    except ValueError:
        relative = None
    if relative is None or relative == os.curdir or relative.split(os.sep)[0] == os.pardir:
        return os.path.realpath(os.path.dirname(info)), [os.path.basename(info)]
    return target, relative.split(os.sep)


def _has_entry(content):
    text = content.decode("utf-8", errors="replace")
    # Leading whitespace is significant to Git; trailing whitespace (and CR) is not.
    return any(line.rstrip() == EXCLUDE_ENTRY for line in text.splitlines())


def _append_exclude(path, expected=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    expected = path if expected is None else expected
    if os.path.normcase(os.path.realpath(path)) != os.path.normcase(expected):
        raise OSError("the exclude path no longer resolves to the expected location")
    try:
        if not stat.S_ISREG(os.lstat(path).st_mode):
            raise OSError("the exclude path is a link or not a regular file")
    except FileNotFoundError:
        pass
    try:
        with open(path, "rb") as handle:
            existing = handle.read()
    except FileNotFoundError:
        existing = b""
    if _has_entry(existing):
        return
    payload = (b"\n" if existing and not existing.endswith(b"\n") else b"") + EXCLUDE_ENTRY.encode() + b"\n"
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | _O_NOFOLLOW | _O_BINARY, 0o666)
    with os.fdopen(fd, "ab") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _manifest_bytes(revision, files):
    document = {"version": 1, "source_revision": revision, "files": files}
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _source_revision(runner):
    # A packaged asset root has no checkout; its marker file identifies the bundled version.
    try:
        bundled = BUNDLE_VERSION_FILE.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        bundled = None
    if bundled is not None:
        return bundled if _BUNDLE_PATTERN.fullmatch(bundled) else "unknown"
    completed, error = readiness._query(
        runner, ["git", "-C", str(SOURCE_ROOT), "rev-parse", "HEAD"], str(SOURCE_ROOT)
    )
    value = completed.stdout.strip() if completed else ""
    return value if not error and _REVISION_PATTERN.fullmatch(value) else "unknown"


def _is_factory_source_checkout(path):
    root = Path(path)
    return (
        (root / "pyproject.toml").is_file()
        and (root / "src" / "specfactory").is_dir()
        and (root / "scripts" / "install_factory.py").is_file()
    )


def _read_source_files():
    files = {}
    for relative in MANAGED_FILES:
        if relative.startswith("/") or ".." in relative.split("/"):
            raise ValueError(f"unsafe managed path: {relative}")
        path = SOURCE_ROOT / relative
        if path.is_symlink() or not path.is_file():
            raise FileNotFoundError(relative)
        files[relative] = path.read_bytes()
    return files


def _run_readiness(target, environment):
    env = {
        key: value
        for key, value in environment.items()
        if not key.upper().startswith("FACTORY_")
        and key.upper() != "PYTHONPATH"
        and key.upper() not in SCRUBBED_GIT_VARIABLES
    }
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-B", str(Path(target) / "scripts" / "check_factory_readiness.py"),
         "--root", str(target)],
        cwd=str(target), env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", shell=False, check=False, timeout=READINESS_TIMEOUT_SECONDS,
    )


def _spec_kit_refusal(runner, target, which):
    root = Path(target)
    specify, executable = readiness.check_specify(root, runner, which)
    speckit = readiness.check_speckit(root, runner, executable, require_pointer=False)
    findings = [r.finding for r in (specify, speckit) if r.status == readiness.FAIL]
    return "; ".join(findings) if findings else None


def _validate_manifest(root):
    """Return an error text for an unsupported existing manifest, else None."""
    path = os.path.join(root, *MANIFEST_PATH.split("/"))
    state, reason = _classify(root, MANIFEST_PATH, lambda data: True)
    if state == "conflict" and reason == "not a regular file (unreadable)":
        return "it could not be read"
    # A link or other non-regular file is an ordinary conflict, reported by the plan.
    if state != "unchanged":
        return None
    try:
        with open(path, "rb") as handle:
            data = json.loads(handle.read().decode("utf-8"))
    except (OSError, UnicodeError, ValueError):
        return "it is not valid JSON"
    if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
        return "it is not a version 1 manifest object"
    return None


def main(
    argv=None, runner=readiness.default_runner, environment=None, which=None,
    stdout=None, readiness_runner=None,
):
    stdout = stdout or sys.stdout
    environment = os.environ if environment is None else environment
    which = which or readiness.make_path_lookup(environment, absolute_only=True)
    runner = _scrubbed(runner)
    readiness_runner = readiness_runner or _run_readiness

    def emit(text=""):
        print(text, file=stdout)

    def refuse(text):
        emit(text)
        return 2

    parser = argparse.ArgumentParser(
        description="Install the Software Factory specialist team into a Git repository."
    )
    parser.add_argument("--target", required=True, help="root directory of a local Git working tree")
    parser.add_argument("--dry-run", action="store_true", help="print the plan and change nothing")
    try:
        arguments = parser.parse_args(argv)
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2

    try:
        sources = _read_source_files()
    except (OSError, ValueError) as error:
        return refuse(
            f"Refused: a managed source file is missing or unusable ({type(error).__name__}: {error})."
        )

    given = Path(arguments.target).expanduser()
    if not given.is_dir():
        return refuse(f"Refused: --target must be an existing directory: {given}")
    target = os.path.realpath(os.path.abspath(given))

    completed, error = _git_query(runner, target, "rev-parse", "--show-toplevel")
    try:
        same = bool(not error and os.path.samefile(completed.stdout.strip(), target))
    except OSError:
        same = False
    if not same:
        return refuse(
            f"Refused: {target} is not the root of a Git working tree. Nothing was written."
        )
    completed, error = _git_query(runner, target, "rev-parse", "--is-bare-repository")
    if error or completed.stdout.strip() != "false":
        return refuse("Refused: the target is a bare repository. Nothing was written.")
    try:
        is_source = os.path.samefile(target, SOURCE_ROOT) or _is_factory_source_checkout(target)
    except OSError:
        is_source = _is_factory_source_checkout(target)
    if is_source:
        return refuse(
            "Refused: the target is the Software Factory source checkout. Nothing was written."
        )

    problem = _validate_manifest(target)
    if problem:
        return refuse(
            f"Refused: {MANIFEST_PATH} is an unsupported manifest ({problem}). Nothing was written."
        )

    completed, error = _git_query(runner, target, "ls-files", "--", PREFERENCES_PATH)
    if error:
        return refuse(f"Refused: could not query tracked files ({error}). Nothing was written.")
    if completed.stdout.strip():
        return refuse(
            f"Refused: {PREFERENCES_PATH} is already tracked by Git, so an exclude rule would not "
            "protect it.\n"
            "Nothing was written. Untrack it yourself, then re-run:\n"
            f"    git rm --cached {PREFERENCES_PATH}"
        )
    ignored, rule, error = _ignored(runner, target, MANIFEST_PATH)
    if error:
        return refuse(f"Refused: could not verify the manifest ignore state ({error}). Nothing was written.")
    if ignored:
        return refuse(
            f"Refused: {MANIFEST_PATH} is ignored by {rule or 'a Git ignore rule'}; the manifest "
            "must be shareable.\nNothing was written. Adjust that ignore rule, then re-run."
        )

    findings = _spec_kit_refusal(runner, target, which)
    if findings:
        return refuse(
            f"Refused: this repository has no valid Spec Kit Copilot integration ({findings}).\n"
            "Nothing was written. Review the official existing-project guidance, initialize or "
            "repair Spec Kit manually, then re-run."
        )

    files = {relative: fingerprint(data) for relative, data in sources.items()}
    manifest = _manifest_bytes(_source_revision(runner), files)

    def manifest_matches(data):
        try:
            document = json.loads(data.decode("utf-8"))
        except (UnicodeError, ValueError):
            return False
        return isinstance(document, dict) and document.get("files") == files

    entries = []
    for relative in MANAGED_FILES:
        matches = lambda data, r=relative: fingerprint(data) == files[r]
        entries.append((relative, *_classify(target, relative, matches), sources[relative]))
    entries.append((MANIFEST_PATH, *_classify(target, MANIFEST_PATH, manifest_matches), manifest))
    conflicts = [(relative, reason) for relative, state, reason, _ in entries if state == "conflict"]

    exclude = _plan_exclude(runner, target)
    warnings = _ignored_managed_paths(runner, target) or []

    emit(f"Target: {target}")
    for relative, state, reason, _ in entries:
        if state == "conflict":
            emit(f"[conflict]  {relative}: {reason}")
        else:
            emit(f"[{state}]".ljust(12) + relative)
    unresolved = False
    if exclude["state"] == "already-ignored":
        rule = exclude["rule"]
        emit(f"[exclude]   already ignored{f' by {rule}' if rule else ''}; no change")
    elif exclude["state"] == "append":
        created = f" (creates {' and '.join(exclude['creates'])})" if exclude["creates"] else ""
        emit(f"[exclude]   append '{EXCLUDE_ENTRY}' to {exclude['file']}{created}")
    elif exclude["state"] == "blocked":
        emit(f"[conflict]  {exclude['file']}: {exclude['reason']}")
        conflicts.append((exclude["file"], exclude["reason"]))
    else:
        emit(f"[exclude]   cannot establish the ignore state ({exclude['message']}); nothing will be written")
        unresolved = True
    if not conflicts and not unresolved:
        for relative, state, _, _ in entries:
            if state != "conflict" and _has_leftover_temp(target, relative):
                head, _, name = relative.rpartition("/")
                emit(f"[cleanup]   {head}/.{name}.sf-tmp: remove leftover temporary file")
    for path, rule in warnings:
        emit(f"[warning]   {path} is ignored by {rule}; it will not be shared")
    counts = {
        state: sum(1 for entry in entries if entry[1] == state) for state in ("create", "unchanged")
    }
    emit(f"Plan: {counts['create']} create, {counts['unchanged']} unchanged, {len(conflicts)} conflict")

    if conflicts:
        emit("Nothing was written. Resolve each conflict yourself, then re-run:")
        for path, reason in conflicts:
            step = next((text for key, text in CONFLICT_STEPS.items() if reason.startswith(key)), None)
            emit(f"    {path}: {step or 'fix the blocking item, then re-run'}")
    if arguments.dry_run:
        emit("DRY RUN: nothing was changed.")
        return 1 if conflicts or unresolved else 0
    if conflicts or unresolved:
        return 1

    if exclude["state"] == "append":
        try:
            _append_exclude(exclude["file"], exclude["expected"])
        except OSError as error:
            emit(f"error: could not update the exclude file ({type(error).__name__}); no assets were written.")
            return 1
        ignored, _, error = _ignored(runner, target, PREFERENCES_PATH)
        if not ignored:
            emit(
                f"error: {PREFERENCES_PATH} is still not ignored after the exclude update; "
                "no assets were written. The appended line, if any, was left in place."
            )
            return 1
        emit(f"[appended]  {EXCLUDE_ENTRY} to {exclude['file']}")

    for relative, _, _, _ in entries:
        try:
            _remove_leftover_temp(_temp_name(os.path.join(target, *relative.split("/"))))
        except (OSError, _Blocked):
            continue

    created = []

    def fail(text):
        emit(text)
        emit("Created: " + (", ".join(created) if created else "nothing"))
        emit("Existing files were not modified. Re-run the installer to complete the installation.")
        return 1

    for relative, state, _, data in entries:
        if state != "create":
            continue
        try:
            _create_exclusive(os.path.join(target, *relative.split("/")), data)
        except _Appeared:
            return fail(f"[conflict]  {relative}: appeared during installation")
        except _Blocked:
            return fail(f"[conflict]  {relative}: blocked path (temporary file is not a regular file)")
        except OSError as error:
            return fail(f"error: {relative} could not be written ({type(error).__name__})")
        created.append(relative)
        emit(f"[created]   {relative}")

    ignored, _, error = _ignored(runner, target, PREFERENCES_PATH)
    manifest_ignored, _, manifest_error = _ignored(runner, target, MANIFEST_PATH)
    if not ignored or manifest_ignored is not False:
        emit("error: final verification failed; the installation is not reported as successful.")
        if not ignored:
            emit(f"    {PREFERENCES_PATH} is not verified as ignored ({error or 'not ignored'}).")
        if manifest_ignored is not False:
            emit(f"    {MANIFEST_PATH} is not verified as shareable ({manifest_error or 'it is ignored'}).")
        return 1

    if not created and exclude["state"] != "append":
        emit("already installed: nothing to change.")
    else:
        emit(f"Installed {len(created)} file(s).")

    emit("Installed readiness check:")
    try:
        result = readiness_runner(target, environment)
    except (subprocess.TimeoutExpired, OSError) as error:
        emit(f"error: the installed readiness check could not run ({type(error).__name__}).")
        return 3
    if result.stdout:
        emit(result.stdout.rstrip("\n"))
    if result.stderr:
        print(result.stderr.rstrip("\n"), file=sys.stderr)
    emit("Next steps:")
    emit("    1. Set model tiers: python scripts/specialist_models.py set-tier ...")
    emit("    2. Open the project in VS Code and select Factory Lead in Copilot Chat.")
    emit("    3. Re-run readiness any time: python scripts/check_factory_readiness.py")
    return 3 if result.returncode != 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
