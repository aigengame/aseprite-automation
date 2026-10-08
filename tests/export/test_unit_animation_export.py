"""Public animation export verification gates with real Artifact Set mechanics."""

from copy import deepcopy
from dataclasses import replace
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from spa.adapters.artifact_set import LocalArtifactSets
from spa.adapters.files import LocalArtifactFiles, LocalTargetFiles
from spa.adapters.gif import decode_gif
from spa.adapters.sequence_png import decode_sequence_png
from spa.contracts.ports import KernelInvocationResult, OperationServices, RuntimeIssue
from spa.contracts.public import Diagnostics
from spa.delivery.animation import (
    ExportGifRequest,
    ExportSequenceRequest,
    export_gif,
    export_sequence,
)
from tests.support import runtime_observation


class _Export:
    """A controlled native response and encoded files, using the real publication port."""

    def __init__(self, tmp_path: Path, file_format: str, *, indexed: bool = False):
        self.file_format = file_format
        self.source = tmp_path / "source.aseprite"
        self.source.write_bytes(b"unchanged Source fixture")
        self.directory = tmp_path / "delivery"
        self.directory.mkdir()
        self.phases = []
        self.staging_root = None
        self.staged_damage = None
        self.png_decoder = decode_sequence_png
        self.gif_decoder = decode_gif
        self.resolution = {
            "width": 2,
            "height": 1,
            "color_mode": "indexed" if indexed else "rgb",
            "color_profile": "none",
            "icc_identity": None,
            "playback": {
                "mode": "explicit_frames",
                "tag_index": None,
                "tag": None,
                "occurrences": [
                    {
                        "occurrence": 1,
                        "source_frame_number": 1,
                        "source_duration_ms": 19,
                    },
                    {
                        "occurrence": 2,
                        "source_frame_number": 2,
                        "source_duration_ms": 27,
                    },
                ],
            },
            "filenames": ["frame_1.png", "frame_2.png"]
            if file_format == "png"
            else ["animation.gif"],
        }
        self.encoded_resolution = None
        self.native_frames = []
        self.pngs = []
        self.pixels = [
            bytes([17, 27, 37, 0, 200, 10, 20, 255]),
            bytes([17, 27, 37, 0, 10, 200, 20, 127]),
        ]
        for number in (1, 2):
            output = BytesIO()
            if indexed:
                entries = [
                    (17, 27, 37, 255),
                    (200, 10, 20, 255),
                    (10, 200, 20, 127),
                    (200, 10, 20, 255),
                ]
                image = Image.new("P", (2, 1))
                image.putpalette(
                    [component for entry in entries for component in entry[:3]]
                )
                image.putdata([0, number])
                image.save(
                    output, format="PNG", bits=2, transparency=bytes([0, 255, 127, 255])
                )
                self.pixels[number - 1] = bytes([0, number])
                palette = {
                    "palette_frame_number": 1,
                    "transparent_color_index": 0,
                    "entries": [
                        {
                            "index": index,
                            "color": dict(
                                zip(
                                    ("red", "green", "blue", "alpha"),
                                    entry,
                                    strict=True,
                                )
                            ),
                        }
                        for index, entry in enumerate(entries)
                    ],
                }
            else:
                Image.frombytes("RGBA", (2, 1), self.pixels[number - 1]).save(
                    output, format="PNG"
                )
                palette = None
            self.pngs.append(output.getvalue())
            frame = {
                "occurrence": number,
                "source_frame_number": number,
                "effective_background": False,
                "resolved_layer_paths": [[1]],
            }
            if file_format == "png":
                frame.update(filename=f"frame_{number}.png", effective_palette=palette)
            self.native_frames.append(frame)
        frames = []
        for number in (1, 2):
            image = Image.new("P", (2, 1))
            image.putpalette([0, 0, 0, 200, 10, 20, 10, 200, 20])
            image.putdata([0, number])
            frames.append(image)
        output = BytesIO()
        frames[0].save(
            output,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=[10, 20],
            loop=0,
            transparency=0,
            disposal=2,
            optimize=False,
        )
        self.gif = output.getvalue()
        self.gif_pixels = [frame.rgba_bytes for frame in decode_gif(self.gif).frames]
        self.input = {
            "source_sprite_file": str(self.source),
            "playback": {"kind": "frames", "frame_numbers": [1, 2]},
            "layer_composition": {"mode": "visible"},
            "destination": {"if_exists": "replace"},
        }
        if file_format == "png":
            self.input["destination"].update(
                directory=str(self.directory), filename_format="frame_{frame1}.png"
            )
            names = ["frame_1.png", "frame_2.png"]
        else:
            self.input["destination"]["path"] = str(self.directory / "animation.gif")
            names = ["animation.gif"]
        for name in names:
            (self.directory / name).write_bytes(b"previous Export")
        self.before = self.files()

    def files(self):
        return {path.name: path.read_bytes() for path in self.directory.iterdir()}

    def invoke(self, _runtime, _handler, payload, _timeout, *, working_directory=None):
        self.phases.append(payload["phase"])
        if payload["phase"] == "resolve":
            facts = deepcopy(self.resolution)
        else:
            output = Path(payload["output_directory"])
            evidence = Path(payload["evidence_directory"])
            self.staging_root = output.parent
            if self.file_format == "png":
                for index, name in enumerate(self.resolution["filenames"]):
                    (output / name).write_bytes(self.pngs[index % 2])
            else:
                (output / payload["output_filename"]).write_bytes(self.gif)
            for index, pixels in enumerate(self.pixels, 1):
                (evidence / f"{index}.pixels").write_bytes(pixels)
                if self.file_format == "gif":
                    (evidence / f"{index}.gif-rgba").write_bytes(
                        self.gif_pixels[index - 1]
                    )
            if self.staged_damage == "missing":
                next(output.iterdir()).unlink()
            elif self.staged_damage == "extra":
                (output / "unexpected.png").write_bytes(self.pngs[0])
            elif self.staged_damage == "malformed":
                next(output.iterdir()).write_bytes(b"not encoded image bytes")
            facts = {
                "resolution": deepcopy(self.encoded_resolution or self.resolution),
                "frames": deepcopy(self.native_frames),
            }
        return KernelInvocationResult(
            facts, "/response.json", Diagnostics(exit_status=0)
        )

    def execute(self):
        files = LocalArtifactFiles()
        services = OperationServices(
            probe_runtime=lambda _request: runtime_observation(
                "aseprite_export_sequence",
                "aseprite_export_gif",
                "aseprite_convert_color_profile",
            ),
            invoke_kernel=self.invoke,
            target_files=LocalTargetFiles(),
            artifact_files=files,
            artifact_sets=LocalArtifactSets(files),
            decode_sequence_png=self.png_decoder,
            decode_gif=self.gif_decoder,
        )
        if self.file_format == "png":
            return export_sequence(
                ExportSequenceRequest.model_validate(self.input), services
            )
        return export_gif(ExportGifRequest.model_validate(self.input), services)

    def unchanged(self):
        assert self.files() == self.before
        assert self.source.read_bytes() == b"unchanged Source fixture"
        if self.staging_root is not None:
            assert not self.staging_root.exists()


