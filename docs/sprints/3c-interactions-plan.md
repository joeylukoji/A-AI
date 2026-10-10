---
goal: Vérifier les interactions 2D de l'éditeur et rendre leur usage clavier explicite
version: 1.0
date_created: 2026-09-24
last_updated: 2026-09-24
owner: Équipe A-AI
status: Completed
tags: [editor, 2d, interaction, accessibility, benchmark]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-green)

Ce sous-sprint poursuit `TASK-013` du [plan MVP 2D](../refactor-mvp-2d-1.md).
Il porte sur `editor.js` et la page de l'éditeur, pas sur Gemini, le PNG
Pillow ou la 3D. Les six documents gelés et les captures du sprint 3C sont
la référence visuelle. La priorité est de prouver les transitions de données
et de caméra, puis de corriger uniquement les défauts démontrés.

## 1. Requirements & Constraints

- **REQ-001**: Caractériser sélection, déplacement valide, permutation,
  annulation, glissement rejeté, panoramique, zoom molette/boutons et ajustement.
  Un changement de caméra ou de style ne doit pas modifier le `PlanDocument`.
- **REQ-002**: Vérifier le cycle édition → validation locale → PUT → réponse
  de révision → rechargement, ainsi que refus serveur/réseau et état affiché.
  Ne jamais envoyer une requête réelle lors des tests navigateur.
- **REQ-003**: Documenter puis tester la navigation clavier/focus : canvas
  identifiable et focalisable, flèches actives seulement quand l'édition du
  plan est intentionnelle, commandes et état accessibles. Ne pas intercepter
  les raccourcis des champs de formulaire.
- **REQ-004**: Maintenir les signatures de `PlanStyle` et `PlanEdit`, les
  coordonnées `PlanDocument`, les contrôles de topologie et les six fixtures.
- **CON-001**: Test rouge avant chaque correction ; bloc logique suivi des
  revues Standards et Spec, puis mise à jour de ce plan et de `3c-bilan.md`.
- **CON-002**: Comparaisons appariées avant/après avec mêmes JSON, viewport,
  zoom et police ; ne pas déduire une amélioration de performance d'un seul
  temps de rendu non contrôlé.
- **PAT-001**: `plan-edit.js` reste le domaine pur des transformations ;
  `editor.js` orchestre événements, caméra et réseau ; template = sémantique
  et contrôles. Ne pas déplacer la validation métier vers le canvas.

## 2. Implementation Steps

### Phase 1 — Cartographie et tests de caractérisation

- **GOAL-001**: Distinguer transformations de plan, vue et sauvegarde avec des
  preuves automatisées sur le vrai code de production.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Relever les chemins `mousedown/mousemove/mouseup`, `keydown`, `wheel`, `zoomAt`, `checkpoint/undo`, `markDirty/save`, topologie et leurs données modifiées ; enregistrer les conventions et limites actuelles. | Oui | 2026-09-24 |
| TASK-002 | Étendre le harnais Chromium avec page d'éditeur minimale et `fetch` intercepté : captures et JSON avant/après sélection, glissement rejeté, déplacement, permutation, annulation, pan et zoom. Tester aussi les outils à boutons. | Oui | 2026-09-24 |
| TASK-003 | Caractériser PUT valide/refus/réseau, `base_revision_id`, version affichée et rechargement depuis une réponse figée ; comparer le document soumis au document attendu, sans serveur ni compte réel. | Oui | 2026-09-24 |

### Phase 2 — Corrections d'interaction fondées sur les tests

- **GOAL-002**: Corriger les défauts prouvés sans changer la géométrie ni le
  contrat réseau.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Écrire des tests rouges ciblés sur les défauts révélés ; séparer les corrections de focus/clavier et de sauvegarde. Caractériser la caméra sans correction si aucun défaut n'est reproduit. | Oui | 2026-09-24 |
| TASK-005 | Corriger chaque bloc avec revues Standards/Spec immédiatement après, puis documenter la transition d'état et les captures concernées. | Oui | 2026-09-24 |
| TASK-006 | Relancer JS, Chromium, Go, Ruff, `git diff --check` ; comparer les captures, JSON et états réseau ; publier un rapport dans `benchmark/comparisons/3c-interactions/` et mettre à jour TASK-013. | Oui | 2026-09-24 |

