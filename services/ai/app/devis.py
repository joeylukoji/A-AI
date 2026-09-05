"""Devis & cahier des charges — chiffrage local, rédaction LLM (gpt-oss-120b), PDF.

Pipeline :
  1. Métriques déterministes extraites du plan (surfaces, périmètres, menuiseries…).
  2. Budgétisation par lots via une bibliothèque de prix pro en USD, calibrée sur
     la réalité de la RDC (main-d'œuvre locale moins chère, matériaux courants) —
     les quantités viennent du plan, jamais inventées par le LLM.
  3. gpt-oss-120b rédige le cahier des charges et le cahier technique en citant
     ces quantités ; repli sur des gabarits locaux sans clé Together.
  4. Rendu PDF (fpdf2) : page de garde, cahier des charges, cahier technique,
     détail chiffré par lot, totaux HT/TVA 16 %/TTC, conditions et signature.
"""
from __future__ import annotations

import base64
import io
import os
from datetime import date
from typing import Any

from . import together_image

# ---------------------------------------------------------------- métriques

_WET = {"kitchen", "bathroom", "wc", "laundry"}


def _poly_area(poly: list[Any]) -> float:
    pts = [(float(p.get("x", 0)), float(p.get("y", 0))) for p in poly if isinstance(p, dict)]
    if len(pts) < 3:
        return 0.0
    acc = 0.0
    for i, (x1, y1) in enumerate(pts):
        x2, y2 = pts[(i + 1) % len(pts)]
        acc += x1 * y2 - x2 * y1
    return abs(acc) / 2.0


def _metrics(spec: dict[str, Any], plan: dict[str, Any], constraints: dict[str, Any]) -> dict[str, Any]:
    """Métriques déterministes du projet (quantités de base du chiffrage)."""
    rooms = plan.get("rooms") or spec.get("rooms") or []
    by_type: dict[str, int] = {}
    sh = 0.0
    garage_area = 0.0
    wet_area = 0.0
    for r in rooms:
        if not isinstance(r, dict):
            continue
        rtype = str(r.get("type") or "other")
        by_type[rtype] = by_type.get(rtype, 0) + 1
        area = float(r.get("area_m2") or 0.0)
        if area <= 0 and r.get("polygon"):
            area = _poly_area(r["polygon"])
        if rtype == "garage":
            garage_area += area
        else:
            sh += area
            if rtype in _WET:
                wet_area += area

    cons = dict(spec.get("constraints") or {}) | dict(constraints or {})
    width = float(cons.get("max_width_m") or 12.0)
    depth = float(cons.get("max_depth_m") or 10.0)
    footprint = round(width * depth, 1)
    if sh <= 0:
        sh = footprint * 0.85  # estimation si le plan n'est pas détaillé
    openings = plan.get("openings") or []
    windows = sum(1 for o in openings if isinstance(o, dict) and o.get("type") == "window")
    if windows <= 0:
        windows = max(4, by_type.get("bedroom", 0) + by_type.get("living", 0) * 2 + 1)
    veranda_depth = float(plan.get("veranda_depth_m") or 0.0)

    return {
        "surface_habitable_m2": round(sh, 1),
        "emprise_m2": footprint,
        "largeur_m": width,
        "profondeur_m": depth,
        "perimetre_m": round(2 * (width + depth), 1),
        "hauteur_murs_m": 2.7,
        "surface_toiture_m2": round(footprint * 1.15, 1),  # pente 2 pans ~15 %
        "surface_murs_ext_m2": round(2 * (width + depth) * 2.7 * 0.9, 1),  # ouvertures déduites
        "surface_garage_m2": round(garage_area, 1),
        "surface_pieces_humides_m2": round(wet_area, 1),
        "surface_veranda_m2": round(width * veranda_depth, 1) if veranda_depth else 0.0,
        "nb_chambres": by_type.get("bedroom", 0),
        "nb_sdb": by_type.get("bathroom", 0),
        "nb_wc": by_type.get("wc", 0),
        "nb_cuisines": max(1, by_type.get("kitchen", 0)),
        "nb_sejours": max(1, by_type.get("living", 0)),
        "nb_buanderies": by_type.get("laundry", 0),
        "garage": by_type.get("garage", 0) > 0,
        "nb_fenetres": windows,
        "nb_pieces": sum(by_type.values()),
        "etages": int(spec.get("floors") or 1),
    }


