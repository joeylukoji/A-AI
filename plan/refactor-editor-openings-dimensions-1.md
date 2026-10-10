---
goal: Professionnaliser les ouvertures et les cotations intérieures du plan 2D
version: 1.0
date_created: 2026-09-27
last_updated: 2026-09-27
owner: Équipe A-AI
status: 'Completed'
tags: [refactor, frontend, editor, 2d, openings, annotations, benchmark]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-brightgreen)

Ce sprint extrait le rendu des ouvertures hors du module de murs, améliore les
portes et fenêtres selon les conventions d’un plan architectural lisible, puis
ajoute des dimensions intérieures compactes aux pièces rectangulaires lorsque
l’espace disponible le permet. La baseline appariée est
`benchmark/runs/editor-presentation-v2`.

## 1. Requirements & Constraints

- **REQ-001**: Créer `web/static/js/plan-style-openings.js` comme unique
  propriétaire de la résolution des segments d’ouverture et du dessin des
  portes, fenêtres, dormants, jambages, vitrages et seuils.
- **REQ-002**: Réduire `web/static/js/plan-style-walls.js` au dessin des murs et
  au point d’extension historique `drawPorch`, sans changer la façade publique
  `PlanStyle.drawOpenings`.
- **REQ-003**: Dessiner chaque porte comme une réservation blanche, deux
  jambages, un seuil fin, un battant plein lisible et un arc de débattement
  secondaire, entièrement contenu dans la largeur visible de l’ouverture.
- **REQ-004**: Dessiner chaque fenêtre comme une réservation blanche, deux
  rails de dormant, un vitrage central bleuté, deux jambages et un meneau
  uniquement lorsque la largeur écran reste lisible.
- **REQ-005**: Ajouter une troisième ligne `largeur × profondeur m` aux labels
  des pièces rectangulaires, hors couloirs, seulement dans l’éditeur et
  uniquement si le texte tient dans la pièce sans recouvrir le mobilier
  volumique ; les tapis, traités comme revêtements de sol, ne bloquent pas le
  label et peuvent rester sous le texte comme sur un plan architectural.
- **REQ-006**: Omettre les dimensions intérieures des polygones concaves,
  irréguliers ou non orthogonaux afin de ne pas présenter une boîte englobante
  comme une mesure architecturale exacte.
- **REQ-007**: Charger le nouveau module dans les templates, les tests et le
  benchmark, puis produire 38 captures appariées avec les documents inchangés.
- **CON-001**: Ne pas inventer de sens de charnière ou de débattement absent du
  schéma PlanDocument 1.0 ; conserver l’orientation conventionnelle actuelle.
- **CON-002**: Ne modifier ni la génération Gemini, ni la 3D, ni la géométrie
  persistée, ni les interactions d’édition.
- **GUD-001**: Les détails de menuiserie doivent rester moins dominants que les
  murs et conserver leur lisibilité aux zooms 50 %, 100 % et 200 %.
- **PAT-001**: Injecter le module d’ouvertures par la façade `plan-style.js`,
  sans état global mutable et sans dépendance vers `editor.js`.

## 2. Implementation Steps

### Implementation Phase 1 — Stabilize

- GOAL-001: Verrouiller les invariants des ouvertures et des labels avant le refactor.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Ajouter les tests du module d’ouvertures pour murs horizontaux, verticaux, inversés, ouvertures tronquées, entrées invalides, hiérarchie des traits et équilibre Canvas ; ajouter les tests de dimensions intérieures rectangulaires et d’omission des géométries irrégulières. | Oui | 2026-09-27 |

### Implementation Phase 2 — Extract and improve

- GOAL-002: Séparer les responsabilités et améliorer la fidélité graphique.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-002 | Après TASK-001, créer `plan-style-openings.js`, y déplacer la résolution des segments et `drawOpenings`, puis implémenter dormant, vitrage, meneau, seuil, jambages, battant et arc. | Oui | 2026-09-27 |
| TASK-003 | Après TASK-002, retirer le rendu des ouvertures de `plan-style-walls.js`, injecter le nouveau module dans `plan-style.js` et centraliser son ordre dans le partial, le loader Node et `RENDER_SCRIPTS`. | Oui | 2026-09-27 |
| TASK-004 | Étendre `plan-style-annotations.js` avec une mesure exacte réservée aux rectangles orthogonaux et adapter l’algorithme de placement à trois lignes avec repli dimensions → surface → nom. | Oui | 2026-09-27 |