@pytest.mark.parametrize("file_format", ["png", "gif"])
def test_complete_verified_animation_publishes_ordered_artifacts(
    tmp_path: Path, file_format: str
) -> None:
    case = _Export(tmp_path, file_format)

    result = case.execute()

    assert result.status == "success"
    assert [frame.source_frame_number for frame in result.frames] == [1, 2]
    assert [artifact.role for artifact in result.artifacts] == (
        ["frame-0001", "frame-0002"] if file_format == "png" else ["animation"]
    )
    assert case.files() != case.before
    assert case.source.read_bytes() == b"unchanged Source fixture"
    assert not case.staging_root.exists()


@pytest.mark.parametrize("file_format", ["png", "gif"])
@pytest.mark.parametrize("damage", ["missing", "extra", "malformed"])
def test_incomplete_or_malformed_staged_animation_never_replaces_destinations(
    tmp_path: Path,
    file_format: str,
    damage: str,
) -> None:
    case = _Export(tmp_path, file_format)
    case.staged_damage = damage

    with pytest.raises(RuntimeIssue) as failure:
        case.execute()

    assert failure.value.kind == (
        "artifact_verification_failed"
        if damage == "malformed"
        else "artifact_file_failed"
    )
    case.unchanged()


@pytest.mark.parametrize("file_format", ["png", "gif"])
def test_malformed_resolution_is_typed_and_never_published(
    tmp_path: Path, file_format: str
) -> None:
    case = _Export(tmp_path, file_format)
    case.resolution["playback"]["occurrences"][0]["occurrence"] = 0

    with pytest.raises(RuntimeIssue) as failure:
        case.execute()

    assert failure.value.kind == "response_malformed"
    case.unchanged()


@pytest.mark.parametrize("file_format", ["png", "gif"])
def test_resolved_frames_must_match_explicit_playback_request(
    tmp_path: Path, file_format: str
) -> None:
    case = _Export(tmp_path, file_format)
    case.resolution["playback"]["occurrences"][1]["source_frame_number"] = 3
    case.native_frames[1]["source_frame_number"] = 3

    with pytest.raises(RuntimeIssue, match="Frames"):
        case.execute()

    case.unchanged()