# ---------------------------------------------------------------- chiffrage

# Bibliothèque de prix unitaires HT en USD, calibrée marché RDC (main-d'œuvre
# locale moins chère, matériaux courants : parpaing/bloc de ciment, tôle, etc.).
# Chaque ligne : (désignation, unité, quantité fn(métriques), PU $ HT)
_LINES: list[tuple[str, str, str, Any, float]] = [
    # lot 1 — terrassement & fondations
    ("1. Terrassement & fondations", "Terrassement général, réglage et évacuation des terres", "m²", lambda m: round(m["emprise_m2"] * 1.2, 0), 4.0),
    ("1. Terrassement & fondations", "Semelles filantes béton dosé 350 kg/m³, ferraillage inclus", "ml", lambda m: round(m["perimetre_m"] * 1.8, 0), 32.0),
    ("1. Terrassement & fondations", "Dalle béton sur hérisson, film plastique et forme de sol", "m²", lambda m: m["emprise_m2"], 22.0),
    # lot 2 — gros œuvre
    ("2. Gros œuvre & maçonnerie", "Élévation murs en blocs de ciment 15/20, chaînages compris", "m²", lambda m: m["surface_murs_ext_m2"], 26.0),
    ("2. Gros œuvre & maçonnerie", "Cloisons de distribution en blocs de ciment 10 ou briques", "ml", lambda m: round(m["surface_habitable_m2"] * 1.2, 0), 14.0),
    ("2. Gros œuvre & maçonnerie", "Crépissage extérieur ciment, 2 passes + finition", "m²", lambda m: m["surface_murs_ext_m2"], 9.0),
    # lot 3 — charpente & couverture
    ("3. Charpente & couverture", "Charpente bois local traité ou métallique légère", "m²", lambda m: m["surface_toiture_m2"], 18.0),
    ("3. Charpente & couverture", "Couverture en tôles prélaquées ou tuiles, sous-face comprise", "m²", lambda m: m["surface_toiture_m2"], 26.0),
    ("3. Charpente & couverture", "Zinguerie, gouttières et descentes d'eaux pluviales", "forfait", lambda m: 1, 900.0),
    # lot 4 — menuiseries extérieures
    ("4. Menuiseries extérieures", "Fenêtre aluminium vitrage simple/double, pose comprise", "u", lambda m: m["nb_fenetres"], 260.0),
    ("4. Menuiseries extérieures", "Grille de protection métallique par fenêtre", "u", lambda m: m["nb_fenetres"], 90.0),
    ("4. Menuiseries extérieures", "Porte d'entrée métallique sécurisée", "u", lambda m: 1, 550.0),
    ("4. Menuiseries extérieures", "Porte de garage basculante ou sectionnelle", "u", lambda m: 1 if m["garage"] else 0, 950.0),
    # lot 5 — isolation
    ("5. Isolation & enveloppe", "Isolation de toiture (laine ou isolant réfléchissant)", "m²", lambda m: m["emprise_m2"], 9.0),
    ("5. Isolation & enveloppe", "Étanchéité à l'air et traitement des ponts thermiques", "m²", lambda m: m["surface_murs_ext_m2"], 6.0),
    # lot 6 — plomberie & CVC
    ("6. Plomberie, sanitaire & ventilation", "Points d'eau : alimentation PPR/PER et évacuation PVC", "u", lambda m: m["nb_sdb"] * 4 + m["nb_cuisines"] * 2 + m["nb_wc"] + m["nb_buanderies"] * 2, 150.0),
    ("6. Plomberie, sanitaire & ventilation", "Chauffe-eau électrique ou solaire + réseau eau chaude", "forfait", lambda m: 1, 900.0),
    ("6. Plomberie, sanitaire & ventilation", "Climatiseurs split, pièces principales", "u", lambda m: m["nb_sejours"] + m["nb_chambres"], 650.0),
    ("6. Plomberie, sanitaire & ventilation", "Appareils sanitaires et robinetterie (par salle de bain)", "u", lambda m: m["nb_sdb"], 1200.0),
    # lot 7 — électricité
    ("7. Électricité", "Points lumineux et prises, câblage en saignée ou apparent", "u", lambda m: round(m["surface_habitable_m2"] * 1.3, 0), 22.0),
    ("7. Électricité", "Tableau de répartition, disjoncteurs et mise à la terre", "u", lambda m: 1, 450.0),
    ("7. Électricité", "Kit solaire de secours (onduleur + batteries) ou groupe électrogène", "forfait", lambda m: 1, 2200.0),
    # lot 8 — revêtements & finitions
    ("8. Revêtements & finitions", "Carrelage grès cérame, pose scellée (pièces humides)", "m²", lambda m: round(m["surface_pieces_humides_m2"] + 6, 0), 28.0),
    ("8. Revêtements & finitions", "Carrelage ou parquet flottant (pièces sèches)", "m²", lambda m: round(max(m["surface_habitable_m2"] - m["surface_pieces_humides_m2"] - 6, 10), 0), 18.0),
    ("8. Revêtements & finitions", "Peinture murs et plafonds, impression + 2 couches vinylique", "m²", lambda m: round(m["surface_habitable_m2"] * 2.6, 0), 6.0),
    ("8. Revêtements & finitions", "Portes intérieures bois ou MDF avec huisseries", "u", lambda m: m["nb_pieces"], 110.0),
    # lot 9 — VRD
    ("9. VRD & extérieurs", "Raccordements réseaux : eau (REGIDESO), électricité (SNEL), assainissement", "forfait", lambda m: 1, 1800.0),
    ("9. VRD & extérieurs", "Terrasse extérieure (dalle béton ou pavés)", "m²", lambda m: m["surface_veranda_m2"] or round(m["largeur_m"] * 2.0, 1), 24.0),
]


