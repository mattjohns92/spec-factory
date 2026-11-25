import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile


ROLES = ("architect", "engineer", "qa-engineer", "code-reviewer")
TIERS = ("budget", "balanced", "quality")
PRESETS = {
    "budget": {
        "architect": "balanced",
        "engineer": "balanced",
        "qa-engineer": "budget",
        "code-reviewer": "balanced",
    },
    "balanced": {role: "balanced" for role in ROLES},
    "quality-first": {role: "quality" for role in ROLES},
}
DEFAULT_PRESET = "budget"
VERSION = 1
MODEL_ID_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._:/() -]{0,198}[A-Za-z0-9._:/()-])?")
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / ".factory" / "model-preferences.json"
NOT_AVAILABLE = "not available"
INHERITED = "none (inherited)"
NO_OVERRIDE_RECORDED = "not available (task_argument, no explicitModelOverride recorded)"
TOKENS_LABEL = "runtime-reported total; composition and cost unknown"
PERMISSIONS_NOTE = (
    "counts of permission events recorded in the log (whole session, not per delegation); "
    "they do not show whether a prompt was visible in the UI. A 'human_response' decision source "
    "records a human reply; 'host_policy' records an automatic decision."
)
LABEL_WARNING = (
    "warning: '{value}' looks like a display label. The task runtime expects its own model identifier, "
    "such as the 'model' value in a prior subagent.started event; confirm it before delegating."
)

EXIT_ERROR = 1
EXIT_INVALID_CONFIG = 2
EXIT_UNRESOLVED = 3


class ConfigError(Exception):
    pass


def _check_model_id(value, label):
    if not isinstance(value, str) or MODEL_ID_PATTERN.fullmatch(value) is None:
        raise ConfigError(
            f"invalid model ID for {label}: use 1-200 ASCII characters, start with a letter or digit, "
            "and use only letters, digits, dot, underscore, colon, slash, parentheses, spaces, or hyphens; "
            "the value must not end with a space"
        )
    return value


def _default_config():
    return {
        "version": VERSION,
        "preset": DEFAULT_PRESET,
        "tiers": {tier: None for tier in TIERS},
        "overrides": {},
    }


def load_config(path):
    """Return a validated config dict; a missing file yields defaults without creating it."""
    try:
        text = path.read_text(encoding="utf-8-sig")  # tolerate a BOM; writes stay BOM-free
    except FileNotFoundError:
        return _default_config()
    except (OSError, UnicodeError) as error:
        raise ConfigError(f"unable to read {path}: {error}")

    try:
        data = json.loads(text)
    except ValueError as error:
        raise ConfigError(f"malformed JSON in {path}: {error}")
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top-level value must be an object")

    version = data.get("version")
    if isinstance(version, bool) or version != VERSION:
        raise ConfigError(f"{path}: unsupported or missing version (expected {VERSION})")

    preset = data.get("preset", DEFAULT_PRESET)
    if not isinstance(preset, str) or preset not in PRESETS:
        raise ConfigError(f"{path}: invalid preset (expected one of {', '.join(PRESETS)})")

    tiers = data.get("tiers", {})
    if not isinstance(tiers, dict):
        raise ConfigError(f"{path}: 'tiers' must be an object")
    for tier, value in tiers.items():
        if tier not in TIERS:
            raise ConfigError(f"{path}: unknown tier '{tier}'")
        if value is not None:
            _check_model_id(value, f"tier '{tier}'")

    overrides = data.get("overrides", {})
    if not isinstance(overrides, dict):
        raise ConfigError(f"{path}: 'overrides' must be an object")
    for role, value in overrides.items():
        if role not in ROLES:
            raise ConfigError(f"{path}: unknown role '{role}' in overrides")
        _check_model_id(value, f"override '{role}'")

    config = dict(data)
    config["preset"] = preset
    config["tiers"] = {tier: tiers.get(tier) for tier in TIERS}
    config["overrides"] = dict(overrides)
    return config


