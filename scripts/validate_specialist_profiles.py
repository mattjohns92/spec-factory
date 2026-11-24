import argparse
import json
from pathlib import Path
import re
import sys

try:
    import yaml
except ImportError:
    yaml = None


PROFILE_PATHS = (
    "factory-lead.agent.md",
    "architect.agent.md",
    "engineer.agent.md",
    "qa-engineer.agent.md",
    "code-reviewer.agent.md",
)
REVIEWER_PROFILE = "code-reviewer.agent.md"
REVIEWER_TOOLS = {"read", "grep", "glob"}

_KEY_LINE = re.compile(r"([A-Za-z][A-Za-z0-9_-]*):(?: +(.*))?")
_YAML_WORD = re.compile(r"(?:true|false|yes|no|on|off|null|y|n|~)", re.IGNORECASE)
_PRINTABLE = re.compile("[\x20-\x7e\xa0-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]*")
_PLAIN_INDICATOR = re.compile(r":[ \t]|[ \t]#|:$")
_SURROGATE_ESCAPE = re.compile(r"\\u[dD][89a-fA-F]")


class _Unsupported(Exception):
    pass


def _fallback_scalar(text):
    # The fallback accepts only what PyYAML parses identically; everything else is unsupported.
    text = (text or "").strip(" ")
    if not text:
        raise _Unsupported
    if text[0] == '"' or text[0] == "[":
        if _SURROGATE_ESCAPE.search(text):
            raise _Unsupported
        try:
            value = json.loads(text)
        except ValueError:
            raise _Unsupported from None
        if text[0] == '"':
            strings = [value]
        elif isinstance(value, list):
            strings = value
        else:
            raise _Unsupported
        if not all(isinstance(item, str) for item in strings):
            raise _Unsupported
        return value
    if text[0] == "'":
        if len(text) < 2 or text[-1] != "'" or "'" in text[1:-1]:
            raise _Unsupported
        return text[1:-1]
    if text in ("true", "false"):
        return text == "true"
    if not text[0].isascii() or not text[0].isalpha() or _PLAIN_INDICATOR.search(text):
        raise _Unsupported
    if _YAML_WORD.fullmatch(text):
        raise _Unsupported
    return text


def _fallback_metadata(lines):
    metadata = {}
    for line in lines:
        if not line.strip(" "):
            continue
        if not _PRINTABLE.fullmatch(line):
            raise _Unsupported
        match = _KEY_LINE.fullmatch(line.rstrip(" \t"))
        if match is None or _YAML_WORD.fullmatch(match.group(1)):
            raise _Unsupported
        metadata[match.group(1)] = _fallback_scalar(match.group(2))
    if not metadata:
        raise _Unsupported
    return metadata


def _frontmatter(content, relative_path, findings):
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        findings.append(f"{relative_path}: missing YAML frontmatter opening delimiter '---'")
        return None

    closing_index = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"),
        None,
    )
    if closing_index is None:
        findings.append(f"{relative_path}: missing YAML frontmatter closing delimiter '---'")
        return None

    if yaml is None:
        try:
            return _fallback_metadata(lines[1:closing_index])
        except _Unsupported:
            findings.append(
                f"{relative_path}: unsupported frontmatter syntax; install PyYAML to validate"
            )
            return None

    try:
        metadata = yaml.safe_load("\n".join(lines[1:closing_index]))
    except yaml.YAMLError as error:
        detail = getattr(error, "problem", None) or str(error).splitlines()[0]
        findings.append(f"{relative_path}: invalid YAML frontmatter: {detail}")
        return None

    if not isinstance(metadata, dict):
        findings.append(f"{relative_path}: YAML frontmatter must be a mapping")
        return None
    return metadata


def _validate_profile(profile_path, relative_path, findings):
    try:
        content = profile_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        findings.append(f"{relative_path}: unable to read profile: {error}")
        return

    metadata = _frontmatter(content, relative_path, findings)
    if metadata is None:
        return

    for field in ("name", "description"):
        value = metadata.get(field)
        if not isinstance(value, str) or not value.strip():
            findings.append(f"{relative_path}: '{field}' must be a non-empty string")

    if relative_path != f".github/agents/{REVIEWER_PROFILE}":
        return

    if metadata.get("strict-tools-list") is not True:
        findings.append(f"{relative_path}: 'strict-tools-list' must be true")

    tools = metadata.get("tools")
    if not isinstance(tools, list):
        findings.append(f"{relative_path}: 'tools' must be a list")
        return
    if any(not isinstance(tool, str) for tool in tools):
        findings.append(f"{relative_path}: every entry in 'tools' must be a string")
        return
    if len(tools) != len(set(tools)):
        findings.append(f"{relative_path}: 'tools' must not contain duplicate entries")
    if len(tools) != len(REVIEWER_TOOLS) or set(tools) != REVIEWER_TOOLS:
        findings.append(
            f"{relative_path}: 'tools' must contain exactly read, grep, and glob"
        )


def validate_profiles(repository_root):
    findings = []
    for filename in PROFILE_PATHS:
        relative_path = f".github/agents/{filename}"
        _validate_profile(repository_root / relative_path, relative_path, findings)
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate specialist Copilot agent profiles.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository root to validate (defaults to the repository containing this script)",
    )
    arguments = parser.parse_args(argv)
    repository_root = arguments.root.expanduser()
    if not repository_root.is_dir() or not (repository_root / ".github" / "agents").is_dir():
        parser.error(f"--root must contain a .github/agents directory: {repository_root}")

    findings = validate_profiles(repository_root)
    if findings:
        print("Specialist profile validation failed:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        return 1

    print("All five specialist profiles are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
