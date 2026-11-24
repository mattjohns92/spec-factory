import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import validate_specialist_profiles as validator_module  # noqa: E402

VALIDATOR = REPOSITORY_ROOT / "scripts" / "validate_specialist_profiles.py"
PROFILE_PATHS = (
    "factory-lead.agent.md",
    "architect.agent.md",
    "engineer.agent.md",
    "qa-engineer.agent.md",
    "code-reviewer.agent.md",
)


class SpecialistProfileValidatorTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.agent_directory = self.root / ".github" / "agents"
        self.agent_directory.mkdir(parents=True)
        for profile_path in PROFILE_PATHS:
            self.write_profile(profile_path)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def write_profile(self, profile_path, frontmatter=None):
        if frontmatter is None:
            if profile_path == "code-reviewer.agent.md":
                frontmatter = (
                    "name: Code Reviewer\n"
                    "description: Reviews approved changes.\n"
                    "strict-tools-list: true\n"
                    "tools: [read, grep, glob]"
                )
            else:
                frontmatter = (
                    f"name: {profile_path.removesuffix('.agent.md')}\n"
                    "description: Specialist profile."
                )
        path = self.agent_directory / profile_path
        path.write_text(f"---\n{frontmatter}\n---\nProfile instructions.\n", encoding="utf-8")
        return path

    def run_validator(self, root=None):
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--root", str(root or self.root)],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_repository_profiles_are_valid(self):
        result = self.run_validator(REPOSITORY_ROOT)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("valid", result.stdout.lower())

    def test_valid_fixture_passes(self):
        result = self.run_validator()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("valid", result.stdout.lower())

    def test_reports_multiple_missing_profiles(self):
        for profile_path in ("architect.agent.md", "engineer.agent.md"):
            (self.agent_directory / profile_path).unlink()

        result = self.run_validator()

        self.assertEqual(result.returncode, 1)
        self.assertIn(".github/agents/architect.agent.md", result.stderr)
        self.assertIn(".github/agents/engineer.agent.md", result.stderr)

    def test_reports_malformed_yaml_and_non_mapping_frontmatter(self):
        self.write_profile("factory-lead.agent.md", "name: [unfinished")
        self.write_profile("architect.agent.md", "- a sequence, not a mapping")

        result = self.run_validator()

        self.assertEqual(result.returncode, 1)
        self.assertIn(".github/agents/factory-lead.agent.md", result.stderr)
        self.assertIn(".github/agents/architect.agent.md", result.stderr)

    def test_reports_absent_and_unclosed_frontmatter(self):
        absent_path = self.agent_directory / "factory-lead.agent.md"
        absent_path.write_text("Profile without metadata.\n", encoding="utf-8")
        unclosed_path = self.agent_directory / "architect.agent.md"
        unclosed_path.write_text(
            "---\nname: Architect\ndescription: Specialist profile.\n",
            encoding="utf-8",
        )

        result = self.run_validator()

        self.assertEqual(result.returncode, 1)
        self.assertIn(".github/agents/factory-lead.agent.md", result.stderr)
        self.assertIn(".github/agents/architect.agent.md", result.stderr)
        self.assertGreaterEqual(result.stderr.count("frontmatter"), 2)

    def test_rejects_missing_empty_and_wrong_type_required_metadata(self):
        self.write_profile(
            "factory-lead.agent.md",
            "description: Missing name.",
        )
        self.write_profile(
            "architect.agent.md",
            "name: ''\ndescription: Empty name.",
        )
        self.write_profile(
            "engineer.agent.md",
            "name: 42\ndescription: Specialist profile.",
        )
        self.write_profile(
            "qa-engineer.agent.md",
            "name: QA Engineer\ndescription: 42",
        )

        result = self.run_validator()

        self.assertEqual(result.returncode, 1)
        for profile_path in PROFILE_PATHS[:4]:
            self.assertIn(f".github/agents/{profile_path}", result.stderr)

    def test_rejects_missing_and_empty_descriptions(self):
        self.write_profile("architect.agent.md", "name: Architect")
        self.write_profile(
            "engineer.agent.md",
            "name: Engineer\ndescription: ''",
        )

        result = self.run_validator()

        self.assertEqual(result.returncode, 1)
        self.assertIn(".github/agents/architect.agent.md", result.stderr)
        self.assertIn(".github/agents/engineer.agent.md", result.stderr)
        self.assertGreaterEqual(result.stderr.count("'description'"), 2)

    def test_rejects_invalid_reviewer_strict_flag_and_additional_tools(self):
        self.write_profile(
            "code-reviewer.agent.md",
            "name: Code Reviewer\n"
            "description: Reviews approved changes.\n"
            "strict-tools-list: false\n"
            "tools: [read, grep, glob, edit]",
        )

        result = self.run_validator()

        self.assertEqual(result.returncode, 1)
        self.assertIn(".github/agents/code-reviewer.agent.md", result.stderr)
        self.assertIn("strict-tools-list", result.stderr)
        self.assertIn("tools", result.stderr.lower())

    def test_rejects_missing_reviewer_tools(self):
        self.write_profile(
            "code-reviewer.agent.md",
            "name: Code Reviewer\n"
            "description: Reviews approved changes.\n"
            "strict-tools-list: true",
        )

        result = self.run_validator()

        self.assertEqual(result.returncode, 1)
        self.assertIn(".github/agents/code-reviewer.agent.md", result.stderr)
        self.assertIn("tools", result.stderr.lower())

    def test_rejects_non_list_reviewer_tools(self):
        self.write_profile(
            "code-reviewer.agent.md",
            "name: Code Reviewer\n"
            "description: Reviews approved changes.\n"
            "strict-tools-list: true\n"
            "tools: read",
        )

        result = self.run_validator()

        self.assertEqual(result.returncode, 1)
        self.assertIn(".github/agents/code-reviewer.agent.md", result.stderr)
        self.assertIn("tools", result.stderr.lower())

    def test_rejects_non_string_reviewer_tool_entries(self):
        self.write_profile(
            "code-reviewer.agent.md",
            "name: Code Reviewer\n"
            "description: Reviews approved changes.\n"
            "strict-tools-list: true\n"
            "tools: [read, 42, glob]",
        )

        result = self.run_validator()

        self.assertEqual(result.returncode, 1)
        self.assertIn(".github/agents/code-reviewer.agent.md", result.stderr)
        self.assertIn("every entry in 'tools' must be a string", result.stderr)

    def test_rejects_incomplete_reviewer_tools(self):
        self.write_profile(
            "code-reviewer.agent.md",
            "name: Code Reviewer\n"
            "description: Reviews approved changes.\n"
            "strict-tools-list: true\n"
            "tools: [read, grep]",
        )

        result = self.run_validator()

        self.assertEqual(result.returncode, 1)
        self.assertIn(".github/agents/code-reviewer.agent.md", result.stderr)
        self.assertIn("exactly read, grep, and glob", result.stderr)

    def test_rejects_duplicate_reviewer_tools(self):
        self.write_profile(
            "code-reviewer.agent.md",
            "name: Code Reviewer\n"
            "description: Reviews approved changes.\n"
            "strict-tools-list: true\n"
            "tools: [read, grep, glob, read]",
        )

        result = self.run_validator()

        self.assertEqual(result.returncode, 1)
        self.assertIn(".github/agents/code-reviewer.agent.md", result.stderr)
        self.assertIn("duplicate", result.stderr.lower())

    def test_invalid_root_returns_usage_error(self):
        result = self.run_validator(self.root / "missing")

        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stderr)

    def test_existing_directory_without_agent_directory_returns_usage_error(self):
        empty_root = Path(self.temporary_directory.name, "empty-repository")
        empty_root.mkdir()
        result = self.run_validator(empty_root)

        self.assertEqual(result.returncode, 2)
        self.assertIn(".github/agents", result.stderr)