### Implementation Phase 3 — Benchmark and validate

- GOAL-003: Démontrer la fidélité, l’absence de régression et le coût maîtrisé.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Exécuter les tests ciblés et Node complet, inspecter une capture de développement et ajuster seulement couleurs, épaisseurs et seuils de lisibilité. | Oui | 2026-09-27 |
| TASK-006 | Générer 38 captures sous `benchmark/runs/editor-openings-dimensions-v1`, comparer images, documents, réseau, assets et temps de couche à `editor-presentation-v2`, puis rédiger le rapport. | Oui | 2026-09-27 |
| TASK-007 | Exécuter pytest benchmark, Ruff, Go HTTP et diff-check ; mener les revues Standards/Spec, corriger les findings et finaliser `docs/`. | Oui | 2026-09-27 |

## 3. Alternatives

- **ALT-001**: Ajouter immédiatement `hinge` et `swing` au schéma : rejeté car
  cela imposerait une migration de la génération, de la validation, de l’export
  et des documents existants, au-delà de ce sprint visuel.
- **ALT-002**: Conserver les ouvertures dans `plan-style-walls.js` : rejeté car
  le module cumulerait structure porteuse et menuiseries détaillées.
- **ALT-003**: Afficher la boîte englobante de toutes les pièces : rejeté car la
  valeur serait trompeuse pour les pièces concaves ou irrégulières.

## 4. Dependencies

- **DEP-001**: Contrat Canvas de `PlanStyle` et ordre de rendu de
  `web/static/js/editor.js`.
- **DEP-002**: Algorithme d’évitement du mobilier de
  `web/static/js/plan-style-annotations.js`.
- **DEP-003**: Harnais Playwright et baseline
  `benchmark/runs/editor-presentation-v2`.

## 5. Files

- **FILE-001**: `web/static/js/plan-style-openings.js` et
  `web/tests/plan-style-openings.test.cjs`.
- **FILE-002**: `web/static/js/plan-style-walls.js` et son test ciblé.
- **FILE-003**: `web/static/js/plan-style-annotations.js`, `web/static/js/editor.js`
  et les tests d’annotations.
- **FILE-004**: `web/static/js/plan-style.js`, `web/templates/partials.html`,
  `web/tests/helpers/plan-style-loader.cjs` et `benchmark/editor_capture.py`.
- **FILE-005**: Captures, comparaison, rapport et documentation du sprint.

## 6. Testing

- **TEST-001**: Chaque ouverture valide reste dans son segment visible, produit
  uniquement des coordonnées finies et équilibre tous les `save`/`restore`.
- **TEST-002**: Les portes produisent réservation, deux jambages, seuil, battant
  et arc ; les fenêtres produisent réservation, dormant, vitrage et jambages.
- **TEST-003**: Les dimensions intérieures n’apparaissent que pour un rectangle
  orthogonal exact, tiennent dans l’espace disponible et évitent le mobilier.
- **TEST-004**: Les 38 captures n’effectuent aucune requête réseau, chargent tous
  les assets et conservent les hashes des six documents de la baseline.
- **TEST-005**: La médiane du temps de couche ne régresse pas de plus de 10 % ;
  Node, pytest, Ruff, Go et diff-check passent.

## 7. Risks & Assumptions

- **RISK-001**: Des détails trop nombreux deviennent illisibles à 50 % ; chaque
  détail secondaire doit être conditionné par une largeur écran minimale.
- **RISK-002**: Une troisième ligne de label peut collisionner avec le mobilier ;
  l’algorithme doit supprimer d’abord la dimension, puis la surface, avant le nom.
- **RISK-003**: L’extraction ajoute un script à tous les points de chargement ;
  l’ordre centralisé doit être vérifié par test.
- **ASSUMPTION-001**: Les pièces rectangulaires générées ont quatre sommets
  orthogonaux et une aire égale à celle de leur boîte englobante à 1e-6 près.

## 8. Related Specifications / Further Reading

- [Sprint de présentation précédent](refactor-editor-presentation-1.md)
- [Audit de l’architecture 2D](../docs/architecture-2d-audit.md)
- [Rapport de présentation](../benchmark/comparisons/editor-presentation/report.md)

