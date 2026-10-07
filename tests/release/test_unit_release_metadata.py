"""Release metadata gate tests."""

import json
from pathlib import Path

import pytest

from scripts.verify_release_metadata import validate_release_metadata


def write_release_tree(root: Path, *, version: str = "1.2.3") -> None:
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "sprite-automation"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    (root / ".release-please-manifest.json").write_text(
        json.dumps({".": version}), encoding="utf-8"
    )
    (root / "uv.lock").write_text(
        f'[[package]]\nname = "sprite-automation"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n"
        f"## [{version}](https://github.test/compare/v1.2.2...v{version}) (today)\n",
        encoding="utf-8",
    )
    (root / "release-please-config.json").write_text(
        json.dumps({"include-component-in-tag": False, "include-v-in-tag": True}),
        encoding="utf-8",
    )


def test_release_metadata_agrees_on_version_and_tag(tmp_path: Path) -> None:
    write_release_tree(tmp_path)

    metadata = validate_release_metadata(tmp_path)

    assert metadata.version == "1.2.3"
    assert metadata.tag == "v1.2.3"


def test_release_metadata_rejects_stale_lock(tmp_path: Path) -> None:
    write_release_tree(tmp_path)
    (tmp_path / "uv.lock").write_text(
        '[[package]]\nname = "sprite-automation"\nversion = "1.2.2"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="uv.lock"):
        validate_release_metadata(tmp_path)


def test_release_metadata_rejects_missing_changelog_entry(tmp_path: Path) -> None:
    write_release_tree(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")

    with pytest.raises(ValueError, match="CHANGELOG.md"):
        validate_release_metadata(tmp_path)