## 3. Alternatives

- **ALT-001**: Réécrire tout `editor.js` avant de tester : rejeté, car les
  interactions et le protocole de révision peuvent régresser sans oracle.
- **ALT-002**: Tester seulement `plan-edit.js` : rejeté ; ses tests actuels ne
  prouvent ni les événements DOM, ni le focus, ni la sauvegarde.
- **ALT-003**: Envoyer les tests à une API réelle : rejeté ; utiliser des
  réponses figées et vérifier le JSON de la requête.

## 4. Dependencies

- **DEP-001**: `web/static/js/editor.js`, `plan-edit.js`, `plan-style*.js` et
  `web/templates/editor.html`.
- **DEP-002**: Playwright Chromium local, Node, fixtures du harnais et tests
  serveur existants.

## 5. Files

- **FILE-001**: Nouveau test navigateur d'interaction dans `benchmark/tests/`.
- **FILE-002**: `web/static/js/editor.js`, `web/templates/editor.html` et
  éventuellement tests Node si une fonction pure est extraite.
- **FILE-003**: `docs/sprints/3c-bilan.md`, ce plan et le rapport benchmark.

## 6. Testing

- **TEST-001**: Chaque action donne un triplet état visuel, état document,
  état réseau attendu ; tester les transitions, pas seulement les pixels.
- **TEST-002**: Comparer le SHA-256 de `PlanDocument` pour actions caméra et
  style ; vérifier les deltas précis pour mouvement/permutation/annulation.
- **TEST-003**: Tester clavier avec focus canvas, bouton, champ de formulaire
  et mode lecture seule ; inspecter nom accessible et annonces de statut.
- **TEST-004**: Tester refus de topologie, réponse HTTP non-2xx, panne réseau,
  double clic Enregistrer et rechargement de révision.

## 7. Risks & Assumptions

- **RISK-001**: Initialement, le canvas n'avait ni `tabindex` ni nom accessible
  et les flèches étaient écoutées sur `window`. Le correctif exige maintenant
  le focus du canvas ; les tests navigateur couvrent ce comportement.
- **RISK-002**: Les captures du harnais sont une page minimale ; la page
  authentifiée, le CSS global et une API réelle demandent une validation
  séparée avant déclaration de fin MVP.
- **RISK-003**: Les coordonnées de pointeur et la caméra dépendent du viewport
  et du DPR ; figer les deux pour toute comparaison.

## Cartographie constatée avant code

| Action | Chemin actuel | PlanDocument | Vue/réseau |
|---|---|---|---|
| Sélection et glissement | `mousedown` choisit `hitRoom`, `mousemove` calcule `snapMove`/`canMove`, `mouseup` appelle `resolveDrop` | Sélection seule : non ; dépôt `move`/`swap` : oui ; rejet : non | Dépôt valide appelle `markDirty`, puis PUT différé 1,2 s |
| Annulation | `checkpoint` mémorise JSON ; `undo` restaure un instantané | Oui si historique | Nouveau PUT différé |
| Pan/zoom | glissement du fond, molette ou boutons → `fitView`/`zoomAt` | Non | Caméra seulement, aucune sauvegarde |
| Clavier | `window.keydown` gère Ctrl+Z, Escape et flèches | Flèches : oui si pièce sélectionnée et édition permise | Actuellement, le focus canvas n'est pas requis pour les flèches |
| Sauvegarde | `markDirty` → `save` → `topology` → PUT avec `base_revision_id` | Requête contient le plan courant | Réponse met à jour `revisionId` et statut ; erreur laisse le plan local |

Avant correction, le canvas du template n'avait ni `tabindex`, ni nom
accessible ; `save-status` et `topo-status` n'avaient pas de région live.
Les tests rouges ont reproduit ces lacunes. Les changements et leur portée
sont détaillés dans le [rapport apparié](../../benchmark/comparisons/3c-interactions/report.md).
Le harnais reste une page minimale ; la validation de la page authentifiée
complète et d'un lecteur d'écran n'est pas revendiquée.

## 8. Related Specifications / Further Reading

- [Plan MVP 2D](../refactor-mvp-2d-1.md)
- [Bilan du sprint 3C](3c-bilan.md)
- [Benchmark de l'éditeur](../../benchmark/README.md)
