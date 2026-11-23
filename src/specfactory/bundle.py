"""Locate and load the bundled, versioned interactive assets."""

import importlib.util
from importlib import resources
from pathlib import Path
import sys

# Mirrors the engine's layout: the engine treats the parent of its own scripts/ directory as the source.
BUNDLED_ASSETS = (
    "BUNDLE_VERSION",
    ".github/agents/factory-lead.agent.md",
    ".github/agents/architect.agent.md",
    ".github/agents/engineer.agent.md",
    ".github/agents/qa-engineer.agent.md",
    ".github/agents/code-reviewer.agent.md",
    ".github/skills/factory-handoff/SKILL.md",
    "scripts/install_factory.py",
    "scripts/check_factory_readiness.py",
    "scripts/validate_specialist_profiles.py",
    "scripts/specialist_models.py",
)

_modules = {}


def asset_root():
    return Path(str(resources.files("specfactory").joinpath("assets")))


def missing_assets(root=None):
    root = asset_root() if root is None else Path(root)
    return [name for name in BUNDLED_ASSETS if not (root / name).is_file()]


def load_script(name):
    """Import a bundled script under a private module name, without writing bytecode."""
    if name in _modules:
        return _modules[name]
    path = asset_root() / "scripts" / f"{name}.py"
    module_name = f"specfactory_bundled_{name}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    finally:
        sys.dont_write_bytecode = previous
    _modules[name] = module
    return module
