from __future__ import annotations

from pathlib import Path

from server import MAX_BODY, SCRIPT


def test_limits_and_script_name():
    assert MAX_BODY >= 1024
    assert Path(SCRIPT).name == "normalize_dxf.js" or "normalize" in str(SCRIPT)
