"""v0.1.3 reliability gates.

The instruction tests below are wording guards: they show the required text ships in the source and
bundled copies. They do not show that an agent follows it, and they are not runtime enforcement.
The permission-report tests do exercise real code against fixture events.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SPECIALIST_MODELS = REPOSITORY_ROOT / "scripts" / "specialist_models.py"
ASSETS = REPOSITORY_ROOT / "src" / "specfactory" / "assets"
LEAD = ".github/agents/factory-lead.agent.md"
REVIEWER = ".github/agents/code-reviewer.agent.md"
HANDOFF = ".github/skills/factory-handoff/SKILL.md"


def normalized(relative, root=REPOSITORY_ROOT):
    return " ".join((root / relative).read_text(encoding="utf-8").split()).lower()


class InstructionWordingGuards(unittest.TestCase):
    def assert_phrases(self, relative, phrases):
        for root in (REPOSITORY_ROOT, ASSETS):
            text = normalized(relative, root)
            for phrase in phrases:
                self.assertIn(phrase, text, f"{root.name}/{relative} is missing: {phrase}")

    def test_completion_gate(self):
        for relative in (LEAD, HANDOFF):
            self.assert_phrases(relative, (
                "has finished and returned its result",
                "`list_agents` or `read_agent`",
                "actual changed files",
                "pending, partial, or blocked",
                "a planned or described check is not completed verification",
            ))
        self.assert_phrases(LEAD, (
            "within the approved scope and the baseline",
            "required verification has completed successfully",
            "including `[x]` in `tasks.md`",
        ))

    def test_review_gate_in_lead_and_handoff(self):
        for relative in (LEAD, HANDOFF):
            self.assert_phrases(relative, (
                "actual diff" if relative == LEAD else "test evidence",
                "cannot be a pass",
                "test evidence",
            ))

    def test_reviewer_must_name_inspected_artifacts_and_cannot_pass_without_them(self):
        self.assert_phrases(REVIEWER, (
            "inspect the approved requirements, the implementation plan, the relevant source code, "
            "the actual diff, and any available test evidence",
            "start your report with the artifacts you inspected",
            "list anything you were not given",
            "do not return a pass",
            "name the missing material",
            "a pass applies only to the diff you inspected",
            "do not edit files, run commands, or delegate further work",
        ))

    def test_independent_review_requires_runtime_evidence_and_is_recorded(self):
        for relative in (LEAD, HANDOFF, REVIEWER):
            self.assert_phrases(relative, ("self-review",))
        for relative in (LEAD, HANDOFF):
            self.assert_phrases(relative, ("independent only when", "evidenc"))
        self.assert_phrases(LEAD, ("record that label and its runtime evidence",))
        self.assert_phrases(HANDOFF, ("record the label and its runtime evidence",))

    def test_stale_review_protection(self):
        for relative in (LEAD, HANDOFF):
            self.assert_phrases(relative, (
                "record the reviewed state",
                "invalidates the review for the affected changes",
                "focused re-review of the final changes",
                "owner-approved exception",
            ))
        self.assert_phrases(LEAD, ("by engineer or by you",))
        self.assert_phrases(HANDOFF, ("by engineer or by factory lead",))

    def test_decomposition_without_numeric_limits(self):
        for relative in (LEAD, HANDOFF):
            self.assert_phrases(relative, (
                "independently verifiable tasks",
                "explicit scope" if relative == LEAD else "completion condition",
                "numeric",
            ))
        self.assert_phrases(LEAD, ("expected outputs, and a completion condition",))

    def test_qa_gate(self):
        for relative in (LEAD, HANDOFF):
            self.assert_phrases(relative, (
                "completed qa assessment or an explicit, owner-approved exception",
                "unfinished qa",
                "not a fixed sequence of specialists",
            ))
        self.assert_phrases(LEAD, ("which tests were executed, which were skipped, and which are still required",))
        self.assert_phrases(HANDOFF, ("checks executed, checks skipped, and checks still required",))

    def test_existing_work_protection(self):
        for relative in (LEAD, HANDOFF):
            self.assert_phrases(relative, (
                "child repository separately",
                "`git add .`",
                "`git add -a`",
                "`git commit -a`",
            ))
        self.assert_phrases(LEAD, (
            "`git rev-parse head`",
            "`git status --porcelain`",
            "escalate to the owner before proceeding",
            "compare the working tree with the baseline",
            "report any unexpected change immediately",
            "do not modify unrelated existing work",
        ))

    def test_approval_and_permission_evidence_are_kept_distinct(self):
        for relative in (LEAD, HANDOFF):
            self.assert_phrases(relative, (
                "owner approval expressed in conversation",
                "permission mode the runtime reports",
                "permission decisions actually recorded in events",
                "enforcement that has been independently demonstrated",
                "conversational approval is not a technical control",
                "allow all or autopilot",
                "`permissionmode`",
                "`agentmode`",
            ))

    def test_lead_keeps_edit_tool_and_reviewer_stays_read_only(self):
        lead = (REPOSITORY_ROOT / LEAD).read_text(encoding="utf-8")
        reviewer = (REPOSITORY_ROOT / REVIEWER).read_text(encoding="utf-8")
        self.assertIn('"edit"', lead.split("---")[1])
        self.assertIn('tools: ["read", "grep", "glob"]', reviewer)

    def test_source_and_bundled_copies_are_identical(self):
        for relative in (LEAD, REVIEWER, HANDOFF, "scripts/specialist_models.py"):
            self.assertEqual(
                (ASSETS / relative).read_bytes(), (REPOSITORY_ROOT / relative).read_bytes(), relative
            )


def request(request_id, agent_id=None, **data):
    event = {"type": "permission.requested", "data": {"requestId": request_id, **data}}
    if agent_id:
        event["agentId"] = agent_id
    return event


def decision(request_id, source, agent_id=None):
    data = {"requestId": request_id}
    if source:
        data["decisionSource"] = source
    event = {"type": "permission.completed", "data": data}
    if agent_id:
        event["agentId"] = agent_id
    return event


def started(call_id, agent_id):
    return {
        "type": "subagent.started",
        "agentId": agent_id,
        "data": {"toolCallId": call_id, "agentName": "Engineer"},
    }


class PermissionReportTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.events_path = Path(self.temporary_directory.name) / "events.jsonl"

    def report(self, events):
        self.events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
        results = []
        for extra in ([], ["--json"]):
            result = subprocess.run(
                [sys.executable, str(SPECIALIST_MODELS), "report", "--events", str(self.events_path), *extra],
                cwd=REPOSITORY_ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            results.append(result.stdout)
        return results[0], json.loads(results[1])

    def test_main_agent_and_specialist_permissions_are_reported_separately(self):
        stdout, data = self.report([
            request("m1", permissionMode="manual", agentMode="interactive"),
            decision("m1", "human_response"),
            started("call-1", "agent-1"),
            request("s1", "agent-1", permissionMode="manual", agentMode="autopilot"),
            request("s2", "agent-1", permissionMode="manual", agentMode="autopilot"),
            decision("s1", "host_policy", "agent-1"),
            decision("s2", "host_policy", "agent-1"),
        ])
        permissions = data["permissions"]
        self.assertEqual(permissions["main"]["requestedEvents"], 1)
        self.assertEqual(permissions["main"]["agentModes"], {"interactive": 1})
        self.assertEqual(permissions["main"]["decisionSources"], {"human_response": 1})
        delegation = data["delegations"][0]["permissions"]
        self.assertEqual(delegation["requestedEvents"], 2)
        self.assertEqual(delegation["agentModes"], {"autopilot": 2})
        self.assertEqual(delegation["permissionModes"], {"manual": 2})
        self.assertEqual(delegation["decisionSources"], {"host_policy": 2})
        self.assertNotIn("requestedEvents", permissions, "main and specialist counts must not be combined")
        self.assertIn("main agent: requested=1", stdout)
        self.assertIn("permission events (this delegation only): requested=2", stdout)

    def test_two_specialists_are_not_conflated(self):
        _, data = self.report([
            {**started("call-1", "agent-1")},
            {**started("call-2", "agent-2")},
            request("a", "agent-1", agentMode="autopilot"),
            request("b", "agent-2", agentMode="interactive"),
        ])
        modes = {d["toolCallId"]: d["permissions"]["agentModes"] for d in data["delegations"]}
        self.assertEqual(modes, {"call-1": {"autopilot": 1}, "call-2": {"interactive": 1}})

    def test_missing_modes_and_sources_are_preserved_as_not_available(self):
        stdout, data = self.report([request("m1"), decision("m1", None)])
        main = data["permissions"]["main"]
        self.assertEqual(main["permissionModes"], {"not available": 1})
        self.assertEqual(main["agentModes"], {"not available": 1})
        self.assertEqual(main["decisionSources"], {"not available": 1})
        self.assertIn("agentMode={'not available': 1}", stdout)

    def test_decision_without_agent_id_is_linked_through_its_request(self):
        _, data = self.report([
            started("call-1", "agent-1"),
            request("s1", "agent-1", agentMode="autopilot"),
            decision("s1", "host_policy"),
        ])
        self.assertEqual(data["delegations"][0]["permissions"]["completedEvents"], 1)
        self.assertEqual(data["permissions"]["main"]["completedEvents"], 0)

    def test_unmatched_decision_is_unattributed_not_guessed_as_main(self):
        stdout, data = self.report([decision("unknown", "host_policy")])
        self.assertEqual(data["permissions"]["unattributed"]["completedEvents"], 1)
        self.assertEqual(data["permissions"]["main"]["completedEvents"], 0)
        self.assertIn("unattributed: requested=0 completed=1", stdout)

    def test_agent_without_a_started_event_is_listed_as_unlinked(self):
        stdout, data = self.report([request("x", "ghost-agent", agentMode="autopilot")])
        self.assertEqual(data["permissions"]["unlinkedAgents"]["ghost-agent"]["requestedEvents"], 1)
        self.assertEqual(data["permissions"]["main"]["requestedEvents"], 0)
        self.assertIn("ghost-agent", stdout)

    def test_delegation_without_permission_events_shows_zero_counts_not_a_guess(self):
        _, data = self.report([started("call-1", "agent-1")])
        permissions = data["delegations"][0]["permissions"]
        self.assertEqual(permissions["requestedEvents"], 0)
        self.assertEqual(permissions["agentModes"], {})

    def test_allow_all_setting_changes_are_reported_with_their_source(self):
        stdout, data = self.report([
            {"type": "session.permissions_changed", "data": {
                "previousAllowAllPermissionMode": "off", "allowAllPermissionMode": "on"}},
            {"type": "session.permissions_changed", "agentId": "agent-1", "data": {"allowAllPermissionMode": "off"}},
        ])
        changes = data["permissions"]["settingChanges"]
        self.assertEqual(changes[0], {
            "source": "main", "allowAllPermissionMode": "on", "previousAllowAllPermissionMode": "off"})
        self.assertEqual(changes[1]["source"], "agent-1")
        self.assertEqual(changes[1]["previousAllowAllPermissionMode"], "not available")
        self.assertIn("allow-all setting change (main): off -> on", stdout)

    def test_report_does_not_imply_prompts_or_enforcement(self):
        stdout, data = self.report([request("m1", permissionMode="manual"), decision("m1", "host_policy")])
        note = data["permissions"]["note"]
        self.assertIn("not proof that a prompt appeared in the UI", note)
        self.assertIn("none of this shows that sandbox or tool restrictions were enforced", note)
        self.assertIn("conversational owner approval is separate", note)
        self.assertNotIn("prompted", stdout.lower())


if __name__ == "__main__":
    unittest.main()
