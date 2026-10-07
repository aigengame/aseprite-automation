"""Inspect release archives as data; never import or execute their contents."""

import argparse
import hashlib
import json
import tarfile
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from email.parser import BytesParser
from pathlib import Path


def read_archives(directory: Path, version: str) -> dict[str, dict[str, bytes]]:
    prefix = f"sprite_automation-{version}"
    wheel = f"{prefix}-py3-none-any.whl"
    sdist = f"{prefix}.tar.gz"
    names = {p.name for p in directory.iterdir() if p.name != ".gitignore"}
    if names != {wheel, sdist}:
        raise ValueError(
            f"expected one SPA wheel and sdist for {version}; got {sorted(names)}"
        )
    with zipfile.ZipFile(directory / wheel) as archive:
        wheel_files = {}
        wheel_members = set()
        for item in archive.infolist():
            if item.filename in wheel_members:
                raise ValueError(f"duplicate archive member: {item.filename}")
            wheel_members.add(item.filename)
            if not item.is_dir():
                wheel_files[item.filename] = archive.read(item)
    with tarfile.open(directory / sdist) as archive:
        sdist_files = {}
        sdist_members = set()
        for member in archive:
            if member.name in sdist_members:
                raise ValueError(f"duplicate archive member: {member.name}")
            sdist_members.add(member.name)
            if member.isdir():
                continue
            stream = archive.extractfile(member) if member.isfile() else None
            if stream is None or not member.name.startswith(prefix + "/"):
                raise ValueError(f"unexpected sdist member: {member.name}")
            sdist_files[member.name.removeprefix(prefix + "/")] = stream.read()
    archives = {wheel: wheel_files, sdist: sdist_files}
    for filename, files in archives.items():
        metadata_path = (
            f"{prefix}.dist-info/METADATA" if filename == wheel else "PKG-INFO"
        )
        metadata = BytesParser().parsebytes(files.get(metadata_path, b""))
        if (
            metadata.get("Name") != "sprite-automation"
            or metadata.get("Version") != version
        ):
            raise ValueError(
                f"{filename}: metadata identity does not match sprite-automation {version}"
            )
    return archives


def verify_pypi(
    directory: Path, version: str, *, allow_missing: bool = False
) -> list[str]:
    archives = read_archives(directory, version)
    url = f"https://pypi.org/pypi/sprite-automation/{urllib.parse.quote(version, safe='')}/json"
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            release = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        release = {
            "info": {"name": "sprite-automation", "version": version},
            "urls": [],
        }
    if (
        release["info"]["name"] != "sprite-automation"
        or release["info"]["version"] != version
    ):
        raise ValueError("PyPI release identity conflict")
    remote = {entry["filename"]: entry for entry in release["urls"]}
    if remote.keys() - archives.keys() or len(remote) != len(release["urls"]):
        raise ValueError("PyPI release file set conflict")
    for name, entry in remote.items():
        payload = (directory / name).read_bytes()
        if (
            entry["size"] != len(payload)
            or entry["digests"]["sha256"] != hashlib.sha256(payload).hexdigest()
        ):
            raise ValueError(
                f"PyPI file conflict: {name}; preserve the existing release and investigate"
            )
    missing = sorted(archives.keys() - remote.keys())
    if missing and not allow_missing:
        raise ValueError(f"PyPI release is missing files: {missing}")
    return missing


def verify_contents(root: Path, directory: Path) -> dict[str, dict[str, bytes]]:
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    version = project["version"]
    archives = read_archives(directory, version)
    source = {
        path.relative_to(root / "src").as_posix(): path.read_bytes()
        for path in (root / "src/spa").rglob("*")
        if path.is_file()
        and (
            path.suffix == ".py"
            or (
                path.is_relative_to(root / "src/spa/kernel")
                and path.suffix in {".lua", ".aseprite", ".icc"}
            )
        )
    }
    if not source:
        raise ValueError("source package inventory is empty")
    for filename, files in archives.items():
        wheel = filename.endswith(".whl")
        info = f"sprite_automation-{version}.dist-info"
        metadata_path = (
            f"sprite_automation-{version}.dist-info/METADATA" if wheel else "PKG-INFO"
        )
        metadata = BytesParser().parsebytes(files[metadata_path])
        if metadata.get("License-Expression") != "MIT":
            raise ValueError(f"{filename}: MIT license metadata is required")
        license_path = (
            f"sprite_automation-{version}.dist-info/licenses/LICENSE"
            if wheel
            else "LICENSE"
        )
        if files.get(license_path) != (root / "LICENSE").read_bytes():
            raise ValueError(f"{filename}: MIT license file differs from source")
        expected = (
            source if wheel else {f"src/{name}": data for name, data in source.items()}
        ) | {license_path: (root / "LICENSE").read_bytes()}
        if not wheel:
            expected.update(
                {
                    name: (root / name).read_bytes()
                    for name in ("README.md", "pyproject.toml")
                }
            )
        generated = (
            {
                f"{info}/{name}"
                for name in ("METADATA", "WHEEL", "RECORD", "entry_points.txt")
            }
            if wheel
            else {"PKG-INFO"}
        )
        unexpected = files.keys() - expected.keys() - generated
        if unexpected:
            raise ValueError(f"{filename}: unexpected files {sorted(unexpected)}")
        for name, payload in expected.items():
            if files.get(name) != payload:
                raise ValueError(f"{filename}: missing or changed source file {name}")
            if (
                not payload and Path(name).suffix in {".lua", ".aseprite", ".icc"}
            ) or payload.startswith(b"version https://git-lfs.github.com/spec/v1"):
                raise ValueError(
                    f"{filename}: empty resource or unresolved LFS pointer: {name}"
                )
    return archives


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument(
        "--pypi-tag", help="Verify PyPI files for the reviewed v-prefixed tag"
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Pre-upload check; matching partial uploads may resume",
    )
    args = parser.parse_args()
    try:
        if args.pypi_tag:
            if not args.pypi_tag.startswith("v") or len(args.pypi_tag) < 2:
                parser.error("--pypi-tag must be the reviewed v-prefixed release tag")
            missing = verify_pypi(
                args.directory, args.pypi_tag[1:], allow_missing=args.allow_missing
            )
            print(json.dumps({"tag": args.pypi_tag, "missing": missing}))
        else:
            if args.allow_missing:
                parser.error("--allow-missing requires --pypi-tag")
            verify_contents(Path.cwd(), args.directory)
            print("verified public distribution contents")
        for path in sorted(args.directory.iterdir()):
            if path.name != ".gitignore":
                print(
                    f"{path.name} size={path.stat().st_size} sha256={hashlib.sha256(path.read_bytes()).hexdigest()}"
                )
    except (
        ValueError,
        KeyError,
        OSError,
        tarfile.TarError,
        zipfile.BadZipFile,
    ) as error:
        raise SystemExit(f"release files verification failed: {error}") from error


if __name__ == "__main__":
    main()
