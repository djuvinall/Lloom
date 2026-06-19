"""Seeding, device, RNG snapshots, metric loggers, VRAM estimation."""
from __future__ import annotations

import csv
import random
import time
from pathlib import Path

import numpy as np
import torch


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def get_device(requested: str = "cuda") -> torch.device:
    if requested == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError(
                "config requests device: cuda but torch.cuda.is_available() is "
                "False -- your torch is almost certainly a CPU-only build, so a "
                "run would crawl on CPU instead of failing. Install a CUDA wheel "
                "(RTX 5070 Ti / Blackwell needs CUDA 12.8):\n"
                "  pip install torch --index-url https://download.pytorch.org/whl/cu128\n"
                "Or set device: cpu in your config to run on CPU deliberately."
            )
        return torch.device("cuda")
    return torch.device("cpu")


def count_params(model: torch.nn.Module, trainable_only: bool = False) -> int:
    return sum(p.numel() for p in model.parameters()
               if p.requires_grad or not trainable_only)


def fmt_params(n: int) -> str:
    if n >= 1e9:
        return f"{n / 1e9:.2f}B"
    return f"{n / 1e6:.0f}M" if n >= 1e6 else f"{n / 1e3:.0f}K"


def estimate_train_vram_gb(n_params: int, optimizer: str = "adamw",
                           n_hidden_2d: int | None = None) -> float:
    """Rough steady-state VRAM for fp32 params + autocast training, before
    activations. AdamW: 16 B/param (w4 + g4 + m4 + v4). Muon: momentum-only
    on 2D hidden weights (12 B/param there), AdamW on the rest.
    Treat as a sanity check, not a promise."""
    if optimizer == "muon" and n_hidden_2d:
        rest = n_params - n_hidden_2d
        return (n_hidden_2d * 12 + rest * 16) / 1e9
    if optimizer == "lion":
        return n_params * 12 / 1e9        # w + g + single momentum
    return n_params * 16 / 1e9


def rng_state() -> dict:
    return {
        "python": random.getstate(),
        "numpy": np.random.get_state(),
        "torch": torch.get_rng_state(),
        "cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None,
    }


def load_rng_state(state: dict) -> None:
    random.setstate(state["python"])
    np.random.set_state(state["numpy"])
    torch.set_rng_state(state["torch"])
    if state.get("cuda") is not None and torch.cuda.is_available():
        torch.cuda.set_rng_state_all(state["cuda"])


class CSVLogger:
    """Append-only local metric log; survives without any external service."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._keys: list[str] | None = None
        if self.path.exists():
            with open(self.path, newline="", encoding="utf-8") as f:
                header = next(csv.reader(f), None)
            self._keys = header

    def log(self, step: int, metrics: dict) -> None:
        row = {"step": step, "time": f"{time.time():.0f}", **metrics}
        if self._keys is None:                       # first write: header from this row
            self._keys = list(row)
            with open(self.path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=self._keys)
                w.writeheader(); w.writerow(row)
            return
        new = [k for k in row if k not in self._keys]
        if new:                                      # new columns (e.g. val/*): grow header
            old_rows = []
            if self.path.exists():
                with open(self.path, newline="", encoding="utf-8") as f:
                    old_rows = list(csv.DictReader(f))
            self._keys = self._keys + new
            with open(self.path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=self._keys, extrasaction="ignore")
                w.writeheader()
                for r in old_rows:
                    w.writerow(r)
                w.writerow(row)
        else:                                        # known columns: fast append
            with open(self.path, "a", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=self._keys, extrasaction="ignore").writerow(row)


class WandbLogger:
    """No-op unless enabled and wandb importable - training never blocks on it."""

    def __init__(self, enabled: bool, project: str, run_name: str, config: dict):
        self.run = None
        if not enabled:
            return
        try:
            import wandb
            self.run = wandb.init(project=project, name=run_name, config=config)
        except Exception as e:  # offline, not installed, not logged in
            print(f"[wandb] disabled ({e})")

    def log(self, metrics: dict, step: int) -> None:
        if self.run is not None:
            self.run.log(metrics, step=step)

    def log_text(self, key: str, text: str, step: int) -> None:
        if self.run is not None:
            import wandb
            self.run.log({key: wandb.Html(f"<pre>{text}</pre>")}, step=step)

    def finish(self) -> None:
        if self.run is not None:
            self.run.finish()
