"""Construit `homekit3d/catalog/manifest.json` à partir des GLB des packs.

Chaque modèle reçoit un RÔLE (ce qu'il est : `bed.double`, `sofa`, `kitchen.stove`…), des étiquettes, les
types de pièces où il a sa place, ses dimensions réelles en mètres (lues dans le GLB, sans Blender) et sa
licence. Les modèles sans rôle utile (nourriture, bacs, pièces murales modulaires…) sont marqués `unused`.

    python tools/build_manifest.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from glbinfo import bounds  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent / "homekit3d"
ASSETS = ROOT / "assets"

PACKS = {
    "kenney-furniture": {
        "author": "Kenney (www.kenney.nl)", "license": "CC0-1.0", "style": ["modern", "simple"],
        "source": "https://kenney.nl/assets/furniture-kit",
    },
    "kaykit-furniture": {
        "author": "Kay Lousberg (www.kaylousberg.com)", "license": "CC0-1.0", "style": ["cozy", "warm"],
        "source": "https://kaylousberg.itch.io/furniture-bits",
    },
    "polyhaven": {
        "author": "Poly Haven contributors (polyhaven.com)", "license": "CC0-1.0", "style": ["premium", "hd", "realistic"],
        "source": "https://polyhaven.com/models", "real_size": True,
    },
    # Modèles de Sweet Home 3D (OBJ + textures) convertis en GLB par tools/sh3d_to_glb.py : déjà à la taille réelle, en mètres.
    "sh3d-b": {
        "author": "Blend Swap contributors, via the Sweet Home 3D catalog (sweethome3d.com)", "license": "CC0-1.0",
        "style": ["realistic", "hd"], "source": "https://github.com/YoannDev90/SweetHome3D-Packs", "real_size": True,
    },
    "sh3d-c": {
        "author": "Sweet Home 3D contributors (Contributions catalog 1.9.3)", "license": "Free Art License 1.3",
        "style": ["realistic", "hd"], "source": "https://www.sweethome3d.com/freeModels.jsp", "real_size": True,
    },
    "kaykit-restaurant": {
        "author": "Kay Lousberg (www.kaylousberg.com)", "license": "CC0-1.0", "style": ["kitchen", "restaurant"],
        "source": "https://kaylousberg.itch.io/restaurant-bits",
    },
}

# (motif sur le nom sans casse ni séparateurs, rôle, pièces, étiquettes) — le premier qui correspond gagne.
Rule = tuple[str, str, list[str], list[str]]
BED, LIV, KIT, BATH, OFF, DIN, HALL = "bedroom", "living", "kitchen", "bathroom", "office", "dining", "hallway"
RULES: list[Rule] = [
    # --- Poly Haven (détaillés, plus lourds : style « premium »)
    (r"^modern_arm_chair|^mid_century_lounge_chair|^armchair_01", "armchair", [LIV, BED], ["seating"]),
    (r"^sofa_0[12]$", "sofa", [LIV], ["seating"]),
    (r"^sofa_03$", "sofa.long", [LIV], ["seating"]),
    (r"^dining_chair|^woodenchair_01|^painted_wooden_chair|^greenchair", "chair.dining", [DIN, KIT], ["seating"]),
    (r"^ottoman_01", "ottoman", [LIV], ["seating"]),
    (r"coffee_?table", "table.coffee", [LIV], ["table"]),
    (r"^dining_table|^wooden_table_02", "table.dining", [DIN, KIT], ["table"]),
    (r"^side_table_01|nightstand", "nightstand", [BED, LIV], ["storage"]),
    (r"^modern_wooden_cabinet", "tv.console", [LIV], ["storage"]),
    (r"^drawer_cabinet|^vintage_cabinet", "wardrobe", [BED, HALL], ["storage", "tall"]),
    (r"^wooden_bookshelf|^shelf_01", "bookcase", [LIV, OFF], ["storage"]),
    (r"^metal_office_desk", "desk", [OFF], ["table"]),
    (r"^chandelier|^modern_ceiling_lamp", "lamp.ceiling", [LIV, BED, DIN, HALL], ["lamp", "ceiling"]),
    (r"^desk_lamp", "lamp.table", [BED, LIV, OFF], ["lamp"]),
    (r"^potted_plant_04", "plant.small", [LIV, BED, KIT, OFF, DIN], ["plant", "decor", "small"]),
    (r"^potted_plant|^calathea", "plant", [LIV, BED, HALL, OFF, DIN], ["plant", "decor"]),
    (r"picture_frame", "picture", [LIV, BED, HALL, DIN], ["decor", "wall"]),
    (r"^ornate_mirror", "mirror", [BATH, HALL, BED, LIV], ["decor", "wall"]),
    (r"^throw_pillows", "pillow", [LIV, BED], ["decor", "small"]),
    (r"^decorative_book", "books", [LIV, OFF], ["decor", "small"]),
    (r"^electric_stove", "kitchen.stove", [KIT], ["appliance"]),
    (r"^wall_clock", "clock", [LIV, KIT, HALL], ["decor", "wall"]),
    (r"^ceramic_vase|^wicker_basket", "vase", [LIV, HALL, DIN], ["decor", "small"]),
    # --- chambre
    (r"^beddouble|^bed-?double", "bed.double", [BED], ["bed"]),
    (r"^bedsingle|^bed-?single", "bed.single", [BED], ["bed"]),
    (r"^bedbunk", "bed.bunk", [BED], ["bed", "kids"]),
    (r"^cabinetbed(?!drawer)$|^cabinetbeddrawer(table)?$", "nightstand", [BED], ["storage"]),
    (r"^sidetable", "nightstand", [BED, LIV], ["storage"]),
    (r"^bookcaseclosed(doors|wide)?$", "wardrobe", [BED, HALL], ["storage", "tall"]),
    (r"^cabinet-?medium", "dresser", [BED, LIV, HALL], ["storage"]),
    (r"^cabinet-?small", "nightstand", [BED, LIV], ["storage"]),
    # --- séjour
    (r"^loungesofacorner|^loungedesignsofacorner", "sofa.corner", [LIV], ["seating"]),
    (r"^loungesofalong", "sofa.long", [LIV], ["seating"]),
    (r"^loungesofaottoman", "ottoman", [LIV], ["seating"]),
    (r"^loungesofa$|^loungedesignsofa$|^couch", "sofa", [LIV], ["seating"]),
    (r"^loungechair|^loungedesignchair|^armchair", "armchair", [LIV, BED], ["seating"]),
    (r"^tablecoffee|^table-?low", "table.coffee", [LIV], ["table"]),
    (r"^cabinettelevision", "tv.console", [LIV], ["storage"]),
    (r"^television(modern|vintage)", "tv", [LIV], ["appliance"]),
    (r"^bookcase(open|openlow)$", "bookcase", [LIV, OFF], ["storage"]),
    (r"^shelf-", "shelf.wall", [LIV, OFF, KIT], ["storage", "wall"]),
    # --- repas / bureau
    (r"^table(cross|glass)?(cloth)?$|^tableround|^table-?medium|^table-?small", "table.dining", [DIN, KIT], ["table"]),
    (r"^kitchentable", "kitchen.island", [KIT], ["counter", "table"]),
    (r"^chair(desk)$", "chair.desk", [OFF], ["seating"]),
    (r"^chair(modern|rounded|cushion|modernframecushion)?$|^chair-[abc]", "chair.dining", [DIN, KIT], ["seating"]),
    (r"^stool", "stool", [KIT, DIN], ["seating"]),
    (r"^chair-stool", "stool", [KIT, DIN], ["seating"]),
    (r"^bench", "bench", [HALL, DIN], ["seating"]),
    (r"^desk$|^deskcorner", "desk", [OFF, BED], ["table"]),
    (r"^computerscreen|^laptop", "computer", [OFF], ["appliance"]),
    # --- cuisine
    (r"^kitchenfridge(large|small|builtin)?$|^fridge-", "kitchen.fridge", [KIT], ["appliance"]),
    (r"^kitchenstove|^stove-", "kitchen.stove", [KIT], ["appliance"]),
    (r"^kitchensink|^kitchencounter-sink|^kitchentable-sink", "kitchen.sink", [KIT], ["counter"]),
    (r"^kitchencabinetupper|^hood|^extractorhood", "kitchen.upper", [KIT], ["counter", "wall"]),
    (r"^kitchencabinetcorner", "kitchen.corner", [KIT], ["counter"]),
    (r"^kitchencabinet(drawer)?$|^kitchencounter-straight|^kitchencabinet$|^kitchencabinet-", "kitchen.base", [KIT], ["counter"]),
    (r"^kitchenbar", "kitchen.bar", [KIT], ["counter"]),
    (r"^kitchen(microwave|coffeemachine|blender)|^toaster", "kitchen.small", [KIT], ["appliance", "decor"]),
    (r"^(washer|dryer|washerdryer)", "laundry.machine", [BATH, KIT, HALL], ["appliance"]),
    # --- salle de bain
    (r"^toilet", "toilet", [BATH], ["sanitary"]),
    (r"^bathroomsink", "sink.bath", [BATH], ["sanitary"]),
    (r"^bathtub", "bathtub", [BATH], ["sanitary"]),
    (r"^shower", "shower", [BATH], ["sanitary"]),
    (r"^bathroomcabinet", "bath.cabinet", [BATH], ["storage"]),
    (r"^bathroommirror", "mirror", [BATH], ["decor", "wall"]),
    # --- décor
    (r"^lamp(round|square)?floor|^lamp-?standing", "lamp.floor", [LIV, BED, OFF], ["lamp"]),
    (r"^lamp(round|square)?table|^lamp-table", "lamp.table", [BED, LIV, OFF], ["lamp"]),
    (r"^lampsquareceiling", "lamp.ceiling", [LIV, BED, KIT, HALL], ["lamp", "ceiling"]),
    (r"^lampwall", "lamp.wall", [HALL, LIV], ["lamp", "wall"]),
    (r"^(plantsmall|cactus-?small)", "plant.small", [LIV, BED, KIT, OFF, DIN], ["plant", "decor", "small"]),
    (r"^(pottedplant|cactus-?medium)", "plant", [LIV, BED, HALL, OFF, DIN], ["plant", "decor"]),
    (r"^rug(doormat)$", "rug.doormat", [HALL], ["rug"]),
    (r"^rug", "rug", [LIV, BED, DIN], ["rug"]),
    (r"^pillow", "pillow", [LIV, BED], ["decor", "small"]),
    (r"^pictureframe", "picture", [LIV, BED, HALL, DIN], ["decor", "wall"]),
    (r"^(books|book-)", "books", [LIV, OFF], ["decor", "small"]),
    (r"^coatrackstanding", "coat.rack", [HALL], ["storage"]),
    (r"^coatrack$", "coat.rack.wall", [HALL], ["storage", "wall"]),
    (r"^trashcan", "trash", [KIT, BATH], ["decor", "small"]),
    (r"^(radio|speaker)", "audio", [LIV], ["appliance", "small"]),
    # --- structure
    (r"^doorway|^door-", "door.frame", [], ["structure"]),
    (r"^stairs", "stairs", [], ["structure"]),
]

# Packs classés à la main, modèle par modèle (leurs noms ne suivent aucune convention) : fichier -> (rôle, pièces, étiquettes).
# Un modèle absent de la table est ignoré : la table est aussi la sélection.
SEAT, STO, APP, CTR, SAN, LMP, PLT = ["seating"], ["storage"], ["appliance"], ["counter"], ["sanitary"], ["lamp"], ["plant", "decor"]
PLANT_ROOMS = [LIV, BED, HALL, OFF, DIN]
SMALL_PLANT_ROOMS = [LIV, BED, KIT, OFF, DIN]
EXPLICIT: dict[str, dict[str, tuple[str, list[str], list[str]]]] = {
    "sh3d-b": {
        "bed1": ("bed.double", [BED], ["bed"]), "bed2": ("bed.double", [BED], ["bed"]), "bed3": ("bed.double", [BED], ["bed"]),
        "bedsideTable2": ("nightstand", [BED], STO), "wardrobeWithSlidingDoors": ("wardrobe", [BED, HALL], STO + ["tall"]),
        
        "couch": ("sofa", [LIV], SEAT), "couch2": ("sofa.corner", [LIV], SEAT), "sofa2": ("sofa", [LIV], SEAT),
        "winchesterSofa": ("sofa", [LIV], SEAT), "sofa": ("sofa.corner", [LIV], SEAT), "L_shaped_sofa": ("sofa.corner", [LIV], SEAT),
        "armchair2": ("armchair", [LIV, BED], SEAT), "modernArmchair": ("armchair", [LIV, BED], SEAT),
        "winchesterArmchair": ("armchair", [LIV, BED], SEAT),
        "oakTable": ("table.dining", [DIN, KIT], ["table"]), "table": ("table.dining", [DIN, KIT], ["table"]),
        "chair": ("chair.dining", [DIN, KIT], SEAT), "chair2": ("chair.dining", [DIN, KIT], SEAT),
        "thonet": ("chair.dining", [DIN, KIT], SEAT), "oakChair": ("chair.dining", [DIN, KIT], SEAT),
        "sillaBlanca": ("chair.dining", [DIN, KIT], SEAT), "chairWithCushion": ("chair.dining", [DIN, KIT], SEAT),
        "designChair": ("chair.dining", [DIN, KIT], SEAT), "stool": ("stool", [KIT, DIN], SEAT),
        "bookcase": ("bookcase", [LIV, OFF], STO), "led_tv": ("tv", [LIV], APP),
        "lbDesk": ("desk", [OFF, BED], ["table"]), "desk": ("desk", [OFF, BED], ["table"]),
        "lowerCabinet": ("kitchen.base", [KIT], CTR), "drawersCabinet": ("kitchen.base", [KIT], CTR),
        "sinkCabinet2": ("kitchen.sink", [KIT], CTR), "upperCabinet": ("kitchen.upper", [KIT], CTR + ["wall"]),
        "highCabinet": ("kitchen.tall", [KIT], STO + ["tall"]), "largeFridge": ("kitchen.fridge", [KIT], APP),
        "refrigerator": ("kitchen.fridge", [KIT], APP), "doubleOven": ("kitchen.oven", [KIT], APP),
        "toiletsUnit": ("toilet", [BATH], SAN), "washbasin": ("sink.bath", [BATH], SAN), "modernVanity": ("sink.bath", [BATH], SAN),
        "showerStall": ("shower", [BATH], SAN), "bidet": ("bidet", [BATH], SAN),
        "desklamp": ("lamp.table", [BED, LIV, OFF], LMP), "lamp2": ("lamp.table", [BED, LIV, OFF], LMP),
        "wallLight": ("lamp.wall", [HALL, LIV], LMP + ["wall"]),
        "decorativePlant": ("plant", PLANT_ROOMS, PLT), "plant": ("plant", PLANT_ROOMS, PLT),
        "orchids": ("plant.small", SMALL_PLANT_ROOMS, PLT + ["small"]),
        "littlePlant": ("plant.small", SMALL_PLANT_ROOMS, PLT + ["small"]),
    },
    "sh3d-c": {
        "captainsBed": ("bed.single", [BED], ["bed", "kids"]), "childBed": ("bed.single", [BED], ["bed", "kids"]),
        "meubleChevet": ("nightstand", [BED], STO), "armoireLotus": ("wardrobe", [BED, HALL], STO + ["tall"]),
        "kommode": ("dresser", [BED, LIV, HALL], STO),
        "petiteCommode": ("dresser", [BED, LIV, HALL], STO),
        "sofa1": ("sofa", [LIV], SEAT), "sofa3": ("sofa.long", [LIV], SEAT), "sofa4": ("sofa", [LIV], SEAT),
        "largeCouch": ("sofa", [LIV], SEAT), "couchTwoSeats": ("sofa", [LIV], SEAT),
        "armchair_wing": ("armchair", [LIV, BED], SEAT), "singleChair": ("armchair", [LIV, BED], SEAT),
        "tableBasse2": ("table.coffee", [LIV], ["table"]), "tableBasseBois": ("table.coffee", [LIV], ["table"]),
        "couchTable": ("table.coffee", [LIV], ["table"]),
        "roundTable": ("table.dining", [DIN, KIT], ["table"]),
        "chaise": ("chair.dining", [DIN, KIT], SEAT), "chaiseOrange": ("chair.dining", [DIN, KIT], SEAT),
        "latticeChair": ("chair.dining", [DIN, KIT], SEAT),
        "smallbookshelves": ("bookcase", [LIV, OFF], STO), "meubleHiFiBas": ("tv.console", [LIV], STO),
        "bureau3": ("desk", [OFF, BED], ["table"]),
        "officeChair": ("chair.desk", [OFF], SEAT), "officeChair2": ("chair.desk", [OFF], SEAT),
        "1DoorLowerCabinet": ("kitchen.base", [KIT], CTR), "2DoorLowerCabinet": ("kitchen.base", [KIT], CTR),
        "kitchenSinkWithMarble": ("kitchen.sink", [KIT], CTR),
        "1DoorUpperCabinet": ("kitchen.upper", [KIT], CTR + ["wall"]), "2DoorUpperCabinet": ("kitchen.upper", [KIT], CTR + ["wall"]),
        "pantry": ("kitchen.tall", [KIT], STO + ["tall"]), "refridgerator": ("kitchen.fridge", [KIT], APP), "piano_cottura_Scene": ("kitchen.stove", [KIT], APP),
        "dishwasher": ("kitchen.dishwasher", [KIT], APP), "washer_dryer": ("laundry.machine", [BATH, KIT, HALL], APP),
        "bath_L": ("bathtub", [BATH], SAN), "bathtub_jet_system": ("bathtub", [BATH], SAN),
        "shower_cabin": ("shower", [BATH], SAN), 
        "lampeHalogene": ("lamp.floor", [LIV, BED, OFF], LMP), "deskLamp1": ("lamp.table", [BED, LIV, OFF], LMP),
        "hangingLight": ("lamp.ceiling", [LIV, BED, KIT, HALL], LMP + ["ceiling"]),
        "lustreBoule": ("lamp.ceiling", [LIV, BED, KIT, HALL], LMP + ["ceiling"]),
        
        "potplant2": ("plant", PLANT_ROOMS, PLT), "flowers": ("plant.small", SMALL_PLANT_ROOMS, PLT + ["small"]),
        "carpet": ("rug", [LIV, BED, DIN], ["rug"]), "kleed_grieks": ("rug", [LIV, BED, DIN], ["rug"]),
    },
}

# Ce qui ne sert pas à meubler une maison (nourriture, ustensiles, pièces murales modulaires, jouets…).
UNUSED = re.compile(
    r"^(food|crate|jar|ketchup|mustard|knife|lid|menu|pan|pot|plate|bowl|cuttingboard|dishrack|papertowel|stew|"
    r"pillar|towelrail|oven|wall|floor|paneling|bear|cardboard|ceilingfan|televisionantenna|"
    r"computer(keyboard|mouse)|table-round)",
)


# Taille RÉELLE visée par rôle : ("length", m) = plus grande dimension horizontale, ("height", m) = hauteur.
# Les packs n'ont pas la même échelle (un canapé Kenney fait 0,98 m, celui de KayKit 3,0 m) : chaque modèle reçoit
# le facteur qui ramène son rôle à une taille de maison réelle.
ROLE_FIT: dict[str, tuple[str, float]] = {
    "bed.double": ("length", 2.05), "bed.single": ("length", 2.0), "bed.bunk": ("length", 2.0),
    "nightstand": ("height", 0.55), "wardrobe": ("height", 2.0), "dresser": ("length", 1.2),
    "sofa": ("length", 2.0), "sofa.corner": ("length", 2.6), "sofa.long": ("length", 2.6), "ottoman": ("length", 0.7),
    "armchair": ("length", 0.9), "table.coffee": ("length", 1.1), "tv.console": ("length", 1.5),
    "tv": ("length", 1.1), "bookcase": ("height", 1.8), "table.dining": ("length", 1.8),
    "chair.dining": ("height", 0.9), "chair.desk": ("height", 0.95), "stool": ("height", 0.65), "bench": ("length", 1.2),
    "desk": ("length", 1.4), "computer": ("length", 0.5),
    "kitchen.fridge": ("height", 1.8), "kitchen.stove": ("length", 0.6), "kitchen.sink": ("length", 1.0),
    "kitchen.upper": ("length", 0.8), "kitchen.corner": ("length", 0.9), "kitchen.base": ("height", 0.9),
    "kitchen.bar": ("length", 1.4), "kitchen.island": ("length", 1.4), "shelf.wall": ("length", 1.0), "kitchen.small": ("length", 0.4), "laundry.machine": ("length", 0.6),
    "toilet": ("length", 0.7), "sink.bath": ("length", 0.6), "bathtub": ("length", 1.7), "shower": ("length", 0.9),
    "bath.cabinet": ("length", 0.6), "mirror": ("length", 0.6),
    "lamp.floor": ("height", 1.5), "lamp.table": ("height", 0.45), "lamp.ceiling": ("height", 0.35), "lamp.wall": ("length", 0.25),
    "plant": ("height", 1.0), "plant.small": ("height", 0.4), "rug": ("length", 2.2), "rug.doormat": ("length", 0.9),
    "pillow": ("length", 0.45), "picture": ("length", 0.6), "books": ("length", 0.3), "coat.rack": ("height", 1.7), "coat.rack.wall": ("length", 0.7),
    "trash": ("height", 0.45), "audio": ("length", 0.3), "door.frame": ("height", 2.1), "stairs": ("height", 2.7),
}


# Un modèle trop grand ou trop petit pour son rôle : {pack/nom: (mode, mètres)} remplace la taille d'origine (voir ROLE_FIT).
ITEM_FIT: dict[str, tuple[str, float]] = {
    "polyhaven/modern_wooden_cabinet": ("length", 1.7),
}


# Poly Haven : téléchargés et vus en planche-contact, écartés (trop gothiques, trop massifs, texture manquante, etc.).
POLYHAVEN_REJECTED = {"woodenchair_01", "coffeetable_01", "dining_table", "hanging_picture_frame_01", "drawer_cabinet",
                      "vintage_cabinet_01", "wooden_bookshelf_worn", "shelf_01", "wooden_display_shelves_01"}


def norm(name: str) -> str:
    return name.lower()


def classify(name: str, pack: str = "") -> tuple[str | None, list[str], list[str]]:
    if pack in EXPLICIT:
        return EXPLICIT[pack].get(name, (None, [], []))
    key = norm(name)
    if pack == "polyhaven" and key in POLYHAVEN_REJECTED:
        return None, [], []
    for pattern, role, rooms, tags in RULES:
        if re.search(pattern, key):
            return role, rooms, tags
    return None, [], []


def build() -> dict:
    items = []
    for pack, meta in PACKS.items():
        folder = ASSETS / pack
        for glb in sorted(folder.glob("*.glb")):
            name = glb.stem
            info = bounds(glb)
            role, rooms, tags = classify(name, pack)
            unused = role is None
            fit = ROLE_FIT.get(role or "")
            scale = 1.0
            fit = ITEM_FIT.get(f"{pack}/{name}") or fit
            if fit and (not meta.get("real_size") or f"{pack}/{name}" in ITEM_FIT):
                basis = max(info["size"][0], info["size"][2]) if fit[0] == "length" else info["size"][1]
                scale = round(fit[1] / basis, 4) if basis > 1e-6 else 1.0
            # Un motif « inutile » n'écrase pas un rôle explicite (ex. `table-round` de la brasserie reste utilisable).
            entry = {
                "id": f"{pack}/{name}", "pack": pack, "name": name, "file": f"assets/{pack}/{glb.name}",
                "role": role or "unused", "rooms": rooms, "tags": sorted(set(tags + meta["style"])),
                "size": info["size"], "min": [round(v, 3) for v in info["min"]], "max": [round(v, 3) for v in info["max"]],
                "tris": info["tris"], "textured": bool(info["textures"]), "unused": unused,
                "scale": scale, "fit_size": [round(v * scale, 3) for v in info["size"]],
            }
            items.append(entry)
    packs = {p: {k: v for k, v in m.items() if k != "style"} | {"style": m["style"]} for p, m in PACKS.items()}
    return {"version": 1, "units": "m", "up": "Y", "packs": packs, "items": items}


def main() -> None:
    manifest = build()
    out = ROOT / "catalog" / "manifest.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    used = [i for i in manifest["items"] if not i["unused"]]
    roles: dict[str, int] = {}
    for it in used:
        roles[it["role"]] = roles.get(it["role"], 0) + 1
    print(f"{len(manifest['items'])} modèles, {len(used)} utilisables, {len(roles)} rôles")
    for role, n in sorted(roles.items()):
        print(f"  {role:18s} {n}")


if __name__ == "__main__":
    main()