def _budget(m: dict[str, Any]) -> list[dict[str, Any]]:
    """Lots chiffrés : quantités issues des métriques, jamais du LLM."""
    lots: dict[str, dict[str, Any]] = {}
    for lot, designation, unit, qty_fn, pu in _LINES:
        qty = float(qty_fn(m))
        if qty <= 0:
            continue
        total = round(qty * pu, 2)
        entry = lots.setdefault(lot, {"lot": lot, "lines": [], "total_ht": 0.0})
        entry["lines"].append({
            "designation": designation,
            "unite": unit,
            "quantite": qty,
            "pu_ht": pu,
            "total_ht": total,
        })
        entry["total_ht"] = round(entry["total_ht"] + total, 2)
    return [lots[k] for k in sorted(lots)]


# ---------------------------------------------------------------- rédaction LLM

_DEVIS_SYSTEM = (
    "Tu es un économiste de la construction et ingénieur bâtiment opérant en "
    "République Démocratique du Congo (RDC). Tu rédiges en français un cahier des "
    "charges et un cahier technique professionnels pour la construction d'une "
    "maison individuelle, utilisables par un architecte ou un ingénieur local. "
    "Réponds en JSON STRICT uniquement.\n"
    "RÈGLES\n"
    "- Cite les quantités et le programme fournis, n'invente ni pièce ni surface.\n"
    "- Contexte RDC : prix en USD, main-d'œuvre locale, matériaux courants "
    "(blocs de ciment, tôle, bois local, aluminium), réseaux REGIDESO/SNEL.\n"
    "- Référence les normes applicables localement (normes congolaises ACNOR, "
    "DTU à titre technique, normes ISO), TVA 16 %.\n"
    "- Ton technique et contractuel, phrases précises.\n"
    "SORTIE JSON:\n"
    "{\n"
    '  "titre": "Devis descriptif — Maison ...",\n'
    '  "resume_projet": "paragraphe",\n'
    '  "cahier_des_charges": {\n'
    '    "programme": "paragraphe",\n'
    '    "exigences": ["..."],\n'
    '    "reglementaire": ["..."],\n'
    '    "prestations_incluses": ["..."],\n'
    '    "prestations_exclues": ["terrain, honoraires, ..."]\n'
    "  },\n"
    '  "cahier_technique": [{"lot": "1. Terrassement & fondations", '
    '"specifications": "paragraphe", "materiaux": ["..."]}],\n'
    '  "conditions": ["validité 3 mois", "..."]\n'
    "}"
)


