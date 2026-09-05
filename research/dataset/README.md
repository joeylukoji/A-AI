# Pipeline dataset

Le produit n’embarque **aucun** corpus d’images. Les scripts ci-dessous servent seulement à la recherche.

## ResPlan (optionnel, vecteur + graphe)

```bash
python research/dataset/download.py --fetch
python research/dataset/resplan_convert.py --limit 50
```

Licence ResPlan : voir la page Zenodo. Ne pas committer `resplan/` ni les `.pkl`.

## Refine GAN (layout-aware)

```bash
python research/dataset/make_refine_pairs.py --count 512
python research/train_gan_refine.py --epochs 20
```

Poids : `research/benchmarks/results/gan_refine/last.pt`

## Scripts

| Script | Rôle |
|--------|------|
| `download.py` | ResPlan (Zenodo) |
| `resplan_convert.py` | pickle → JSON A-AI |
| `make_refine_pairs.py` | paires coarse → clean pour le refine |
