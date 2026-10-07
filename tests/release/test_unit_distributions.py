"""Inspect real archive bytes before they can become public release files."""

import hashlib
import io
import json
import tarfile
import urllib.error
import zipfile
from pathlib import Path

import pytest

from scripts.release_distributions import verify_contents, verify_pypi


@pytest.fixture
def distributions(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "source"
    package = root / "src/spa"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('"""SPA."""\n')
    (package / "kernel").mkdir()
    (package / "kernel/probe.lua").write_text("return true\n")
    (root / "LICENSE").write_text("MIT License\nCopyright (c) 2026 aigengame\n")
    (root / "README.md").write_text("# SPA\n")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "sprite-automation"\nversion = "1.2.3"\n'
    )
    dist = tmp_path / "dist"
    dist.mkdir()
    write_distributions(root, dist)
    return root, dist


def write_distributions(
    root: Path, dist: Path, *, license: bool = True, metadata_version: str = "1.2.3"
) -> None:
    metadata = (
        f"Metadata-Version: 2.4\nName: sprite-automation\nVersion: {metadata_version}\n".encode()
        + (b"License-Expression: MIT\nLicense-File: LICENSE\n" if license else b"")
        + b"\n# SPA\n"
    )
    prefix = "sprite_automation-1.2.3"
    files = {
        p.relative_to(root / "src").as_posix(): p.read_bytes()
        for p in (root / "src/spa").rglob("*")
        if p.is_file()
    }
    with zipfile.ZipFile(dist / f"{prefix}-py3-none-any.whl", "w") as wheel:
        for name, payload in files.items():
            wheel.writestr(name, payload)
        wheel.writestr(f"{prefix}.dist-info/METADATA", metadata)
        for name in ("WHEEL", "RECORD", "entry_points.txt"):
            wheel.writestr(f"{prefix}.dist-info/{name}", b"")
        if license:
            wheel.writestr(
                f"{prefix}.dist-info/licenses/LICENSE", (root / "LICENSE").read_bytes()
            )
    with tarfile.open(dist / f"{prefix}.tar.gz", "w:gz") as sdist:
        content = {f"src/{name}": data for name, data in files.items()}
        content.update(
            {
                name: (root / name).read_bytes()
                for name in ("README.md", "pyproject.toml")
            }
        )
        content["PKG-INFO"] = metadata
        if license:
            content["LICENSE"] = (root / "LICENSE").read_bytes()
        for name, payload in content.items():
            info = tarfile.TarInfo(f"{prefix}/{name}")
            info.size = len(payload)
            sdist.addfile(info, io.BytesIO(payload))


def test_public_distributions_require_the_confirmed_license(distributions) -> None:
    root, dist = distributions
    write_distributions(root, dist, license=False)

    with pytest.raises(ValueError, match="MIT"):
        verify_contents(root, dist)


def test_public_distributions_exclude_unintended_workspace_files(distributions) -> None:
    root, dist = distributions
    with zipfile.ZipFile(next(dist.glob("*.whl")), "a") as wheel:
        wheel.writestr("spa/.env", "TOKEN=private-workspace-material")

    with pytest.raises(ValueError, match="unexpected"):
        verify_contents(root, dist)


def test_archive_metadata_must_match_the_reviewed_version(distributions) -> None:
    root, dist = distributions
    write_distributions(root, dist, metadata_version="1.2.2")

    with pytest.raises(ValueError, match="metadata identity"):
        verify_contents(root, dist)


def test_public_pair_contains_the_same_sources_and_license(distributions) -> None:
    root, dist = distributions
    assert len(verify_contents(root, dist)) == 2


def test_changed_kernel_resource_is_rejected(distributions) -> None:
    root, dist = distributions
    (root / "src/spa/kernel/probe.lua").write_text("return false\n")
    with pytest.raises(ValueError, match="changed source file spa/kernel/probe.lua"):
        verify_contents(root, dist)


def test_unresolved_lfs_resource_cannot_be_published(distributions) -> None:
    root, dist = distributions
    (root / "src/spa/kernel/fixture.aseprite").write_text(
        "version https://git-lfs.github.com/spec/v1\noid sha256:example\n"
    )
    write_distributions(root, dist)
    with pytest.raises(ValueError, match="unresolved LFS"):
        verify_contents(root, dist)


def test_extra_distribution_does_not_become_public(distributions) -> None:
    root, dist = distributions
    (dist / "aseprite").write_bytes(b"external native executable")
    with pytest.raises(ValueError, match="one SPA wheel and sdist"):
        verify_contents(root, dist)


def pypi_response(dist: Path, names: list[str]) -> bytes:
    return json.dumps(
        {
            "info": {"name": "sprite-automation", "version": "1.2.3"},
            "urls": [
                {
                    "filename": name,
                    "size": (dist / name).stat().st_size,
                    "digests": {
                        "sha256": hashlib.sha256((dist / name).read_bytes()).hexdigest()
                    },
                }
                for name in names
            ],
        }
    ).encode()


def test_matching_partial_upload_can_resume_but_is_not_complete(
    distributions, monkeypatch
) -> None:
    _, dist = distributions
    existing = next(dist.glob("*.whl")).name
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *a, **kw: io.BytesIO(pypi_response(dist, [existing])),
    )

    assert verify_pypi(dist, "1.2.3", allow_missing=True) == [
        "sprite_automation-1.2.3.tar.gz"
    ]
    with pytest.raises(ValueError, match="missing"):
        verify_pypi(dist, "1.2.3")


@pytest.mark.parametrize("conflict", ["digest", "size", "version"])
def test_existing_conflicting_files_cannot_be_skipped(
    distributions, monkeypatch, conflict
) -> None:
    _, dist = distributions
    existing = next(dist.glob("*.whl")).name
    response = json.loads(pypi_response(dist, [existing]))
    if conflict == "digest":
        response["urls"][0]["digests"]["sha256"] = "0" * 64
    elif conflict == "size":
        response["urls"][0]["size"] += 1
    else:
        response["info"]["version"] = "1.2.2"
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *a, **kw: io.BytesIO(json.dumps(response).encode()),
    )
    with pytest.raises(ValueError, match="conflict"):
        verify_pypi(dist, "1.2.3", allow_missing=True)


def test_complete_matching_upload_can_be_reused(distributions, monkeypatch) -> None:
    _, dist = distributions
    response = pypi_response(dist, [path.name for path in dist.iterdir()])
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: io.BytesIO(response))
    assert verify_pypi(dist, "1.2.3") == []


@pytest.mark.parametrize("status", [403, 404, 503])
def test_only_not_found_can_start_a_new_upload(
    distributions, monkeypatch, status
) -> None:
    _, dist = distributions

    def unavailable(url, **kwargs):
        raise urllib.error.HTTPError(url, status, "controlled response", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", unavailable)
    if status == 404:
        assert len(verify_pypi(dist, "1.2.3", allow_missing=True)) == 2
        with pytest.raises(ValueError, match="missing"):
            verify_pypi(dist, "1.2.3")
    else:
        with pytest.raises(urllib.error.HTTPError):
            verify_pypi(dist, "1.2.3", allow_missing=True)
