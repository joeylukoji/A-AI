# Galerie des générations pour l'article — 29 septembre 2026

## Résultat

Galerie locale : [ouvrir les candidats](../articles/selection-generations/index.html).
18 candidats G004 à G021, avec image originale et brief historique côte à côte,
agrandissement et sélection de cinq images exportable en JSON. Le choix final appartient à l'utilisateur.

## Données et limites

- PostgreSQL et MinIO consultés en lecture seule ; les deux conteneurs initialement arrêtés ont été démarrés pour cette consultation.
- 94 aperçus récupérés sur 94 enregistrements correspondant à la jointure jobs/révisions et comportant une clé d'image.
- Association : job réussi generate_2d → output.revision_id → révision source ai → preview_key → objet MinIO.
- Le prompt affiché est jobs.input.brief, accompagné de jobs.input.constraints, et non le brief actuel du projet.
- Le prompt technique enrichi et la version du modèle par résultat ne sont pas archivés.
- Les journaux disponibles mentionnent google/gemini-3-pro-image-preview via Eden et des erreurs de quota entraînant des replis locaux.
- Les trois premiers exports sont des replis locaux identiques ; exclus. G004–G021 forment un premier lot récent inspecté visuellement, distinct de ces replis. Cette inspection n'est pas une preuve cryptographique de provenance par modèle.
- Les 73 autres exports ne sont pas classifiés dans cette première galerie. Ils restent disponibles dans le manifeste local.
- Aucun appel de génération, aucune capture de l'éditeur, aucune retouche des originaux. Aucun secret ni identifiant utilisateur exporté.
- La sélection pour illustration ne doit pas servir à estimer les performances du système : biais de sélection et absence de validation architecturale indépendante.

## Vérification

`python research/test_article_gallery.py` : succès pour les 94 hashes SHA-256, les 18 associations exactes image/brief, le chargement des images, la limite de cinq choix, le téléchargement JSON et la mise en page mobile sans débordement.

`python -m ruff check research/export_article_gallery.py research/render_article_gallery.py research/test_article_gallery.py` : succès.

Inspection visuelle du lot et de la capture de la galerie effectuée. Les tests ouvrent une page séparée et ne présélectionnent rien dans la page de l'utilisateur.

## Revues

### Standards

Une annotation trop générale du retour Docker a été relevée : ajout d'une validation de liste/dictionnaire avant indexation. Le nombre de candidats affiché est désormais dérivé du lot. L'export conserve les erreurs par objet dans son manifeste ; un code de sortie réussi ne garantit pas à lui seul un export intégral. Ici les 94 objets sont récupérés et vérifiés.

### Spec

Aucun écart bloquant relevé. Limites de provenance affichées explicitement et sélection finale laissée à l'utilisateur.

## Reproduction

L'export `research/export_article_gallery.py` exige un dossier de sortie inexistant pour éviter tout écrasement.
La galerie peut être reconstruite sans Docker avec `python research/render_article_gallery.py`, puis vérifiée avec le test ci-dessus.
L'ouverture directe du fichier HTML fonctionne hors ligne ; le serveur de prévisualisation éventuel ne lie que 127.0.0.1.
