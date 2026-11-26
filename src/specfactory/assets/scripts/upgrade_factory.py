"""Upgrade an existing Software Factory installation to the bundled version.

Only files listed in the install manifest and owned by Spec Factory are touched. Model preferences,
the workspace index and child repositories are never written. Consent is collected by the caller
(`specfactory upgrade`); this engine applies a plan only when run without --dry-run.
"""

import argparse
import datetime
import importlib
import json
import os
from pathlib import Path
import re
import sys

_DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(_DIRECTORY))
try:
    install = importlib.import_module("install_factory")
finally:
    sys.path.pop(0)

readiness = install.readiness
fingerprint = install.fingerprint
MANAGED_FILES = install.MANAGED_FILES
MANIFEST_PATH = install.MANIFEST_PATH
PREFERENCES_PATH = install.PREFERENCES_PATH
WORKSPACE_MANIFEST_PATH = readiness.WORKSPACE_MANIFEST_PATH
RECORD_NAME = "upgrade-record.json"
_VERSION_PATTERN = re.compile(r"specfactory-(\d+)\.(\d+)\.(\d+)")
_FINGERPRINT_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
_KNOWN_PATHS = (*MANAGED_FILES, WORKSPACE_MANIFEST_PATH)


def _before_apply(relative):
    """Test seam: called immediately before each file is written."""


class _Refused(Exception):
    pass


def _inspect(root, relative):
    """Return (state, reason, data): create (absent), conflict (blocked), or unchanged (regular file)."""
    box = {}

    def capture(data):
        box["data"] = data
        return True

    state, reason = install._classify(root, relative, capture)
    return state, reason, box.get("data")


