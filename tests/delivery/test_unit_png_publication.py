"""The shared PNG scope verifies before explicit publication and owns cleanup."""

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from spa.adapters.files import LocalArtifactFiles
from spa.adapters.png import verify_png
from spa.contracts.ports import KernelInvocationResult
from spa.contracts.public import Diagnostics
from spa.delivery.png_publication import staged_png


@pytest.mark.parametrize("publish", (False, True))
def test_scoped_verification_does_not_publish_until_caller_accepts(
    tmp_path: Path, publish: bool
):
    source = tmp_path / "source.aseprite"
    source.write_bytes(b"source")
    destination = tmp_path / "output.png"
    destination.write_bytes(b"previous")
    native = SimpleNamespace(
        width=1,
        height=1,
        color_profile="none",
        alpha_min=255,
        alpha_max=255,
        rendered_byte_size=4,
    )
    with staged_png(
        LocalArtifactFiles(),
        verify_png,
        source=source,
        destination=str(destination),
        if_exists="replace",
    ) as staged:
        Image.new("RGBA", (1, 1), (12, 34, 56, 255)).save(staged.png_file)
        staged.rgba_file.write_bytes(bytes((12, 34, 56, 255)))
        decoded = staged.verify(
            native,
            KernelInvocationResult({}, "/response.json", Diagnostics()),
            matches_expected=True,
            mismatch_message="Unexpected native render",
        )
        assert decoded.rgba_bytes == bytes((12, 34, 56, 255))
        assert destination.read_bytes() == b"previous"
        if publish:
            published = staged.publish()
            assert published.path == str(destination)
            assert published.byte_size == destination.stat().st_size
            assert (
                published.sha256 == hashlib.sha256(destination.read_bytes()).hexdigest()
            )
    assert not staged.png_file.exists()
    assert not staged.rgba_file.exists()
    assert source.read_bytes() == b"source"
    if not publish:
        assert destination.read_bytes() == b"previous"


def test_unverified_scope_cannot_publish(tmp_path: Path):
    destination = tmp_path / "output.png"
    destination.write_bytes(b"previous")
    with staged_png(
        LocalArtifactFiles(),
        verify_png,
        source=tmp_path / "source.aseprite",
        destination=str(destination),
        if_exists="replace",
    ) as staged:
        staged.png_file.write_bytes(b"unverified")
        with pytest.raises(RuntimeError, match="must pass verification"):
            staged.publish()
    assert not staged.png_file.exists()
    assert destination.read_bytes() == b"previous"
