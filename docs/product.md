# Produit SaaS

## Proposition de valeur

Pour les particuliers ambitieux et les petits cabinets : passer d’un brief en langage naturel à un plan éditable et une maquette 3D exportable, sans démarrer de zéro dans un logiciel CAD lourd.

## Personas

1. **Particulier** — explore des layouts avant de rencontrer un architecte
2. **Architecte indépendant** — accélère l’esquisse, garde la main sur l’édition
3. **Cabinet** — volume de avant-projets + API (phase 2)

## Parcours Studio

1. Brief NL + contraintes
2. Génération IA (preview + `PlanDocument`)
3. Édition architecte (orthogonal, 1 niveau MVP)
4. Validation
5. Maquette 3D
6. Exports (PDF, SVG, DXF QCAD, OBJ/glTF)

## Plans tarifaires (cible)

| Plan | Générations / mois | Exports | 3D | Sièges | API |
|------|--------------------|---------|----|--------|-----|
| Free | 5 | 5 | 2 | 1 | Non |
| Pro | 50 | Illimités raisonnables | 30 | 3 | Non |
| Bureau | 300 | Illimités | 200 | 15 | Oui (phase 2) |

Les quotas GPU-minutes complètent ces plafonds pour protéger la marge.

## RBAC

| Action | owner | architect | viewer |
|--------|-------|-----------|--------|
| Gérer billing | oui | non | non |
| Inviter membres | oui | non | non |
| Créer projet | oui | oui | non |
| Générer / éditer | oui | oui | non |
| Lancer 3D / export | oui | oui | non |
| Lecture | oui | oui | oui |

## Roadmap produit

### Phase 0 — Fondations

Auth, orgs, projets, schemas, Compose, UI shell.

### Phase 1 — MVP génération

Pipeline stub/réel LLM→diffusion→vectorisation, éditeur minimal, SSE jobs.

### Phase 2 — Raffinement + 3D

GAN refine, Blender, viewer glTF, exports PDF / DXF QCAD / OBJ.

### Phase 3 — Commercial

Stripe, quotas, onboarding, hardening sécu, landing.

### Phase 4 — Scale cabinets + recherche

API publique, webhooks, IFC/DWG, publication scientifique.

## Risques produit

- **Éditeur** : complexité UX n°1 → borner à orthogonal / 1 étage
- **Coût GPU** : free tier strict + cache briefs similaires
- **Vectorisation** : sans graphe propre, pas d’exports sérieux
- **Attentes CAD** : communiquer « esquisse assistée », pas remplacement Revit dès le MVP

## Critères de succès MVP

- Parcours brief → plan éditable → 3D en < 2 minutes (mode stub)
- Un architecte peut corriger un mur et réexporterer sans régénérer
- Au moins 3 formats d’export fonctionnels
- Quotas free respectés côté API
