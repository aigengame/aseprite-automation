"""One observed native runtime per Tile test module."""

import os

import pytest

from spa.adapters.aseprite.aseprite import probe
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest


@pytest.fixture(scope="module")
def runtime():
    return probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )
