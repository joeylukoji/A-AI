# Métriques d’évaluation

Métriques prévues pour les benchmarks et la publication :

- **Raster** : FID, KID (papier) ; MAE + IoU murs dans `raster.py` (local, sans deps)
- **Sémantique** : IoU par type de pièce
- **Topologie** : fermeture des murs, connexité, orthogonalité
- **Contraintes** : conformité au `BuildingSpec`
- **Système** : latence, VRAM

Les résultats JSON des runs vont dans `research/benchmarks/results/`.
