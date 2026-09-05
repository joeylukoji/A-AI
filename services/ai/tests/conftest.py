from __future__ import annotations

import os
import sys
from pathlib import Path

# Les tests NLU / pipeline restent heuristiques (pas d'appel Together).
os.environ.setdefault("TOGETHER_NLU", "0")
os.environ.setdefault("IMAGE_BACKEND", "procedural")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