@pytest.mark.parametrize("file_format", ["png", "gif"])
@pytest.mark.parametrize("contradiction", ["ordinal", "tag_address", "tag_direction"])
def test_resolved_occurrences_and_tag_facts_must_match_declared_playback(
    tmp_path: Path,
    file_format: str,
    contradiction: str,
) -> None:
    case = _Export(tmp_path, file_format)
    if contradiction == "ordinal":
        case.resolution["playback"]["occurrences"][1]["occurrence"] = 1
    else:
        case.input["playback"] = {"kind": "tag", "tag": {"tag_name": "walk"}}
        case.resolution["playback"].update(
            mode="tag_traversal",
            tag_index=1,
            tag={
                "name": "wrong" if contradiction == "tag_address" else "walk",
                "from_frame": 1,
                "to_frame": 2,
                "direction": "reverse"
                if contradiction == "tag_direction"
                else "forward",
                "repeats": 0,
                "color": {"red": 0, "green": 0, "blue": 0, "alpha": 0},
            },
        )

    with pytest.raises(RuntimeIssue):
        case.execute()

    case.unchanged()


@pytest.mark.parametrize("contradiction", ["wrong_name", "incomplete_names"])
def test_sequence_resolution_must_match_complete_filename_expansion(
    tmp_path: Path, contradiction: str
) -> None:
    case = _Export(tmp_path, "png")
    if contradiction == "wrong_name":
        case.resolution["filenames"][0] = "unrequested.png"
        case.native_frames[0]["filename"] = "unrequested.png"
    else:
        case.resolution["filenames"].pop()
        case.native_frames.pop()

    with pytest.raises(RuntimeIssue):
        case.execute()

    case.unchanged()


@pytest.mark.parametrize("file_format", ["png", "gif"])
def test_encode_phase_cannot_change_resolved_animation(
    tmp_path: Path, file_format: str
) -> None:
    case = _Export(tmp_path, file_format)
    case.encoded_resolution = deepcopy(case.resolution)
    case.encoded_resolution["playback"]["occurrences"][0]["source_duration_ms"] = 39

    with pytest.raises(RuntimeIssue, match="changed before encoding"):
        case.execute()

    case.unchanged()


@pytest.mark.parametrize("contradiction", ["profile", "palette"])
def test_sequence_profile_and_complete_palette_must_match_native_occurrence(
    tmp_path: Path, contradiction: str
) -> None:
    case = _Export(tmp_path, "png", indexed=contradiction == "palette")
    if contradiction == "profile":
        case.png_decoder = lambda payload: replace(
            decode_sequence_png(payload), color_profile="srgb"
        )
    else:
        case.native_frames[0]["effective_palette"]["entries"][3]["color"]["red"] = 199

    with pytest.raises(RuntimeIssue) as failure:
        case.execute()

    assert failure.value.kind == "artifact_verification_failed"
    case.unchanged()


@pytest.mark.parametrize("contradiction", ["duration", "alpha"])
def test_gif_decoded_timing_and_binary_alpha_must_match_native_evidence(
    tmp_path: Path, contradiction: str
) -> None:
    case = _Export(tmp_path, "gif")

    def decoder(payload):
        observed = decode_gif(payload)
        frame = observed.frames[0]
        if contradiction == "duration":
            frame = replace(frame, duration_ms=20)
        else:
            rgba = frame.rgba_bytes
            frame = replace(frame, rgba_bytes=rgba[:3] + bytes([255]) + rgba[4:])
        return replace(observed, frames=(frame, *observed.frames[1:]))

    case.gif_decoder = decoder
    with pytest.raises(RuntimeIssue) as failure:
        case.execute()

    assert failure.value.kind == "artifact_verification_failed"
    case.unchanged()


def test_gif_refuses_subcentisecond_source_frame_even_when_encoded_delay_is_zero(
    tmp_path: Path,
) -> None:
    case = _Export(tmp_path, "gif")
    case.resolution["playback"]["occurrences"][0]["source_duration_ms"] = 9
    encoded = bytearray(case.gif)
    control = encoded.index(b"\x21\xf9\x04")
    encoded[control + 4 : control + 6] = bytes(2)
    case.gif = bytes(encoded)

    with pytest.raises(RuntimeIssue):
        case.execute()

    case.unchanged()


@pytest.mark.parametrize("file_format", ["png", "gif"])
def test_unknown_icc_identity_cannot_become_an_admitted_animation_profile(
    tmp_path: Path, file_format: str
) -> None:
    case = _Export(tmp_path, file_format)
    case.resolution.update(color_profile="icc", icc_identity=None)
    if file_format == "png":
        profile = bytearray(
            Path("src/spa/kernel/color/profiles/display_p3.icc").read_bytes()
        )
        # A valid profile with a changed rendering intent has no packaged exact identity.
        profile[67] = (profile[67] + 1) % 4
        images = []
        for payload in case.pngs:
            output = BytesIO()
            with Image.open(BytesIO(payload)) as image:
                image.save(output, format="PNG", icc_profile=bytes(profile))
            images.append(output.getvalue())
        case.pngs = images

    with pytest.raises(RuntimeIssue):
        case.execute()

    case.unchanged()