def _llm_sections(brief: str, m: dict[str, Any], budget: list[dict[str, Any]]) -> dict[str, Any] | None:
    recap = (
        f"Brief client : {brief or 'maison individuelle'}\n"
        f"Programme : {m['nb_pieces']} pièces, {m['nb_chambres']} chambre(s), "
        f"{m['nb_sdb']} salle(s) de bain, {m['nb_wc']} WC, "
        f"{'garage, ' if m['garage'] else ''}surface habitable {m['surface_habitable_m2']} m², "
        f"emprise {m['emprise_m2']} m² ({m['largeur_m']}×{m['profondeur_m']} m), "
        f"toiture {m['surface_toiture_m2']} m², {m['nb_fenetres']} fenêtres, "
        f"{m['etages']} niveau(x).\n"
        "Lots chiffrés (USD HT) : " + "; ".join(f"{b['lot']} = {b['total_ht']:.0f} $" for b in budget)
    )
    from .nlu import _parse_json_obj  # extraction JSON tolérante partagée

    for _ in range(3):  # 1er appel parfois dégradé (cold start), 503 transitoires
        text = together_image.chat_completion(
            [
                {"role": "system", "content": _DEVIS_SYSTEM},
                {"role": "user", "content": recap},
            ],
            max_tokens=2600,
            temperature=0.3,
            timeout=240.0,
            json_mode=True,
        )
        if not text:
            continue
        data = _parse_json_obj(text)
        # gpt-oss encapsule parfois la sortie dans {"final": "...json..."} (canal harmony)
        if isinstance(data, dict) and isinstance(data.get("final"), str):
            data = _parse_json_obj(data["final"])
        if isinstance(data, dict) and data.get("cahier_technique"):
            return data
    return None


