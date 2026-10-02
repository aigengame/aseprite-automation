"""Bounded source declarations for native Convolution Matrix resources.

This reads metadata, not native acceptance or convolution semantics. Coefficients,
divisors, and biases remain opaque. Aseprite owns their parsing and computation.
"""

import re
import stat
import sys
from collections import Counter
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

_MAX_SOURCE_BYTES = 1024 * 1024
_MAX_LINE_BYTES = 4095
_MAX_TOKEN_BYTES = 255
_BASENAMES = ("convmatr.usr", "convmatr.gen", "convmatr.def")
_DECLARATION_NOTE = (
    "Source declarations only; native parsing and Resource usability are not verified."
)


class _IncompleteDeclaration(ValueError):
    pass


def _tokens(text: str) -> Iterator[str]:
    """Read the bounded native space/comment/quote syntax, not shell syntax."""
    lines = text.split("\n")
    for line in lines:
        if len(line.encode("utf-8")) > _MAX_LINE_BYTES:
            raise _IncompleteDeclaration("physical line exceeds 4095 bytes")
    # Native fgets strips line endings; quoted multiline values concatenate lines.
    lines = [line.rstrip("\r") for line in lines]
    row, column = 0, 0
    while row < len(lines):
        line = lines[row]
        if column == len(line):
            row, column = row + 1, 0
            continue
        character = line[column]
        if character == " ":
            column += 1
            continue
        if character == "#":
            row, column = row + 1, 0
            continue
        if character != '"':
            end = line.find(" ", column)
            end = len(line) if end < 0 else end
            token = line[column:end]
            column = end
        else:
            column += 1
            value: list[str] = []
            while True:
                if column == len(lines[row]):
                    row, column = row + 1, 0
                    if row == len(lines):
                        raise _IncompleteDeclaration("unterminated quoted token")
                    continue
                character = lines[row][column]
                column += 1
                if character == '"':
                    break
                if character == "\\":
                    if column == len(lines[row]):
                        raise _IncompleteDeclaration("escape at end of physical line")
                    character = lines[row][column]
                    column += 1
                    if character == "n":
                        character = "\n"
                value.append(character)
                if len("".join(value).encode("utf-8")) > _MAX_TOKEN_BYTES:
                    raise _IncompleteDeclaration("token exceeds 255 bytes")
            token = "".join(value)
        if len(token.encode("utf-8")) > _MAX_TOKEN_BYTES:
            raise _IncompleteDeclaration("token exceeds 255 bytes")
        if token:  # Native tok_read does not return empty quoted values.
            yield token


def _declarations(text: str, source: str) -> tuple[list[dict[str, Any]], str | None]:
    tokens = _tokens(text)
    resources: list[dict[str, Any]] = []

    def take() -> str:
        try:
            return next(tokens)
        except StopIteration as exc:
            raise _IncompleteDeclaration("truncated declaration") from exc

    def integer() -> int:
        value = take()
        if re.fullmatch(r"[+-]?[0-9]+", value) is None:
            raise _IncompleteDeclaration("unsupported dimension or center token")
        return int(value)

    while True:
        try:
            name = next(tokens, None)
            if name is None:
                return resources, None
            width, height, center_x, center_y = (
                integer(),
                integer(),
                integer(),
                integer(),
            )
            if not 1 <= width <= 32 or not 1 <= height <= 32:
                raise _IncompleteDeclaration("dimension is outside 1..32")
            if not 0 <= center_x < width or not 0 <= center_y < height:
                raise _IncompleteDeclaration("center is outside the matrix")
            if take() != "{":
                raise _IncompleteDeclaration("unsupported opening brace token")
            for _ in range(width * height):
                if take() in ("{", "}"):
                    raise _IncompleteDeclaration(
                        "coefficient count does not match dimensions"
                    )
            if take() != "}":
                raise _IncompleteDeclaration(
                    "unsupported closing brace or coefficient count"
                )
            take()  # Divisor: native computation remains opaque.
            take()  # Bias: native computation remains opaque.
            target = take()
            channels = [
                channel
                for letter, channel in (
                    ("r", "red"),
                    ("g", "green"),
                    ("b", "blue"),
                    ("a", "alpha"),
                )
                if letter in target
            ]
            if any(letter in target for letter in "rgb"):
                channels.append("gray")
            resources.append(
                {
                    "name": name,
                    "source_path": source,
                    "declared_default_channels": channels,
                }
            )
        except _IncompleteDeclaration as exc:
            return resources, f"declaration {len(resources) + 1}: {exc}"


