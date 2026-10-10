"""Keep the extracted geometry independent of orchestration and presentation."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_geometry_imports_without_transport_rendering_or_orchestration() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "\n".join(
                [
                    "import sys",
                    "from app import plan_geometry, plan_openings, plan_walls, room_program",
                    "for name in ('app.diffusion', 'app.pipeline', 'app.layout_opt', 'PIL', 'httpx', 'redis', 'fastapi'):",
                    "    assert name not in sys.modules, name",
                ]
            ),
        ],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root)},
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