def _fallback_sections(brief: str, m: dict[str, Any]) -> dict[str, Any]:
    """Rédaction contractuelle locale si le LLM est indisponible."""
    prog = (
        f"Construction d'une maison individuelle de plain-pied de "
        f"{m['surface_habitable_m2']} m² habitables sur une emprise de {m['emprise_m2']} m² "
        f"({m['largeur_m']} × {m['profondeur_m']} m), comprenant {m['nb_pieces']} pièces dont "
        f"{m['nb_chambres']} chambre(s), {m['nb_sdb']} salle(s) de bain et {m['nb_wc']} WC"
        f"{', avec garage attenant' if m['garage'] else ''}."
    )
    return {
        "titre": "Devis descriptif — Maison individuelle",
        "resume_projet": prog + (" " + brief[:400] if brief else ""),
        "cahier_des_charges": {
            "programme": prog,
            "exigences": [
                "Confort thermique et acoustique adapté au climat tropical",
                "Matériaux de première qualité disponibles localement ou importés conformes",
                "Chantier exécuté dans les règles de l'art par des corps de métier qualifiés",
            ],
            "reglementaire": [
                "Normes congolaises (ACNOR) et réglementation urbaine locale",
                "DTU applicables à titre technique (maçonnerie, couverture, plomberie, électricité)",
                "Installation électrique conforme aux règles de sécurité en vigueur",
                "Raccordements REGIDESO (eau) et SNEL (électricité)",
            ],
            "prestations_incluses": [
                "Gros œuvre, charpente, couverture et menuiseries extérieures",
                "Second œuvre : isolation, cloisons, plomberie, CVC, électricité",
                "Revêtements de sols et murs, peinture, VRD et raccordements",
            ],
            "prestations_exclues": [
                "Terrain, frais de notaire et taxes d'urbanisme",
                "Honoraires d'architecte et d'études (géotechnique, thermique)",
                "Mobilier, cuisine équipée et aménagements paysagers",
            ],
        },
        "cahier_technique": [
            {"lot": "1. Terrassement & fondations",
             "specifications": "Fouilles réglées, semelles filantes en béton dosé 350 kg/m³ ferraillé, dalle béton sur hérisson drainant avec film plastique.",
             "materiaux": ["Béton dosé 350 kg/m³", "Acier tor HA", "Film plastique de sous-dalle"]},
            {"lot": "2. Gros œuvre & maçonnerie",
             "specifications": "Élévation en blocs de ciment 15/20 fabriqués localement, chaînages verticaux et horizontaux, crépissage extérieur ciment 2 passes.",
             "materiaux": ["Blocs de ciment 15/20", "Mortier ciment-sable", "Ciment gris 42,5"]},
            {"lot": "3. Charpente & couverture",
             "specifications": "Charpente en bois local traité (ou profilés métalliques légers), couverture en tôles prélaquées ou tuiles, zinguerie complète.",
             "materiaux": ["Bois traité anti-termites", "Tôles prélaquées 0,5 mm", "Accessoires de zinguerie"]},
            {"lot": "4. Menuiseries extérieures",
             "specifications": "Menuiseries aluminium à vitrage simple ou double, grilles de protection métalliques, porte d'entrée métallique sécurisée.",
             "materiaux": ["Profilés aluminium", "Vitrage 4 mm ou double", "Grilles métalliques soudées"]},
            {"lot": "5. Isolation & enveloppe",
             "specifications": "Confort thermique sous climat tropical : isolation de toiture (isolant réfléchissant ou laine), étanchéité à l'air, brise-soleil si requis.",
             "materiaux": ["Isolant réfléchissant multicouche", "Laine minérale toiture", "Mastic d'étanchéité"]},
            {"lot": "6. Plomberie, sanitaire & ventilation",
             "specifications": "Distribution PPR/PER, évacuations PVC, chauffe-eau électrique ou solaire, climatiseurs split dans les pièces principales.",
             "materiaux": ["Tubes PPR/PER", "PVC évacuation Ø40-110", "Chauffe-eau", "Splits inverter"]},
            {"lot": "7. Électricité",
             "specifications": "Installation complète aux règles de sécurité : points lumineux, prises, tableau de répartition, prise de terre, secours solaire ou groupe.",
             "materiaux": ["Câbles cuivre 1,5/2,5/6 mm²", "Tableau modulaire", "Onduleur et batteries ou groupe électrogène"]},
            {"lot": "8. Revêtements & finitions",
             "specifications": "Carrelage grès cérame en pièces humides, carrelage ou parquet flottant en pièces sèches, peinture impression + 2 couches vinylique.",
             "materiaux": ["Grès cérame 40×40 ou 45×45", "Parquet flottant", "Peinture vinylique"]},
            {"lot": "9. VRD & extérieurs",
             "specifications": "Raccordements REGIDESO et SNEL, assainissement individuel ou collectif, terrasse extérieure et accès.",
             "materiaux": ["Canalisations PVC", "Regards béton", "Terrasse béton ou pavés"]},
        ],
        "conditions": [
            "Devis valable 3 mois à compter de sa date d'émission, prix en USD",
            "Acompte à la commande, paiement échelonné selon l'avancement des travaux",
            "Prix fermes sous réserve de la disponibilité des matériaux importés et de la stabilité du taux de change",
        ],
    }


# ---------------------------------------------------------------- PDF

# Polices Unicode (Dejavu installées dans l'image Docker) : €, accents, —, etc.
_TTF_DIRS = (
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/dejavu",
    "/usr/local/share/fonts",
)
_FAMILY = "helvetica"
_CORE_FONTS = True


def _latin(text: Any) -> str:
    """Sanitisation pour les polices core (latin-1) ; identité avec une police TTF."""
    s = str(text)
    if not _CORE_FONTS:
        return s
    s = s.replace("€", "EUR ").replace("—", "-").replace("–", "-")
    s = s.replace("’", "'").replace("“", '"').replace("”", '"')
    return s.encode("latin-1", "replace").decode("latin-1")


_TVA_RATE = 0.16  # TVA RDC


def _eur(v: float) -> str:
    s = f"{v:,.2f}".replace(",", " ").replace(".", ",")
    return _latin(s + " $")


class _DevisPDF:
    def __init__(self, title: str) -> None:
        from fpdf import FPDF

        global _FAMILY, _CORE_FONTS
        import pathlib

        regular = bold = italic = None
        for d in _TTF_DIRS:
            p = pathlib.Path(d)
            if (p / "DejaVuSans.ttf").exists():
                regular, bold, italic = (p / "DejaVuSans.ttf", p / "DejaVuSans-Bold.ttf", p / "DejaVuSans-Oblique.ttf")
                break
        _CORE_FONTS = regular is None
        _FAMILY = "helvetica" if _CORE_FONTS else "dejavu"

        class _Doc(FPDF):
            def header(self) -> None:  # noqa: N802 (API fpdf2)
                if self.page_no() == 1:
                    return
                self.set_font(_FAMILY, "I", 8)
                self.set_text_color(120, 113, 108)
                half = self.epw / 2
                self.cell(half, 8, _latin(title), align="L")
                self.cell(half, 8, _latin("Devis descriptif — confidentiel"), align="R", new_x="LMARGIN", new_y="NEXT")
                self.set_draw_color(176, 141, 87)
                self.line(self.l_margin, 14, self.w - self.r_margin, 14)
                self.ln(4)

            def footer(self) -> None:  # noqa: N802 (API fpdf2)
                self.set_y(-14)
                self.set_font(_FAMILY, "I", 8)
                self.set_text_color(120, 113, 108)
                self.cell(0, 8, _latin(f"Page {self.page_no()}/{{nb}}"), align="C")

        self.pdf = _Doc(orientation="P", unit="mm", format="A4")
        if not _CORE_FONTS:
            self.pdf.add_font("dejavu", "", str(regular))
            self.pdf.add_font("dejavu", "B", str(bold))
            if italic.exists():  # fonts-dejavu-core n'a pas toujours l'italique
                self.pdf.add_font("dejavu", "I", str(italic))
            else:  # l'italique retombe sur la régulière
                self.pdf.add_font("dejavu", "I", str(regular))
        self.pdf.set_auto_page_break(auto=True, margin=20)
        self.pdf.set_margins(16, 18, 16)
        self.pdf.alias_nb_pages()
        self.w = 210 - 16 - 16  # largeur utile

    # -- blocs de mise en page -------------------------------------------------
    def cover(self, title: str, ref: str, brief: str, m: dict[str, Any]) -> None:
        p = self.pdf
        p.add_page()
        p.set_fill_color(28, 25, 23)
        p.rect(0, 0, 210, 52, "F")
        p.set_xy(16, 16)
        p.set_font(_FAMILY, "B", 22)
        p.set_text_color(245, 241, 235)
        short = title if len(title) <= 90 else title[:87].rstrip() + "…"
        p.multi_cell(self.w, 9, _latin(short))
        p.set_xy(16, 40)
        p.set_font(_FAMILY, "", 10)
        p.set_text_color(214, 202, 188)
        p.cell(self.w, 6, _latin(f"Réf. {ref} · Édité le {date.today():%d/%m/%Y}"), new_x="LMARGIN", new_y="NEXT")
        p.ln(14)

        p.set_text_color(28, 25, 23)
        p.set_font(_FAMILY, "B", 13)
        p.cell(0, 8, _latin("Programme du projet"), new_x="LMARGIN", new_y="NEXT")
        p.set_font(_FAMILY, "", 10)
        p.multi_cell(self.w, 5.4, _latin(brief or "Maison individuelle"))
        p.ln(4)

        rows = [
            ("Surface habitable", f"{m['surface_habitable_m2']} m²"),
            ("Emprise au sol", f"{m['emprise_m2']} m² ({m['largeur_m']} × {m['profondeur_m']} m)"),
            ("Toiture", f"{m['surface_toiture_m2']} m²"),
            ("Pièces", f"{m['nb_pieces']} dont {m['nb_chambres']} chambre(s), {m['nb_sdb']} salle(s) de bain, {m['nb_wc']} WC"),
            ("Menuiseries", f"{m['nb_fenetres']} fenêtres{' + porte de garage' if m['garage'] else ''}"),
            ("Niveaux", str(m["etages"])),
        ]
        p.set_font(_FAMILY, "", 10)
        for label, value in rows:
            p.set_draw_color(231, 229, 228)
            p.set_line_width(0.2)
            p.cell(62, 7, _latin(label), border="B")
            p.set_font(_FAMILY, "B", 10)
            p.cell(self.w - 62, 7, _latin(value), border="B", new_x="LMARGIN", new_y="NEXT")
            p.set_font(_FAMILY, "", 10)

    def section(self, num: str, title: str) -> None:
        p = self.pdf
        p.ln(5)
        p.set_font(_FAMILY, "B", 13)
        p.set_text_color(148, 108, 52)
        p.cell(0, 8, _latin(f"{num}. {title}" if num else title), new_x="LMARGIN", new_y="NEXT")
        p.set_text_color(28, 25, 23)

    def paragraph(self, text: str) -> None:
        p = self.pdf
        p.set_font(_FAMILY, "", 10)
        p.set_x(p.l_margin)
        p.multi_cell(self.w, 5.4, _latin(text), new_x="LMARGIN", new_y="NEXT")
        p.ln(2)

    def bullets(self, items: list[Any]) -> None:
        p = self.pdf
        p.set_font(_FAMILY, "", 10)
        glyph = "•" if not _CORE_FONTS else "-"
        for it in items or []:
            p.set_x(p.l_margin)
            p.cell(5, 5.4, glyph)
            p.multi_cell(p.w - p.r_margin - p.get_x(), 5.4, _latin(it), new_x="LMARGIN", new_y="NEXT")
        p.ln(2)

    def budget_table(self, budget: list[dict[str, Any]]) -> None:
        p = self.pdf
        widths = (76, 14, 18, 32, 38)  # désignation, unité, qté, PU, total
        header = ("Désignation", "Unité", "Qté", "PU HT", "Total HT")
        grand = 0.0
        for lot in budget:
            p.ln(1)
            p.set_font(_FAMILY, "B", 10.5)
            p.set_fill_color(240, 236, 229)
            p.cell(sum(widths), 7, _latin(lot["lot"]), border=0, fill=True, new_x="LMARGIN", new_y="NEXT")
            p.set_font(_FAMILY, "B", 9)
            for wcol, h in zip(widths, header):
                p.cell(wcol, 6, _latin(h), border="B", align="R" if h in {"Qté", "PU HT", "Total HT"} else "L")
            p.ln(6)
            p.set_font(_FAMILY, "", 9)
            for ln in lot["lines"]:
                x0 = p.get_x()
                y0 = p.get_y()
                p.multi_cell(widths[0], 5, _latin(ln["designation"]), border=0)
                row_h = max(5.0, p.get_y() - y0)
                y_end = p.get_y()
                p.set_xy(x0 + widths[0], y0)
                p.cell(widths[1], row_h, _latin(ln["unite"]), align="C")
                p.cell(widths[2], row_h, f"{ln['quantite']:g}", align="R")
                p.cell(widths[3], row_h, _eur(ln["pu_ht"]), align="R")
                p.cell(widths[4], row_h, _eur(ln["total_ht"]), align="R")
                p.set_xy(x0, y_end)
            p.set_font(_FAMILY, "B", 9.5)
            p.cell(sum(widths[:4]), 6, _latin(f"Sous-total {lot['lot']}"), align="R")
            p.cell(widths[4], 6, _eur(lot["total_ht"]), border="T", align="R", new_x="LMARGIN", new_y="NEXT")
            grand += float(lot["total_ht"])

        tva = round(grand * _TVA_RATE, 2)
        p.ln(3)
        p.set_font(_FAMILY, "B", 11)
        tva_pct = f"{_TVA_RATE:.0%}"
        for label, value in (("Total travaux HT", grand), (f"TVA {tva_pct}", tva), ("Total TTC", grand + tva)):
            p.cell(sum(widths[:4]), 7.5, _latin(label), align="R")
            p.cell(widths[4], 7.5, _eur(value), border="T", align="R", new_x="LMARGIN", new_y="NEXT")

    def signature(self) -> None:
        p = self.pdf
        p.ln(8)
        p.set_font(_FAMILY, "", 10)
        p.multi_cell(self.w, 5.4, _latin(
            "Bon pour accord : le client reconnaît avoir pris connaissance du présent "
            "devis descriptif, du cahier des charges et des conditions ci-dessus."
        ))
        p.ln(10)
        p.cell(self.w / 2, 6, _latin("Le client (signature précédée de « lu et approuvé »)"))
        p.cell(self.w / 2, 6, _latin("L'entreprise"), align="R", new_x="LMARGIN", new_y="NEXT")
        p.set_draw_color(168, 162, 158)
        p.rect(16, p.get_y() + 2, self.w / 2 - 6, 30)
        p.rect(16 + self.w / 2 + 4, p.get_y() + 2, self.w / 2 - 6, 30)

    def bytes(self) -> bytes:
        return bytes(self.pdf.output())


