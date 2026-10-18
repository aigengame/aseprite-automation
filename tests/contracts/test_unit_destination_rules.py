"""Edit-file and export destination rules, as one table for each rule.

Each rule refuses the request before the Kernel. Each Kernel port raises
`PortReached`, so a row that gets to the Kernel fails. Unless a rule says otherwise,
its CLI request uses a probe that reports every capability.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from spa.contracts.operation import OperationDescriptor
from spa.contracts.ports import RequestIssue
from tests.contracts.command_rules import (
    DESCRIPTORS,
    INPUT_REFUSAL,
    Outcome,
    PortReached,
    Rule,
    check_exemptions,
    check_row,
    minimal_request,
    rows,
    run_request,
    services,
    source_location,
)
from tests.host_permissions import symlink_creation_permission

ARTIFACT_REFUSAL = (1, "execution", "artifact_file_failed")


def edit_command(descriptor: OperationDescriptor[Any, Any]) -> bool:
    return descriptor.execution_kind == "mutation"


def export_command(descriptor: OperationDescriptor[Any, Any]) -> bool:
    return descriptor.execution_kind == "export"


NOT_EDIT = {
    "sprite create": "creates a Sprite without a Source",
    "sprite copy": "copies a Source to a Target without an in_place intent",
}
EXPORT_EXEMPT = {
    "export sequence": "names its files with the native Filename Format, in the Kernel",
}
NO_SPRITE_SOURCE = {
    "raster prepare": "has no Source Sprite",
    "selection export": "has no Source Sprite",
    "selection preview": "has no Source Sprite",
}
GIF_PREFLIGHT = {
    "export gif": "checks its destination after the native resolve phase (#279 part D)",
}


# Edit rules ----------------------------------------------------------------------


def _edit_root(request: dict[str, Any]) -> dict[str, Any]:
    return request.get("plan", request)


def _edit_location(command: str, *names: str) -> list[str]:
    # `plan run` reports the locations of its Plan under "plan".
    location = source_location(command)
    assert location is not None
    return [*location[:-1], *names]


def _edit(change: Callable[[dict[str, Any], Path], None], probe: str = "capable"):
    def run(command: str, directory: Path) -> Outcome:
        request = minimal_request(command, directory)
        change(_edit_root(request), directory)
        return run_request(command, request, probe=probe)

    return run


def _alias_target(root: dict[str, Any], _directory: Path) -> None:
    root.update(target_sprite_file=root["source_sprite_file"], in_place=False)
    root.update(overwrite=True)


def _distinct_target_in_place(root: dict[str, Any], _directory: Path) -> None:
    root.update(in_place=True, overwrite=True)


def _in_place_without_overwrite(root: dict[str, Any], _directory: Path) -> None:
    root.update(target_sprite_file=root["source_sprite_file"], in_place=True)
    root.update(overwrite=False)


def _source_symlink_to_target(root: dict[str, Any], directory: Path) -> None:
    target = Path(root["target_sprite_file"])
    target.write_bytes(b"Target")
    source = directory / "alias.aseprite"
    with symlink_creation_permission():
        source.symlink_to(target)
    root.update(source_sprite_file=str(source), in_place=False, overwrite=True)


def _files(directory: Path) -> dict[str, tuple[bool, bytes]]:
    return {
        path.name: (path.is_symlink(), path.read_bytes())
        for path in directory.iterdir()
    }


def _identity(
    change: Callable[[dict[str, Any], Path], None],
    name: str,
    message: str,
    intents: tuple[bool, ...] = (),
):
    """Refuse at the Operation, before its probe, the Kernel and staging.

    The dispatch of most commands probes the runtime first, so the CLI row uses a
    probe that reports every capability.
    """

    def run(command: str, directory: Path) -> Outcome:
        request = minimal_request(command, directory)
        root = _edit_root(request)
        change(root, directory)
        cli_intent = root["in_place"]
        descriptor = DESCRIPTORS[command]
        before = _files(directory)
        for in_place in intents or (cli_intent,):
            root["in_place"] = in_place
            with pytest.raises(RequestIssue) as refused:
                validated = descriptor.request_type.model_validate(request)
                descriptor.execute(validated, services("unreached"))
            assert [issue.model_dump() for issue in refused.value.issues] == [
                {
                    "location": _edit_location(command, name),
                    "code": "source_target_identity",
                    "message": message,
                }
            ], in_place
        assert _files(directory) == before
        root["in_place"] = cli_intent
        return run_request(command, request, probe="capable")

    return run


def _error(name: str, message: str):
    def check(command: str, outcome: Outcome) -> None:
        assert outcome.envelope["details"]["errors"] == [
            {
                "location": _edit_location(command, name),
                "code": "source_target_identity",
                "message": message,
            }
        ]

    return check


def _identity_rule(
    name: str,
    change: Callable[[dict[str, Any], Path], None],
    location: str,
    message: str,
    intents: tuple[bool, ...] = (),
) -> Rule:
    return Rule(
        name,
        edit_command,
        INPUT_REFUSAL,
        _identity(change, location, message, intents),
        _error(location, message),
        exempt=NOT_EDIT,
    )


def _overwrite_required(command: str, outcome: Outcome) -> None:
    message = "in_place requires overwrite permission"
    if command == "plan run":
        message = "In-place Plan requires overwrite permission"
    assert outcome.errors == [(_edit_location(command), "value_error")]
    assert outcome.envelope["details"]["errors"][0]["message"] == (
        f"Value error, {message}"
    )


IDENTITY_MISMATCH = "Source/Target publication identity must match in_place intent"

ALIAS_TRAVERSES_TARGET = "Source alias traverses the Target publication entry"

EDIT_RULES = (
    _identity_rule(
        "source_aliases_target", _alias_target, "in_place", IDENTITY_MISMATCH
    ),
    _identity_rule(
        "distinct_target_in_place",
        _distinct_target_in_place,
        "in_place",
        IDENTITY_MISMATCH,
    ),
    _identity_rule(
        "source_symlink_traverses_target",
        _source_symlink_to_target,
        "source_sprite_file",
        ALIAS_TRAVERSES_TARGET,
        intents=(False, True),
    ),
    Rule(
        "in_place_without_overwrite",
        edit_command,
        INPUT_REFUSAL,
        # The request model refuses it, before dispatch probes the runtime.
        _edit(_in_place_without_overwrite, probe="unreached"),
        _overwrite_required,
        exempt=NOT_EDIT,
    ),
)
EDIT_COMMANDS = EDIT_RULES[0].commands()


# Export rules --------------------------------------------------------------------


def _destinations(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for child in value for item in _destinations(child)]
    if not isinstance(value, dict):
        return []
    found = [value] if "path" in value and "if_exists" in value else []
    return found + [item for child in value.values() for item in _destinations(child)]


def _export(change: Callable[[dict[str, Any], Path], None]):
    def run(command: str, directory: Path) -> Outcome:
        request = minimal_request(command, directory)
        destinations = _destinations(request)
        assert destinations, "exempt an Export command without a destination"
        for destination in destinations:
            change(destination, directory)
        return run_request(command, request, probe="capable")

    return run


def _existing_destination(destination: dict[str, Any], _directory: Path) -> None:
    destination["if_exists"] = "fail"
    Path(destination["path"]).write_bytes(b"existing")


def _missing_parent(destination: dict[str, Any], directory: Path) -> None:
    name = Path(destination["path"]).name
    destination["path"] = str(directory / "missing" / name)


def _source_symlink_to_destination(command: str, directory: Path) -> Outcome:
    request = minimal_request(command, directory)
    destinations = _destinations(request)
    for destination in destinations:
        destination["if_exists"] = "replace"
    first = Path(destinations[0]["path"])
    first.write_bytes(b"destination")
    source = directory / "alias.aseprite"
    with symlink_creation_permission():
        source.symlink_to(first)
    location = source_location(command)
    assert location == ["source_sprite_file"], location
    request["source_sprite_file"] = str(source)
    return run_request(command, request, probe="capable")


def _reason(expected: str):
    def check(_command: str, outcome: Outcome) -> None:
        assert outcome.envelope["details"]["reason"] == expected, outcome.envelope

    return check


EXPORT_RULES = (
    Rule(
        "destination_exists",
        export_command,
        ARTIFACT_REFUSAL,
        _export(_existing_destination),
        _reason("destination_exists"),
        exempt=EXPORT_EXEMPT,
        xfail=GIF_PREFLIGHT,
    ),
    Rule(
        "destination_parent_missing",
        export_command,
        ARTIFACT_REFUSAL,
        _export(_missing_parent),
        _reason("destination_parent_missing"),
        exempt=EXPORT_EXEMPT,
        xfail=GIF_PREFLIGHT,
    ),
    Rule(
        "source_symlink_aliases_destination",
        export_command,
        ARTIFACT_REFUSAL,
        _source_symlink_to_destination,
        _reason("source_destination_alias"),
        exempt={**EXPORT_EXEMPT, **NO_SPRITE_SOURCE},
        xfail=GIF_PREFLIGHT,
    ),
)


@pytest.mark.parametrize(("rule", "command"), rows(EDIT_RULES + EXPORT_RULES))
def test_destination_rule(rule: Rule, command: str, tmp_path: Path) -> None:
    check_row(rule, command, tmp_path)


# User decision 2026-10-18 (#279): keep both behaviours. A standalone Edit command
# refuses an existing Target when it commits, after the Kernel. `plan run` refuses it
# before Aseprite starts, in its preflight (ADR-0003).
EXISTING_TARGET_REFUSED_BEFORE_ASEPRITE = {
    "plan run": {
        "location": ["plan", "target_sprite_file"],
        "code": "target_not_writable",
        "message": "Target Sprite File exists and overwrite is false",
    },
}


@pytest.mark.parametrize("command", EDIT_COMMANDS)
def test_existing_target_without_overwrite(command: str, tmp_path: Path) -> None:
    request = minimal_request(command, tmp_path)
    root = _edit_root(request)
    Path(root["target_sprite_file"]).write_bytes(b"Target")
    root.update(in_place=False, overwrite=False)
    error = EXISTING_TARGET_REFUSED_BEFORE_ASEPRITE.get(command)
    if error is None:
        with pytest.raises(PortReached, match="^invoke_kernel$"):
            run_request(command, request, probe="capable")
        return
    outcome = run_request(command, request, probe="capable")
    assert outcome.result == INPUT_REFUSAL
    assert outcome.envelope["details"]["errors"] == [error]


def _request_in(directory: Path, command: str) -> dict[str, Any]:
    directory = directory / command.replace(" ", "-")
    directory.mkdir()
    return minimal_request(command, directory)


def test_rule_sets_are_literal_predicates_minus_true_exemptions(
    tmp_path: Path,
) -> None:
    edit = {
        name for name, descriptor in DESCRIPTORS.items() if edit_command(descriptor)
    }
    assert len(edit - set(NOT_EDIT)) == len(EDIT_COMMANDS) == 72
    for command in edit:
        root = _edit_root(_request_in(tmp_path, command))
        has_intent = {"source_sprite_file", "in_place"} <= set(root)
        assert has_intent == (command not in NOT_EDIT), command
    export = {
        name for name, descriptor in DESCRIPTORS.items() if export_command(descriptor)
    }
    assert len(export) == 10
    for command in export:
        destinations = _destinations(_request_in(tmp_path, command))
        assert bool(destinations) == (command not in EXPORT_EXEMPT), command
        assert (source_location(command) is None) == (command in NO_SPRITE_SOURCE)
    for rule in EDIT_RULES + EXPORT_RULES:
        check_exemptions(rule)