SHIPPED_FILES = tuple(f".github/agents/{name}" for name in PROFILE_PATHS) + (
    ".github/skills/factory-handoff/SKILL.md",
)
UNSUPPORTED = "unsupported frontmatter syntax"
REVIEWER = ".github/agents/code-reviewer.agent.md"


class FallbackParserTests(unittest.TestCase):
    """The built-in frontmatter parser used when PyYAML is not importable."""

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        (self.root / ".github" / "agents").mkdir(parents=True)
        for name in PROFILE_PATHS:
            self.write_profile(name)

    def write_profile(self, name, frontmatter=None):
        if frontmatter is None:
            if name == "code-reviewer.agent.md":
                frontmatter = (
                    "name: Code Reviewer\n"
                    "description: Reviews approved changes.\n"
                    "strict-tools-list: true\n"
                    'tools: ["read", "grep", "glob"]'
                )
            else:
                frontmatter = f"name: {name.removesuffix('.agent.md')}\ndescription: Specialist profile."
        path = self.root / ".github" / "agents" / name
        path.write_text(f"---\n{frontmatter}\n---\nBody.\n", encoding="utf-8")

    def fallback_findings(self):
        with mock.patch.object(validator_module, "yaml", None):
            return validator_module.validate_profiles(self.root)

    def parse(self, relative, content, use_yaml):
        findings = []
        if use_yaml:
            metadata = validator_module._frontmatter(content, relative, findings)
        else:
            with mock.patch.object(validator_module, "yaml", None):
                metadata = validator_module._frontmatter(content, relative, findings)
        return metadata, findings

    # parity
    def test_pyyaml_and_fallback_agree_on_all_shipped_files(self):
        if validator_module.yaml is None:
            self.skipTest("PyYAML is not installed; parity cannot be compared")
        for relative in SHIPPED_FILES:
            with self.subTest(relative=relative):
                content = (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")
                with_yaml, yaml_findings = self.parse(relative, content, use_yaml=True)
                without_yaml, fallback_findings = self.parse(relative, content, use_yaml=False)
                self.assertEqual(yaml_findings, [])
                self.assertEqual(fallback_findings, [])
                self.assertIsInstance(with_yaml, dict)
                self.assertEqual(without_yaml, with_yaml)
                self.assertTrue(without_yaml["name"].strip())
                self.assertTrue(without_yaml["description"].strip())

    def test_shipped_profiles_validate_without_pyyaml(self):
        with mock.patch.object(validator_module, "yaml", None):
            findings = validator_module.validate_profiles(REPOSITORY_ROOT)
        self.assertEqual(findings, [])

    def test_fallback_parses_supported_subset(self):
        content = (
            "---\nname: Example\ndescription: 'single quoted'\nflag: true\nother: false\n"
            'tools: ["a", "b"]\nlabel: "double"\n\n---\nBody\n'
        )
        metadata, findings = self.parse("x.md", content, use_yaml=False)
        self.assertEqual(findings, [])
        self.assertEqual(
            metadata,
            {
                "name": "Example",
                "description": "single quoted",
                "flag": True,
                "other": False,
                "tools": ["a", "b"],
                "label": "double",
            },
        )
        if validator_module.yaml is not None:
            self.assertEqual(metadata, self.parse("x.md", content, use_yaml=True)[0])

    PARITY_INPUTS = (
        "off: false",
        "description: Note:",
        "x: 2026-01-01",
        "x: 0x1f",
        "x: 1:30",
        "x: .inf",
        "x: '''''",
        "x: \"a\"\u00a0",
    )

    def test_fallback_keeps_trailing_non_breaking_space_like_pyyaml(self):
        if validator_module.yaml is None:
            self.skipTest("PyYAML is not installed; parity cannot be compared")
        content = "---\nx: a\u00a0\n---\nBody\n"
        expected, _ = self.parse("x.md", content, use_yaml=True)
        actual, _ = self.parse("x.md", content, use_yaml=False)
        self.assertEqual(actual, expected)
        self.assertEqual(actual, {"x": "a\u00a0"})

    def test_fallback_never_returns_a_different_mapping_than_pyyaml(self):
        if validator_module.yaml is None:
            self.skipTest("PyYAML is not installed; parity cannot be compared")
        for frontmatter in self.PARITY_INPUTS:
            with self.subTest(frontmatter=frontmatter):
                content = f"---\n{frontmatter}\n---\nBody\n"
                expected, _ = self.parse("x.md", content, use_yaml=True)
                actual, findings = self.parse("x.md", content, use_yaml=False)
                if actual is None:
                    self.assertTrue(any(UNSUPPORTED in f for f in findings), findings)
                else:
                    self.assertEqual(actual, expected)

    def test_fallback_reports_unsupported_syntax_for_yaml_resolved_values(self):
        inputs = self.PARITY_INPUTS + (
            "On: x", "NULL: x", "y: x", "n: x", "_a: x", "1a: x",
            "x: True", "x: NO", "x: Null", "x: ~",
            "x: 'a''b'", "x: 'a' 'b'", 'x: "a" tail', 'x: "unclosed', "x: 'unclosed",
            'x: "\\ud83d\\ude00"', 'x: "\\x41"', 'x: ["a", 1]', 'x: ["a",]', "x: [a]",
            "x: a #c", "x: a: b", "x: a\tb", "x:\ta", "x: -1", "x: 1.5", "x: 1e3", "x: +1",
            "x: a\x00b",
        )
        for frontmatter in inputs:
            with self.subTest(frontmatter=frontmatter):
                content = f"---\n{frontmatter}\n---\nBody\n"
                metadata, findings = self.parse("x.md", content, use_yaml=False)
                self.assertIsNone(metadata)
                self.assertEqual(len(findings), 1, findings)
                self.assertIn(UNSUPPORTED, findings[0])

    def test_fallback_still_reports_missing_delimiters(self):
        metadata, findings = self.parse("x.md", "name: x\n", use_yaml=False)
        self.assertIsNone(metadata)
        self.assertIn("opening delimiter", findings[0])
        metadata, findings = self.parse("x.md", "---\nname: x\n", use_yaml=False)
        self.assertIsNone(metadata)
        self.assertIn("closing delimiter", findings[0])

    # unsupported syntax
    def test_fallback_rejects_unsupported_syntax(self):
        cases = {
            "block list": 'name: X\ndescription: d\ntools:\n  - "read"\n  - "grep"',
            "nested mapping": "name: X\ndescription: d\nextra:\n  inner: value",
            "comment line": "# a comment\nname: X\ndescription: d",
            "indented comment": "name: X\n  # a comment\ndescription: d",
            "block scalar": "name: X\ndescription: |\n  folded text",
            "flow mapping": "name: X\ndescription: {a: b}",
            "anchor": "name: X\ndescription: &anchor d",
            "yaml null word": "name: X\ndescription: null",
            "unquoted list items": "name: X\ndescription: d\ntools: [read, grep]",
            "number scalar": "name: 42\ndescription: d",
            "bare key": "name: X\ndescription: d\nnovalue",
        }
        for label, frontmatter in cases.items():
            with self.subTest(case=label):
                path = self.root / ".github" / "agents" / "factory-lead.agent.md"
                path.write_text(f"---\n{frontmatter}\n---\nBody\n", encoding="utf-8")
                findings = self.fallback_findings()
                matching = [f for f in findings if "factory-lead.agent.md" in f]
                self.assertEqual(len(matching), 1, findings)
                self.assertIn(UNSUPPORTED, matching[0])
                self.assertIn("install PyYAML", matching[0])

    def test_unsupported_syntax_never_passes_silently(self):
        self.write_profile("architect.agent.md", "name: A\n# comment\ndescription: d")
        findings = self.fallback_findings()
        self.assertTrue(any(UNSUPPORTED in finding for finding in findings), findings)
        with mock.patch.object(validator_module, "yaml", None), \
                mock.patch("sys.stderr", new=io.StringIO()):
            exit_code = validator_module.main(["--root", str(self.root)])
        self.assertEqual(exit_code, 1)

    def test_cli_with_fallback_reports_unsupported_syntax_to_stderr(self):
        self.write_profile("architect.agent.md", "name: A\ndescription: d\ntools:\n  - read")
        stderr = io.StringIO()
        with mock.patch.object(validator_module, "yaml", None), \
                mock.patch("sys.stderr", new=stderr):
            exit_code = validator_module.main(["--root", str(self.root)])
        self.assertEqual(exit_code, 1)
        self.assertIn(".github/agents/architect.agent.md", stderr.getvalue())
        self.assertIn(UNSUPPORTED, stderr.getvalue())

    # reviewer tool restrictions without PyYAML
    def reviewer(self, tools, strict="true"):
        lines = ["name: Code Reviewer", "description: Reviews approved changes."]
        if strict is not None:
            lines.append(f"strict-tools-list: {strict}")
        if tools is not None:
            lines.append(f"tools: {tools}")
        self.write_profile("code-reviewer.agent.md", "\n".join(lines))
        return [f for f in self.fallback_findings() if REVIEWER in f]

    def test_fallback_accepts_exact_reviewer_tools_in_any_order(self):
        self.assertEqual(self.reviewer('["read", "grep", "glob"]'), [])
        self.assertEqual(self.reviewer('["glob", "read", "grep"]'), [])

    def test_fallback_rejects_extra_reviewer_tool(self):
        findings = self.reviewer('["read", "grep", "glob", "edit"]')
        self.assertTrue(any("exactly read, grep, and glob" in f for f in findings), findings)

    def test_fallback_rejects_incomplete_reviewer_tools(self):
        findings = self.reviewer('["read", "grep"]')
        self.assertTrue(any("exactly read, grep, and glob" in f for f in findings), findings)

    def test_fallback_rejects_duplicate_reviewer_tools(self):
        findings = self.reviewer('["read", "grep", "glob", "read"]')
        self.assertTrue(any("duplicate" in f.lower() for f in findings), findings)

    def test_fallback_rejects_non_string_reviewer_tool_entries(self):
        # Inline lists may hold only double-quoted strings; anything else is unsupported syntax.
        findings = self.reviewer('["read", 42, "glob"]')
        self.assertTrue(any(UNSUPPORTED in f for f in findings), findings)

    def test_fallback_rejects_non_list_and_missing_reviewer_tools(self):
        findings = self.reviewer("read")
        self.assertTrue(any("'tools' must be a list" in f for f in findings), findings)
        findings = self.reviewer(None)
        self.assertTrue(any("'tools' must be a list" in f for f in findings), findings)

    def test_fallback_enforces_strict_tools_list(self):
        for strict in ("false", None):
            with self.subTest(strict=strict):
                findings = self.reviewer('["read", "grep", "glob"]', strict=strict)
                self.assertTrue(any("'strict-tools-list' must be true" in f for f in findings), findings)

    def test_fallback_still_requires_name_and_description(self):
        self.write_profile("architect.agent.md", "description: Missing name.")
        self.write_profile("engineer.agent.md", 'name: ""\ndescription: Empty name.')
        findings = self.fallback_findings()
        self.assertTrue(any("architect.agent.md" in f and "'name'" in f for f in findings), findings)
        self.assertTrue(any("engineer.agent.md" in f and "'name'" in f for f in findings), findings)

    def test_pyyaml_behavior_unchanged_when_available(self):
        if validator_module.yaml is None:
            self.skipTest("PyYAML is not installed")
        self.write_profile(
            "code-reviewer.agent.md",
            "name: Code Reviewer\ndescription: Reviews.\nstrict-tools-list: true\n"
            "tools:\n  - read\n  - grep\n  - glob",
        )
        self.assertEqual(validator_module.validate_profiles(self.root), [])
        self.assertTrue(any(UNSUPPORTED in f for f in self.fallback_findings()))


if __name__ == "__main__":
    unittest.main()