def render_pdf(devis: dict[str, Any], brief: str, m: dict[str, Any], budget: list[dict[str, Any]], ref: str) -> bytes:
    title = str(devis.get("titre") or "Devis descriptif — Maison individuelle")
    doc = _DevisPDF(title)
    doc.cover(title, ref, brief, m)

    doc.section("1", "Résumé du projet")
    doc.paragraph(str(devis.get("resume_projet") or ""))

    cdc = devis.get("cahier_des_charges") or {}
    doc.section("2", "Cahier des charges")
    if cdc.get("programme"):
        doc.paragraph(str(cdc["programme"]))
    for label, key in (("Exigences", "exigences"), ("Cadre réglementaire", "reglementaire"),
                       ("Prestations incluses", "prestations_incluses"), ("Prestations exclues", "prestations_exclues")):
        if cdc.get(key):
            doc.pdf.set_font(_FAMILY, "B", 10.5)
            doc.pdf.cell(0, 6, _latin(label), new_x="LMARGIN", new_y="NEXT")
            doc.bullets(list(cdc[key]))

    doc.section("3", "Cahier technique (par lot)")
    for lot in devis.get("cahier_technique") or []:
        if not isinstance(lot, dict):
            continue
        doc.pdf.set_font(_FAMILY, "B", 10.5)
        doc.pdf.cell(0, 6, _latin(lot.get("lot") or ""), new_x="LMARGIN", new_y="NEXT")
        doc.paragraph(str(lot.get("specifications") or ""))
        if lot.get("materiaux"):
            doc.pdf.set_font(_FAMILY, "I", 9.5)
            doc.pdf.set_text_color(87, 83, 78)
            doc.pdf.set_x(doc.pdf.l_margin)
            doc.pdf.multi_cell(doc.w, 5, _latin("Matériaux : " + ", ".join(str(x) for x in lot["materiaux"])), new_x="LMARGIN", new_y="NEXT")
            doc.pdf.set_text_color(28, 25, 23)
        doc.pdf.ln(1)

    doc.section("4", "Budgétisation détaillée")
    doc.budget_table(budget)

    doc.section("5", "Conditions")
    doc.bullets(list(devis.get("conditions") or []))
    doc.signature()
    return doc.bytes()


