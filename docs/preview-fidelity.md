# Aperçu Gemini : suivre le plan

L'aperçu est un redessin par Gemini du plan vectoriel exact.

**Le plan de référence n'est jamais abandonné.** Si l'appel échoue, il est retenté avec le même plan
(un appel Gemini de plus, facturé). En cas d'échec persistant, l'aperçu est le rendu vectoriel exact :
plus sobre, mais fidèle. Avant, le code retombait sur une génération texte seul (puis `universal-ai`),
où Gemini invente un plan : pièces manquantes ou en trop, murs déplacés.

`GEMINI_TEXT_FALLBACK=1` rétablit l'ancien repli texte seul (déconseillé).

## Mode `GEMINI_ONLY` (actif par défaut dans `deploy/`)

L'éditeur 2D et les pages 3D sont mis en pause : leurs routes redirigent vers la page projet.
Si Gemini échoue, aucun rendu vectoriel de secours n'est affiché : la page indique « Aperçu
indisponible ». Le `PlanDocument` reste calculé (il guide Gemini) et les exports restent disponibles.
`GEMINI_ONLY=0` réactive l'éditeur, la 3D et le repli vectoriel.
