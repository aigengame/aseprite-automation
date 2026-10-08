"""Inspect real archive bytes before they can become public release files."""

import hashlib
import io
import json
import tarfile
import tomllib
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
    (root / "LICENSES").mkdir()
    (root / "LICENSES/CC0-1.0.txt").write_text("CC0 fixture license\n")
    (root / "THIRD_PARTY_NOTICES.md").write_text("# Third-party notices\n")
    (package / "kernel/color/profiles").mkdir(parents=True)
    (package / "kernel/color/profiles/NOTICE.txt").write_text(
        "CC0 Display P3 reference\n"
    )
    (package / "kernel/color/profiles/identities.json").write_text('{"profiles": []}\n')
    (root / "README.md").write_text("# SPA\n")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "aseprite-automation"\nversion = "1.2.3"\nlicense = "MIT AND CC0-1.0"\n'
        'license-files = ["LICENSE", "LICENSES/CC0-1.0.txt"]\n'
    )
    dist = tmp_path / "dist"
    dist.mkdir()
    write_distributions(root, dist)
    return root, dist


def write_distributions(
    root: Path, dist: Path, *, license: bool = True, metadata_version: str = "1.2.3"
) -> None:
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    license_names = project["license-files"]
    license_metadata = (
        "License-Expression: "
        + project["license"]
        + "\n"
        + "".join(f"License-File: {name}\n" for name in license_names)
    ).encode()
    metadata = (
        f"Metadata-Version: 2.4\nName: aseprite-automation\nVersion: {metadata_version}\n".encode()
        + (license_metadata if license else b"")
        + b"\n# SPA\n"
    )
    prefix = "aseprite_automation-1.2.3"
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
            for name in license_names:
                wheel.writestr(
                    f"{prefix}.dist-info/licenses/{name}", (root / name).read_bytes()
                )
    with tarfile.open(dist / f"{prefix}.tar.gz", "w:gz") as sdist:
        content = {f"src/{name}": data for name, data in files.items()}
        content.update(
            {
                name: (root / name).read_bytes()
                for name in ("README.md", "pyproject.toml", "THIRD_PARTY_NOTICES.md")
            }
        )
        content["PKG-INFO"] = metadata
        if license:
            content.update({name: (root / name).read_bytes() for name in license_names})
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


@pytest.mark.parametrize("archive_kind", ["wheel", "sdist"])
@pytest.mark.filterwarnings("ignore:Duplicate name:UserWarning")
def test_duplicate_paths_cannot_hide_unintended_archive_content(
    distributions, archive_kind: str
) -> None:
    root, dist = distributions
    private_payload = b"private sentinel that must never enter a public archive"
    if archive_kind == "wheel":
        path = next(dist.glob("*.whl"))
        with zipfile.ZipFile(path) as archive:
            members = [(item, archive.read(item)) for item in archive.infolist()]
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("spa/__init__.py", private_payload)
            for item, payload in members:
                archive.writestr(item, payload)
    else:
        path = next(dist.glob("*.tar.gz"))
        with tarfile.open(path) as archive:
            members = [(item, archive.extractfile(item).read()) for item in archive]
        with tarfile.open(path, "w:gz") as archive:
            duplicate = tarfile.TarInfo("aseprite_automation-1.2.3/README.md")
            duplicate.size = len(private_payload)
            archive.addfile(duplicate, io.BytesIO(private_payload))
            for item, payload in members:
                archive.addfile(item, io.BytesIO(payload))

    with pytest.raises(ValueError, match="duplicate archive member"):
        verify_contents(root, dist)


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
            "info": {"name": "aseprite-automation", "version": "1.2.3"},
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
        "aseprite_automation-1.2.3.tar.gz"
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


@pytest.mark.parametrize("embedded", [False, True])
@pytest.mark.parametrize("archive_kind", ["wheel", "sdist"])
def test_known_profile_payload_is_rejected_even_when_source_inventory_matches(
    distributions, monkeypatch, embedded: bool, archive_kind: str
) -> None:
    root, dist = distributions
    # A synthetic ICC-shaped sentinel tests the boundary without storing Apple bytes.
    sentinel = bytearray(536)
    sentinel[:4] = (536).to_bytes(4, "big")
    sentinel[36:40] = b"acsp"
    sentinel[128:] = b"x" * (536 - 128)
    monkeypatch.setattr(
        "scripts.release_distributions.APPLE_DISPLAY_P3_SHA256",
        hashlib.sha256(sentinel).hexdigest(),
    )
    payload = bytes(sentinel)
    if embedded:
        payload = b"authored document prefix" + payload + b"document suffix"
    resource = root / "src/spa/kernel/fixture.aseprite"
    resource.write_bytes(payload)
    write_distributions(root, dist)
    # Remove the sentinel from the other archive so both archive readers are exercised.
    other = "sdist" if archive_kind == "wheel" else "wheel"
    path = next(dist.glob("*.tar.gz" if other == "sdist" else "*.whl"))
    if other == "wheel":
        with zipfile.ZipFile(path) as archive:
            members = [(item, archive.read(item)) for item in archive.infolist()]
        with zipfile.ZipFile(path, "w") as archive:
            for item, data in members:
                archive.writestr(
                    item,
                    b"safe fixture"
                    if item.filename.endswith("fixture.aseprite")
                    else data,
                )
    else:
        with tarfile.open(path) as archive:
            members = [(item, archive.extractfile(item).read()) for item in archive]
        with tarfile.open(path, "w:gz") as archive:
            for item, data in members:
                if item.name.endswith("fixture.aseprite"):
                    data = b"safe fixture"
                    item.size = len(data)
                archive.addfile(item, io.BytesIO(data))
    with pytest.raises(ValueError, match="forbidden Apple Display P3"):
        verify_contents(root, dist)


def test_icc_structure_alone_does_not_reject_a_different_profile(distributions) -> None:
    root, dist = distributions
    profile = bytearray(536)
    profile[:4] = (536).to_bytes(4, "big")
    profile[36:40] = b"acsp"
    (root / "src/spa/kernel/reference.icc").write_bytes(profile)
    write_distributions(root, dist)
    assert len(verify_contents(root, dist)) == 2


@pytest.mark.parametrize("resource", ["identities.json", "NOTICE.txt"])
def test_changed_profile_identity_or_notice_is_rejected(
    distributions, resource
) -> None:
    root, dist = distributions
    (root / "src/spa/kernel/color/profiles" / resource).write_text("changed content\n")
    with pytest.raises(ValueError, match="changed source file"):
        verify_contents(root, dist)


def test_cc0_license_contents_must_match_source(distributions) -> None:
    root, dist = distributions
    (root / "LICENSES/CC0-1.0.txt").write_text("changed license\n")
    with pytest.raises(ValueError, match="changed source file"):
        verify_contents(root, dist)