def _replace_file(path, data):
    """Atomically replace (or create) path; the previous content stays intact until the swap."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = install._temp_name(path)
    install._remove_leftover_temp(temp)
    fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | install._O_BINARY, 0o666)
    try:
        install._write_all(fd, data)
        os.replace(temp, path)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise


def _load_manifest(root):
    """Return (document, raw_bytes); raise _Refused for a missing or unsupported manifest."""
    state, reason, data = _inspect(root, MANIFEST_PATH)
    if state == "create":
        raise _Refused(
            f"{MANIFEST_PATH} was not found, so this is not a Software Factory installation. "
            "Use `specfactory init` to install."
        )
    if state == "conflict":
        raise _Refused(f"{MANIFEST_PATH} is not usable ({reason}).")
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise _Refused(f"{MANIFEST_PATH} is not valid JSON.") from None
    files = document.get("files") if isinstance(document, dict) else None
    if (
        type(document.get("version") if isinstance(document, dict) else None) is not int
        or document["version"] != 1
        or not isinstance(files, dict)
        or any(path not in _KNOWN_PATHS for path in files)
        or any(not isinstance(value, str) or not _FINGERPRINT_PATTERN.fullmatch(value) for value in files.values())
        or not isinstance(document.get("source_revision"), str)
    ):
        raise _Refused(f"{MANIFEST_PATH} is not a version 1 manifest this tool recognizes; nothing was written.")
    return document, data


def _version(label):
    match = _VERSION_PATTERN.fullmatch(label)
    return tuple(int(part) for part in match.groups()) if match else None


def _label(text):
    return re.sub(r"[^A-Za-z0-9._-]", "_", text)[:40] or "unknown"


def _backup_base(root, runner):
    """Return (directory, error). Backups sit in the Git directory (never untracked working-tree files)
    or, in a Gitless workspace, under .factory."""
    if _inspect(root, WORKSPACE_MANIFEST_PATH)[0] != "create":
        base = os.path.join(root, ".factory", "upgrade-backups")
        checks = (os.path.join(root, ".factory"), base)
    else:
        completed, error = install._git_query(runner, root, "rev-parse", "--absolute-git-dir")
        if error:
            return None, f"the Git directory could not be found ({error})"
        base = os.path.join(os.path.realpath(completed.stdout.strip()), "software-factory-upgrade-backups")
        checks = (base,)
    for path in checks:
        problem = install._ancestor_problem(path)
        if problem not in (None, "absent"):
            return None, f"{path}: {problem}"
    return base, None


def _records(base):
    """Return [(directory, record)] for upgrade records, oldest first; unreadable ones are skipped."""
    found = []
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return found
    for name in names:
        path = os.path.join(base, name, RECORD_NAME)
        try:
            with open(path, "rb") as handle:
                record = json.loads(handle.read().decode("utf-8"))
        except (OSError, UnicodeError, ValueError):
            continue
        if isinstance(record, dict) and isinstance(record.get("entries"), list):
            found.append((os.path.join(base, name), record))
    return found


def _valid_entry(entry):
    return (
        isinstance(entry, dict)
        and entry.get("path") in (*MANAGED_FILES, MANIFEST_PATH)
        and entry.get("backup") in (None, "files/" + str(entry.get("path")))
    )


def _restore(root, directory, record):
    """Put every recorded file back: previous bytes where a backup exists, otherwise remove it."""
    for entry in reversed(record["entries"]):
        if not _valid_entry(entry):
            raise _Refused(f"{RECORD_NAME} contains an unexpected path; restore from {directory} by hand.")
        path = os.path.join(root, *entry["path"].split("/"))
        if entry["backup"] is None:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
            continue
        with open(os.path.join(directory, *entry["backup"].split("/")), "rb") as handle:
            _replace_file(path, handle.read())


def _set_status(directory, record, status):
    record["status"] = status
    _replace_file(os.path.join(directory, RECORD_NAME), (json.dumps(record, indent=2) + "\n").encode("utf-8"))


def _roll_back(root, directory, record, emit):
    """Restore the pre-upgrade files, confirm they match the backup, and mark the record rolled back."""
    try:
        _restore(root, directory, record)
        for entry in record["entries"]:
            path = os.path.join(root, *entry["path"].split("/"))
            if entry["backup"] is None:
                restored = not os.path.lexists(path)
            else:
                with open(os.path.join(directory, *entry["backup"].split("/")), "rb") as handle:
                    expected = handle.read()
                restored = _inspect(root, entry["path"])[2] == expected
            if not restored:
                raise OSError(f"{entry['path']} does not match its backup after restoring")
        _set_status(directory, record, "rolled-back")
    except BaseException as error:
        emit(
            f"error: rollback did not complete ({type(error).__name__}: {error}). Run "
            f"`specfactory upgrade --recover`, or copy the files from {directory}\\files back by hand."
        )
        return False
    emit(f"Rolled back: every file is as before the upgrade. Backup kept at {directory}.")
    return True


_FAIL_LINE = re.compile(r"^\[FAIL\] (install-manifest|specialist-profiles): (.*)$", re.MULTILINE)


def _upgrade_failures(report):
    """Return readiness FAIL lines about files this upgrade wrote.

    Only the manifest-integrity and profile checks qualify. Other failures (tools, Spec Kit, hooks,
    Git state) and a changed workspace index existed independently of this upgrade.
    """
    written = (*MANAGED_FILES, MANIFEST_PATH)
    found = []
    for check, finding in _FAIL_LINE.findall(report):
        if check == "specialist-profiles" or any(path in finding for path in written):
            found.append(f"{check}: {finding}")
    return found


def main(argv=None, runner=readiness.default_runner, environment=None, stdout=None, readiness_runner=None):
    stdout = stdout or sys.stdout
    environment = os.environ if environment is None else environment
    runner = install._scrubbed(runner)
    readiness_runner = readiness_runner or install._run_readiness

    def emit(text=""):
        print(text, file=stdout)

    parser = argparse.ArgumentParser(description="Upgrade an installed Software Factory to the bundled version.")
    parser.add_argument("--target", required=True, help="project or workspace root of the installation")
    parser.add_argument("--dry-run", action="store_true", help="print the plan and change nothing")
    parser.add_argument(
        "--replace", action="append", default=[], metavar="PATH",
        help="approve replacing this locally modified managed file (a backup is kept); repeatable",
    )
    parser.add_argument("--recover", action="store_true", help="restore the backup of an interrupted upgrade")
    try:
        arguments = parser.parse_args(argv)
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2

    def refuse(text):
        emit(f"Refused: {text} Nothing was written.")
        return 2

    given = Path(arguments.target).expanduser()
    if not given.is_dir():
        return refuse(f"--target must be an existing directory: {given}.")
    target = os.path.realpath(os.path.abspath(given))
    try:
        if os.path.samefile(target, install.SOURCE_ROOT) or install._is_factory_source_checkout(target):
            return refuse("the target is the Software Factory source checkout.")
    except OSError:
        pass
    unknown = [path for path in arguments.replace if path not in MANAGED_FILES]
    if unknown:
        return refuse(f"--replace accepts only managed files, not: {', '.join(unknown)}.")
    if arguments.recover:
        base, problem = _backup_base(target, runner)
        if problem:
            return refuse(f"the backup location is unusable ({problem}).")
        interrupted = [item for item in _records(base) if item[1].get("status") == "applying"]
        if not interrupted:
            emit("No interrupted upgrade was found; nothing to recover.")
            return 0
        directory, record = interrupted[-1]
        if arguments.dry_run:
            emit(f"Would restore {len(record['entries'])} file(s) from {directory}.")
            emit("DRY RUN: nothing was changed.")
            return 0
        try:
            _restore(target, directory, record)
            _set_status(directory, record, "rolled-back")
        except (OSError, _Refused) as error:
            emit(f"error: recovery did not complete ({type(error).__name__}: {error}); backup kept at {directory}.")
            return 1
        emit(f"Restored {len(record['entries'])} file(s) from {directory}.")
        return 0

    try:
        manifest, manifest_bytes = _load_manifest(target)
    except _Refused as error:
        return refuse(str(error))
    recorded = manifest["files"]
    workspace_mode = WORKSPACE_MANIFEST_PATH in recorded
    if workspace_mode:
        problem = install._validate_workspace_manifest(target)
        state, _, _ = _inspect(target, WORKSPACE_MANIFEST_PATH)
        if problem or state != "unchanged":
            return refuse(f"{WORKSPACE_MANIFEST_PATH} is missing or unsupported ({problem or 'not found'}).")
    else:
        if _inspect(target, WORKSPACE_MANIFEST_PATH)[0] != "create":
            return refuse(f"{WORKSPACE_MANIFEST_PATH} exists but the manifest does not record a workspace installation.")
        completed, error = install._git_query(runner, target, "rev-parse", "--show-toplevel")
        try:
            same = bool(not error and os.path.samefile(completed.stdout.strip(), target))
        except OSError:
            same = False
        if not same:
            return refuse(f"{target} is not the root of a Git working tree.")

    base, problem = _backup_base(target, runner)
    if problem:
        return refuse(f"the backup location is unusable ({problem}).")
    interrupted = [item for item in _records(base) if item[1].get("status") == "applying"]
    if interrupted:
        return refuse(
            f"an interrupted upgrade was found at {interrupted[-1][0]}; "
            "run `specfactory upgrade --recover` to restore it first."
        )

    try:
        sources = install._read_source_files()
    except (OSError, ValueError) as error:
        return refuse(f"a bundled source file is missing or unusable ({type(error).__name__}: {error}).")
    bundled = install._source_revision(runner)
    installed = manifest["source_revision"]
    if _version(installed) and _version(bundled) and _version(installed) > _version(bundled):
        return refuse(f"the installation ({installed}) is newer than this release ({bundled}); downgrades are not supported.")

    new_files = {relative: fingerprint(data) for relative, data in sources.items()}
    if workspace_mode:
        new_files[WORKSPACE_MANIFEST_PATH] = recorded[WORKSPACE_MANIFEST_PATH]
    new_manifest = install._manifest_bytes(bundled, new_files)

    approved = set(arguments.replace)
    entries = []  # (relative, action, note, planned_bytes, current_bytes)
    for relative in MANAGED_FILES:
        state, reason, current = _inspect(target, relative)
        wanted = new_files[relative]
        if state == "conflict":
            entries.append((relative, "conflict", reason, None, None))
        elif state == "create":
            note = "missing; will be restored" if relative in recorded else "new in this release"
            entries.append((relative, "add", note, sources[relative], None))
        elif fingerprint(current) == wanted:
            entries.append((relative, "unchanged", "", None, current))
        elif relative in recorded and fingerprint(current) == recorded[relative]:
            entries.append((relative, "replace", "", sources[relative], current))
        elif relative in approved:
            entries.append((relative, "replace", "locally modified; replacement approved, backup kept", sources[relative], current))
        else:
            why = "not recorded in the manifest" if relative not in recorded else "differs from its recorded fingerprint"
            entries.append((relative, "modified", f"locally modified ({why}); approve with --replace {relative} (a backup is kept)", None, current))
    if manifest_bytes == new_manifest:
        entries.append((MANIFEST_PATH, "unchanged", "", None, manifest_bytes))
    else:
        entries.append((MANIFEST_PATH, "replace", "updated last, after every file is applied", new_manifest, manifest_bytes))

    emit(f"Target: {target}")
    emit(f"Mode: {'Gitless workspace' if workspace_mode else 'single repository'}")
    emit(f"Installed: {installed}; bundled: {bundled}")
    for relative, action, note, _, _ in entries:
        emit(f"[{action}]".ljust(12) + relative + (f": {note}" if note else ""))
    preserved = [PREFERENCES_PATH] + ([WORKSPACE_MANIFEST_PATH] if workspace_mode else [])
    for relative in preserved:
        if _inspect(target, relative)[0] == "unchanged":
            emit("[preserved] ".ljust(12) + f"{relative}: never modified")
    counts = {
        name: sum(1 for entry in entries[:-1] if entry[1] == name)
        for name in ("replace", "add", "unchanged", "modified", "conflict")
    }
    emit(
        f"Plan: {counts['replace']} replace, {counts['add']} add, {counts['unchanged']} unchanged, "
        f"{counts['modified']} locally modified, {counts['conflict']} conflict"
    )

    if counts["modified"] or counts["conflict"]:
        emit("Nothing was written. Resolve each item, then re-run:")
        for relative, action, note, _, _ in entries:
            if action == "conflict":
                step = next((text for key, text in install.CONFLICT_STEPS.items() if note.startswith(key)), None)
                emit(f"    {relative}: {step or 'fix the blocking item, then re-run'}")
            elif action == "modified":
                emit(f"    {relative}: keep your edits elsewhere, or approve replacement with --replace {relative}")
        return 1
    changes = [entry for entry in entries if entry[1] in ("replace", "add")]
    if not changes:
        emit("already up to date: nothing to change.")
        return 0
    if arguments.dry_run:
        emit("DRY RUN: nothing was changed.")
        return 0

    for relative, action, _, _, current in entries:
        if action == "unchanged":
            continue
        state, _, now = _inspect(target, relative)
        if (state == "create") != (current is None) or (current is not None and now != current):
            emit(f"Refused: {relative} changed during planning; nothing was written. Re-run to plan again.")
            return 1

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"{stamp}-{_label(installed)}-to-{_label(bundled)}"
    directory = os.path.join(base, name)
    suffix = 1
    while os.path.exists(directory):
        suffix += 1
        directory = os.path.join(base, f"{name}-{suffix}")
    record = {
        "version": 1, "status": "applying", "from": installed, "to": bundled,
        "entries": [
            {"path": relative, "backup": f"files/{relative}" if current is not None else None}
            for relative, _, _, _, current in changes
        ],
    }
    try:
        for relative, _, _, _, current in changes:
            if current is not None:
                install._create_exclusive(os.path.join(directory, "files", *relative.split("/")), current)
        install._create_exclusive(
            os.path.join(directory, RECORD_NAME), (json.dumps(record, indent=2) + "\n").encode("utf-8")
        )
    except (OSError, install._Appeared, install._Blocked) as error:
        emit(f"error: the backup could not be written ({type(error).__name__}); nothing was changed.")
        return 1
    emit(f"Backup: {directory}")

    # The manifest is the last entry of the plan, so an interrupted run never records unapplied files.
    ordered = changes
    try:
        for relative, action, _, data, _ in ordered:
            _before_apply(relative)
            _replace_file(os.path.join(target, *relative.split("/")), data)
            emit(f"[{'replaced' if action == 'replace' else 'added'}]".ljust(12) + relative)
        for relative, _, _, data, _ in ordered:
            _, _, now = _inspect(target, relative)
            if now != data:
                raise OSError(f"{relative} did not verify after writing")
    except BaseException as error:
        emit(f"error: the upgrade failed ({type(error).__name__}: {error}); restoring the previous files.")
        _roll_back(target, directory, record, emit)
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        return 1
    emit(f"Upgraded {len([c for c in changes if c[0] != MANIFEST_PATH])} file(s) from {installed} to {bundled}.")
    emit(f"Model preferences and overrides ({PREFERENCES_PATH}) were not modified.")

    # The record stays "applying" until verification passes, so an interrupted run can be recovered.
    emit("Installed readiness check:")
    try:
        result = readiness_runner(target, environment)
    except Exception as error:
        _set_status(directory, record, "complete")
        emit(
            f"error: the installed readiness check could not run ({type(error).__name__}). The written files "
            f"were verified byte-for-byte, but the upgrade was not checked by readiness; it was kept. Backup: {directory}"
        )
        return 3
    report = result.stdout or ""
    if report:
        emit(report.rstrip("\n"))
    if result.stderr:
        print(result.stderr.rstrip("\n"), file=sys.stderr)
    failures = _upgrade_failures(report)
    if failures:
        emit("Post-upgrade verification FAILED for files this upgrade wrote; restoring the previous files:")
        for line in failures:
            emit(f"    {line}")
        _roll_back(target, directory, record, emit)
        return 1
    _set_status(directory, record, "complete")
    if result.returncode != 0:
        if "Verdict:" not in report:
            emit(f"The readiness check produced no verdict, so the upgrade could not be verified; it was kept. Backup: {directory}")
        else:
            emit(
                "Readiness is NOT READY only for reasons unrelated to the files this upgrade wrote "
                f"(see above); the upgrade was kept. Backup: {directory}"
            )
        return 3
    emit(f"The backup at {directory} may be deleted once you are satisfied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
