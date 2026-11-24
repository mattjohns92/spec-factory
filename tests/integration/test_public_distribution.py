"""Feature 007 public distribution: build the wheel and sdist locally, install the wheel into a
clean venv, and exercise B1-B8 against it.

No registry, publication or upstream initialization is involved. `specify`, `uv` and `copilot` are
local fakes placed on the child's PATH; the real engine, readiness checker and model helper run
from the installed wheel. Interactive consent is driven by importing the installed
`specfactory.cli.main` in a venv child with scripted answers (there is no pty in the stdlib), so a
real terminal's isatty detection is not covered here.
"""

import base64
import configparser
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = REPOSITORY_ROOT
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import check_factory_readiness as readiness  # noqa: E402
import specialist_models  # noqa: E402  (the checkout's helper: source of truth for presets)


with open(PROJECT_ROOT / "pyproject.toml", "rb") as _handle:
    VERSION = tomllib.load(_handle)["project"]["version"]

CODE_MODULES = ("__init__.py", "__main__.py", "bundle.py", "cli.py")
ASSET_FILES = (
    "BUNDLE_VERSION",
    ".github/agents/architect.agent.md",
    ".github/agents/code-reviewer.agent.md",
    ".github/agents/engineer.agent.md",
    ".github/agents/factory-lead.agent.md",
    ".github/agents/qa-engineer.agent.md",
    ".github/skills/factory-handoff/SKILL.md",
    "scripts/check_factory_readiness.py",
    "scripts/install_factory.py",
    "scripts/specialist_models.py",
    "scripts/validate_specialist_profiles.py",
)
DIST_INFO = f"specfactory-{VERSION}.dist-info"
WHEEL_MEMBERS = (
    {f"specfactory/{name}" for name in CODE_MODULES}
    | {f"specfactory/assets/{name}" for name in ASSET_FILES}
    | {f"{DIST_INFO}/{name}" for name in ("METADATA", "WHEEL", "entry_points.txt", "RECORD")}
    | {f"{DIST_INFO}/licenses/LICENSE"}
)
SDIST_PREFIX = f"specfactory-{VERSION}/"
# PKG-INFO and .gitignore are added by the build backend, not by the project's only-include list.
SDIST_MEMBERS = (
    {
        f"{SDIST_PREFIX}{name}"
        for name in ("pyproject.toml", "README.md", "build-constraints.txt", "LICENSE", "PKG-INFO", ".gitignore")
    }
    | {f"{SDIST_PREFIX}src/specfactory/{name}" for name in CODE_MODULES}
    | {f"{SDIST_PREFIX}src/specfactory/assets/{name}" for name in ASSET_FILES}
)
# The nine files the engine installs into a project (install_factory.py itself is never installed).
MANAGED = (
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
MANIFEST = ".github/software-factory/install-manifest.json"
PREFERENCES = ".factory/model-preferences.json"
EXCLUDE_LINE = "/.factory/model-preferences.json"
INSTALLED = set(MANAGED) | {MANIFEST}

NAME_DENYLIST = re.compile(
    r"software_factory|(^|/)\.specify(/|$)|(^|/)specs(/|$)|(^|/)tests?(/|$)|(^|/)\.factory(/|$)|"
    r"model-preferences|policy|hooks?(/|\.|$)|sandbox|settings\.local|run_engineer|speckit\.|"
    r"(^|/)\.git(/|$)|(^|/)dist(/|$)|(^|/)distributions(/|$)|\.venv|__pycache__|\.py[co]$",
    re.IGNORECASE,
)
MODEL_IDENTIFIER = re.compile(rb"claude-|gpt-\d|gemini-|sonnet|haiku|opus", re.IGNORECASE)

# Only these variables reach a child; PYTHONPATH, FACTORY_*, GIT_* and the rest are dropped.
ALLOWED_VARIABLES = frozenset(
    name.upper() for name in (
        "SystemRoot", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE",
        "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "ProgramFiles",
        "ProgramFiles(x86)", "ProgramW6432", "PROCESSOR_ARCHITECTURE", "USERNAME", "LANG", "LC_ALL",
        "LC_CTYPE", "TERM",
    )
)
UNROUTABLE_PROXY = "http://127.0.0.1:9"

ARTIFACTS = None


def lf(data):
    return data.replace(b"\r\n", b"\n")


def scrubbed_environment(path_entries, source=None):
    """Allowlisted environment with an explicit PATH, offline guards and no Git overrides."""
    source = os.environ if source is None else source
    environment = {key: value for key, value in source.items() if key.upper() in ALLOWED_VARIABLES}
    environment["PATH"] = os.pathsep.join(str(entry) for entry in path_entries)
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["UV_OFFLINE"] = "1"
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        environment[name] = UNROUTABLE_PROXY
    return environment


def tool_environment():
    """Environment for the host-side uv/python steps (not a child under test): no overrides leak in."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(("FACTORY_", "GIT_"))
        and key.upper() not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")
    }
    environment["UV_OFFLINE"] = "1"
    return environment


def run(arguments, cwd=None, environment=None, stdin=subprocess.DEVNULL, input=None):
    return subprocess.run(
        [str(argument) for argument in arguments],
        cwd=None if cwd is None else str(cwd),
        env=tool_environment() if environment is None else environment,
        stdin=None if input is not None else stdin, input=input,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        shell=False, check=False, timeout=300,
    )


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


def tracked_sources(root):
    return sorted(
        path.relative_to(root).as_posix()
        for path in Path(root).rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )


def is_inside(path, root):
    try:
        Path(os.path.realpath(path)).relative_to(os.path.realpath(root))
    except ValueError:
        return False
    return True


def last_json_line(text):
    lines = [line for line in text.splitlines() if line.strip()]
    return json.loads(lines[-1])


def make_launcher(directory, name, python, script):
    """Write an executable `name` in directory that runs fake_tool.py for that tool name."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        path = directory / f"{name}.cmd"
        path.write_text(f'@echo off\r\n"{python}" "{script}" {name} %*\r\n', encoding="utf-8")
    else:
        path = directory / name
        path.write_text(f'#!/bin/sh\nexec "{python}" "{script}" {name} "$@"\n', encoding="utf-8")
        path.chmod(0o755)
    return path


FAKE_TOOL = r'''
import json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "config.json"), encoding="utf-8") as handle:
    CONFIG = json.load(handle)
NAME, ARGS = sys.argv[1], sys.argv[2:]


def record(code, note=""):
    entry = {"tool": NAME, "args": ARGS, "cwd": os.getcwd(), "exit": code, "note": note}
    with open(os.path.join(HERE, "log.jsonl"), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
    sys.exit(code)


if NAME == "specify":
    if ARGS == ["--version"]:
        print("specify 1.0.6")
        record(0)
    if ARGS == ["integration", "status", "--json"]:
        if os.path.isfile(os.path.join(".specify", "fake-integration")) or CONFIG["integration_always"]:
            print(json.dumps({
                "status": "ok", "default_integration": "copilot",
                "installed_integrations": ["copilot"], "missing_managed_files": 0,
                "modified_managed_files": 0, "invalid_manifest_paths": 0,
                "unchecked_manifests": 0, "findings": [],
            }))
            record(0)
        print("no integration", file=sys.stderr)
        record(1)
elif NAME == "uv":
    if ARGS == ["tool", "install", "specify-cli==1.0.6"]:
        if CONFIG["uv_fail"]:
            record(1)
        if CONFIG["uv_installs_specify"]:
            staged = os.path.join(HERE, "staged")
            for entry in os.listdir(staged):
                shutil.copy(os.path.join(staged, entry), os.path.join(CONFIG["bin"], entry))
        record(0)
elif NAME == "copilot":
    record(99, "executed")
record(64, "unexpected")
'''

DRIVER = r'''
import io, json, os, sys

from specfactory import cli

spec = json.loads(sys.argv[1])
answers = list(spec["answers"])
records = []


def log_length():
    try:
        with open(spec["log"], encoding="utf-8") as handle:
            return len(handle.read().splitlines())
    except OSError:
        return 0


def input_fn(prompt):
    answer = answers.pop(0) if answers else None
    records.append({
        "prompt": prompt, "answer": answer, "log_length": log_length(),
        "present": {path: os.path.exists(path) for path in spec["watch"]},
    })
    if answer is None:
        raise EOFError
    return answer


out = io.StringIO()
code = cli.main(spec["argv"], stdout=out, input_fn=input_fn, interactive=True)
print(json.dumps({"code": code, "stdout": out.getvalue(), "prompts": records, "unused": answers}))
'''

PROBE = r'''
import importlib.metadata, json, os, sys

import specfactory
from specfactory import bundle, cli

try:
    import software_factory
    leaked = software_factory.__file__
except ModuleNotFoundError:
    leaked = None
engine = bundle.load_script("install_factory")
distribution = importlib.metadata.distribution("specfactory")
print(json.dumps({
    "prefix": sys.prefix, "cwd": os.getcwd(), "path": sys.path,
    "package_file": specfactory.__file__, "bundle_file": bundle.__file__, "cli_file": cli.__file__,
    "asset_root": str(bundle.asset_root()), "engine_source_root": str(engine.SOURCE_ROOT),
    "missing": bundle.missing_assets(), "version": specfactory.__version__,
    "distribution_version": distribution.version,
    "console_scripts": sorted(e.name for e in distribution.entry_points if e.group == "console_scripts"),
    "leaked": leaked,
}))
'''


class Artifacts:
    pass


def _build_and_install():
    work = os.path.realpath(tempfile.mkdtemp(prefix="sf-public-"))
    artifacts = Artifacts()
    artifacts.work = Path(work)
    try:
        if is_inside(work, REPOSITORY_ROOT):
            raise RuntimeError("the temporary work directory must be outside the checkout.")
        artifacts.source_before = tracked_sources(PROJECT_ROOT)
        out = artifacts.work / "dist"
        built = run([
            "uv", "build", "--offline", "--wheel", "--sdist", "--require-hashes",
            "--build-constraint", PROJECT_ROOT / "build-constraints.txt", "--out-dir", out, PROJECT_ROOT,
        ])
        if built.returncode != 0:
            text = built.stdout + built.stderr
            raise RuntimeError(
                "the mandatory offline wheel/sdist build failed; provision the pinned backend "
                f"locally before running B1-B8: {text}"
            )
        artifacts.wheel = out / f"specfactory-{VERSION}-py3-none-any.whl"
        artifacts.sdist = out / f"specfactory-{VERSION}.tar.gz"

        venv = artifacts.work / "venv"
        created = run([sys.executable, "-m", "venv", "--without-pip", venv])
        if created.returncode != 0:
            raise RuntimeError(f"venv creation failed: {created.stdout}{created.stderr}")
        bin_dir = venv / ("Scripts" if os.name == "nt" else "bin")
        artifacts.venv, artifacts.bin = venv, bin_dir
        artifacts.python = bin_dir / ("python.exe" if os.name == "nt" else "python")
        installed = run([
            "uv", "pip", "install", "--offline", "--no-index", "--no-deps",
            "--python", artifacts.python, artifacts.wheel,
        ])
        if installed.returncode != 0:
            raise RuntimeError(f"offline wheel install failed: {installed.stdout}{installed.stderr}")
        artifacts.cli = bin_dir / ("specfactory.exe" if os.name == "nt" else "specfactory")
        artifacts.git_directory = os.path.dirname(shutil.which("git"))
    except BaseException:
        remove_tree(work)
        raise
    return artifacts


def setUpModule():
    global ARTIFACTS
    if shutil.which("uv") is None:
        raise RuntimeError("uv is required: the B1-B8 gate must build local wheel and sdist artifacts")
    if shutil.which("git") is None:
        raise RuntimeError("git is required: B1-B8 create and validate disposable Git projects")
    ARTIFACTS = _build_and_install()
    unittest.addModuleCleanup(remove_tree, str(ARTIFACTS.work))


def wheel_bytes():
    with zipfile.ZipFile(ARTIFACTS.wheel) as archive:
        return {name: archive.read(name) for name in archive.namelist() if not name.endswith("/")}


def sdist_bytes():
    with tarfile.open(ARTIFACTS.sdist) as archive:
        return {
            member.name: archive.extractfile(member).read()
            for member in archive.getmembers() if member.isfile()
        }


class BuildArtifactTests(unittest.TestCase):
    """B7: inspect the built archives against explicit allowlists and denylists."""

    def test_wheel_members_are_exactly_the_allowlist(self):
        self.assertEqual(set(wheel_bytes()), WHEEL_MEMBERS)

    def test_sdist_members_are_exactly_the_allowlist(self):
        self.assertEqual(set(sdist_bytes()), SDIST_MEMBERS)

    def test_no_denylisted_name_in_either_archive(self):
        for label, members in (("wheel", wheel_bytes()), ("sdist", sdist_bytes())):
            for name in members:
                with self.subTest(archive=label, member=name):
                    self.assertIsNone(NAME_DENYLIST.search(name))

    def test_no_checkout_path_home_directory_or_model_identifier_in_any_member(self):
        needles = {str(REPOSITORY_ROOT), REPOSITORY_ROOT.as_posix(), str(Path.home()), Path.home().as_posix()}
        for label, members in (("wheel", wheel_bytes()), ("sdist", sdist_bytes())):
            for name, data in members.items():
                with self.subTest(archive=label, member=name):
                    text = data.decode("utf-8", errors="replace").lower()
                    for needle in needles:
                        self.assertNotIn(needle.lower(), text)
                    self.assertIsNone(MODEL_IDENTIFIER.search(data))

    def test_sdist_ignore_file_matches_the_canonical_root(self):
        actual = sdist_bytes()[f"{SDIST_PREFIX}.gitignore"]
        expected = (PROJECT_ROOT / ".gitignore").read_bytes()
        self.assertEqual(lf(actual), lf(expected))
        self.assertNotIn(str(Path.home()).encode(), actual)
        self.assertIsNone(MODEL_IDENTIFIER.search(actual))

    def test_wheel_entry_points_declare_only_specfactory(self):
        parser = configparser.ConfigParser()
        parser.optionxform = str
        parser.read_string(wheel_bytes()[f"{DIST_INFO}/entry_points.txt"].decode("utf-8"))
        self.assertEqual(parser.sections(), ["console_scripts"])
        self.assertEqual(dict(parser["console_scripts"]), {"specfactory": "specfactory.cli:main"})

    def test_wheel_metadata_names_the_package_without_dependencies(self):
        metadata = wheel_bytes()[f"{DIST_INFO}/METADATA"].decode("utf-8")
        self.assertRegex(metadata, rf"(?m)^Name: specfactory$")
        self.assertRegex(metadata, rf"(?m)^Version: {re.escape(VERSION)}$")
        self.assertRegex(metadata, r"(?m)^Requires-Python: >=3\.11$")
        self.assertRegex(metadata, r"(?m)^License-Expression: MIT$")
        self.assertRegex(metadata, r"(?m)^License-File: LICENSE$")
        self.assertNotRegex(metadata, r"(?m)^Project-URL:")
        self.assertIn("# Spec Factory", metadata)
        self.assertNotRegex(metadata, r"(?m)^Requires-Dist:")

    def test_public_readme_license_and_build_constraints_are_in_sdist(self):
        members = sdist_bytes()
        self.assertIn(b"# Spec Factory", members[f"{SDIST_PREFIX}README.md"])
        self.assertIn(f"{SDIST_PREFIX}build-constraints.txt", members)
        self.assertIn(f"{SDIST_PREFIX}LICENSE", members)
        self.assertNotIn(f"{SDIST_PREFIX}RELEASE.md", members)

    def test_wheel_includes_the_approved_mit_license(self):
        members = wheel_bytes()
        self.assertIn(f"{DIST_INFO}/licenses/LICENSE", members)
        self.assertIn(b"Copyright (c) 2026 Matthew Johns", members[f"{DIST_INFO}/licenses/LICENSE"])

    def test_wheel_record_hashes_match_members(self):
        members = wheel_bytes()
        rows = members[f"{DIST_INFO}/RECORD"].decode("utf-8").splitlines()
        recorded = {}
        for row in rows:
            name, digest, _size = row.rsplit(",", 2)
            recorded[name] = digest
        self.assertEqual(set(recorded), set(members))
        for name, data in members.items():
            if name.endswith("/RECORD"):
                continue
            expected = "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
            with self.subTest(member=name):
                self.assertEqual(recorded[name], expected)

    def test_wheel_assets_match_the_accepted_checkout_sources(self):
        members = wheel_bytes()
        for name in ASSET_FILES:
            if name == "BUNDLE_VERSION":
                self.assertEqual(lf(members[f"specfactory/assets/{name}"]), f"specfactory-{VERSION}\n".encode())
                continue
            with self.subTest(asset=name):
                self.assertEqual(lf(members[f"specfactory/assets/{name}"]), lf((REPOSITORY_ROOT / name).read_bytes()))

    def test_sdist_builds_the_same_wheel_without_git_or_the_checkout(self):
        extracted = ARTIFACTS.work / "sdist-build"
        extracted.mkdir()
        with tarfile.open(ARTIFACTS.sdist) as archive:
            for member in archive.getmembers():
                self.assertTrue(is_inside(extracted / member.name, extracted), member.name)
            if hasattr(tarfile, "data_filter"):
                archive.extractall(extracted, filter="data")
            else:
                archive.extractall(extracted)
        source = extracted / f"specfactory-{VERSION}"
        self.assertFalse((source / ".git").exists())
        self.assertFalse(is_inside(source, REPOSITORY_ROOT))
        out = ARTIFACTS.work / "dist-from-sdist"
        built = run([
            "uv", "build", "--offline", "--wheel", "--require-hashes",
            "--build-constraint", source / "build-constraints.txt", "--out-dir", out, source,
        ])
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        with zipfile.ZipFile(out / ARTIFACTS.wheel.name) as archive:
            rebuilt = {name: archive.read(name) for name in archive.namelist() if not name.endswith("/")}
        self.assertEqual(rebuilt, wheel_bytes())

    def test_building_does_not_modify_the_source_distribution_directory(self):
        self.assertEqual(tracked_sources(PROJECT_ROOT), ARTIFACTS.source_before)


class CleanRuntimeTests(unittest.TestCase):
    """B1/B7: the installed wheel runs in a clean venv, outside the checkout, with scrubbed env."""

    def child_environment(self):
        return scrubbed_environment([ARTIFACTS.bin, ARTIFACTS.git_directory])

    def test_scrubbing_drops_poisoned_variables(self):
        poisoned = dict(os.environ)
        poisoned.update(
            PYTHONPATH=str(REPOSITORY_ROOT / "src"), FACTORY_REPOSITORY_ROOT=str(REPOSITORY_ROOT),
            FACTORY_POLICY_PATH="x", GIT_DIR="bogus", GIT_WORK_TREE="bogus", GIT_INDEX_FILE="bogus",
            GIT_CEILING_DIRECTORIES="bogus", PYTHONHOME="bogus", VIRTUAL_ENV=str(REPOSITORY_ROOT / ".venv"),
        )
        environment = scrubbed_environment([ARTIFACTS.bin], poisoned)
        for key in environment:
            upper = key.upper()
            self.assertFalse(upper.startswith("FACTORY_"), key)
            self.assertNotIn(upper, ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CEILING_DIRECTORIES"))
        self.assertEqual(environment["PATH"], str(ARTIFACTS.bin))
        self.assertEqual(environment["GIT_CONFIG_GLOBAL"], os.devnull)

    def probe(self):
        result = run(
            [ARTIFACTS.python, "-I", "-c", PROBE], cwd=ARTIFACTS.work, environment=self.child_environment()
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_imports_and_assets_resolve_only_inside_the_venv(self):
        facts = self.probe()
        self.assertTrue(is_inside(facts["cwd"], ARTIFACTS.work))
        self.assertFalse(is_inside(facts["cwd"], REPOSITORY_ROOT))
        self.assertEqual(os.path.realpath(facts["prefix"]), os.path.realpath(ARTIFACTS.venv))
        for key in ("package_file", "bundle_file", "cli_file", "asset_root", "engine_source_root"):
            with self.subTest(location=key):
                self.assertTrue(is_inside(facts[key], ARTIFACTS.venv), facts[key])
                self.assertFalse(is_inside(facts[key], REPOSITORY_ROOT), facts[key])
        for entry in facts["path"]:
            if entry:
                self.assertFalse(is_inside(entry, REPOSITORY_ROOT), entry)
        self.assertIsNone(facts["leaked"], "the checkout's software_factory package must not be importable")
        self.assertEqual(facts["missing"], [])
        self.assertEqual(facts["version"], VERSION)
        self.assertEqual(facts["distribution_version"], VERSION)
        self.assertEqual(facts["console_scripts"], ["specfactory"])

    def test_installed_files_are_byte_identical_to_the_built_wheel(self):
        package = Path(self.probe()["package_file"]).parent
        installed = {
            path.relative_to(package.parent).as_posix(): path.read_bytes()
            for path in package.rglob("*") if path.is_file() and "__pycache__" not in path.parts
        }
        expected = {name: data for name, data in wheel_bytes().items() if name.startswith("specfactory/")}
        self.assertEqual(installed, expected)

    def test_only_the_specfactory_executable_is_installed_and_no_factory_alias_exists(self):
        names = {entry.name.lower() for entry in ARTIFACTS.bin.iterdir()}
        self.assertTrue(ARTIFACTS.cli.is_file())
        self.assertEqual({name for name in names if name.startswith("factory")}, set())
        self.assertEqual({name for name in names if "specfactory" in name} - {ARTIFACTS.cli.name.lower()}, set())

    def test_console_script_and_module_help_start_from_the_wheel(self):
        for command in ([ARTIFACTS.cli, "--help"], [ARTIFACTS.cli, "init", "--help"], [ARTIFACTS.python, "-I", "-m", "specfactory", "init", "--help"]):
            with self.subTest(command=[str(part) for part in command[1:]]):
                result = run(command, cwd=ARTIFACTS.work, environment=self.child_environment())
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("specfactory", result.stdout)
        result = run([ARTIFACTS.cli, "init", "--help"], cwd=ARTIFACTS.work, environment=self.child_environment())
        for option in ("--target", "--dry-run", "--non-interactive", "--yes"):
            self.assertIn(option, result.stdout)
        self.assertNotIn("--force", result.stdout)

    def test_force_is_not_an_accepted_option(self):
        result = run([ARTIFACTS.cli, "init", "--force"], cwd=ARTIFACTS.work, environment=self.child_environment())
        self.assertEqual(result.returncode, 2)
        self.assertIn("unrecognized arguments: --force", result.stderr)

    def test_real_specify_is_not_reachable_from_the_child_path(self):
        self.assertIsNone(shutil.which("specify", path=self.child_environment()["PATH"]))


class World:
    """A disposable Git project plus fake machine tools (specify/uv/copilot) for one scenario."""

    counter = 0

    def __init__(self, *, speckit="valid", specify=True, uv=False, copilot=True):
        World.counter += 1
        self.root = ARTIFACTS.work / f"world-{World.counter}"
        self.project = self.root / "project"
        self.bin = self.root / "bin"
        self.fakes = self.root / "fakes"
        for directory in (self.project, self.bin, self.fakes / "staged"):
            directory.mkdir(parents=True)
        self.script = self.fakes / "fake_tool.py"
        self.script.write_text(FAKE_TOOL, encoding="utf-8")
        self.set_config()
        made = run(["git", "init", "-q", str(self.project)], environment=self.environment())
        if made.returncode != 0:
            raise AssertionError(made.stdout + made.stderr)
        if specify:
            self.add_tool("specify")
        if uv:
            self.add_tool("uv")
        if copilot:
            self.add_tool("copilot")
        if speckit == "valid":
            self.write_speckit()
        elif speckit == "incomplete":
            (self.project / ".specify").mkdir()

    def set_config(self, **changes):
        config = {
            "uv_fail": False, "uv_installs_specify": True,
            "speckit_files": list(readiness.SPECKIT_FILES), "bin": str(self.bin), "integration_always": False,
        }
        path = self.fakes / "config.json"
        if path.exists():
            config = json.loads(path.read_text(encoding="utf-8"))
        config.update(changes)
        path.write_text(json.dumps(config), encoding="utf-8")

    def add_tool(self, name, *, staged=False):
        directory = self.fakes / "staged" if staged else self.bin
        make_launcher(directory, name, ARTIFACTS.python, self.script)

    def write_speckit(self):
        for relative in (*readiness.SPECKIT_FILES, ".specify/fake-integration"):
            path = self.project / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fake\n", encoding="utf-8")

    def environment(self):
        return scrubbed_environment([ARTIFACTS.bin, self.bin, ARTIFACTS.git_directory])

    def git(self, *arguments):
        return run(["git", *arguments], cwd=self.project, environment=self.environment())

    def snapshot(self):
        return snapshot(self.project)

    def cli(self, *arguments, input=None):
        return run(
            [ARTIFACTS.cli, "init", *arguments], cwd=self.project, environment=self.environment(),
            input=input,
        )

    def guided(self, argv, answers):
        spec = {
            "argv": list(argv), "answers": list(answers), "log": str(self.fakes / "log.jsonl"),
            "watch": [*MANAGED, MANIFEST, ".specify/memory/constitution.md"],
        }
        driver = self.fakes / "driver.py"
        driver.write_text(DRIVER, encoding="utf-8")
        result = run(
            [ARTIFACTS.python, "-I", driver, json.dumps(spec)], cwd=self.project, environment=self.environment()
        )
        if result.returncode != 0:
            raise AssertionError(f"driver failed: {result.stdout}{result.stderr}")
        payload = last_json_line(result.stdout)
        payload["stderr"] = result.stderr
        return payload

    def log(self):
        path = self.fakes / "log.jsonl"
        if not path.exists():
            return []
        entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        for entry in entries:
            if "--force" in entry["args"] or entry["note"] in ("force", "unexpected", "executed"):
                raise AssertionError(f"forbidden fake-tool call: {entry}")
        return entries

    def setup_calls(self):
        return [
            (entry["tool"], entry["args"], entry["cwd"]) for entry in self.log()
            if entry["tool"] == "uv" or (entry["tool"] == "specify" and entry["args"][:1] == ["init"])
        ]

    def installed_paths(self):
        return {
            path.relative_to(self.project).as_posix()
            for path in self.project.rglob("*")
            if path.is_file() and ".git" not in path.relative_to(self.project).parts
        }

    def exclude_text(self):
        return (self.project / ".git" / "info" / "exclude").read_text(encoding="utf-8")


class WorldTestCase(unittest.TestCase):
    def assertNoCheckoutPaths(self, *texts):
        for text in texts:
            lowered = text.lower()
            self.assertNotIn(str(REPOSITORY_ROOT).lower(), lowered)
            self.assertNotIn(REPOSITORY_ROOT.as_posix().lower(), lowered)

    def assertUntouched(self, world, before):
        self.assertEqual(world.snapshot(), before)

    def assertInstalled(self, world, before_paths=frozenset()):
        wheel = wheel_bytes()
        new = world.installed_paths() - set(before_paths)
        self.assertEqual(new - {PREFERENCES}, INSTALLED)
        for relative in MANAGED:
            with self.subTest(installed=relative):
                self.assertEqual((world.project / relative).read_bytes(), wheel[f"specfactory/assets/{relative}"])
        manifest = json.loads((world.project / MANIFEST).read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], 1)
        self.assertEqual(manifest["source_revision"], f"specfactory-{VERSION}")
        self.assertEqual(set(manifest["files"]), set(MANAGED))
        self.assertIn(EXCLUDE_LINE, world.exclude_text().splitlines())
        self.assertFalse(any("__pycache__" in path or path.endswith(".pyc") for path in world.installed_paths()))
        self.assertFalse((world.project / "scripts" / "install_factory.py").exists())
        self.assertNoCheckoutPaths(*(
            (world.project / relative).read_text(encoding="utf-8", errors="replace")
            for relative in INSTALLED
        ))


class B1CleanWheelInstallTests(WorldTestCase):
    def test_b1_console_script_installs_into_a_disposable_project_from_the_wheel(self):
        world = World()
        before = world.installed_paths()
        result = world.cli("--non-interactive", "--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Software Factory is installed.", result.stdout)
        self.assertIn("Verdict: ready with limitations", result.stdout)
        self.assertInstalled(world, before)
        self.assertNoCheckoutPaths(result.stdout, result.stderr)
        self.assertEqual(world.setup_calls(), [])
        self.assertNotIn(PREFERENCES, world.installed_paths())

    def test_b1_default_target_is_the_current_directory_and_a_non_root_is_refused(self):
        world = World()
        nested = world.project / "nested"
        nested.mkdir()
        before = world.snapshot()
        result = run(
            [ARTIFACTS.cli, "init", "--non-interactive", "--yes"], cwd=nested, environment=world.environment()
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("not the Git project root", result.stdout)
        self.assertUntouched(world, before)

    def test_b1_repeat_install_is_a_byte_identical_no_op(self):
        world = World()
        first = world.cli("--non-interactive", "--yes")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        before = world.snapshot()
        second = world.cli("--non-interactive", "--yes")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn("already installed", second.stdout)
        self.assertUntouched(world, before)

    def test_b1_bundled_installer_refuses_the_spec_factory_source_checkout(self):
        git_path = run([
            "git", "-C", REPOSITORY_ROOT, "rev-parse", "--git-path", "info/exclude"
        ])
        self.assertEqual(git_path.returncode, 0, git_path.stdout + git_path.stderr)
        exclude = Path(git_path.stdout.strip())
        if not exclude.is_absolute():
            exclude = REPOSITORY_ROOT / exclude
        exclude_before = exclude.read_bytes()
        manifest = REPOSITORY_ROOT / MANIFEST
        manifest_existed = manifest.exists()
        result = run(
            [
                sys.executable,
                "-B",
                PROJECT_ROOT / "src" / "specfactory" / "assets" / "scripts" / "install_factory.py",
                "--target",
                REPOSITORY_ROOT,
                "--dry-run",
            ],
            cwd=ARTIFACTS.work,
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("target is the Software Factory source checkout", result.stdout)
        self.assertEqual(exclude.read_bytes(), exclude_before)
        self.assertEqual(manifest.exists(), manifest_existed)


class B2GuidedInstallTests(WorldTestCase):
    def test_b2_plan_is_shown_then_one_install_approval_then_install(self):
        world = World()
        before = world.installed_paths()
        outcome = world.guided(["init"], ["y", ""])
        self.assertEqual(outcome["code"], 0, outcome["stdout"] + outcome["stderr"])
        install, models = outcome["prompts"]
        self.assertIn("Install the Software Factory files", install["prompt"])
        self.assertFalse(any(install["present"][path] for path in (*MANAGED, MANIFEST)))
        self.assertIn("Preset to configure now", models["prompt"])
        text = outcome["stdout"]
        self.assertLess(text.index("Software Factory plan (from the installer; dry run):"), text.index("Result:"))
        for relative in (*MANAGED, MANIFEST):
            self.assertRegex(text, rf"\[create\]\s+{re.escape(relative)}")
        self.assertRegex(text, r"Plan: \d+ create, 0 unchanged, 0 conflict")
        self.assertIn("Verdict: ready with limitations", text)
        self.assertIn("select 'Factory Lead'", text)
        self.assertIn("Not verified:", text)
        self.assertEqual(world.setup_calls(), [])
        self.assertInstalled(world, before)
        self.assertEqual(outcome["unused"], [])

    def test_b2_declining_the_install_approval_changes_nothing(self):
        world = World()
        before = world.snapshot()
        outcome = world.guided(["init"], ["n"])
        self.assertEqual(outcome["code"], 2, outcome["stdout"])
        self.assertEqual(len(outcome["prompts"]), 1)
        self.assertIn("Declined. Software Factory was not installed.", outcome["stdout"])
        self.assertUntouched(world, before)
        self.assertEqual(world.setup_calls(), [])

    def test_b2_not_ready_readiness_is_reported_as_such_and_not_rolled_back(self):
        world = World(copilot=False)
        hook = world.project / ".github" / "hooks" / "factory-policy.json"
        hook.parent.mkdir(parents=True)
        hook.write_text("{broken", encoding="utf-8")
        result = world.cli("--non-interactive", "--yes")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("readiness is NOT READY", result.stdout)
        self.assertIn("[INFO] tool-copilot:", result.stdout)
        self.assertIn("[FAIL] interactive-hooks:", result.stdout)
        self.assertNotIn("Software Factory is installed.", result.stdout)
        self.assertEqual(world.installed_paths() & INSTALLED, INSTALLED)

    def test_b2_missing_copilot_cli_is_optional_for_installed_chat_workflow(self):
        world = World(copilot=False)
        outcome = world.guided(["init"], ["y"])
        self.assertEqual(outcome["code"], 0, outcome["stdout"] + outcome["stderr"])
        self.assertIn("[INFO] tool-copilot:", outcome["stdout"])
        self.assertIn("use VS Code Copilot Chat (Copilot CLI is optional)", outcome["stdout"])
        self.assertIn("Verdict: ready with limitations", outcome["stdout"])


class B3MissingSpecKitTests(WorldTestCase):
    def test_b3_preview_with_missing_spec_kit_writes_nothing_and_runs_no_setup(self):
        world = World(speckit="missing")
        before = world.snapshot()
        for argv in (["--dry-run"], ["--non-interactive"]):
            with self.subTest(argv=argv):
                result = world.cli(*argv)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("Not ready to install", result.stdout)
                self.assertIn("initialize or repair it manually", result.stdout)
                self.assertNotIn("Initialize Spec Kit", result.stdout)
                self.assertNotIn("[y/N]", result.stdout)
        self.assertUntouched(world, before)
        self.assertEqual(world.setup_calls(), [])

    def test_b3_missing_spec_kit_never_offers_automatic_initialization(self):
        world = World(speckit="missing")
        before = world.snapshot()
        outcome = world.guided(["init"], [])
        self.assertEqual(outcome["code"], 2, outcome["stdout"])
        self.assertEqual(outcome["prompts"], [])
        self.assertIn("Automatic initialization is unavailable without --force", outcome["stdout"])
        self.assertIn("initialize or repair it manually", outcome["stdout"])
        self.assertIn("No project changes were made.", outcome["stdout"])
        self.assertUntouched(world, before)
        self.assertEqual(world.setup_calls(), [])

    def test_b3_git_only_project_is_not_offered_force_required_spec_kit_initialization(self):
        world = World(speckit="missing")
        before = world.snapshot()
        outcome = world.guided(["init"], [])
        self.assertEqual(outcome["code"], 2, outcome["stdout"])
        self.assertIn("without --force in a Git project", outcome["stdout"])
        self.assertEqual(outcome["prompts"], [])
        self.assertEqual(world.setup_calls(), [])
        self.assertUntouched(world, before)

    def test_b3_incomplete_spec_kit_is_never_repaired_or_force_reinitialized(self):
        world = World(speckit="incomplete")
        before = world.snapshot()
        outcome = world.guided(["init"], ["y", "y"])
        self.assertEqual(outcome["code"], 2, outcome["stdout"])
        self.assertEqual(outcome["prompts"], [])
        self.assertIn("Automatic initialization is unavailable without --force", outcome["stdout"])
        self.assertUntouched(world, before)
        self.assertEqual(world.setup_calls(), [])


class B4ManualSpecKitSetupTests(WorldTestCase):
    def test_b4_missing_spec_kit_requires_manual_setup_before_factory_install(self):
        world = World(speckit="missing")
        before = world.snapshot()
        outcome = world.guided(["init"], [])
        self.assertEqual(outcome["code"], 2, outcome["stdout"])
        self.assertEqual(outcome["prompts"], [])
        self.assertIn("initialize or repair it manually", outcome["stdout"])
        self.assertUntouched(world, before)
        self.assertEqual(world.setup_calls(), [])


class B8MissingSpecifyCliTests(WorldTestCase):
    def test_b8_declining_the_cli_install_invokes_nothing(self):
        world = World(speckit="missing", specify=False, uv=True)
        before = world.snapshot()
        outcome = world.guided(["init"], ["n"])
        self.assertEqual(outcome["code"], 2, outcome["stdout"])
        self.assertEqual([p["prompt"] for p in outcome["prompts"]], ["Install the Specify CLI now? [y/N]: "])
        self.assertIn("The Specify CLI was not installed.", outcome["stdout"])
        self.assertEqual(world.setup_calls(), [])
        self.assertUntouched(world, before)

    def test_b8_approved_cli_install_is_disclosed_rechecked_then_manual_setup_is_required(self):
        world = World(speckit="missing", specify=False, uv=True)
        world.add_tool("specify", staged=True)
        before = world.snapshot()
        outcome = world.guided(["init"], ["y"])
        self.assertEqual(outcome["code"], 2, outcome["stdout"] + outcome["stderr"])
        prompts = [p["prompt"] for p in outcome["prompts"]]
        self.assertEqual(len(prompts), 1)
        self.assertIn("Install the Specify CLI", prompts[0])
        self.assertIn("tool install specify-cli==1.0.6", outcome["stdout"])
        self.assertIn("official PyPI `specify-cli` package", outcome["stdout"])
        self.assertIn("initialize or repair it manually", outcome["stdout"])
        calls = world.setup_calls()
        self.assertEqual(
            [(tool, args) for tool, args, _ in calls],
            [("uv", ["tool", "install", "specify-cli==1.0.6"])],
        )
        entries = world.log()
        uv_index = next(i for i, e in enumerate(entries) if e["tool"] == "uv")
        after = [e["args"] for e in entries[uv_index + 1:]]
        self.assertIn(["--version"], after, "the CLI must be re-checked after installation")
        self.assertEqual({e["tool"] for e in entries}, {"uv", "specify"})
        self.assertUntouched(world, before)

    def test_b8_approved_cli_install_never_initializes_or_writes_project_files(self):
        world = World(speckit="missing", specify=False, uv=True)
        world.add_tool("specify", staged=True)
        before = world.snapshot()
        outcome = world.guided(["init"], ["y"])
        self.assertEqual(outcome["code"], 2, outcome["stdout"])
        self.assertEqual([tool for tool, _, _ in world.setup_calls()], ["uv"])
        self.assertIn("Changes made so far: installed the Specify CLI.", outcome["stdout"])
        self.assertIn("initialize or repair it manually", outcome["stdout"])
        self.assertUntouched(world, before)

    def test_b8_failed_cli_install_stops_without_spec_kit_or_factory_changes(self):
        world = World(speckit="missing", specify=False, uv=True)
        world.set_config(uv_fail=True)
        before = world.snapshot()
        outcome = world.guided(["init"], ["y"])
        self.assertEqual(outcome["code"], 1, outcome["stdout"])
        self.assertEqual(len(outcome["prompts"]), 1)
        self.assertEqual([tool for tool, _, _ in world.setup_calls()], ["uv"])
        self.assertUntouched(world, before)

    def test_b8_cli_not_on_path_after_install_stops_and_never_assumes_success(self):
        world = World(speckit="missing", specify=False, uv=True)
        world.set_config(uv_installs_specify=False)
        outcome = world.guided(["init"], ["y"])
        self.assertEqual(outcome["code"], 1, outcome["stdout"])
        self.assertEqual(len(outcome["prompts"]), 1)
        self.assertIn("still not on PATH", outcome["stdout"])
        self.assertEqual([tool for tool, _, _ in world.setup_calls()], ["uv"])

    def test_b8_missing_cli_and_missing_uv_is_a_refusal_with_no_prompt(self):
        world = World(speckit="missing", specify=False, uv=False)
        before = world.snapshot()
        outcome = world.guided(["init"], [])
        self.assertEqual(outcome["code"], 2, outcome["stdout"])
        self.assertEqual(outcome["prompts"], [])
        self.assertIn("uv is not available", outcome["stdout"])
        self.assertUntouched(world, before)


class B5NonInteractiveTests(WorldTestCase):
    def test_b5_without_authorization_is_preview_only(self):
        world = World()
        before = world.snapshot()
        result = world.cli("--non-interactive")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Preview only: nothing was changed. To apply, re-run with --non-interactive --yes.", result.stdout)
        self.assertNotIn("[y/N]", result.stdout)
        self.assertRegex(result.stdout, r"Plan: \d+ create, 0 unchanged, 0 conflict")
        self.assertUntouched(world, before)

    def test_b5_redirected_stdin_never_prompts_and_changes_nothing(self):
        world = World()
        before = world.snapshot()
        result = world.cli(input="y\ny\ny\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("input is not a terminal", result.stdout)
        self.assertNotIn("[y/N]", result.stdout)
        self.assertUntouched(world, before)

    def test_b5_null_device_stdin_never_approves_anything(self):
        # Windows reports NUL as a terminal; POSIX /dev/null is redirected input.
        world = World()
        before = world.snapshot()
        result = world.cli()
        if os.name == "nt":
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("Declined. Software Factory was not installed.", result.stdout)
        else:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("input is not a terminal", result.stdout)
        self.assertNotIn("Software Factory is installed.", result.stdout)
        self.assertUntouched(world, before)
        self.assertEqual(world.setup_calls(), [])

    def test_b5_dry_run_is_byte_identical_for_the_whole_project_including_git(self):
        world = World()
        before = world.snapshot()
        result = world.cli("--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("DRY RUN: nothing was changed", result.stdout)
        self.assertUntouched(world, before)
        self.assertEqual(world.setup_calls(), [])

    def test_b5_authorized_install_with_valid_prerequisites_installs(self):
        world = World()
        before = world.installed_paths()
        result = world.cli("--non-interactive", "--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertInstalled(world, before)

    def test_b5_authorization_never_initializes_spec_kit_or_installs_the_cli(self):
        for label, kwargs in (
            ("spec-kit-missing", {"speckit": "missing"}),
            ("specify-and-spec-kit-missing", {"speckit": "missing", "specify": False, "uv": True}),
        ):
            with self.subTest(case=label):
                world = World(**kwargs)
                before = world.snapshot()
                result = world.cli("--non-interactive", "--yes")
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertNotIn("[y/N]", result.stdout)
                self.assertIn("complete Spec Kit setup manually", result.stdout)
                self.assertUntouched(world, before)
                self.assertEqual(world.setup_calls(), [])

    def test_b5_contradictory_or_unpaired_flags_are_rejected_with_no_effect(self):
        world = World()
        before = world.snapshot()
        for arguments, message in (
            (("--dry-run", "--non-interactive", "--yes"), "--yes cannot be combined with --dry-run"),
            (("--yes",), "--yes is accepted only together with --non-interactive"),
            (("--force",), "unrecognized arguments: --force"),
        ):
            with self.subTest(arguments=arguments):
                result = world.cli(*arguments)
                self.assertEqual(result.returncode, 2)
                self.assertIn(message, result.stderr)
        self.assertUntouched(world, before)
        self.assertEqual(world.setup_calls(), [])


class B6ConflictAndModelTests(WorldTestCase):
    def test_b6_conflicting_paths_are_preserved_and_nothing_is_written(self):
        for label, runner in (
            ("non-interactive", lambda world: (world.cli("--non-interactive", "--yes"), None)),
            ("interactive", lambda world: (None, world.guided(["init"], ["y"]))),
        ):
            with self.subTest(mode=label):
                world = World()
                conflicts = {
                    ".github/agents/engineer.agent.md": b"my own engineer\n",
                    ".github/skills/factory-handoff/SKILL.md": b"my own skill\n",
                }
                for relative, data in conflicts.items():
                    path = world.project / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                before = world.snapshot()
                result, outcome = runner(world)
                code = result.returncode if result else outcome["code"]
                text = result.stdout if result else outcome["stdout"]
                self.assertEqual(code, 1, text)
                for relative in conflicts:
                    self.assertRegex(text, rf"\[conflict\]\s+{re.escape(relative)}")
                if outcome:
                    self.assertEqual(outcome["prompts"], [], "no install approval may be requested with conflicts")
                self.assertNotIn("Software Factory is installed.", text)
                self.assertUntouched(world, before)
                for relative, data in conflicts.items():
                    self.assertEqual((world.project / relative).read_bytes(), data)

    def test_b6_a_tracked_preferences_file_is_refused_with_guidance(self):
        world = World()
        path = world.project / PREFERENCES
        path.parent.mkdir()
        path.write_text('{"preset": "balanced", "tiers": {}}\n', encoding="utf-8")
        added = world.git("add", "-f", PREFERENCES)
        self.assertEqual(added.returncode, 0, added.stderr)
        before = world.snapshot()
        result = world.cli("--non-interactive", "--yes")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("already tracked by Git", result.stdout)
        self.assertIn("git rm --cached .factory/model-preferences.json", result.stdout)
        self.assertUntouched(world, before)

    def test_b6_existing_untracked_preferences_are_left_unchanged_and_not_echoed(self):
        world = World()
        path = world.project / PREFERENCES
        path.parent.mkdir()
        content = b'{"preset": "balanced", "tiers": {"balanced": "my-private-model"}}\n'
        path.write_bytes(content)
        result = world.cli("--non-interactive", "--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(path.read_bytes(), content)
        self.assertIn("Existing preferences were found and are left unchanged", result.stdout)
        self.assertNotIn("my-private-model", result.stdout + result.stderr)
        self.assertEqual(world.git("check-ignore", "--no-index", PREFERENCES).returncode, 0)

    def test_b6_guidance_lists_every_preset_mapping_exactly_as_the_helper_defines_them(self):
        world = World()
        result = world.cli("--non-interactive", "--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        installed_helper = (world.project / "scripts" / "specialist_models.py").read_text(encoding="utf-8")
        self.assertEqual(lf(installed_helper.encode()), lf((REPOSITORY_ROOT / "scripts" / "specialist_models.py").read_bytes()))
        for name, mapping in specialist_models.PRESETS.items():
            roles = ", ".join(f"{role}={tier}" for role, tier in mapping.items())
            marker = " (helper default)" if name == specialist_models.DEFAULT_PRESET else ""
            self.assertIn(f"  {name}{marker}: {roles}", result.stdout)
        self.assertIn("'quality-first' uses the 'quality' tier for every role and may cost more", result.stdout)
        self.assertIn("python scripts/specialist_models.py set-preset <preset>", result.stdout)
        self.assertIn("set-tier <tier> <model-id>", result.stdout)
        # Nothing was configured, and no model identifier appears in output or any new file.
        self.assertFalse((world.project / ".factory").exists())
        combined = result.stdout + result.stderr + "".join(
            (world.project / relative).read_text(encoding="utf-8", errors="replace") for relative in INSTALLED
        )
        self.assertIsNone(MODEL_IDENTIFIER.search(combined.encode("utf-8")))

    def test_b6_skipping_interactive_model_setup_creates_no_preferences(self):
        world = World()
        outcome = world.guided(["init"], ["y", ""])
        self.assertEqual(outcome["code"], 0, outcome["stdout"])
        self.assertIn("Model setup skipped", outcome["stdout"])
        self.assertFalse((world.project / ".factory").exists())

    def test_b6_each_preset_asks_only_for_its_own_tiers_and_writes_only_user_supplied_ids(self):
        for preset, mapping in specialist_models.PRESETS.items():
            with self.subTest(preset=preset):
                needed = [tier for tier in specialist_models.TIERS if tier in set(mapping.values())]
                world = World()
                answers = ["y", preset] + [f"user-model-{tier}" for tier in needed] + ["y"]
                outcome = world.guided(["init"], answers)
                self.assertEqual(outcome["code"], 0, outcome["stdout"] + outcome["stderr"])
                asked = [
                    re.search(r"tier '(\w+)'", p["prompt"]).group(1)
                    for p in outcome["prompts"] if "Model ID or display name for tier" in p["prompt"]
                ]
                self.assertEqual(asked, needed, "no tier outside the preset's mapping may be requested")
                self.assertEqual(outcome["unused"], [])
                preferences = json.loads((world.project / PREFERENCES).read_text(encoding="utf-8"))
                self.assertEqual(preferences["preset"], preset)
                for tier in specialist_models.TIERS:
                    expected = f"user-model-{tier}" if tier in needed else None
                    self.assertEqual(preferences["tiers"].get(tier), expected)
                self.assertEqual(world.git("check-ignore", "--no-index", PREFERENCES).returncode, 0)
                status = world.git("status", "--porcelain", "--untracked-files=all").stdout
                self.assertNotIn("model-preferences", status)

    def test_b6_declining_the_preferences_write_creates_nothing(self):
        world = World()
        outcome = world.guided(["init"], ["y", "balanced", "user-model", "n"])
        self.assertEqual(outcome["code"], 0, outcome["stdout"])
        self.assertIn("Declined; preferences were not created.", outcome["stdout"])
        self.assertFalse((world.project / ".factory").exists())

    def test_b6_an_invalid_model_id_is_ignored_and_creates_nothing(self):
        world = World()
        outcome = world.guided(["init"], ["y", "balanced", "--bad id--"])
        self.assertEqual(outcome["code"], 0, outcome["stdout"])
        self.assertIn("is not a valid model ID", outcome["stdout"])
        self.assertFalse((world.project / ".factory").exists())


if __name__ == "__main__":
    unittest.main()
