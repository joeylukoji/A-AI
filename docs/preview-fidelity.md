# Aperçu Gemini : suivre le plan

L'aperçu est un redessin par Gemini du plan vectoriel exact.

**Le plan de référence n'est jamais abandonné.** Si l'appel échoue, il est retenté avec le même plan
(un appel Gemini de plus, facturé). En cas d'échec persistant, l'aperçu est le rendu vectoriel exact :
plus sobre, mais fidèle. Avant, le code retombait sur une génération texte seul (puis `universal-ai`),
où Gemini invente un plan : pièces manquantes ou en trop, murs déplacés.

`GEMINI_TEXT_FALLBACK=1` rétablit l'ancien repli texte seul (déconseillé).
