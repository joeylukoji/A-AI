"""Catalogue de composants 3D réutilisables (murs, chaises, lits, tables)."""

from .primitives import CATALOG, default_size, glb_override, known_id, parts_for, world_boxes

__all__ = ["CATALOG", "default_size", "glb_override", "known_id", "parts_for", "world_boxes"]
