"""Validate the reviewed version and changelog before release cutting."""

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReleaseMetadata:
    version: str
    tag: str


def validate_release_metadata(root: Path) -> ReleaseMetadata:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]

    manifest = json.loads(
        (root / ".release-please-manifest.json").read_text(encoding="utf-8")
    )
    if manifest.get(".") != version:
        raise ValueError(
            "pyproject.toml and .release-please-manifest.json versions differ"
        )

    lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    locked_versions = [
        package["version"]
        for package in lock["package"]
        if package["name"] == "aseprite-automation"
    ]
    if locked_versions != [version]:
        raise ValueError(
            f"uv.lock has SPA versions {locked_versions!r}; expected {version!r}"
        )

    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    heading = re.compile(
        rf"^## (?:\[{re.escape(version)}\]|{re.escape(version)})(?:\s|$)",
        re.MULTILINE,
    )
    if heading.search(changelog) is None:
        raise ValueError(f"CHANGELOG.md has no release heading for {version}")

    config = json.loads(
        (root / "release-please-config.json").read_text(encoding="utf-8")
    )
    if config.get("include-component-in-tag") is not False:
        raise ValueError("release tags must exclude the package component")
    if config.get("include-v-in-tag") is not True:
        raise ValueError("release tags must retain the v prefix")

    return ReleaseMetadata(version=version, tag=f"v{version}")


def main() -> None:
    metadata = validate_release_metadata(Path.cwd())
    print(f"verified reviewed release metadata for {metadata.tag}")


if __name__ == "__main__":
    main()
