"""Une maison construite avec les seuls outils de la bibliothèque, meublée et décorée automatiquement.

    python examples/villa.py maison.json && python -m homekit3d build maison.json maison.glb
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from homekit3d import Catalog, Plan
from homekit3d.stylist import Stylist

plan = Plan(width=12.0, depth=9.0, seed=7)
plan.rect_room("living", 0, 0, 6.0, 5.0, name="Séjour")
plan.rect_room("kitchen", 6.0, 0, 12.0, 3.0, name="Cuisine")
plan.rect_room("dining", 6.0, 3.0, 12.0, 5.0, name="Repas")
plan.rect_room("hallway", 0, 5.0, 12.0, 6.0, name="Couloir")
plan.rect_room("bedroom", 0, 6.0, 4.5, 9.0, name="Chambre 1")
plan.rect_room("bedroom", 4.5, 6.0, 8.5, 9.0, name="Chambre 2")
plan.rect_room("bathroom", 8.5, 6.0, 12.0, 9.0, name="Salle de bain")
plan.outline()
plan.walls_from_rooms()
plan.door(plan.wall_at(6.0, 5.0, tol=0.3), 1.0)                      # séjour -> couloir
plan.door(plan.wall_at(2.0, 6.0), 1.2)                              # couloir -> chambre 1
plan.door(plan.wall_at(6.5, 6.0), 0.8)                              # couloir -> chambre 2
plan.door(plan.wall_at(10.0, 6.0), 0.8)                             # couloir -> salle de bain
plan.window(plan.wall_at(3.0, 0.0), 1.5, width=1.4)
plan.window(plan.wall_at(9.0, 0.0), 1.5, width=1.4)
plan.window(plan.wall_at(0.0, 2.5), 1.0)
plan.window(plan.wall_at(2.0, 9.0), 1.2)
plan.window(plan.wall_at(6.5, 9.0), 1.2)
plan.window(plan.wall_at(12.0, 7.5), 0.8, width=0.9)
plan.validate()

report = Stylist(Catalog.load()).style(plan)
print(json.dumps(report, ensure_ascii=False))
out = Path(sys.argv[1] if len(sys.argv) > 1 else "villa.json")
out.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
print(out, len(plan.items), "objets")
