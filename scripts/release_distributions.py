"""Inspect release archives as data; never import or execute their contents."""

import argparse
import tarfile
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path


def read_archives(directory: Path, version: str) -> dict[str, dict[str, bytes]]:
    prefix = f"aseprite_automation-{version}"
    wheel = f"{prefix}-py3-none-any.whl"
    sdist = f"{prefix}.tar.gz"
    names = {p.name for p in directory.iterdir() if p.name != ".gitignore"}
    if names != {wheel, sdist}:
        raise ValueError(
            f"expected one SPA wheel and sdist for {version}; got {sorted(names)}"
        )
    with zipfile.ZipFile(directory / wheel) as archive:
        wheel_files = {
            item.filename: archive.read(item)
            for item in archive.infolist()
            if not item.is_dir()
        }
    with tarfile.open(directory / sdist) as archive:
        sdist_files = {}
        for member in archive:
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
            metadata.get("Name") != "aseprite-automation"
            or metadata.get("Version") != version
        ):
            raise ValueError(
                f"{filename}: metadata identity does not match aseprite-automation {version}"
            )
    return archives


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
        info = f"aseprite_automation-{version}.dist-info"
        metadata_path = (
            f"aseprite_automation-{version}.dist-info/METADATA" if wheel else "PKG-INFO"
        )
        metadata = BytesParser().parsebytes(files[metadata_path])
        if metadata.get("License-Expression") != "MIT":
            raise ValueError(f"{filename}: MIT license metadata is required")
        license_path = (
            f"aseprite_automation-{version}.dist-info/licenses/LICENSE"
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
    args = parser.parse_args()
    verify_contents(Path.cwd(), args.directory)
    print("verified public distribution contents")


if __name__ == "__main__":
    main()