def save_config(path, config):
    """Write the config atomically (temp file in the same directory, then os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(config, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def resolve_role(config, role):
    """Return (model_id_or_None, source) with source override | preset:<tier> | unresolved."""
    override = config["overrides"].get(role)
    if override:
        return override, "override"
    tier = PRESETS[config["preset"]][role]
    model = config["tiers"].get(tier)
    if model:
        return model, f"preset:{tier}"
    return None, "unresolved"


def _status(config, path):
    roles = {}
    for role in ROLES:
        model, source = resolve_role(config, role)
        roles[role] = {"model": model, "source": source}
    return {
        "config": str(path),
        "preset": config["preset"],
        "tiers": config["tiers"],
        "overrides": config["overrides"],
        "roles": roles,
    }


def cmd_status(arguments):
    config = load_config(arguments.config)
    status = _status(config, arguments.config)
    if arguments.json:
        print(json.dumps(status, indent=2))
        return 0
    print(f"config: {status['config']}")
    print(f"preset: {status['preset']}")
    print("tiers:")
    for tier in TIERS:
        print(f"  {tier}: {status['tiers'][tier] or 'unresolved'}")
    print("overrides:")
    if status["overrides"]:
        for role in ROLES:
            if role in status["overrides"]:
                print(f"  {role}: {status['overrides'][role]}")
    else:
        print("  (none)")
    print("resolved models:")
    for role in ROLES:
        entry = status["roles"][role]
        print(f"  {role}: {entry['model'] or entry['source']}" + (f" ({entry['source']})" if entry["model"] else ""))
    return 0


def cmd_resolve(arguments):
    config = load_config(arguments.config)
    model, source = resolve_role(config, arguments.role)
    if model is None:
        tier = PRESETS[config["preset"]][arguments.role]
        print(
            f"{arguments.role}: unresolved (no override and tier '{tier}' of preset "
            f"'{config['preset']}' has no model ID); set one with set-shared, set-tier, or set-override",
            file=sys.stderr,
        )
        return EXIT_UNRESOLVED
    print(model)
    return 0


def _mutate(arguments, change, message):
    config = load_config(arguments.config)
    change(config)
    save_config(arguments.config, config)
    print(message)
    return 0


def cmd_set_preset(arguments):
    return _mutate(
        arguments,
        lambda config: config.__setitem__("preset", arguments.preset),
        f"preset set to {arguments.preset}",
    )


def _warn_if_label(value):
    if re.search(r"[ ()]", value):
        print(LABEL_WARNING.format(value=value), file=sys.stderr)


def cmd_set_shared(arguments):
    """One shared starting model for every role: the balanced preset with one tier model."""
    _check_model_id(arguments.model_id, "shared model")
    _warn_if_label(arguments.model_id)

    def change(config):
        config["preset"] = "balanced"
        config["tiers"]["balanced"] = arguments.model_id

    return _mutate(arguments, change, f"all roles now use {arguments.model_id} (preset balanced); override per role if needed")


def cmd_set_tier(arguments):
    _check_model_id(arguments.model_id, f"tier '{arguments.tier}'")
    _warn_if_label(arguments.model_id)
    return _mutate(
        arguments,
        lambda config: config["tiers"].__setitem__(arguments.tier, arguments.model_id),
        f"tier {arguments.tier} set to {arguments.model_id}",
    )


def cmd_set_override(arguments):
    _check_model_id(arguments.model_id, f"override '{arguments.role}'")
    _warn_if_label(arguments.model_id)
    return _mutate(
        arguments,
        lambda config: config["overrides"].__setitem__(arguments.role, arguments.model_id),
        f"override {arguments.role} set to {arguments.model_id}",
    )


def cmd_clear_override(arguments):
    return _mutate(
        arguments,
        lambda config: config["overrides"].pop(arguments.role, None),
        f"override {arguments.role} cleared",
    )


def _newest_events_file():
    sessions = Path.home() / ".copilot" / "session-state"
    candidates = []
    for candidate in sessions.glob("*/events.jsonl"):
        try:
            candidates.append((candidate.stat().st_mtime, candidate))
        except OSError:
            continue
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def _read_events(path):
    """Return (started, completed, skipped, context) from an events file.

    started/completed are dicts keyed by toolCallId; skipped counts bad lines. context holds the
    parent session model in effect when each delegation started and the permission-event counts.
    """
    started = {}
    completed = {}
    skipped = 0
    parent_model = None
    context = {
        "parentModels": {},
        "permissions": {"requested": 0, "completed": 0, "decisionSources": {}},
    }
    with path.open("rb") as stream:
        for raw in stream:
            if not raw.strip():
                continue
            try:
                event = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeError):
                skipped += 1
                continue
            if not isinstance(event, dict):
                skipped += 1
                continue
            kind = event.get("type")
            data = event.get("data")
            if not isinstance(data, dict):
                data = {}
            if kind == "session.start":
                selected = data.get("selectedModel")
                # "auto" is a selection mode, not a model that could be compared.
                if isinstance(selected, str) and selected and selected != "auto":
                    parent_model = selected
            elif kind == "session.model_change":
                # Events carrying an agentId belong to a delegated agent, not the parent session.
                new_model = data.get("newModel")
                if "agentId" not in event and isinstance(new_model, str) and new_model:
                    parent_model = new_model
            elif kind == "permission.requested":
                context["permissions"]["requested"] += 1
            elif kind == "permission.completed":
                context["permissions"]["completed"] += 1
                source = _text(data.get("decisionSource"))
                sources = context["permissions"]["decisionSources"]
                sources[source] = sources.get(source, 0) + 1
            elif kind in ("subagent.started", "subagent.completed"):
                call_id = data.get("toolCallId")
                if not isinstance(call_id, str) or not call_id:
                    skipped += 1
                    continue
                # A duplicate toolCallId overwrites the earlier event of the same kind.
                if kind == "subagent.started":
                    started[call_id] = data
                    context["parentModels"][call_id] = parent_model
                else:
                    completed[call_id] = data
    return started, completed, skipped, context


def _text(*values):
    for value in values:
        if isinstance(value, str) and value:
            return value
    return NOT_AVAILABLE


def _number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return None


def _override_effect(requested, evidence, actual, parent_model):
    """Say what the events support about an override; equality alone is not proof it changed anything."""
    if evidence == "none":
        return "n/a (no override requested)"
    if requested == NO_OVERRIDE_RECORDED or not actual:
        return NOT_AVAILABLE
    if any(model != requested for model in actual):
        return "requested model not observed (actual differs from requested)"
    if parent_model is None:
        return "not demonstrated (parent session model not available)"
    if parent_model == requested:
        return "not demonstrated (parent session used the same model)"
    return "consistent with override (actual differs from parent session model)"


def _delegation(call_id, started, completed, parent_model=None):
    # Requested model comes only from the completed event's explicitModelOverride.
    requested = INHERITED
    evidence = "none"
    explicit = completed.get("explicitModelOverride")
    if isinstance(explicit, str) and explicit:
        requested = explicit
        evidence = "explicitModelOverride recorded"
    elif started.get("taskModelSource") == "task_argument":
        requested = NO_OVERRIDE_RECORDED
        evidence = "task_argument only (no explicitModelOverride recorded)"

    started_model = _text(started.get("model"))
    completed_model = _text(completed.get("model"))
    actual = [m for m in (started_model, completed_model) if m != NOT_AVAILABLE]
    if requested == INHERITED:
        match = "n/a"
    elif requested == NO_OVERRIDE_RECORDED or not actual:
        match = NOT_AVAILABLE
    else:
        match = "yes" if all(m == requested for m in actual) else "no"

    tokens = _number(completed.get("totalTokens"))
    tool_calls = _number(completed.get("totalToolCalls"))
    duration = _number(completed.get("durationMs"))
    return {
        "toolCallId": call_id,
        "agent": _text(
            started.get("agentType"),
            started.get("agentName"),
            completed.get("agentType"),
            completed.get("agentName"),
        ),
        "requested": requested,
        "overrideEvidence": evidence,
        "taskModelSource": _text(started.get("taskModelSource")),
        "modelSelectionSource": _text(
            started.get("modelSelectionSource"), completed.get("modelSelectionSource")
        ),
        "parentModel": _text(parent_model),
        "startedModel": started_model,
        "completedModel": completed_model,
        "firstDispatchedModel": _text(completed.get("firstDispatchedModel")),
        "totalTokens": NOT_AVAILABLE if tokens is None else tokens,
        "totalTokensNote": TOKENS_LABEL,
        "totalToolCalls": NOT_AVAILABLE if tool_calls is None else tool_calls,
        "durationMs": NOT_AVAILABLE if duration is None else duration,
        "match": match,
        "overrideEffect": _override_effect(requested, evidence, actual, parent_model),
    }


def build_report(path):
    started, completed, skipped, context = _read_events(path)
    delegations = [
        _delegation(
            call_id,
            started.get(call_id, {}),
            completed.get(call_id, {}),
            context["parentModels"].get(call_id),
        )
        for call_id in list(started) + [c for c in completed if c not in started]
    ]
    # Totals sum task-level figures only; session-wide usage is not attributed to any delegation.
    totals = {}
    for item in delegations:
        entry = totals.setdefault(
            item["agent"], {"delegations": 0, "tokens": 0, "toolCalls": 0, "durationMs": 0}
        )
        entry["delegations"] += 1
        for key, field in (("tokens", "totalTokens"), ("toolCalls", "totalToolCalls"), ("durationMs", "durationMs")):
            if item[field] != NOT_AVAILABLE:
                entry[key] += item[field]
    permissions = context["permissions"]
    return {
        "events": str(path),
        "skippedLines": skipped,
        "delegations": delegations,
        "totals": totals,
        "permissions": {
            "requestedEvents": permissions["requested"],
            "completedEvents": permissions["completed"],
            "decisionSources": permissions["decisionSources"],
            "note": PERMISSIONS_NOTE,
        },
    }

def cmd_report(arguments):
    path = arguments.events
    if path is None:
        path = _newest_events_file()
        if path is None:
            print(
                f"no events.jsonl found under {Path.home() / '.copilot' / 'session-state'}",
                file=sys.stderr,
            )
            return EXIT_ERROR
    elif not path.is_file():
        print(f"events file not found: {path}", file=sys.stderr)
        return EXIT_ERROR

    report = build_report(path)
    if arguments.json:
        print(json.dumps(report, indent=2))
        return 0

    print(f"events: {report['events']}")
    print(f"skipped unreadable/malformed lines: {report['skippedLines']}")
    print(f"delegations: {len(report['delegations'])}")
    for index, item in enumerate(report["delegations"], start=1):
        print(f"{index}. agent: {item['agent']} (toolCallId {item['toolCallId']})")
        print(f"   requested: {item['requested']}")
        print(f"   taskModelSource: {item['taskModelSource']}")
        print(f"   modelSelectionSource: {item['modelSelectionSource']}")
        print(f"   parent session model: {item['parentModel']}")
        print(f"   started model: {item['startedModel']}")
        print(f"   completed model: {item['completedModel']}")
        print(f"   firstDispatchedModel: {item['firstDispatchedModel']}")
        print(f"   override evidence: {item['overrideEvidence']}")
        print(f"   requested == actual: {item['match']}")
        print(f"   override effect: {item['overrideEffect']}")
        print(f"   totalTokens: {item['totalTokens']} ({TOKENS_LABEL})")
        print(f"   totalToolCalls: {item['totalToolCalls']}")
        print(f"   durationMs: {item['durationMs']}")
    print("per-agent totals (sums of task-level figures; session-wide usage is not attributed):")
    if not report["totals"]:
        print("  (none)")
    for agent, entry in report["totals"].items():
        print(
            f"  {agent}: delegations={entry['delegations']} "
            f"tokens={entry['tokens']} toolCalls={entry['toolCalls']} durationMs={entry['durationMs']}"
        )
    permissions = report["permissions"]
    print(
        f"permission events: requested={permissions['requestedEvents']} "
        f"completed={permissions['completedEvents']} decisionSources={permissions['decisionSources']}"
    )
    print(f"  note: {permissions['note']}")
    return 0


def _build_parser():
    parser = argparse.ArgumentParser(
        description="Inspect and change per-specialist model preferences, and report delegations."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="preferences file (default: .factory/model-preferences.json in the repository root)",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    status = commands.add_parser("status", help="show preset, tiers, overrides, resolved models")
    status.add_argument("--json", action="store_true", help="emit JSON")
    status.set_defaults(handler=cmd_status)

    resolve = commands.add_parser("resolve", help="print the model ID for a role")
    resolve.add_argument("role", choices=ROLES)
    resolve.set_defaults(handler=cmd_resolve)

    preset = commands.add_parser("set-preset", help="select a preset")
    preset.add_argument("preset", choices=tuple(PRESETS))
    preset.set_defaults(handler=cmd_set_preset)

    shared = commands.add_parser(
        "set-shared", help="use one model ID for every role (balanced preset); overrides stay optional"
    )
    shared.add_argument("model_id", metavar="MODEL_ID")
    shared.set_defaults(handler=cmd_set_shared)

    tier = commands.add_parser("set-tier", help="set the model ID for a tier")
    tier.add_argument("tier", choices=TIERS)
    tier.add_argument("model_id", metavar="MODEL_ID")
    tier.set_defaults(handler=cmd_set_tier)

    override = commands.add_parser("set-override", help="set a per-role model ID override")
    override.add_argument("role", choices=ROLES)
    override.add_argument("model_id", metavar="MODEL_ID")
    override.set_defaults(handler=cmd_set_override)

    clear = commands.add_parser("clear-override", help="remove a per-role override")
    clear.add_argument("role", choices=ROLES)
    clear.set_defaults(handler=cmd_clear_override)

    report = commands.add_parser("report", help="requested vs actual models from events.jsonl")
    report.add_argument(
        "--events",
        type=Path,
        help="events file (default: newest ~/.copilot/session-state/*/events.jsonl)",
    )
    report.add_argument("--json", action="store_true", help="emit JSON")
    report.set_defaults(handler=cmd_report)
    return parser


def main(argv=None):
    arguments = _build_parser().parse_args(argv)
    arguments.config = arguments.config.expanduser()
    if getattr(arguments, "events", None) is not None:
        arguments.events = arguments.events.expanduser()
    try:
        return arguments.handler(arguments)
    except ConfigError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_INVALID_CONFIG
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
