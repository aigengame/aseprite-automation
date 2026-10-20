"""Color Curve and Replace Color refuse inconsistent native evidence.

Each row names the validator text that refuses it. The Palette and parameter
rules of each Filter are rows of the `filter_case` table in
`test_integration_filter_correspondence.py`.
"""

import pytest

from spa.contracts.ports import RuntimeIssue
from tests.filter.support import (
    assert_malformed,
    assert_unpublished,
    operation_case,
    setup_operation,
)

# The validator text that refuses each corrupted evidence field.
CORRUPTION_CAUSES = {
    "channels": "Filter evidence disagrees with the requested application",
    "cel_survival": "Image survival disagrees with affected Cels",
    "processing": "Pixel Filter must process every distinct target Image",
    "persisted": "persisted_reopen_verified\n  Input should be True",
}


@pytest.mark.parametrize("name", ["color-curve", "replace-color"])
@pytest.mark.parametrize("corruption", [None, *CORRUPTION_CAUSES])
def test_pixel_filter_commit_requires_consistent_evidence(tmp_path, name, corruption):
    response, parameters, request_type, execute = operation_case(name)
    if corruption == "channels":
        response["channels"] = {"kind": "components", "names": ["alpha"]}
    elif corruption == "cel_survival":
        response["cel_effects"][0]["after"] = None
    elif corruption == "processing":
        response["processed_image_numbers"] = []
    elif corruption == "persisted":
        response["persisted_reopen_verified"] = False
    brightness, services, source, target, staged = setup_operation(tmp_path, response)
    fields = brightness.model_dump(exclude={"application", "brightness", "contrast"})
    application = brightness.application.model_dump(
        exclude={"kind", "tileset_mode"}, exclude_none=True
    )
    request = request_type.model_validate({**fields, **application, **parameters})
    if corruption:
        with pytest.raises(RuntimeIssue) as caught:
            execute(request, services)
        assert_malformed(caught, CORRUPTION_CAUSES[corruption])
        assert_unpublished(source, target, staged)
    else:
        execute(request, services)
        assert target.read_bytes() == b"native staged output"
        assert source.read_bytes() == b"original source"


def test_impossible_changed_count_cannot_publish(tmp_path):
    response, parameters, request_type, execute = operation_case("replace-color")
    response["changed_pixel_count"] = 2
    brightness, services, source, target, staged = setup_operation(tmp_path, response)
    request = request_type.model_validate(
        {
            **brightness.model_dump(exclude={"application", "brightness", "contrast"}),
            **brightness.application.model_dump(
                exclude={"kind", "tileset_mode"}, exclude_none=True
            ),
            **parameters,
        }
    )
    with pytest.raises(RuntimeIssue) as caught:
        execute(request, services)
    assert_malformed(
        caught, "Changed pixel count disagrees with observed native writeback"
    )
    assert_unpublished(source, target, staged)
