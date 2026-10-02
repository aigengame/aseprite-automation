"""Convolution Resource declarations, independent of native filter execution."""

import json
from pathlib import Path

import pytest

from spa.adapters.aseprite.convolution import discover_convolution_resources


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _stock(name: str, target: str = "rgb") -> str:
    return (
        f"{name} 1 1 0 0 {{ opaque-coefficient }} opaque-divisor opaque-bias {target}\n"
    )


def _discover(tmp_path: Path, text: str) -> dict:
    executable = tmp_path / "bin/aseprite"
    _write(executable.parent / "data/convmatr.def", text)
    return discover_convolution_resources(executable, {}, platform="linux")


def test_declared_names_channels_and_opaque_computation_tokens(tmp_path: Path) -> None:
    result = _discover(
        tmp_path,
        _stock("brightness")
        + _stock("alpha-only", "a")
        + _stock("odd-flags", "RRrgxi")
        + _stock("unknown", "IX"),
    )
    assert result["complete"]
    assert [resource["name"] for resource in result["resources"]] == [
        "brightness",
        "alpha-only",
        "odd-flags",
        "unknown",
    ]
    assert [
        resource["declared_default_channels"] for resource in result["resources"]
    ] == [
        ["red", "green", "blue", "gray"],
        ["alpha"],
        ["red", "green", "gray"],
        [],
    ]
    assert result["duplicate_names"] == []
    assert "native parsing" in result["notes"][0]
    json.dumps(result, allow_nan=False)


def test_installed_like_multiline_matrix_comments_and_quotes(tmp_path: Path) -> None:
    result = _discover(
        tmp_path,
        '# heading\r\n"quoted name" 2 2 1 1 # header comment\r\n'
        " { 1 2\n 3 4 } auto auto rgba # tail\n"
        + _stock("literal#hash")
        + _stock("unquoted\\name")
        + _stock('"escaped\\nname\\""')
        + _stock('"multi\nline"'),
    )
    assert result["complete"]
    assert [resource["name"] for resource in result["resources"]] == [
        "quoted name",
        "literal#hash",
        "unquoted\\name",
        'escaped\nname"',
        "multiline",
    ]
    assert result["resources"][0]["declared_default_channels"] == [
        "red",
        "green",
        "blue",
        "alpha",
        "gray",
    ]


def test_tab_is_part_of_a_native_token_not_a_separator(tmp_path: Path) -> None:
    result = _discover(tmp_path, _stock("name\twith-tab"))
    assert result["complete"]
    assert result["resources"][0]["name"] == "name\twith-tab"
    result = _discover(tmp_path, "name\t1 1 0 0 { 1 } 1 0 rgb\n")
    assert not result["complete"]
    assert result["resources"] == []


@pytest.mark.parametrize(
    "invalid",
    [
        "broken 0 1 0 0 { 1 } 1 0 rgb",
        "broken 33 1 0 0 { 1 } 1 0 rgb",
        "broken 1 1 -1 0 { 1 } 1 0 rgb",
        "broken 1 1 1 0 { 1 } 1 0 rgb",
        "broken 1.0 1 0 0 { 1 } 1 0 rgb",
        "broken 1suffix 1 0 0 { 1 } 1 0 rgb",
        "broken 2 1 0 0 { 1 } 1 0 rgb",
        "broken 1 1 0 0 { 1 2 } 1 0 rgb",
        "broken 1 1 0 0 {suffix 1 } 1 0 rgb",
    ],
)
def test_malformed_record_stops_source_without_skipping_ahead(
    tmp_path: Path,
    invalid: str,
) -> None:
    result = _discover(tmp_path, _stock("before") + invalid + "\n" + _stock("after"))
    assert not result["complete"]
    assert [resource["name"] for resource in result["resources"]] == ["before"]
    assert "incomplete declarations" in result["notes"][-1]


@pytest.mark.parametrize("tail", ["broken 1 1 0 0 { 1 }", '"unterminated'])
def test_truncated_tail_retains_only_complete_prior_declarations(
    tmp_path: Path, tail: str
) -> None:
    result = _discover(tmp_path, _stock("before") + tail)
    assert not result["complete"]
    assert [r["name"] for r in result["resources"]] == ["before"]


