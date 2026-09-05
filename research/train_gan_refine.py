#!/usr/bin/env python3
"""Train layout-aware pix2pix refine (coarse+mask -> clean). GPU only."""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import cast

from PIL import Image

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "services" / "ai"))
sys.path.insert(0, str(REPO / "research"))

def require_cuda(available: bool, version: str) -> str:
    if not available:
        raise SystemExit(f"CUDA requis (torch {version}).")
    return "cuda"


def load_stems(root: Path, split: str, limit: int) -> list[str]:
    folder = root / split
    if not folder.is_dir():
        raise SystemExit(f"Paires introuvables: {folder}\nLance: python research/dataset/make_refine_pairs.py")
    stems = sorted({p.name.split("_")[0] for p in folder.glob("*_in.png")})
    if limit:
        stems = stems[:limit]
    if not stems:
        raise SystemExit(f"Aucune paire dans {folder}")
    return stems


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", type=Path, default=REPO / "research" / "dataset" / "data" / "refine_pairs")
    parser.add_argument("--out", type=Path, default=REPO / "research" / "benchmarks" / "results" / "gan_refine")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--lr-d", type=float, default=5e-5)
    parser.add_argument("--l1", type=float, default=10.0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    try:
        import torch
        from torch.utils.data import DataLoader, Dataset
        from torchvision import transforms
        from torchvision.utils import save_image
    except ImportError as exc:
        raise SystemExit("Installe PyTorch CUDA: pip install -r research/requirements-gan.txt") from exc

    from app.gan_unet import UNet

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device(require_cuda(torch.cuda.is_available(), torch.__version__))
    torch.cuda.manual_seed_all(args.seed)
    torch.backends.cudnn.benchmark = True

    stems = load_stems(args.src, "train", args.limit)
    _tfm = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.5,), (0.5,))])

    def tfm(img: Image.Image) -> torch.Tensor:
        """Applique la transformation en explicitant le type de retour.

        `transforms.Compose.__call__` est typé de façon générique, si bien que
        les vérificateurs de types voient `Image` au lieu du `Tensor` réellement
        renvoyé, et signalent à tort les `torch.cat` en aval.
        """
        return cast(torch.Tensor, _tfm(img))

    class Pairs(Dataset):
        def __len__(self) -> int:
            return len(stems)

        def __getitem__(self, i: int):
            stem = stems[i]
            folder = args.src / "train"
            coarse = Image.open(folder / f"{stem}_in.png").convert("L").resize((args.size, args.size))
            mask = Image.open(folder / f"{stem}_mask.png").convert("L").resize((args.size, args.size))
            clean = Image.open(folder / f"{stem}_out.png").convert("L").resize((args.size, args.size))
            x = torch.cat([tfm(coarse), tfm(mask)], 0)
            return x, tfm(clean)

    loader = DataLoader(
        Pairs(),
        batch_size=args.batch,
        shuffle=True,
        drop_last=True,
        pin_memory=True,
        num_workers=0,
    )
    G = UNet(2, 1).to(device)
    # Patch discriminator: cond(2)+img(1)
    import torch.nn as nn

    D = nn.Sequential(
        nn.Conv2d(3, 64, 4, 2, 1),
        nn.LeakyReLU(0.2, inplace=True),
        nn.Conv2d(64, 128, 4, 2, 1, bias=False),
        nn.BatchNorm2d(128),
        nn.LeakyReLU(0.2, inplace=True),
        nn.Conv2d(128, 256, 4, 2, 1, bias=False),
        nn.BatchNorm2d(256),
        nn.LeakyReLU(0.2, inplace=True),
        nn.Conv2d(256, 1, 4, 1, 1),
    ).to(device)

    opt_g = torch.optim.Adam(G.parameters(), lr=args.lr, betas=(0.5, 0.999))
    opt_d = torch.optim.Adam(D.parameters(), lr=args.lr_d, betas=(0.5, 0.999))
    mse = nn.MSELoss()
    l1 = nn.L1Loss()

    args.out.mkdir(parents=True, exist_ok=True)
    history = []
    steps = max(1, len(stems) // args.batch)
    print(f"{len(stems)} paires, device={device} ({torch.cuda.get_device_name(0)}), pix2pix")

    for epoch in range(1, args.epochs + 1):
        acc_d = acc_g = 0.0
        for cond, real in loader:
            cond, real = cond.to(device, non_blocking=True), real.to(device, non_blocking=True)
            fake = G(cond)
            opt_d.zero_grad()
            d_real = D(torch.cat([cond, real], 1))
            d_fake = D(torch.cat([cond, fake.detach()], 1))
            loss_d = mse(d_real, torch.full_like(d_real, 0.9)) + mse(d_fake, torch.full_like(d_fake, 0.1))
            loss_d.backward()
            opt_d.step()

            opt_g.zero_grad()
            loss_g = mse(D(torch.cat([cond, fake], 1)), torch.ones_like(d_real)) + args.l1 * l1(fake, real)
            loss_g.backward()
            opt_g.step()
            acc_d += float(loss_d)
            acc_g += float(loss_g)

        row = {"epoch": epoch, "loss_d": acc_d / steps, "loss_g": acc_g / steps}
        history.append(row)
        print(f"epoch {epoch}/{args.epochs}  D={row['loss_d']:.3f}  G={row['loss_g']:.3f}")
        with torch.no_grad():
            preview = G(cond[:8])
            grid = torch.cat([cond[:8, :1], preview, real[:8]], 0)
            save_image((grid * 0.5) + 0.5, args.out / f"preview_e{epoch:03d}.png", nrow=8)
        torch.save(
            {"G": G.state_dict(), "D": D.state_dict(), "epoch": epoch, "size": args.size, "in_ch": 2},
            args.out / "last.pt",
        )

    (args.out / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    print(f"Checkpoints -> {args.out / 'last.pt'}")
    print("Produit: AI_STUB=0 GAN_WEIGHTS=" + str(args.out / "last.pt"))


if __name__ == "__main__":
    main()
