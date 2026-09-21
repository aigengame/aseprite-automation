"""Local filesystem adapter for staged Sprite publication."""

import hashlib
import os
import uuid
from pathlib import Path

from spa.ports import TargetCommitObservation


class LocalTargetFiles:
    def staged_path(self, target: Path) -> Path:
        token = uuid.uuid4().hex
        return target.with_name(f".{target.stem}.{token}.staged.aseprite")

    def commit(self, staged: Path, target: Path) -> TargetCommitObservation:
        if not staged.is_file():
            raise ValueError("Kernel did not produce a staged Sprite file")
        payload = staged.read_bytes()
        if not payload:
            raise ValueError("Kernel produced an empty staged Sprite file")
        digest = hashlib.sha256(payload).hexdigest()
        os.replace(staged, target)
        stat = target.stat()
        if stat.st_size != len(payload):
            raise OSError("Target Commit size changed during publication")
        return TargetCommitObservation(
            target_sprite_file=str(target),
            byte_size=stat.st_size,
            sha256=digest,
        )

    def discard(self, staged: Path) -> None:
        try:
            staged.unlink()
        except OSError:
            pass