@pytest.mark.parametrize(
    "invalid",
    ['"unclosed', '"escape\\\nname"', _stock("a" * 256), "#" + "a" * 4095],
)
def test_unsafe_or_unsupported_lexical_input_is_incomplete(
    tmp_path: Path,
    invalid: str,
) -> None:
    result = _discover(tmp_path, invalid)
    assert not result["complete"]
    assert result["resources"] == []


def test_source_size_encoding_and_nul_bounds(tmp_path: Path) -> None:
    executable = tmp_path / "bin/aseprite"
    source = _write(executable.parent / "data/convmatr.def", " " * (1024 * 1024 + 1))
    for content in (source.read_bytes(), b"\xff", b"name\0"):
        source.write_bytes(content)
        result = discover_convolution_resources(executable, {}, platform="linux")
        assert not result["complete"]
        assert result["source_paths"] == [str(source.resolve())]
        assert result["resources"] == []


def test_native_basename_and_path_order_retains_duplicate_declarations(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "prefix/bin/aseprite"
    config = tmp_path / "config"
    user = config / "aseprite/data"
    binary = executable.parent / "data"
    share = executable.parent / "../share/aseprite/data"
    sources = [
        _write(
            user / "convmatr.usr", _stock("duplicate", "a") + _stock("duplicate", "r")
        ),
        _write(binary / "convmatr.usr", _stock("bin-usr")),
        _write(share / "convmatr.usr", _stock("share-usr")),
        _write(user / "convmatr.gen", _stock("user-gen")),
        _write(binary / "convmatr.def", _stock("duplicate", "b")),
    ]
    result = discover_convolution_resources(
        executable, {"XDG_CONFIG_HOME": str(config)}, platform="linux"
    )
    assert result["complete"]
    assert [r["name"] for r in result["resources"]] == [
        "duplicate",
        "duplicate",
        "bin-usr",
        "share-usr",
        "user-gen",
        "duplicate",
    ]
    assert result["duplicate_names"] == ["duplicate"]
    assert result["source_paths"] == [str(source.resolve()) for source in sources]


def test_mac_prepared_launch_symlink_uses_adjacent_data_and_stable_source(
    tmp_path: Path,
) -> None:
    canonical = tmp_path / "Aseprite.app/Contents/MacOS/aseprite"
    _write(canonical, "binary")
    installed_data = canonical.parent / "../Resources/data"
    source = _write(installed_data / "convmatr.def", _stock("installed"))
    launch = tmp_path / "work/aseprite"
    launch.parent.mkdir()
    launch.symlink_to(canonical)
    (launch.parent / "data").symlink_to(installed_data, target_is_directory=True)
    _write(canonical.parent / "data/convmatr.usr", _stock("canonical-only"))
    _write(
        tmp_path / "home/Library/Application Support/Aseprite/data/convmatr.usr",
        _stock("ambient"),
    )
    user = tmp_path / "work/aseprite-user"
    result = discover_convolution_resources(
        launch,
        {"ASEPRITE_USER_FOLDER": str(user), "HOME": str(tmp_path / "home")},
        platform="darwin",
    )
    assert [r["name"] for r in result["resources"]] == ["installed"]
    assert result["resources"][0]["source_path"] == str(source.resolve())
    assert result["source_paths"] == [str(source.resolve())]


def test_mac_user_and_bundle_roots_are_independent_sources(tmp_path: Path) -> None:
    executable = tmp_path / "bundle/Contents/MacOS/aseprite"
    home = tmp_path / "home"
    _write(
        home / "Library/Application Support/Aseprite/data/convmatr.usr", _stock("home")
    )
    _write(executable.parent / "../Resources/data/convmatr.def", _stock("bundle"))
    result = discover_convolution_resources(
        executable, {"HOME": str(home)}, platform="darwin"
    )
    assert [r["name"] for r in result["resources"]] == ["home", "bundle"]


@pytest.mark.parametrize("config", [None, ""])
def test_linux_empty_config_uses_home_and_ignores_user_folder(
    tmp_path: Path, config: str | None
) -> None:
    executable = tmp_path / "prefix/bin/aseprite"
    home = tmp_path / "home"
    user = tmp_path / "isolated-user"
    _write(home / ".config/aseprite/data/convmatr.usr", _stock("home"))
    _write(user / "data/convmatr.usr", _stock("user-folder"))
    environment = {"HOME": str(home), "ASEPRITE_USER_FOLDER": str(user)}
    if config is not None:
        environment["XDG_CONFIG_HOME"] = config
    result = discover_convolution_resources(executable, environment, platform="linux")
    assert [r["name"] for r in result["resources"]] == ["home"]


def test_linux_missing_home_uses_native_relative_config_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    source = _write(Path(".config/aseprite/data/convmatr.usr"), _stock("relative"))
    result = discover_convolution_resources(
        tmp_path / "bin/aseprite", {}, platform="linux"
    )
    assert result["source_paths"] == [str(source.resolve())]
    assert result["resources"][0]["name"] == "relative"


@pytest.mark.parametrize("appdata_key", ["AppData", "APPDATA", "appdata"])
def test_windows_uses_appdata_and_binary_but_not_user_folder(
    tmp_path: Path, appdata_key: str
) -> None:
    executable = tmp_path / "bin/aseprite.exe"
    appdata = tmp_path / "appdata"
    user = tmp_path / "user"
    _write(appdata / "Aseprite/data/convmatr.usr", _stock("appdata"))
    _write(executable.parent / "data/convmatr.def", _stock("binary"))
    _write(user / "data/convmatr.usr", _stock("user-folder"))
    result = discover_convolution_resources(
        executable,
        {appdata_key: str(appdata), "ASEPRITE_USER_FOLDER": str(user)},
        platform="win32",
    )
    assert [r["name"] for r in result["resources"]] == ["appdata", "binary"]
    result = discover_convolution_resources(executable, {}, platform="win32")
    assert [r["name"] for r in result["resources"]] == ["binary"]


def test_missing_sources_are_normal_and_unreadable_source_is_incomplete(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "bin/aseprite"
    result = discover_convolution_resources(executable, {}, platform="linux")
    assert result["complete"] and result["source_paths"] == []
    (executable.parent / "data/convmatr.usr").mkdir(parents=True)
    _write(executable.parent / "data/convmatr.def", _stock("after-failed-source"))
    result = discover_convolution_resources(executable, {}, platform="linux")
    assert not result["complete"]
    assert result["resources"][0]["name"] == "after-failed-source"


def test_alias_search_paths_retain_native_duplicate_loads(tmp_path: Path) -> None:
    executable = tmp_path / "bin/aseprite"
    source = _write(executable.parent / "data/convmatr.def", _stock("alias"))
    config = tmp_path / "config"
    (config / "aseprite").mkdir(parents=True)
    (config / "aseprite/data").symlink_to(source.parent, target_is_directory=True)
    result = discover_convolution_resources(
        executable, {"XDG_CONFIG_HOME": str(config)}, platform="linux"
    )
    assert len(result["resources"]) == 2
    assert result["source_paths"] == [str(source.resolve())]
    assert result["duplicate_names"] == ["alias"]


def test_safe_native_dimension_and_token_boundaries(tmp_path: Path) -> None:
    name = "n" * 255
    coefficients = " ".join(["opaque"] * (32 * 32))
    # Keep physical lines inside the native line buffer.
    coefficients = coefficients.replace(
        "opaque opaque opaque opaque", "opaque opaque\nopaque opaque"
    )
    result = _discover(
        tmp_path, f"{name} 32 32 31 31 {{ {coefficients} }} auto auto rgba\n"
    )
    assert result["complete"]
    assert result["resources"][0]["name"] == name


def test_unsupported_platform_does_not_guess_resource_locations(tmp_path: Path) -> None:
    result = discover_convolution_resources(
        tmp_path / "aseprite", {}, platform="unknown"
    )
    assert not result["complete"]
    assert result["source_paths"] == []
    assert "Unsupported resource platform" in result["notes"][-1]