# ---------------------------------------------------------------- point d'entrée


def generate_devis(
    brief: str = "",
    building_spec: dict[str, Any] | None = None,
    plan_document: dict[str, Any] | None = None,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Devis complet : métriques + budget locaux, rédaction LLM, PDF professionnel."""
    spec = building_spec or {}
    plan = plan_document or {}
    cons = constraints or {}
    m = _metrics(spec, plan, cons)
    budget = _budget(m)

    sections = _llm_sections(brief, m, budget) if together_image.planner_enabled() else None
    method = "gpt-oss-120b+fpdf2"
    if sections is None:
        sections = _fallback_sections(brief, m)
        method = "local+fpdf2" if not together_image.planner_enabled() else "fallback+fpdf2"

    ref = "DVS-" + date.today().strftime("%Y%m%d")
    pdf = render_pdf(sections, brief, m, budget, ref)
    total_ht = round(sum(float(b["total_ht"]) for b in budget), 2)

    return {
        "devis": {
            "reference": ref,
            "date": date.today().isoformat(),
            "titre": sections.get("titre"),
            "devise": "USD",
            "tva_taux": _TVA_RATE,
            "metriques": m,
            "budget": budget,
            "total_ht": total_ht,
            "tva": round(total_ht * _TVA_RATE, 2),
            "total_ttc": round(total_ht * (1 + _TVA_RATE), 2),
            "sections": sections,
        },
        "pdf_base64": base64.b64encode(pdf).decode("ascii"),
        "method": method,
    }
