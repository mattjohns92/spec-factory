import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SPECIALIST_MODELS = REPOSITORY_ROOT / "scripts" / "specialist_models.py"


class SpecialistModelsTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temporary_directory.name) / "config.json"
        self.events_path = Path(self.temporary_directory.name) / "events.jsonl"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def run_script(self, args, check=False):
        cmd = [sys.executable, str(SPECIALIST_MODELS), "--config", str(self.config_path)] + args
        result = subprocess.run(cmd, cwd=REPOSITORY_ROOT, capture_output=True, text=True, check=False)
        if check and result.returncode != 0:
            self.fail(f"Command failed with exit {result.returncode}: {result.stderr}")
        return result

    def run_resolve(self, role):
        return self.run_script(["resolve", role])

    def run_status(self):
        return self.run_script(["status"])

    def run_status_json(self):
        return self.run_script(["status", "--json"])

    def set_preset(self, preset):
        return self.run_script(["set-preset", preset], check=True)

    def set_tier(self, tier, model_id):
        return self.run_script(["set-tier", tier, model_id], check=True)

    def set_override(self, role, model_id):
        return self.run_script(["set-override", role, model_id], check=True)

    def clear_override(self, role):
        return self.run_script(["clear-override", role], check=True)

    def write_config(self, data):
        self.config_path.write_text(json.dumps(data) + "\n")

    def write_events(self, lines):
        self.events_path.write_text("\n".join(json.dumps(line) for line in lines) + "\n")

    # (1) Default Budget preset with unresolved tiers and missing config not being created by status/resolve
    def test_default_budget_preset_with_missing_config_not_created(self):
        result = self.run_status()
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("model-preferences.json", result.stdout)
        self.assertFalse(self.config_path.exists(), "config file should not be created by status")

    def test_unresolved_role_with_missing_config(self):
        result = self.run_resolve("architect")
        self.assertEqual(result.returncode, 3)
        self.assertIn("unresolved", result.stderr)
        self.assertFalse(self.config_path.exists(), "config file should not be created by resolve")

    def test_missing_config_shows_unresolved_in_status(self):
        result = self.run_status()
        self.assertEqual(result.returncode, 0)
        self.assertIn("preset: budget", result.stdout)
        self.assertIn("unresolved", result.stdout)

    # (2) Preset maps for budget, balanced, quality-first (qa-engineer uses budget tier only in budget preset)
    def test_budget_preset_map(self):
        self.set_tier("budget", "model-budget")
        self.set_tier("balanced", "model-balanced")
        self.set_tier("quality", "model-quality")
        self.set_preset("budget")

        # architect, engineer, code-reviewer -> balanced; qa-engineer -> budget
        self.assertEqual(self.run_resolve("architect").stdout.strip(), "model-balanced")
        self.assertEqual(self.run_resolve("engineer").stdout.strip(), "model-balanced")
        self.assertEqual(self.run_resolve("qa-engineer").stdout.strip(), "model-budget")
        self.assertEqual(self.run_resolve("code-reviewer").stdout.strip(), "model-balanced")

    def test_balanced_preset_map(self):
        self.set_tier("balanced", "model-balanced-tier")
        self.set_preset("balanced")

        # all roles -> balanced
        for role in ("architect", "engineer", "qa-engineer", "code-reviewer"):
            self.assertEqual(self.run_resolve(role).stdout.strip(), "model-balanced-tier")

    def test_quality_first_preset_map(self):
        self.set_tier("quality", "model-quality-tier")
        self.set_preset("quality-first")

        # all roles -> quality
        for role in ("architect", "engineer", "qa-engineer", "code-reviewer"):
            self.assertEqual(self.run_resolve(role).stdout.strip(), "model-quality-tier")

    # (3) Changing the preset changes the resolved ID that resolve prints for subsequent calls
    def test_changing_preset_changes_resolved_id(self):
        self.set_tier("balanced", "model-balanced-v1")
        self.set_tier("quality", "model-quality-v1")
        self.set_preset("balanced")

        result1 = self.run_resolve("architect")
        self.assertEqual(result1.stdout.strip(), "model-balanced-v1")

        self.set_preset("quality-first")
        result2 = self.run_resolve("architect")
        self.assertEqual(result2.stdout.strip(), "model-quality-v1")

    # (4) Override precedence over preset, persistence across set-preset, and clear-override
    def test_override_precedence_over_preset(self):
        self.set_tier("balanced", "preset-model")
        self.set_tier("quality", "quality-model")
        self.set_preset("balanced")
        self.set_override("architect", "override-model")

        result = self.run_resolve("architect")
        self.assertEqual(result.stdout.strip(), "override-model")

    def test_override_persists_across_preset_change(self):
        self.set_tier("balanced", "balanced-model")
        self.set_tier("quality", "quality-model")
        self.set_preset("balanced")
        self.set_override("architect", "my-override")

        self.set_preset("quality-first")
        result = self.run_resolve("architect")
        self.assertEqual(result.stdout.strip(), "my-override")

    def test_clear_override_restores_preset(self):
        self.set_tier("balanced", "balanced-model")
        self.set_preset("balanced")
        self.set_override("engineer", "override-model")

        result1 = self.run_resolve("engineer")
        self.assertEqual(result1.stdout.strip(), "override-model")

        self.clear_override("engineer")
        result2 = self.run_resolve("engineer")
        self.assertEqual(result2.stdout.strip(), "balanced-model")

    # (5) Persistence across separate process invocations, atomic write leaves no temp files, unknown top-level keys preserved
    def test_persistence_across_process_invocations(self):
        self.set_tier("balanced", "persisted-model")
        self.set_preset("balanced")

        # Verify in a separate invocation
        result = self.run_resolve("architect")
        self.assertEqual(result.stdout.strip(), "persisted-model")

    def test_atomic_write_no_temp_files(self):
        self.set_tier("balanced", "test-model")
        # Check that only the config file exists, no temp files
        parent_contents = list(self.config_path.parent.glob(".*"))
        temp_files = [f for f in parent_contents if f.name.startswith(f".{self.config_path.name}.")]
        self.assertEqual(len(temp_files), 0, f"Found temp files: {temp_files}")

    def test_unknown_toplevel_keys_preserved(self):
        data = {
            "version": 1,
            "preset": "balanced",
            "tiers": {"budget": None, "balanced": "my-model", "quality": None},
            "overrides": {},
            "unknown_key": "should-be-preserved",
            "another_unknown": {"nested": "value"},
        }
        self.write_config(data)

        self.set_override("architect", "new-override")

        saved = json.loads(self.config_path.read_text())
        self.assertEqual(saved.get("unknown_key"), "should-be-preserved")
        self.assertEqual(saved.get("another_unknown"), {"nested": "value"})

    # (6) Invalid config exits 2 with file bytes unchanged; invalid model IDs rejected; factory-lead not accepted
    def test_malformed_json_exits_2_preserves_file(self):
        original = "not valid json {"
        self.config_path.write_text(original)

        result = self.run_resolve("architect")
        self.assertEqual(result.returncode, 2)
        self.assertIn("malformed JSON", result.stderr)

        self.assertEqual(self.config_path.read_text(), original)

    def test_bad_version_exits_2_preserves_file(self):
        data = {"version": 2, "preset": "budget", "tiers": {}, "overrides": {}}
        original = json.dumps(data)
        self.write_config(data)

        result = self.run_resolve("architect")
        self.assertEqual(result.returncode, 2)

        self.assertEqual(self.config_path.read_text().strip(), original)

    def test_bad_preset_exits_2(self):
        data = {"version": 1, "preset": "invalid", "tiers": {}, "overrides": {}}
        self.write_config(data)

        result = self.run_resolve("architect")
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid preset", result.stderr)

    def test_bad_tier_exits_2(self):
        data = {"version": 1, "preset": "budget", "tiers": {"unknown-tier": "model"}, "overrides": {}}
        self.write_config(data)

        result = self.run_resolve("architect")
        self.assertEqual(result.returncode, 2)

    def test_bad_role_in_overrides_exits_2(self):
        data = {"version": 1, "preset": "budget", "tiers": {}, "overrides": {"invalid-role": "model"}}
        self.write_config(data)

        result = self.run_resolve("architect")
        self.assertEqual(result.returncode, 2)

    def test_bad_override_id_exits_2(self):
        self.set_tier("balanced", "good-model")
        result = self.run_script(["set-override", "architect", "bad model id!"])
        self.assertEqual(result.returncode, 2)

    def test_bad_tier_id_exits_2(self):
        result = self.run_script(["set-tier", "balanced", "bad model id!"])
        self.assertEqual(result.returncode, 2)

    def test_set_preset_invalid_value_exits_2(self):
        self.set_tier("balanced", "good-model")
        result = self.run_script(["set-preset", "invalid-preset"])
        self.assertEqual(result.returncode, 2)

    def test_malformed_json_config_not_rewritten_by_set_preset(self):
        original = "not valid json {"
        self.config_path.write_text(original)

        result = self.run_script(["set-preset", "balanced"])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.config_path.read_text(), original)

    def test_malformed_json_config_not_rewritten_by_set_tier(self):
        original = "not valid json {"
        self.config_path.write_text(original)

        result = self.run_script(["set-tier", "balanced", "good-model"])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.config_path.read_text(), original)

    def test_malformed_json_config_not_rewritten_by_set_override(self):
        original = "not valid json {"
        self.config_path.write_text(original)

        result = self.run_script(["set-override", "architect", "good-model"])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.config_path.read_text(), original)

    def test_malformed_json_config_not_rewritten_by_clear_override(self):
        original = "not valid json {"
        self.config_path.write_text(original)

        result = self.run_script(["clear-override", "architect"])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.config_path.read_text(), original)

    def test_bad_version_config_not_rewritten_by_set_preset(self):
        data = {"version": 2, "preset": "budget", "tiers": {}, "overrides": {}}
        original = json.dumps(data)
        self.write_config(data)

        result = self.run_script(["set-preset", "balanced"])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.config_path.read_text().strip(), original)

    def test_bad_version_config_not_rewritten_by_set_tier(self):
        data = {"version": 2, "preset": "budget", "tiers": {}, "overrides": {}}
        original = json.dumps(data)
        self.write_config(data)

        result = self.run_script(["set-tier", "balanced", "good-model"])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.config_path.read_text().strip(), original)

    def test_bad_version_config_not_rewritten_by_set_override(self):
        data = {"version": 2, "preset": "budget", "tiers": {}, "overrides": {}}
        original = json.dumps(data)
        self.write_config(data)

        result = self.run_script(["set-override", "architect", "good-model"])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.config_path.read_text().strip(), original)

    def test_bad_version_config_not_rewritten_by_clear_override(self):
        data = {"version": 2, "preset": "budget", "tiers": {}, "overrides": {}}
        original = json.dumps(data)
        self.write_config(data)

        result = self.run_script(["clear-override", "architect"])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.config_path.read_text().strip(), original)

    def test_model_id_with_dot_accepted(self):
        # Model IDs can contain dots
        result = self.run_script(["set-tier", "balanced", "claude-3.5-sonnet"])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.run_resolve("architect").stdout.strip(), "claude-3.5-sonnet")

    def test_model_id_with_colon_accepted(self):
        # Model IDs can contain colons
        result = self.run_script(["set-tier", "balanced", "a:b"])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.run_resolve("architect").stdout.strip(), "a:b")

    def test_model_id_with_slash_accepted(self):
        # Model IDs can contain slashes
        result = self.run_script(["set-tier", "balanced", "a/b:c-1"])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.run_resolve("architect").stdout.strip(), "a/b:c-1")

    def test_copilot_display_name_round_trips_through_tier(self):
        display_name = "Claude Sonnet 5.5 (copilot)"
        result = self.run_script(["set-tier", "balanced", display_name])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(self.config_path.read_text())["tiers"]["balanced"], display_name)
        self.assertEqual(self.run_resolve("architect").stdout.strip(), display_name)

    def test_copilot_display_name_is_accepted_for_override(self):
        display_name = "Claude Haiku 4.5 (copilot)"
        result = self.run_script(["set-override", "engineer", display_name])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.run_resolve("engineer").stdout.strip(), display_name)

    def test_model_id_with_trailing_space_is_rejected(self):
        result = self.run_script(["set-tier", "balanced", "model-name "])
        self.assertEqual(result.returncode, 2)

    def test_unsafe_model_ids_are_rejected(self):
        for model_id in (" model-name", "model!name", "model\nname", "model\tname", ""):
            with self.subTest(model_id=repr(model_id)):
                result = self.run_script(["set-tier", "balanced", model_id])
                self.assertEqual(result.returncode, 2)
                self.assertIn("parentheses, spaces", result.stderr)

    def test_invalid_display_name_in_config_is_rejected_by_status_and_resolve(self):
        for model_id in (
            "Claude Sonnet 5.5 (copilot) ",
            "Claude\nSonnet (copilot)",
            "Claude\x01Sonnet (copilot)",
            "Claude\x00Sonnet (copilot)",
        ):
            with self.subTest(model_id=repr(model_id)):
                self.write_config({
                    "version": 1,
                    "preset": "balanced",
                    "tiers": {"balanced": model_id},
                    "overrides": {},
                })
                self.assertEqual(self.run_status().returncode, 2)
                self.assertEqual(self.run_resolve("engineer").returncode, 2)

    def test_model_id_200_chars_accepted(self):
        # Maximum 200 chars is accepted
        id_200 = "a" * 200
        result = self.run_script(["set-tier", "balanced", id_200])
        self.assertEqual(result.returncode, 0)

    def test_model_id_201_chars_rejected(self):
        # 201 chars is rejected
        id_201 = "a" * 201
        result = self.run_script(["set-tier", "balanced", id_201])
        self.assertEqual(result.returncode, 2)

    def test_model_id_with_internal_space_accepted(self):
        model_id = "display name"
        result = self.run_script(["set-tier", "balanced", model_id])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.run_resolve("architect").stdout.strip(), model_id)

    def test_model_id_starting_with_hyphen_rejected(self):
        # Model IDs must start with alphanumeric
        result = self.run_script(["set-tier", "balanced", "-invalid"])
        self.assertEqual(result.returncode, 2)

    def test_factory_lead_not_accepted_role(self):
        result = self.run_script(["resolve", "factory-lead"])
        self.assertEqual(result.returncode, 2)

    # (7) resolve prints only the ID on stdout, exit 3 with empty stdout when unresolved
    def test_resolve_prints_only_id(self):
        self.set_tier("balanced", "my-model-id")
        self.set_preset("balanced")

        result = self.run_resolve("architect")
        self.assertEqual(result.stdout.strip(), "my-model-id")
        self.assertEqual(result.stderr, "")

    def test_config_with_utf8_bom_accepted_by_status(self):
        # Config files with UTF-8 BOM should be accepted
        bom_data = b"\xef\xbb\xbf" + json.dumps({"version": 1, "preset": "budget", "tiers": {}, "overrides": {}}).encode("utf-8")
        self.config_path.write_bytes(bom_data)
        result = self.run_status()
        self.assertEqual(result.returncode, 0)
        self.assertIn("preset: budget", result.stdout)

    def test_config_with_utf8_bom_accepted_by_resolve(self):
        # Config files with UTF-8 BOM should be accepted by resolve
        bom_data = b"\xef\xbb\xbf" + json.dumps({"version": 1, "preset": "balanced", "tiers": {"balanced": "my-model"}, "overrides": {}}).encode("utf-8")
        self.config_path.write_bytes(bom_data)
        result = self.run_resolve("architect")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "my-model")

    def test_unresolved_exit_3_with_empty_stdout(self):
        # No tiers set, so unresolved
        result = self.run_resolve("architect")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, "")
        self.assertIn("unresolved", result.stderr)

    # (8) report over a fixture events.jsonl
    def test_report_explicit_override_matching_actual(self):
        self.write_events([
            {
                "type": "subagent.started",
                "data": {
                    "toolCallId": "call-1",
                    "agentName": "Architect",
                    "taskModelSource": "task_argument",
                    "model": "claude-opus",
                    "modelSelectionSource": "explicit_override",
                }
            },
            {
                "type": "subagent.completed",
                "data": {
                    "toolCallId": "call-1",
                    "agentName": "Architect",
                    "model": "claude-opus",
                    "explicitModelOverride": "claude-opus",
                    "totalTokens": 1000,
                    "durationMs": 5000,
                }
            }
        ])

        result = self.run_script(["report", "--events", str(self.events_path)])
        self.assertEqual(result.returncode, 0)
        self.assertIn("claude-opus", result.stdout)
        self.assertIn("requested == actual: yes", result.stdout)

    def test_report_inherited_session_inheritance(self):
        self.write_events([
            {
                "type": "subagent.started",
                "data": {
                    "toolCallId": "call-1",
                    "agentName": "Engineer",
                    "modelSelectionSource": "session_inheritance",
                }
            },
            {
                "type": "subagent.completed",
                "data": {
                    "toolCallId": "call-1",
                    "agentName": "Engineer",
                    "model": "claude-sonnet",
                    "totalTokens": 2000,
                    "durationMs": 3000,
                }
            }
        ])

        result = self.run_script(["report", "--events", str(self.events_path)])
        self.assertEqual(result.returncode, 0)
        self.assertIn("none (inherited)", result.stdout)
        self.assertIn("requested == actual: n/a", result.stdout)

    def test_report_mismatch_requested_vs_actual(self):
        self.write_events([
            {
                "type": "subagent.started",
                "data": {
                    "toolCallId": "call-1",
                    "agentName": "QA Engineer",
                    "taskModelSource": "task_argument",
                    "model": "claude-haiku",
                    "modelSelectionSource": "explicit_override",
                }
            },
            {
                "type": "subagent.completed",
                "data": {
                    "toolCallId": "call-1",
                    "agentName": "QA Engineer",
                    "model": "claude-sonnet",
                    "totalTokens": 500,
                    "durationMs": 1000,
                }
            }
        ])

        result = self.run_script(["report", "--events", str(self.events_path)])
        self.assertEqual(result.returncode, 0)
        self.assertIn("claude-haiku", result.stdout)
        self.assertIn("claude-sonnet", result.stdout)
        self.assertIn("requested == actual: no", result.stdout)

    def test_report_task_argument_without_explicit_override_text(self):
        # task_argument without explicitModelOverride => "not available (task_argument, no explicitModelOverride recorded)"
        self.write_events([
            json.loads(json.dumps({
                "type": "subagent.started",
                "data": {
                    "toolCallId": "call-1",
                    "agentName": "Engineer",
                    "taskModelSource": "task_argument",
                    "model": "claude-sonnet",
                    "modelSelectionSource": "explicit_override",
                }
            })),
            json.loads(json.dumps({
                "type": "subagent.completed",
                "data": {
                    "toolCallId": "call-1",
                    "agentName": "Engineer",
                    "model": "claude-sonnet",
                }
            }))
        ])

        result = self.run_script(["report", "--events", str(self.events_path)])
        self.assertEqual(result.returncode, 0)
        self.assertIn("not available (task_argument, no explicitModelOverride recorded)", result.stdout)
        self.assertIn("requested == actual: not available", result.stdout)

    def test_report_task_argument_without_explicit_override_json(self):
        # Same but with JSON output
        self.write_events([
            json.loads(json.dumps({
                "type": "subagent.started",
                "data": {
                    "toolCallId": "call-1",
                    "agentName": "Engineer",
                    "taskModelSource": "task_argument",
                    "model": "claude-sonnet",
                }
            })),
            json.loads(json.dumps({
                "type": "subagent.completed",
                "data": {
                    "toolCallId": "call-1",
                    "agentName": "Engineer",
                    "model": "claude-sonnet",
                }
            }))
        ])

        result = self.run_script(["report", "--events", str(self.events_path), "--json"])
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(len(data["delegations"]), 1)
        self.assertEqual(data["delegations"][0]["requested"], "not available (task_argument, no explicitModelOverride recorded)")
        self.assertEqual(data["delegations"][0]["match"], "not available")

    def test_report_duplicate_tool_call_id_does_not_crash(self):
        # Duplicate toolCallId should overwrite, not crash
        self.write_events([
            json.loads(json.dumps({
                "type": "subagent.started",
                "data": {
                    "toolCallId": "call-1",
                    "agentName": "Architect",
                    "model": "first-model",
                }
            })),
            json.loads(json.dumps({
                "type": "subagent.started",
                "data": {
                    "toolCallId": "call-1",
                    "agentName": "Architect",
                    "model": "second-model",
                }
            })),
            json.loads(json.dumps({
                "type": "subagent.completed",
                "data": {
                    "toolCallId": "call-1",
                    "agentName": "Architect",
                    "model": "second-model",
                    "explicitModelOverride": "second-model",
                }
            }))
        ])

        result = self.run_script(["report", "--events", str(self.events_path)])
        self.assertEqual(result.returncode, 0)
        self.assertIn("second-model", result.stdout)

    def test_report_missing_fields_shown_as_not_available(self):
        self.write_events([
            {
                "type": "subagent.started",
                "data": {
                    "toolCallId": "call-1",
                    "agentName": "Code Reviewer",
                }
            },
            {
                "type": "subagent.completed",
                "data": {
                    "toolCallId": "call-1",
                    "agentName": "Code Reviewer",
                }
            }
        ])

        result = self.run_script(["report", "--events", str(self.events_path)])
        self.assertEqual(result.returncode, 0)
        self.assertIn("not available", result.stdout)

    def test_report_malformed_lines_skipped_and_counted(self):
        # Skipped: invalid JSON, a non-object JSON value, and a subagent event without toolCallId.
        lines = [
            json.dumps({"type": "subagent.started", "data": {"toolCallId": "call-1", "agentName": "Architect", "agentType": "Architect", "model": "m-1"}}),
            "{ invalid json",
            json.dumps([1, 2, 3]),
            json.dumps({"type": "subagent.started", "data": {"agentName": "Engineer"}}),
            json.dumps({"type": "subagent.completed", "data": {"toolCallId": "call-1", "agentName": "Architect", "model": "m-1", "totalTokens": 10, "durationMs": 20}}),
        ]
        self.events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        result = self.run_script(["report", "--events", str(self.events_path), "--json"])
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["skippedLines"], 3)
        self.assertEqual(len(data["delegations"]), 1)
        self.assertEqual(data["delegations"][0]["toolCallId"], "call-1")
        self.assertEqual(data["delegations"][0]["completedModel"], "m-1")
        self.assertEqual(data["totals"]["Architect"]["tokens"], 10)

        text = self.run_script(["report", "--events", str(self.events_path)])
        self.assertIn("skipped unreadable/malformed lines: 3", text.stdout)

    def test_report_per_agent_totals(self):
        self.write_events([
            {
                "type": "subagent.started",
                "data": {"toolCallId": "call-1", "agentName": "Architect"}
            },
            {
                "type": "subagent.completed",
                "data": {"toolCallId": "call-1", "agentName": "Architect", "totalTokens": 1000, "durationMs": 2000}
            },
            {
                "type": "subagent.started",
                "data": {"toolCallId": "call-2", "agentName": "Architect"}
            },
            {
                "type": "subagent.completed",
                "data": {"toolCallId": "call-2", "agentName": "Architect", "totalTokens": 1500, "durationMs": 3000}
            },
        ])

        result = self.run_script(["report", "--events", str(self.events_path)])
        self.assertEqual(result.returncode, 0)
        self.assertIn("delegations=2", result.stdout)
        self.assertIn("tokens=2500", result.stdout)
        self.assertIn("durationMs=5000", result.stdout)

    def test_report_json_output(self):
        self.write_events([
            {
                "type": "subagent.started",
                "data": {"toolCallId": "call-1", "agentName": "Engineer", "model": "claude-opus"}
            },
            {
                "type": "subagent.completed",
                "data": {"toolCallId": "call-1", "agentName": "Engineer", "totalTokens": 2000, "durationMs": 4000}
            }
        ])

        result = self.run_script(["report", "--events", str(self.events_path), "--json"])
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(len(data["delegations"]), 1)
        self.assertIn("Engineer", data["totals"])

    def test_report_nonexistent_events_exit_1(self):
        result = self.run_script(["report", "--events", "/nonexistent/path"])
        self.assertEqual(result.returncode, 1)
        self.assertIn("not found", result.stderr)

    # (9) Instruction guard tests - real repository files
    def test_factory_lead_contains_resolve_command(self):
        factory_lead_path = REPOSITORY_ROOT / ".github" / "agents" / "factory-lead.agent.md"
        content = factory_lead_path.read_text()
        self.assertIn("scripts/specialist_models.py resolve", content)

    def test_factory_lead_documents_model_argument(self):
        self.assert_model_contract_wording(REPOSITORY_ROOT / ".github" / "agents" / "factory-lead.agent.md")

    def assert_model_contract_wording(self, path):
        text = " ".join(path.read_text(encoding="utf-8").split()).lower()
        for phrase in (
            "`model` argument",
            "verbatim",
            "ask the owner",
            "silently inherit",
            "never escalate",
            "do not retry without the `model` argument",
            "substitute another model",
        ):
            self.assertIn(phrase, text, f"{path.name} is missing: {phrase}")

    def test_factory_handoff_contains_resolve_command(self):
        handoff_path = REPOSITORY_ROOT / ".github" / "skills" / "factory-handoff" / "SKILL.md"
        content = handoff_path.read_text()
        self.assertIn("scripts/specialist_models.py resolve", content)

    def test_factory_handoff_documents_model_contract(self):
        self.assert_model_contract_wording(REPOSITORY_ROOT / ".github" / "skills" / "factory-handoff" / "SKILL.md")

    @staticmethod
    def frontmatter_fields(path):
        lines = path.read_text(encoding="utf-8").splitlines()
        end = lines.index("---", 1)
        return {
            key.strip(): value.strip()
            for key, _, value in (line.partition(":") for line in lines[1:end])
            if value
        }

    def test_factory_lead_tools_exactly(self):
        fields = self.frontmatter_fields(REPOSITORY_ROOT / ".github" / "agents" / "factory-lead.agent.md")
        self.assertEqual(
            json.loads(fields["tools"]),
            ["read", "grep", "glob", "edit", "execute", "task", "list_agents", "read_agent", "skill"],
        )
        self.assertEqual(fields["strict-tools-list"], "true")

    def test_code_reviewer_tools_exactly(self):
        fields = self.frontmatter_fields(REPOSITORY_ROOT / ".github" / "agents" / "code-reviewer.agent.md")
        self.assertEqual(json.loads(fields["tools"]), ["read", "grep", "glob"])
        self.assertEqual(fields["strict-tools-list"], "true")

    def test_specialist_profiles_no_model_frontmatter_line(self):
        specialist_profiles = [
            "architect.agent.md",
            "engineer.agent.md",
            "qa-engineer.agent.md",
            "code-reviewer.agent.md",
        ]
        for profile in specialist_profiles:
            profile_path = REPOSITORY_ROOT / ".github" / "agents" / profile
            self.assertNotIn("model", self.frontmatter_fields(profile_path), f"Found 'model' in {profile} frontmatter")


if __name__ == "__main__":
    unittest.main()