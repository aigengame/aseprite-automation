"""Real filesystem checks for bounded export publication."""

from pathlib import Path

from spa.adapters.artifact_set import LocalArtifactSets
from spa.contracts.artifact_set import ArtifactDestination


def test_verified_set_publishes_in_declared_order_and_discards_staging(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    source.write_bytes(b"source")
    destinations = tuple(
        ArtifactDestination("image", tmp_path / name, "fail")
        for name in ("002.png", "001.png")
    )
    files = LocalArtifactSets()
    staged = files.prepare(source, destinations)
    assert staged.output_directory != staged.evidence_directory
    for destination, payload in zip(destinations, (b"second", b"first"), strict=True):
        (staged.output_directory / destination.path.name).write_bytes(payload)
    (staged.evidence_directory / "render.rgba").write_bytes(b"private evidence")
    observations = files.verify_set(staged)
    published = files.publish(staged, tuple(item.sha256 for item in observations))
    assert tuple(item.path for item in published) == tuple(
        str(item.path) for item in destinations
    )
    assert destinations[0].path.read_bytes() == b"second"
    assert destinations[1].path.read_bytes() == b"first"
    files.discard(staged)
    assert not staged.root.exists()
    assert source.read_bytes() == b"source"
    assert destinations[0].path.read_bytes() == b"second"


def test_set_preflight_rejects_empty_duplicate_and_colliding_destinations(
    tmp_path: Path,
) -> None:
    import pytest

    from spa.contracts.ports import RuntimeIssue

    source = tmp_path / "source.aseprite"
    source.write_bytes(b"source")
    (tmp_path / "other").mkdir()
    files = LocalArtifactSets()
    first = ArtifactDestination("image", tmp_path / "001.png", "fail")
    for destinations in (
        (),
        (first, first),
        (first, ArtifactDestination("image", tmp_path / "other" / "001.png", "fail")),
        (ArtifactDestination("image", source, "replace"),),
    ):
        with pytest.raises(RuntimeIssue) as caught:
            files.prepare(source, destinations)
        assert caught.value.kind == "artifact_file_failed"
    assert source.read_bytes() == b"source"
    assert not first.path.exists()


def test_complete_set_preflight_checks_existing_intent_before_staging(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import tempfile

    import pytest

    from spa.contracts.ports import RuntimeIssue

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    source = tmp_path / "source.aseprite"
    source.write_bytes(b"source")
    existing = tmp_path / "002.png"
    existing.write_bytes(b"old")
    files = LocalArtifactSets()
    destinations = (
        ArtifactDestination("image", tmp_path / "001.png", "fail"),
        ArtifactDestination("image", existing, "fail"),
    )
    with pytest.raises(RuntimeIssue) as caught:
        files.prepare(source, destinations)
    assert caught.value.evidence.reason == "destination_exists"
    assert {item.name for item in tmp_path.iterdir()} == {
        "source.aseprite",
        "002.png",
    }
    assert existing.read_bytes() == b"old"


def test_missing_unexpected_and_nonregular_outputs_never_publish(
    tmp_path: Path,
) -> None:
    import pytest

    from spa.contracts.ports import RuntimeIssue

    source = tmp_path / "source.aseprite"
    source.write_bytes(b"source")
    destination = ArtifactDestination("image", tmp_path / "001.png", "fail")
    files = LocalArtifactSets()
    staged = files.prepare(source, (destination,))
    output = staged.output_directory / "001.png"
    try:
        with pytest.raises(RuntimeIssue):
            files.verify_set(staged)
        output.write_bytes(b"encoded")
        unexpected = staged.output_directory / "002.png"
        unexpected.write_bytes(b"partial native output")
        with pytest.raises(RuntimeIssue):
            files.verify_set(staged)
        unexpected.unlink()
        output.unlink()
        output.symlink_to(source)
        with pytest.raises(RuntimeIssue):
            files.verify_set(staged)
        output.unlink()
        output.mkdir()
        with pytest.raises(RuntimeIssue):
            files.verify_set(staged)
        assert not destination.path.exists()
    finally:
        files.discard(staged)


def test_second_publication_failure_retains_first_replacement_and_reports_every_path(
    tmp_path: Path,
) -> None:
    import pytest

    from spa.adapters.files import LocalArtifactFiles
    from spa.contracts.artifact_set import ArtifactSetPublicationError
    from spa.contracts.ports import ArtifactFileEvidence, RuntimeIssue

    class SecondWriteFails(LocalArtifactFiles):
        def publish(self, staged, destination, *, if_exists, sha256):
            if destination.name == "002.png":
                raise RuntimeIssue(
                    "artifact_file_failed",
                    "Injected write failure",
                    ArtifactFileEvidence(str(destination), "publication_failed"),
                )
            return super().publish(
                staged, destination, if_exists=if_exists, sha256=sha256
            )

    source = tmp_path / "source.aseprite"
    source.write_bytes(b"source")
    first = tmp_path / "001.png"
    first.write_bytes(b"old first")
    last = tmp_path / "003.png"
    last.write_bytes(b"old last")
    destinations = tuple(
        ArtifactDestination("image", tmp_path / name, "replace")
        for name in ("001.png", "002.png", "003.png")
    )
    files = LocalArtifactSets(SecondWriteFails())
    staged = files.prepare(source, destinations)
    for destination in destinations:
        (staged.output_directory / destination.path.name).write_bytes(b"new")
    digests = tuple(item.sha256 for item in files.verify_set(staged))
    with pytest.raises(ArtifactSetPublicationError) as caught:
        files.publish(staged, digests)
    states = caught.value.destinations
    assert tuple(item.state for item in states) == (
        "published",
        "not_published",
        "not_published",
    )
    assert tuple(item.existed_before_publication for item in states) == (
        True,
        False,
        True,
    )
    assert states[0].replaced_existing is True
    assert states[1].replaced_existing is None
    assert tuple(item.path for item in states) == tuple(
        str(item.path) for item in destinations
    )
    files.discard(staged)
    assert first.read_bytes() == b"new"
    assert last.read_bytes() == b"old last"
    assert not destinations[1].path.exists()
    assert source.read_bytes() == b"source"


def test_after_write_failure_is_indeterminate_even_on_the_first_destination(
    tmp_path: Path,
) -> None:
    import pytest

    from spa.adapters.files import LocalArtifactFiles
    from spa.contracts.artifact_set import ArtifactSetPublicationError

    class AfterWriteFails(LocalArtifactFiles):
        def publish(self, staged, destination, *, if_exists, sha256):
            super().publish(staged, destination, if_exists=if_exists, sha256=sha256)
            raise OSError("Injected failure after final-path write")

    source = tmp_path / "source.aseprite"
    source.write_bytes(b"source")
    destination = ArtifactDestination("image", tmp_path / "001.png", "replace")
    destination.path.write_bytes(b"old")
    files = LocalArtifactSets(AfterWriteFails())
    staged = files.prepare(source, (destination,))
    (staged.output_directory / "001.png").write_bytes(b"new")
    digests = tuple(item.sha256 for item in files.verify_set(staged))
    with pytest.raises(ArtifactSetPublicationError) as caught:
        files.publish(staged, digests)
    assert caught.value.destinations[0].state == "indeterminate"
    assert caught.value.destinations[0].existed_before_publication is True
    assert caught.value.destinations[0].replaced_existing is None
    files.discard(staged)
    assert destination.path.read_bytes() == b"new"
    assert source.read_bytes() == b"source"


def test_tampered_later_output_fails_before_any_final_path_changes(
    tmp_path: Path,
) -> None:
    import pytest

    from spa.contracts.ports import RuntimeIssue

    source = tmp_path / "source.aseprite"
    source.write_bytes(b"source")
    files = LocalArtifactSets()
    destinations = tuple(
        ArtifactDestination("image", tmp_path / name, "replace")
        for name in ("001.png", "002.png")
    )
    destinations[0].path.write_bytes(b"old")
    staged = files.prepare(source, destinations)
    for destination in destinations:
        (staged.output_directory / destination.path.name).write_bytes(b"new")
    digests = tuple(item.sha256 for item in files.verify_set(staged))
    (staged.output_directory / "002.png").write_bytes(b"tampered")
    with pytest.raises(RuntimeIssue) as caught:
        files.publish(staged, digests)
    assert caught.value.evidence.reason == "staged_file_changed"
    assert destinations[0].path.read_bytes() == b"old"
    assert not destinations[1].path.exists()
    files.discard(staged)


def test_source_alias_that_appears_after_staging_is_refused_before_publication(
    tmp_path: Path,
) -> None:
    import pytest

    from spa.contracts.ports import RuntimeIssue

    original = tmp_path / "original.aseprite"
    original.write_bytes(b"source")
    source = tmp_path / "source.aseprite"
    source.symlink_to(original)
    destination = ArtifactDestination("image", tmp_path / "001.png", "replace")
    files = LocalArtifactSets()
    staged = files.prepare(source, (destination,))
    (staged.output_directory / "001.png").write_bytes(b"new")
    digests = tuple(item.sha256 for item in files.verify_set(staged))
    source.unlink()
    source.symlink_to(destination.path)
    with pytest.raises(RuntimeIssue) as caught:
        files.publish(staged, digests)
    assert caught.value.evidence.reason == "source_destination_alias"
    assert not destination.path.exists()
    assert original.read_bytes() == b"source"
    files.discard(staged)


def test_staging_allocation_failure_is_typed_and_leaves_final_paths_unchanged(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import errno
    import tempfile

    import pytest

    from spa.contracts.ports import RuntimeIssue

    source = tmp_path / "source.aseprite"
    source.write_bytes(b"source")

    def fail_allocation(*args, **kwargs):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(tempfile, "mkdtemp", fail_allocation)
    destination = ArtifactDestination("image", tmp_path / "001.png", "fail")
    with pytest.raises(RuntimeIssue) as caught:
        LocalArtifactSets().prepare(source, (destination,))
    assert caught.value.kind == "artifact_file_failed"
    assert caught.value.evidence.reason == "staging_failed"
    assert not destination.path.exists()
    assert source.read_bytes() == b"source"


def test_partial_native_output_and_wrong_digest_count_never_publish(
    tmp_path: Path,
) -> None:
    import pytest

    from spa.contracts.ports import RuntimeIssue

    source = tmp_path / "source.aseprite"
    source.write_bytes(b"source")
    files = LocalArtifactSets()
    destinations = tuple(
        ArtifactDestination("image", tmp_path / name, "fail")
        for name in ("001.png", "002.png")
    )
    staged = files.prepare(source, destinations)
    try:
        (staged.output_directory / "001.png").write_bytes(b"first")
        with pytest.raises(RuntimeIssue):
            files.publish(staged, ("irrelevant", "irrelevant"))
        (staged.output_directory / "002.png").write_bytes(b"second")
        verified = files.verify_set(staged)
        with pytest.raises(RuntimeIssue):
            files.publish(staged, (verified[0].sha256,))
        assert not any(item.path.exists() for item in destinations)
        assert source.read_bytes() == b"source"
    finally:
        files.discard(staged)


def test_publication_uses_destination_filesystem_when_system_temp_is_elsewhere(
    tmp_path: Path, monkeypatch
) -> None:
    import errno
    import os
    import tempfile

    temporary_volume = tmp_path / "system-temp-volume"
    destination_volume = tmp_path / "destination-volume"
    temporary_volume.mkdir()
    destination_volume.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temporary_volume))
    source = tmp_path / "source.aseprite"
    source.write_bytes(b"source")
    link, replace = os.link, os.replace

    def on_same_volume(operation):
        def guarded(staged, destination, **kwargs):
            # Model the OS boundary while retaining real link/replace and file contents.
            if not Path(staged).resolve().is_relative_to(destination_volume.resolve()):
                raise OSError(errno.EXDEV, "Invalid cross-device link")
            return operation(staged, destination, **kwargs)

        return guarded

    monkeypatch.setattr(os, "link", on_same_volume(link))
    monkeypatch.setattr(os, "replace", on_same_volume(replace))
    for policy in ("fail", "replace"):
        destination = destination_volume / f"{policy}.png"
        if policy == "replace":
            destination.write_bytes(b"old")
        files = LocalArtifactSets()
        staged = files.prepare(
            source, (ArtifactDestination("image", destination, policy),)
        )
        try:
            (staged.output_directory / destination.name).write_bytes(b"new")
            digests = tuple(item.sha256 for item in files.verify_set(staged))
            files.publish(staged, digests)
            assert destination.read_bytes() == b"new"
        finally:
            files.discard(staged)
        assert not staged.root.exists()
    assert source.read_bytes() == b"source"
