from pathlib import Path

from omnity_soap.explore import load_scene, viewer_roles_payload
from omnity_soap.paths import viewer_static_dir


def test_viewer_roles_payload_keys():
    root = Path(__file__).resolve().parent.parent
    scene = load_scene(root / "examples" / "mall-mixed-reality.json")
    roles = viewer_roles_payload(scene)
    assert len(roles) == 6
    keys = {r["key"] for r in roles}
    assert keys == {"mr", "phone", "glasses", "robot", "npc", "mr_npc"}
    for r in roles:
        assert "visible_object_ids" in r
        assert isinstance(r["visible_object_ids"], list)


def test_viewer_static_dir_has_index():
    d = viewer_static_dir()
    assert (d / "index.html").is_file(), f"missing index.html under {d}"
