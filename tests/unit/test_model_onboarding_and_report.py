"""v0.1.2: first-run model setup, telemetry wording, and delegation guidance."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SPECIALIST_MODELS = REPOSITORY_ROOT / "scripts" / "specialist_models.py"
LEAD = REPOSITORY_ROOT / ".github" / "agents" / "factory-lead.agent.md"
HANDOFF = REPOSITORY_ROOT / ".github" / "skills" / "factory-handoff" / "SKILL.md"
ROLES = ("architect", "engineer", "qa-engineer", "code-reviewer")


def normalized(path):
    return " ".join(path.read_text(encoding="utf-8").split()).lower()


class HelperTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.config_path = Path(self.temporary_directory.name) / "config.json"
        self.events_path = Path(self.temporary_directory.name) / "events.jsonl"

    def run_script(self, args):
        return subprocess.run(
            [sys.executable, str(SPECIALIST_MODELS), "--config", str(self.config_path), *args],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )


class FirstRunModelConfigurationTests(HelperTestCase):
    def test_unresolved_models_exit_3_and_point_to_shared_setup(self):
        for role in ROLES:
            with self.subTest(role=role):
                result = self.run_script(["resolve", role])
                self.assertEqual(result.returncode, 3)
                self.assertEqual(result.stdout, "")
                self.assertIn("set-shared", result.stderr)
        self.assertFalse(self.config_path.exists(), "resolve must not create configuration")

    def test_status_does_not_configure_anything(self):
        self.assertEqual(self.run_script(["status"]).returncode, 0)
        self.assertFalse(self.config_path.exists())

    def test_set_shared_resolves_every_role_to_one_model(self):
        result = self.run_script(["set-shared", "runtime-model-1"])
        self.assertEqual(result.returncode, 0, result.stderr)
        for role in ROLES:
            resolved = self.run_script(["resolve", role])
            self.assertEqual(resolved.returncode, 0)
            self.assertEqual(resolved.stdout.strip(), "runtime-model-1")
        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["preset"], "balanced")
        self.assertEqual(saved["tiers"]["balanced"], "runtime-model-1")

    def test_role_override_wins_over_shared_model(self):
        self.run_script(["set-shared", "runtime-model-1"])
        self.assertEqual(self.run_script(["set-override", "qa-engineer", "runtime-model-2"]).returncode, 0)
        self.assertEqual(self.run_script(["resolve", "qa-engineer"]).stdout.strip(), "runtime-model-2")
        self.assertEqual(self.run_script(["resolve", "engineer"]).stdout.strip(), "runtime-model-1")

    def test_set_shared_rejects_invalid_identifier_without_writing(self):
        result = self.run_script(["set-shared", "bad id!"])
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.config_path.exists())

    def test_set_shared_preserves_existing_overrides(self):
        self.run_script(["set-override", "architect", "keep-me"])
        self.run_script(["set-shared", "runtime-model-1"])
        self.assertEqual(self.run_script(["resolve", "architect"]).stdout.strip(), "keep-me")

    def test_display_label_is_accepted_but_warned_about(self):
        for args in (
            ["set-shared", "Claude Sonnet 5.5 (copilot)"],
            ["set-tier", "balanced", "Claude Sonnet 5.5 (copilot)"],
            ["set-override", "engineer", "Some Label"],
        ):
            with self.subTest(args=args):
                result = self.run_script(args)
                self.assertEqual(result.returncode, 0)
                self.assertIn("display label", result.stderr)

    def test_runtime_style_identifier_is_not_warned_about(self):
        for args in (
            ["set-shared", "claude-sonnet-5.5"],
            ["set-tier", "quality", "vendor/model:1.0"],
            ["set-override", "engineer", "model-x"],
        ):
            with self.subTest(args=args):
                result = self.run_script(args)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stderr, "")

    def test_helper_bundles_no_model_identifiers(self):
        text = SPECIALIST_MODELS.read_text(encoding="utf-8").lower()
        for vendor in ("claude-", "gpt-", "gemini-"):
            self.assertNotIn(vendor, text)


class FirstRunGuidanceTests(unittest.TestCase):
    def test_lead_and_handoff_describe_owner_approved_first_run_setup(self):
        for path in (LEAD, HANDOFF):
            text = normalized(path)
            for phrase in (
                "optional until",
                "not a copilot display label",
                "set-shared",
                "set-override",
                "explicit owner approval",
                "run `resolve <role>` to verify",
                "do not invent",
                "expensive model",
                "report it exactly" if path is HANDOFF else "report the rejection exactly",
            ):
                self.assertIn(phrase, text, f"{path.name} is missing: {phrase}")

    def test_guidance_prefers_scoped_evidence_backed_delegation_without_hard_limits(self):
        for path in (LEAD, HANDOFF):
            text = normalized(path)
            for phrase in (
                "paths in scope",
                "specific questions",
                "relevant source files before any broad repository search",
                "evidence-backed findings",
                "sufficient evidence",
                "arbitrary numeric limits",
            ):
                self.assertIn(phrase, text, f"{path.name} is missing: {phrase}")

    def test_guidance_states_telemetry_limits(self):
        for path in (LEAD, HANDOFF):
            text = normalized(path)
            for phrase in (
                "`totaltokens`",
                "unknown composition and cost",
                "do not present it as a billable cost or infer cache use",
                "`totaltoolcalls`",
                "parent session used the same model",
                "not evidence of a visible ui prompt",
            ):
                self.assertIn(phrase, text, f"{path.name} is missing: {phrase}")


def start(call_id="call-1", agent="Architect", **extra):
    data = {
        "toolCallId": call_id,
        "agentName": agent,
        "taskModelSource": "task_argument",
        "modelSelectionSource": "explicit_override",
    }
    data.update(extra)
    return {"type": "subagent.started", "agentId": "agent-1", "data": data}


def complete(call_id="call-1", agent="Architect", **extra):
    data = {"toolCallId": call_id, "agentName": agent}
    data.update(extra)
    return {"type": "subagent.completed", "agentId": "agent-1", "data": data}


def parent_model(name):
    return {"type": "session.model_change", "data": {"newModel": name}}


class TelemetryReportTests(HelperTestCase):
    def report(self, events):
        self.events_path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")
        text = self.run_script(["report", "--events", str(self.events_path)])
        as_json = self.run_script(["report", "--events", str(self.events_path), "--json"])
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertEqual(as_json.returncode, 0, as_json.stderr)
        return text.stdout, json.loads(as_json.stdout)

    def single(self, events):
        stdout, data = self.report(events)
        self.assertEqual(len(data["delegations"]), 1)
        return stdout, data["delegations"][0]

    def test_tokens_are_labelled_runtime_reported_with_unknown_composition_and_cost(self):
        stdout, item = self.single([
            start(model="m-1"),
            complete(model="m-1", explicitModelOverride="m-1", totalTokens=900, totalToolCalls=7, durationMs=50),
        ])
        self.assertIn("totalTokens: 900 (runtime-reported total; composition and cost unknown)", stdout)
        self.assertIn("totalToolCalls: 7", stdout)
        self.assertEqual(item["totalToolCalls"], 7)
        self.assertIn("composition and cost unknown", item["totalTokensNote"])

    def test_report_never_invents_cost_or_cache_figures(self):
        stdout, _ = self.single([
            start(model="m-1"),
            complete(model="m-1", totalTokens=900),
        ])
        lowered = stdout.lower()
        self.assertNotIn("cache", lowered)
        self.assertNotIn("$", stdout)
        self.assertNotIn("billable", lowered.replace("cost unknown", ""))

    def test_missing_tool_calls_and_parent_model_are_not_available(self):
        _, item = self.single([start(), complete()])
        self.assertEqual(item["totalToolCalls"], "not available")
        self.assertEqual(item["parentModel"], "not available")

    def test_matching_override_with_same_parent_model_is_not_proof(self):
        stdout, item = self.single([
            parent_model("m-1"),
            start(model="m-1"),
            complete(model="m-1", explicitModelOverride="m-1"),
        ])
        self.assertEqual(item["parentModel"], "m-1")
        self.assertEqual(item["overrideEvidence"], "explicitModelOverride recorded")
        self.assertEqual(item["match"], "yes")
        self.assertIn("not demonstrated (parent session used the same model)", item["overrideEffect"])
        self.assertIn("override effect: not demonstrated", stdout)

    def test_matching_override_with_different_parent_model_is_consistent_with_override(self):
        _, item = self.single([
            parent_model("parent-model"),
            start(model="m-1"),
            complete(model="m-1", explicitModelOverride="m-1"),
        ])
        self.assertEqual(item["parentModel"], "parent-model")
        self.assertTrue(item["overrideEffect"].startswith("consistent with override"))

    def test_matching_override_without_parent_model_is_not_demonstrated(self):
        _, item = self.single([start(model="m-1"), complete(model="m-1", explicitModelOverride="m-1")])
        self.assertIn("parent session model not available", item["overrideEffect"])

    def test_requested_model_not_observed_is_reported(self):
        _, item = self.single([
            parent_model("parent-model"),
            start(model="actual-model"),
            complete(model="actual-model", explicitModelOverride="requested-model"),
        ])
        self.assertEqual(item["match"], "no")
        self.assertTrue(item["overrideEffect"].startswith("requested model not observed"))

    def test_task_argument_without_recorded_override_is_not_evidence_of_override(self):
        _, item = self.single([
            parent_model("m-1"),
            start(model="m-1"),
            complete(model="m-1"),
        ])
        self.assertTrue(item["overrideEvidence"].startswith("task_argument only"))
        self.assertEqual(item["overrideEffect"], "not available")

    def test_inherited_delegation_has_no_override_effect(self):
        _, item = self.single([
            {"type": "subagent.started", "data": {"toolCallId": "call-1", "agentName": "Engineer"}},
            complete(agent="Engineer", model="m-1"),
        ])
        self.assertEqual(item["overrideEvidence"], "none")
        self.assertEqual(item["overrideEffect"], "n/a (no override requested)")

    def test_parent_model_tracks_latest_parent_change_and_ignores_delegated_agent_events(self):
        _, data = self.report([
            parent_model("parent-1"),
            start("call-1", model="m-1"),
            {"type": "session.model_change", "agentId": "agent-1", "data": {"newModel": "delegated-model"}},
            complete("call-1", model="m-1"),
            parent_model("parent-2"),
            start("call-2", model="m-1"),
            complete("call-2", model="m-1"),
        ])
        self.assertEqual([d["parentModel"] for d in data["delegations"]], ["parent-1", "parent-2"])

    def test_session_start_model_is_used_unless_it_is_auto(self):
        _, item = self.single([
            {"type": "session.start", "data": {"selectedModel": "auto"}},
            start(model="m-1"),
            complete(model="m-1"),
        ])
        self.assertEqual(item["parentModel"], "not available")
        _, item = self.single([
            {"type": "session.start", "data": {"selectedModel": "session-model"}},
            start(model="m-1"),
            complete(model="m-1"),
        ])
        self.assertEqual(item["parentModel"], "session-model")

    def test_permission_events_are_counted_without_claiming_a_visible_prompt(self):
        stdout, data = self.report([
            {"type": "permission.requested", "data": {"requestId": "1"}},
            {"type": "permission.requested", "data": {"requestId": "2"}},
            {"type": "permission.completed", "data": {"requestId": "1", "decisionSource": "host_policy"}},
            {"type": "permission.completed", "data": {"requestId": "2", "decisionSource": "human_response"}},
            {"type": "permission.completed", "data": {"requestId": "3"}},
        ])
        permissions = data["permissions"]
        self.assertEqual(permissions["requestedEvents"], 2)
        self.assertEqual(permissions["completedEvents"], 3)
        self.assertEqual(
            permissions["decisionSources"], {"host_policy": 1, "human_response": 1, "not available": 1}
        )
        self.assertIn("do not show whether a prompt was visible in the UI", permissions["note"])
        self.assertIn("permission events: requested=2 completed=3", stdout)
        self.assertNotIn("prompts shown", stdout.lower())

    def test_totals_sum_task_level_figures_only_and_ignore_session_usage(self):
        stdout, data = self.report([
            start("call-1"),
            complete("call-1", totalTokens=1000, totalToolCalls=4, durationMs=10),
            {"type": "session.usage_checkpoint", "data": {"totalNanoAiu": 999999, "totalPremiumRequests": 42}},
            start("call-2"),
            complete("call-2", totalTokens=500, totalToolCalls=6, durationMs=20),
        ])
        self.assertEqual(
            data["totals"]["Architect"],
            {"delegations": 2, "tokens": 1500, "toolCalls": 10, "durationMs": 30},
        )
        self.assertIn("session-wide usage is not attributed", stdout)
        self.assertNotIn("999999", stdout)
        self.assertNotIn("42", stdout.replace("toolCallId", ""))

    def test_report_without_delegations_still_reports_permissions(self):
        _, data = self.report([{"type": "permission.requested", "data": {}}])
        self.assertEqual(data["delegations"], [])
        self.assertEqual(data["permissions"]["requestedEvents"], 1)


class PublicPackageExclusionTests(unittest.TestCase):
    FORBIDDEN = ("model-preferences", ".factory", "events.jsonl", "session-state")

    def test_build_allowlists_and_bundled_assets_exclude_preferences_and_telemetry(self):
        pyproject = (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assets = REPOSITORY_ROOT / "src" / "specfactory" / "assets"
        names = [path.relative_to(assets).as_posix() for path in assets.rglob("*") if path.is_file()]
        for marker in self.FORBIDDEN:
            self.assertNotIn(marker, pyproject)
            self.assertFalse([name for name in names if marker in name], marker)

    def test_bundled_copies_match_repository_sources(self):
        assets = REPOSITORY_ROOT / "src" / "specfactory" / "assets"
        for relative in (
            ".github/agents/factory-lead.agent.md",
            ".github/skills/factory-handoff/SKILL.md",
            "scripts/specialist_models.py",
            "scripts/install_factory.py",
        ):
            self.assertEqual(
                (assets / relative).read_bytes(), (REPOSITORY_ROOT / relative).read_bytes(), relative
            )


if __name__ == "__main__":
    unittest.main()
