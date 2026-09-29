"""Ownership and native facts at the shared Sprite persistence boundary."""

from importlib.resources import files
from pathlib import Path

import pytest

from tests.frame.test_e2e_frame import _run_fixture

pytestmark = pytest.mark.e2e


def run_verified_save(tmp_path: Path, case: str) -> None:
    kernel = files("spa.kernel")
    _run_fixture(
        str(Path(__file__).parent / "fixtures" / "verified_save.lua"),
        persistence=str(kernel.joinpath("sprite_persistence.lua")),
        inspection=str(kernel.joinpath("sprite_inspect.lua")),
        digest=str(kernel.joinpath("digest.lua")),
        staged=str(tmp_path / "staged.aseprite"),
        case=case,
    )


def test_verified_save_transfers_ownership_and_returns_fresh_facts(
    tmp_path: Path,
) -> None:
    run_verified_save(tmp_path, "success")
    assert (tmp_path / "staged.aseprite").is_file()


@pytest.mark.parametrize("case", ["save", "reopen", "observation", "comparison"])
def test_verified_save_closes_owned_sprites_on_failure(
    tmp_path: Path,
    case: str,
) -> None:
    run_verified_save(tmp_path, case)