def discover_convolution_resources(
    executable: Path,
    environment: Mapping[str, str],
    *,
    platform: str = sys.platform,
) -> dict[str, Any]:
    """Observe declarations at this invocation's native ResourceFinder locations.

    The executable is the prepared launch path: resolving it before deriving its
    directory would change macOS resource lookup. Missing files are ordinary
    absence; unreadable or unsupported sources make metadata coverage incomplete.
    """
    binary_directory = executable.absolute().parent
    if platform == "darwin":
        user = environment.get("ASEPRITE_USER_FOLDER")
        user_directory = (
            Path(user)
            if user is not None
            else Path(environment.get("HOME", ""))
            / "Library/Application Support/Aseprite"
        )
        directories = [
            user_directory / "data",
            binary_directory / "data",
            binary_directory / "../Resources/data",
        ]
    elif platform == "win32":
        directories = []
        # Windows getenv is case-insensitive; os.environ.copy uses uppercase keys.
        appdata = next(
            (value for key, value in environment.items() if key.lower() == "appdata"),
            None,
        )
        if appdata is not None:
            directories.append(Path(appdata) / "Aseprite/data")
        directories.append(binary_directory / "data")
    elif platform.startswith("linux"):
        config = environment.get("XDG_CONFIG_HOME")
        config_directory = (
            Path(config) if config else Path(environment.get("HOME", "")) / ".config"
        )
        directories = [
            config_directory / "aseprite/data",
            binary_directory / "data",
            binary_directory / "../share/aseprite/data",
        ]
    else:
        return {
            "resources": [],
            "duplicate_names": [],
            "source_paths": [],
            "complete": False,
            "notes": [_DECLARATION_NOTE, f"Unsupported resource platform: {platform}"],
        }
    resources: list[dict[str, Any]] = []
    source_paths: list[str] = []
    notes = [_DECLARATION_NOTE]
    complete = True
    for basename in _BASENAMES:
        for directory in directories:
            candidate = directory / basename
            source = str(candidate.absolute())
            try:
                # stat distinguishes normal absence from permissions and bad paths.
                metadata = candidate.stat()
                source = str(candidate.resolve(strict=True))
                if not stat.S_ISREG(metadata.st_mode):
                    raise _IncompleteDeclaration("source is not a regular file")
                if source not in source_paths:
                    source_paths.append(source)
                with candidate.open("rb") as stream:
                    content = stream.read(_MAX_SOURCE_BYTES + 1)
                if len(content) > _MAX_SOURCE_BYTES:
                    raise _IncompleteDeclaration("source exceeds 1048576 bytes")
                text = content.decode("utf-8")
                if "\0" in text:
                    raise _IncompleteDeclaration("source contains NUL bytes")
                declarations, problem = _declarations(text, source)
                resources.extend(declarations)
                if problem is not None:
                    raise _IncompleteDeclaration(problem)
            except FileNotFoundError:
                continue
            except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
                complete = False
                notes.append(f"{source}: incomplete declarations: {exc}")
    counts = Counter(resource["name"] for resource in resources)
    return {
        "resources": resources,
        "duplicate_names": list(
            dict.fromkeys(
                resource["name"]
                for resource in resources
                if counts[resource["name"]] > 1
            )
        ),
        "source_paths": source_paths,
        "complete": complete,
        "notes": notes,
    }
