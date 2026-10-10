---
goal: Refonte complète du langage graphique des plans de l'éditeur 2D
version: 1.0
date_created: 2026-09-25
last_updated: 2026-09-25
owner: Équipe A-AI
status: Completed
tags: [design, editor, 2d, benchmark]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-green)

Refonte visuelle globale demandée après les corrections localisées. Les deux
références utilisateur guident le contraste des murs, la richesse des objets
vus de dessus et la lecture des matériaux. La géométrie des plans reste la
source de vérité. Référence mesurée : `benchmark/runs/3d-car-glyph-v2`.

## 1. Requirements & Constraints

- **REQ-001**: Unifier la direction artistique : papier blanc, murs anthracite,
  chêne clair en chambres/bureaux, dalles claires au séjour, carrelage minéral
  en cuisine et pièces d'eau, béton clair au garage. Garder les sols découpés
  au polygone réel et les couleurs de légende synchronisées.
- **REQ-002**: Moderniser tous les glyphes du catalogue dans
  `plan-style-furniture.js` : lits à oreillers rectangulaires et linge bicolore,
  canapés modulaires sauge, tables et rangements en chêne, cuisine blanche
  avec évier et plaque anthracite, sanitaires blancs, véhicule graphite,
  tapis neutre et feuillage vert structuré. Supprimer le blanchiment global
  des couleurs et les helpers d'ombres/reflets vides.
- **REQ-003**: Les détails dérivent de la largeur/profondeur ; clipper l'encre
  à l'empreinte de chaque objet. Respecter positions, rotations et ordre
  tapis/mobilier ; ne pas ajouter d'objets absents du document.
- **REQ-004**: Dans l'éditeur, placer nom et surface dans une zone de la pièce
  libre de mobilier (hors tapis), en tenant compte de la rotation du mobilier.
  Préférer l'ancre existante, puis une grille déterministe de candidats ; si
  aucun bloc complet ne tient, essayer le nom seul, puis omettre le libellé.
  Le bloc de texte doit rester à l'intérieur du polygone de la pièce.
- **REQ-005**: Conserver les contrats publics de PlanStyle, les opérations
  d'édition et la sérialisation. Mesurer les changements sur les mêmes 38
  images et six documents ; compléter avec une planche de tout le catalogue.
- **REQ-006**: Après le retour utilisateur sur la première capture, rapprocher
  les objets des références avec une silhouette automobile profilée, des
  matières à variations tonales, coutures/plis de tissus, veinage du bois et
  détails végétaux. Conserver une projection 2D de dessus et l'empreinte réelle.
- **CON-001**: Pas de modification du moteur Gemini, de Pillow ou de la 3D.
- **PAT-001**: Garder les responsabilités dans les modules palette, sols,
  mobilier, murs et annotations. Employer des primitives graphiques communes
  aux glyphes sans créer un nouveau framework de rendu.

## 2. Implementation Steps

### Implementation Phase 1 — Contrats et langage graphique

- **GOAL-001**: Livrer la palette, les matériaux et le catalogue contemporain.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Adapter les tests de mobilier aux invariants utiles (géométrie finie, clipping, non-mutation, rotations, distinction des glyphes), conserver les régressions canapé/voiture et ajouter les cas de valeurs invalides avant le code. | Oui | 2026-09-25 |
| TASK-002 | Moderniser `plan-style-palette.js`, `plan-style-floors.js`, `plan-style-furniture.js`, `plan-style-walls.js` et le papier de `plan-style.js`. Revue Standards/Spec du bloc. | Oui | 2026-09-25 |

### Implementation Phase 2 — Lisibilité des textes

- **GOAL-002**: Retirer les chevauchements texte/mobilier quand l'espace existe.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-003 | Ajouter des tests d'une pièce meublée avec place libre, d'un meuble tourné et d'une pièce concave ; vérifier boîtes de texte et non-mutation. | Oui | 2026-09-25 |
| TASK-004 | Ajouter la recherche de placement dans `plan-style-annotations.js` et transmettre le mobilier depuis `editor.js`. Revue Standards/Spec. | Oui | 2026-09-25 |

### Implementation Phase 3 — Validation visuelle

- **GOAL-003**: Rendre la refonte vérifiable sur les plans et tout le catalogue.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Capturer les 38 vues et une planche catalogue avant/après avec Chromium ; vérifier trois zooms et deux DPR, comparer les six JSON et inspecter les images. | Oui | 2026-09-25 |
| TASK-006 | Exécuter Node, tests benchmark et Go HTTP ; rédiger `benchmark/comparisons/editor-modern/report.md`, mettre à jour bilan et plan global. | Oui | 2026-09-25 |
| TASK-007 | Polir le catalogue après inspection de `editor-modern-v1` : matières nuancées, silhouette de voiture, textiles et bois ; vérifier les invariants et les deux planches avant la capture finale. | Oui | 2026-09-25 |

## 3. Alternatives

- **ALT-001**: Coller des photos d'objets : rejeté car leur résolution et leur
  détourage compliquent rotations, zooms et cohérence du plan.
- **ALT-002**: Modifier l'agencement pour copier les références : hors de la
  demande de refonte du design de l'éditeur.

## 4. Dependencies

- **DEP-001**: Canvas 2D, renderer PlanStyle et harnais Chromium existants.
- **DEP-002**: Les images utilisateur fournissent une direction artistique,
  pas une spécification des dimensions des documents de test.

## 5. Files

- **FILE-001**: `web/static/js/plan-style*.js`, `web/static/js/editor.js`.
- **FILE-002**: Tests correspondants dans `web/tests/`, harnais dans `benchmark/`.
- **FILE-003**: Ce plan, `docs/sprints/3c-bilan.md`,
  `docs/refactor-mvp-2d-1.md`, rapport et captures benchmark.

## 6. Testing

- **TEST-001**: Géométrie, rotation, bornes, valeurs invalides, non-mutation,
  positionnement des textes et conservation des formats de surface.
- **TEST-002**: 38 captures appariées et planche catalogue ; hashes des six
  entrées JSON identiques. Analyse visuelle explicite, sans score esthétique
  présenté comme validation scientifique.
- **TEST-003**: `node --test "web/tests/*.test.cjs"`,
  `python -m pytest benchmark/tests -q`, `go test ./internal/httpapi`,
  `git diff --check` et contrôle des erreurs console dans le harnais.

## 7. Risks & Assumptions

- **RISK-001**: Une pièce très encombrée peut ne pas offrir d'emplacement de
  texte ; l'omission est préférable à une superposition trompeuse.
- **RISK-002**: Le corpus ne contient pas tous les glyphes ; la planche
  complémentaire doit inclure tous les types et leurs dimensions nominales.
- **ASSUMPTION-001**: Le mobilier reste vectoriel et schématique ; la refonte
  vise les codes graphiques des références, pas leur reproduction pixel à pixel.

## 8. Related Specifications / Further Reading

- [Plan MVP 2D](../refactor-mvp-2d-1.md)
- [Bilan des travaux 2D](3c-bilan.md)
