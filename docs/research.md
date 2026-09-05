# Piste recherche

Contribution : **raffinement layout-aware par GAN** (pix2pix) au-dessus d’un générateur procédural (`BuildingSpec` → `PlanDocument`).

## Dataset

Aucun corpus n’est versionné dans le dépôt.

| Source | Usage | Script |
|--------|--------|--------|
| Synthèse A-AI | paires refine | `make_refine_pairs.py` |
| ResPlan (optionnel) | vecteurs ~17k | `download.py` puis `resplan_convert.py` |

```bash
python research/dataset/make_refine_pairs.py --count 512
python research/train_gan_refine.py --epochs 20
```

Poids : `research/benchmarks/results/gan_refine/last.pt`

Ne pas committer les `.pkl`, `resplan/`, ni les previews d’entraînement.

## Métriques

Scripts : `research/metrics/` (topologie, contraintes, raster).

## Ablations

```bash
python research/benchmarks/run_ablation.py
```
