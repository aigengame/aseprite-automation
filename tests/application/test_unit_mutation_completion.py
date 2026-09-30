"""Explicit publication and cleanup through standalone mutation completion."""

from hashlib import sha256
from pathlib import Path

import pytest

from spa.adapters.files import LocalTargetFiles
from spa.application.mutation import prepare_mutation
from spa.contracts.ports import (
    RequestIssue,
    RuntimeIssue,
    TargetCommitObservation,
)


class ObservedFiles(LocalTargetFiles):
    def __init__(self) -> None:
        self.stages: list[Path] = []
        self.discards: list[Path] = []
        self.commits = 0
        self.identity_unavailable = False

    def same_publication_entry(self, source: Path, target: Path) -> bool:
        if self.identity_unavailable:
            raise OSError("Identity observation failed")
        return super().same_publication_entry(source, target)

    def staged_path(self, target: Path) -> Path:
        staged = super().staged_path(target)
        self.stages.append(staged)
        return staged

    def commit(
        self, staged: Path, target: Path, *, overwrite: bool
    ) -> TargetCommitObservation:
        self.commits += 1
        return super().commit(staged, target, overwrite=overwrite)

    def discard(self, staged: Path) -> None:
        self.discards.append(staged)
        super().discard(staged)


@pytest.fixture(params=[False, True], ids=["separate-target", "in-place"])
def publication(tmp_path: Path, request: pytest.FixtureRequest):
    source = tmp_path / "source.aseprite"
    source.write_bytes(b"original Source")
    in_place = request.param
    target = source if in_place else tmp_path / "target.aseprite"
    if not in_place:
        target.write_bytes(b"original Target")
    return source, target, in_place


def prepare(files, publication, *, overwrite=True):
    source, target, in_place = publication
    return prepare_mutation(
        files,
        source,
        target,
        in_place=in_place,
        overwrite=overwrite,
        identity_change_message="Caller identity failure message",
    )


def assert_discarded(files: ObservedFiles) -> None:
    assert len(files.stages) == 1
    assert files.discards == files.stages
    assert not files.stages[0].exists()


def test_preflight_is_immediate_and_does_not_allocate_staging(publication) -> None:
    files = ObservedFiles()
    files.identity_unavailable = True
    with pytest.raises(RequestIssue) as failure:
        prepare(files, publication)
    assert failure.value.issues[0].code == "source_target_identity"
    assert files.stages == files.discards == []
    assert files.commits == 0


def test_staging_starts_on_entry_and_never_implies_commit(publication) -> None:
    files = ObservedFiles()
    source, target, _ = publication
    before_source, before_target = source.read_bytes(), target.read_bytes()
    completion = prepare(files, publication)
    assert files.stages == []
    with completion as mutation:
        mutation.staged_sprite_file.write_bytes(b"unvalidated Sprite")
    assert files.commits == 0
    assert source.read_bytes() == before_source
    assert target.read_bytes() == before_target
    assert_discarded(files)


@pytest.mark.parametrize("partial_file", [False, True])
def test_body_failure_is_preserved_and_staging_is_discarded(
    publication, partial_file: bool
) -> None:
    files = ObservedFiles()
    source, target, _ = publication
    before_source, before_target = source.read_bytes(), target.read_bytes()
    rejected = ValueError("Caller rejected native evidence")
    with pytest.raises(ValueError) as failure, prepare(files, publication) as mutation:
        if partial_file:
            mutation.staged_sprite_file.write_bytes(b"partial Sprite")
        raise rejected
    assert failure.value is rejected
    assert files.commits == 0
    assert source.read_bytes() == before_source
    assert target.read_bytes() == before_target
    assert_discarded(files)


def test_commit_rechecks_identity_before_publication(publication) -> None:
    files = ObservedFiles()
    source, target, _ = publication
    before_source, before_target = source.read_bytes(), target.read_bytes()
    with (
        pytest.raises(RuntimeIssue) as failure,
        prepare(files, publication) as mutation,
    ):
        mutation.staged_sprite_file.write_bytes(b"validated Sprite")
        files.identity_unavailable = True
        mutation.commit()
    assert failure.value.kind == "target_commit_failed"
    assert str(failure.value) == "Caller identity failure message"
    assert failure.value.evidence.reason == "source_target_identity_changed"
    assert failure.value.evidence.target_sprite_file == str(target)
    assert files.commits == 0
    assert source.read_bytes() == before_source
    assert target.read_bytes() == before_target
    assert_discarded(files)


def test_commit_failure_keeps_classification_and_discards_staging(publication) -> None:
    files = ObservedFiles()
    source, target, _ = publication
    before_source, before_target = source.read_bytes(), target.read_bytes()
    with (
        pytest.raises(RuntimeIssue) as failure,
        prepare(files, publication, overwrite=False) as mutation,
    ):
        mutation.staged_sprite_file.write_bytes(b"validated Sprite")
        mutation.commit()
    assert failure.value.kind == "target_commit_failed"
    assert failure.value.evidence.reason == "overwrite_not_allowed"
    assert files.commits == 1
    assert source.read_bytes() == before_source
    assert target.read_bytes() == before_target
    assert_discarded(files)


def test_explicit_commit_returns_exact_facts_and_cleans_staging(publication) -> None:
    files = ObservedFiles()
    source, target, in_place = publication
    before_source = source.read_bytes()
    payload = b"validated Sprite"
    with prepare(files, publication) as mutation:
        mutation.staged_sprite_file.write_bytes(payload)
        committed = mutation.commit()
    assert committed.model_dump() == {
        "target_sprite_file": str(target),
        "byte_size": len(payload),
        "sha256": sha256(payload).hexdigest(),
    }
    assert target.read_bytes() == payload
    if not in_place:
        assert source.read_bytes() == before_source
    assert files.commits == 1
    assert_discarded(files)
