from __future__ import annotations

from pathlib import Path

import pytest

from omnity_soap.paths import package_root
from omnity_soap.runtime import SOAPRuntime
from omnity_soap.validate import validate_action_file, validate_scene_file


EXAMPLES = package_root() / "examples"


@pytest.mark.parametrize(
    "name",
    ["minimal-scene.json", "mall-mixed-reality.json"],
)
def test_scene_examples_validate(name: str) -> None:
    validate_scene_file(EXAMPLES / name)


def test_sample_action_validates() -> None:
    validate_action_file(EXAMPLES / "sample-action-observe.json")


def test_runtime_load_mall() -> None:
    rt = SOAPRuntime.load(EXAMPLES / "mall-mixed-reality.json")
    assert rt.space_id == "mall_01"
    assert rt.get_object("npc_merchant_lin") is not None
    assert rt.get_region("atrium") is not None
