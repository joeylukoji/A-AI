from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from import_sh3d import catalog_entries  # noqa: E402

PROPS = """
id#1=Author#bed
name#1=Bed
category#1=Bedroom
model#1=/pack/bed/bed.obj
width#1=140.5
depth#1=208
height#1=90
modelRotation#1=0 0 1 0 1 0 -1 0 0
name#2=Lamp
model#2=/pack/lamp.obj
width#2=20
depth#2=20
height#2=40
name#3=Incomplete
"""


def test_the_catalog_properties_give_size_rotation_and_model_of_each_piece():
    bed, lamp = catalog_entries(PROPS)
    assert (bed["name"], bed["model"], bed["width"], bed["depth"], bed["height"]) == ("Bed", "/pack/bed/bed.obj", "140.5", "208", "90")
    assert bed["modelRotation"] == "0 0 1 0 1 0 -1 0 0" and "modelRotation" not in lamp


def test_an_entry_without_a_model_is_skipped():
    assert [e["name"] for e in catalog_entries(PROPS)] == ["Bed", "Lamp"]
