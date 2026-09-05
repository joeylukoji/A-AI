"""U-Net used by refine training and inference (2-ch cond -> 1-ch plan)."""
from __future__ import annotations


def UNet(in_ch: int, out_ch: int):
    import torch
    import torch.nn as nn

    def block(a: int, b: int, down: bool) -> nn.Sequential:
        if down:
            return nn.Sequential(
                nn.Conv2d(a, b, 4, 2, 1, bias=False),
                nn.BatchNorm2d(b),
                nn.LeakyReLU(0.2, inplace=True),
            )
        return nn.Sequential(
            nn.ConvTranspose2d(a, b, 4, 2, 1, bias=False),
            nn.BatchNorm2d(b),
            nn.ReLU(True),
        )

    class Net(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.d1 = block(in_ch, 64, True)
            self.d2 = block(64, 128, True)
            self.d3 = block(128, 256, True)
            self.d4 = block(256, 512, True)
            self.u1 = block(512, 256, False)
            self.u2 = block(512, 128, False)
            self.u3 = block(256, 64, False)
            self.u4 = nn.Sequential(nn.ConvTranspose2d(128, out_ch, 4, 2, 1), nn.Tanh())

        def forward(self, x):
            e1 = self.d1(x)
            e2 = self.d2(e1)
            e3 = self.d3(e2)
            e4 = self.d4(e3)
            z = self.u1(e4)
            z = self.u2(torch.cat([z, e3], 1))
            z = self.u3(torch.cat([z, e2], 1))
            return self.u4(torch.cat([z, e1], 1))

    return Net()
