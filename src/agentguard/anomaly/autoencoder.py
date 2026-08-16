"""Autoencoder — gelişmiş anomali dedektörü — §8.3.

Mimari: 24 → 16 → 8 → 4 → 8 → 16 → 24. Skor = yeniden yapılandırma hatası
(örnek başına ortalama MSE). Eğitim yalnızca normal trace'lerdir; girdi
gürültüsü (`N(0, 0.05)`, denoising) aşırı ezberlemeyi azaltır.

**Eğitim tuzağı** (§8.3): eğitim verisine anomali sızarsa AE onları da iyi
yeniden yapılandırmayı öğrenir ve tespit çöker. Bu yüzden eğitim seti,
IsolationForest'ın en anormal %1'i çıkarılarak temizlenir — bu iki aşamalı
temizlik `scripts/train_models.py`'de uygulanır (detector kendi başına
"temiz" veri varsayar).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from numpy.typing import NDArray
from torch import nn
from torch.optim import AdamW  # type: ignore[attr-defined]  # torch stub'ları eksik export ediyor
from torch.optim.lr_scheduler import ReduceLROnPlateau

D_IN = 24
LATENT = 4
BATCH_SIZE = 64
MAX_EPOCHS = 200
EARLY_STOP_PATIENCE = 15
LR_PATIENCE = 5
LR_FACTOR = 0.5
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4
NOISE_STD = 0.05
VAL_FRACTION = 0.2


class TabularAE(nn.Module):
    def __init__(self, d_in: int = D_IN, latent: int = LATENT, p_drop: float = 0.1) -> None:
        super().__init__()
        self.enc = nn.Sequential(
            nn.Linear(d_in, 16),
            nn.BatchNorm1d(16),
            nn.GELU(),
            nn.Dropout(p_drop),
            nn.Linear(16, 8),
            nn.BatchNorm1d(8),
            nn.GELU(),
            nn.Linear(8, latent),
        )
        self.dec = nn.Sequential(
            nn.Linear(latent, 8),
            nn.GELU(),
            nn.Linear(8, 16),
            nn.GELU(),
            nn.Linear(16, d_in),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out: torch.Tensor = self.dec(self.enc(x))
        return out


class AutoencoderDetector:
    name = "autoencoder"

    def __init__(
        self,
        version: str = "v1",
        *,
        d_in: int = D_IN,
        latent: int = LATENT,
        seed: int = 42,
        max_epochs: int = MAX_EPOCHS,
    ) -> None:
        self.version = version
        self._d_in = d_in
        self._latent = latent
        self._seed = seed
        self._max_epochs = max_epochs
        # Determinizm: ağırlık ilklenmesi de seed'e bağlı olmalı; bu yüzden
        # gerçek model `fit()` içinde, seed set edildikten SONRA yaratılır.
        # `fit()` öncesi `raw_score`/`save` çağrılırsa `_fitted=False` zaten
        # hata fırlatır; bu placeholder yalnızca tip tutarlılığı içindir.
        self._model = TabularAE(d_in=d_in, latent=latent)
        self._fitted = False

    def fit(self, x: NDArray[np.float64]) -> None:
        torch.manual_seed(self._seed)
        torch.backends.cudnn.deterministic = True
        # Ağırlık ilklenmesi seed'e bağlı olsun diye model burada YENİDEN
        # yaratılır (__init__'teki placeholder'ın rastgele ağırlıkları atılır).
        self._model = TabularAE(d_in=self._d_in, latent=self._latent)
        generator = torch.Generator().manual_seed(self._seed)

        n = x.shape[0]
        n_val = max(1, int(n * VAL_FRACTION))
        perm = torch.randperm(n, generator=generator).numpy()
        val_idx, train_idx = perm[:n_val], perm[n_val:]

        x_tensor = torch.tensor(x, dtype=torch.float32)
        x_train, x_val = x_tensor[train_idx], x_tensor[val_idx]

        optimizer = AdamW(self._model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
        scheduler = ReduceLROnPlateau(optimizer, patience=LR_PATIENCE, factor=LR_FACTOR)
        loss_fn = nn.MSELoss(reduction="none")

        best_val_loss = float("inf")
        best_state: dict[str, torch.Tensor] | None = None
        epochs_without_improvement = 0

        n_train = x_train.shape[0]
        for _epoch in range(self._max_epochs):
            self._model.train()
            order = torch.randperm(n_train, generator=generator)
            for start in range(0, n_train, BATCH_SIZE):
                batch_idx = order[start : start + BATCH_SIZE]
                if len(batch_idx) < 2:  # BatchNorm en az 2 örnek ister
                    continue
                batch = x_train[batch_idx]
                noisy = batch + torch.randn(batch.shape, generator=generator) * NOISE_STD

                optimizer.zero_grad()
                reconstructed = self._model(noisy)
                loss = loss_fn(reconstructed, batch).mean()
                loss.backward()
                optimizer.step()

            val_loss = self._reconstruction_loss(x_val).mean().item()
            scheduler.step(val_loss)

            if val_loss < best_val_loss - 1e-6:
                best_val_loss = val_loss
                best_state = {k: v.clone() for k, v in self._model.state_dict().items()}
                epochs_without_improvement = 0
            else:
                epochs_without_improvement += 1
                if epochs_without_improvement >= EARLY_STOP_PATIENCE:
                    break

        if best_state is not None:
            self._model.load_state_dict(best_state)
        self._fitted = True

    def _reconstruction_loss(self, x_tensor: torch.Tensor) -> torch.Tensor:
        self._model.eval()
        with torch.inference_mode():
            reconstructed: torch.Tensor = self._model(x_tensor)
            per_sample: torch.Tensor = ((reconstructed - x_tensor) ** 2).mean(dim=1)
        return per_sample

    def raw_score(self, x: NDArray[np.float64]) -> NDArray[np.float64]:
        if not self._fitted:
            raise RuntimeError("AutoencoderDetector henüz fit edilmedi")
        x_tensor = torch.tensor(x, dtype=torch.float32)
        losses: NDArray[np.float64] = self._reconstruction_loss(x_tensor).numpy().astype(np.float64)
        return losses

    def save(self, path: Path) -> None:
        # weights_only uyumlu: yalnızca state_dict kaydedilir (§21.3 — pickle RCE riskini kapatır)
        torch.save(
            {
                "state_dict": self._model.state_dict(),
                "d_in": self._d_in,
                "latent": self._latent,
            },
            path,
        )

    @classmethod
    def load(cls, path: Path, *, version: str = "v1") -> AutoencoderDetector:
        checkpoint = torch.load(path, weights_only=True, map_location="cpu")
        instance = cls(version=version, d_in=checkpoint["d_in"], latent=checkpoint["latent"])
        instance._model.load_state_dict(checkpoint["state_dict"])
        instance._model.eval()
        instance._fitted = True
        return instance
