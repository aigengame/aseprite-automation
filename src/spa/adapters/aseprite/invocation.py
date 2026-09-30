"""Prepare the host process environment for an Aseprite CLI invocation."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from spa.contracts.ports import LaunchEvidence, RuntimeIssue


@dataclass(frozen=True)
class PreparedInvocation:
    executable: Path
    environment: dict[str, str]


def prepare_invocation(
    executable: Path, gui_resource: Path, work_dir: Path
) -> PreparedInvocation:
    """Keep installation identity separate from the path used to launch a process."""
    environment = os.environ.copy()
    user_folder = work_dir / "aseprite-user"
    environment["ASEPRITE_USER_FOLDER"] = str(user_folder)
    launch_path = executable

    try:
        user_folder.mkdir()
        if (
            sys.platform == "darwin"
            and executable.parent.name == "MacOS"
            and executable.parent.parent.name == "Contents"
            and executable.parent.parent.parent.suffix == ".app"
        ):
            launch_path = work_dir / executable.name
            launch_path.symlink_to(executable)
            (work_dir / "data").symlink_to(
                gui_resource.parent, target_is_directory=True
            )
    except OSError as exc:
        raise RuntimeIssue(
            "launch_failed",
            f"Could not prepare Aseprite CLI invocation: {exc}",
            LaunchEvidence(executable=str(executable)),
        ) from exc

    return PreparedInvocation(launch_path, environment)
