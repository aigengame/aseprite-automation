"""The Snapshot publication Interface requires completed owner verification."""

from pathlib import Path

import pytest

from spa.adapters.files import LocalArtifactFiles
from spa.contracts.snapshot import SnapshotDestination
from spa.delivery.snapshot_publication import staged_snapshot


@pytest.mark.parametrize("verify", (False, True))
def test_unverified_or_rejected_snapshot_cannot_be_published(tmp_path: Path, verify):
    source, destination = tmp_path / "source.aseprite", tmp_path / "snapshot.json"
    source.write_bytes(b"source")
    destination.write_bytes(b"previous artifact")

    def reject(_contents):
        raise ValueError("Snapshot differs from requested domain facts")

    with staged_snapshot(
        LocalArtifactFiles(),
        source=source,
        destination=SnapshotDestination(path=str(destination), if_exists="replace"),
    ) as staged:
        assert staged is not None
        staged.path.write_bytes(b"{}")
        if verify:
            with pytest.raises(ValueError, match="domain facts"):
                staged.verify(reject)
        with pytest.raises(RuntimeError, match="must pass verification"):
            staged.publish()
    assert destination.read_bytes() == b"previous artifact"
    assert source.read_bytes() == b"source"
    assert set(tmp_path.iterdir()) == {source, destination}
