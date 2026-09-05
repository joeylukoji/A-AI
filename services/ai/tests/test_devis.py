"""Tests du module devis : métriques, budget, PDF, LLM stub."""
import base64

from app import devis


def _spec():
    return {
        "constraints": {"max_width_m": 14, "max_depth_m": 10},
        "floors": 1,
        "rooms": [
            {"type": "living", "area_m2": 32},
            {"type": "kitchen", "area_m2": 12},
            {"type": "bedroom", "area_m2": 13},
            {"type": "bedroom", "area_m2": 12},
            {"type": "bedroom", "area_m2": 11},
            {"type": "bathroom", "area_m2": 6},
            {"type": "bathroom", "area_m2": 5},
            {"type": "wc", "area_m2": 2},
            {"type": "garage", "area_m2": 18},
            {"type": "laundry", "area_m2": 5},
            {"type": "hallway", "area_m2": 8},
        ],
    }


def _plan():
    return {"rooms": _spec()["rooms"], "openings": [{"type": "window"}] * 8}


def test_metrics_from_spec():
    m = devis._metrics(_spec(), _plan(), {})
    assert m["surface_habitable_m2"] == 32 + 12 + 13 + 12 + 11 + 6 + 5 + 2 + 5 + 8
    assert m["emprise_m2"] == 140
    assert m["nb_chambres"] == 3
    assert m["nb_sdb"] == 2
    assert m["garage"] is True
    assert m["nb_fenetres"] == 8


def test_metrics_area_from_polygon():
    plan = {"rooms": [{"type": "living", "polygon": [
        {"x": 0, "y": 0}, {"x": 5, "y": 0}, {"x": 5, "y": 4}, {"x": 0, "y": 4}]}]}
    m = devis._metrics({}, plan, {"max_width_m": 10, "max_depth_m": 8})
    assert m["surface_habitable_m2"] == 20


def test_budget_lines_and_totals():
    m = devis._metrics(_spec(), _plan(), {})
    budget = devis._budget(m)
    assert len(budget) == 9
    names = {b["lot"] for b in budget}
    assert "2. Gros œuvre & maçonnerie" in names
    garage_lot = next(b for b in budget if b["lot"].startswith("4."))
    assert any(l["designation"].startswith("Porte de garage") for l in garage_lot["lines"])
    for lot in budget:
        assert lot["total_ht"] > 0
        for ln in lot["lines"]:
            assert ln["quantite"] > 0 and ln["pu_ht"] > 0
            assert abs(ln["quantite"] * ln["pu_ht"] - ln["total_ht"]) < 0.01


def test_generate_devis_fallback_pdf(monkeypatch):
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    monkeypatch.delenv("TOGETHER_AI_API_KEY", raising=False)
    out = devis.generate_devis("Maison plain-pied 3 chambres avec garage", _spec(), _plan(), {})
    pdf = base64.b64decode(out["pdf_base64"])
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 4000
    d = out["devis"]
    assert out["method"] == "local+fpdf2"
    assert d["devise"] == "USD"
    assert d["tva_taux"] == 0.16
    assert d["total_ttc"] > d["total_ht"] > 15000  # ordre de grandeur maison RDC
    assert abs(d["total_ttc"] - d["total_ht"] * 1.16) < 1.0
    assert abs(d["tva"] - d["total_ht"] * 0.16) < 1.0
    sections = d["sections"]
    assert sections["cahier_des_charges"]["reglementaire"]
    assert len(sections["cahier_technique"]) == 9


def test_generate_devis_uses_llm_sections(monkeypatch):
    monkeypatch.setenv("TOGETHER_API_KEY", "test-key")
    monkeypatch.setenv("TOGETHER_PLANNER", "1")
    fake = {
        "titre": "Devis descriptif — Villa test",
        "resume_projet": "Projet de 106 m² habitables.",
        "cahier_des_charges": {"programme": "Maison 3 chambres.", "exigences": ["RE2020"]},
        "cahier_technique": [{"lot": "1. Terrassement & fondations",
                              "specifications": "Semelles C25/30.",
                              "materiaux": ["Béton C25/30"]}],
        "conditions": ["Validité 3 mois"],
    }
    import json
    monkeypatch.setattr(devis.together_image, "chat_completion", lambda *a, **k: json.dumps(fake))
    out = devis.generate_devis("Villa", _spec(), _plan(), {})
    assert out["method"] == "gpt-oss-120b+fpdf2"
    assert out["devis"]["titre"] == "Devis descriptif — Villa test"
    pdf = base64.b64decode(out["pdf_base64"])
    assert pdf[:5] == b"%PDF-"


def test_generate_devis_llm_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("TOGETHER_API_KEY", "test-key")
    monkeypatch.setattr(devis.together_image, "chat_completion", lambda *a, **k: "pas du json")
    out = devis.generate_devis("Villa", _spec(), _plan(), {})
    assert out["method"] == "fallback+fpdf2"
    assert out["devis"]["sections"]["cahier_technique"]
