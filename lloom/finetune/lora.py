"""Pure-PyTorch LoRA: inject, train, save/load adapters, merge back.

W' = W + (alpha/r) * B @ A, with A kaiming-init and B zero-init so training
starts exactly at the base model. Injection wraps existing nn.Linear modules
in place (state_dict of the base weights is unchanged apart from the
`.base.` prefix on wrapped layers - merge_lora() removes the wrappers again).
"""
from __future__ import annotations

import math
from pathlib import Path

import torch
import torch.nn as nn

DEFAULT_TARGETS = ("q_proj", "k_proj", "v_proj", "o_proj", "gate", "up", "down")


class LoRALinear(nn.Module):
    def __init__(self, base: nn.Linear, r: int, alpha: float, dropout: float):
        super().__init__()
        self.base = base
        self.r, self.alpha = r, alpha
        self.scaling = alpha / r
        self.lora_A = nn.Parameter(torch.empty(r, base.in_features))
        self.lora_B = nn.Parameter(torch.zeros(base.out_features, r))
        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))
        self.lora_drop = nn.Dropout(dropout)

    def forward(self, x):
        out = self.base(x)
        lora = self.lora_drop(x) @ self.lora_A.mT @ self.lora_B.mT
        return out + self.scaling * lora

    @torch.no_grad()
    def merged(self) -> nn.Linear:
        self.base.weight += (self.scaling * self.lora_B @ self.lora_A
                             ).to(self.base.weight.dtype)
        return self.base


def inject_lora(model: nn.Module, r: int = 32, alpha: float = 64.0,
                dropout: float = 0.05,
                targets: tuple[str, ...] = DEFAULT_TARGETS) -> int:
    """Wrap every nn.Linear whose attribute name is in `targets`. Returns the
    number of layers wrapped. Freezes all non-LoRA params."""
    wrapped = 0
    for parent in list(model.modules()):
        for attr, child in list(parent.named_children()):
            if isinstance(child, nn.Linear) and attr in targets:
                setattr(parent, attr, LoRALinear(child, r, alpha, dropout))
                wrapped += 1
    if wrapped == 0:
        raise ValueError(f"no Linear layers matched targets {targets}")
    mark_only_lora_trainable(model)
    return wrapped


def mark_only_lora_trainable(model: nn.Module) -> None:
    for name, p in model.named_parameters():
        p.requires_grad = "lora_" in name


def merge_lora(model: nn.Module) -> nn.Module:
    """Fold adapters into base weights and remove wrappers (in place)."""
    for parent in list(model.modules()):
        for attr, child in list(parent.named_children()):
            if isinstance(child, LoRALinear):
                setattr(parent, attr, child.merged())
    for p in model.parameters():
        p.requires_grad = True
    return model


def lora_state_dict(model: nn.Module) -> dict:
    return {k: v for k, v in model.state_dict().items() if "lora_" in k}


def save_adapter(model: nn.Module, path: str | Path, r: int, alpha: float,
                 targets: tuple[str, ...] = DEFAULT_TARGETS) -> None:
    torch.save({"lora": lora_state_dict(model),
                "meta": {"r": r, "alpha": alpha, "targets": list(targets)}}, path)


def load_adapter(model: nn.Module, path: str | Path, device="cpu",
                 dropout: float = 0.0) -> nn.Module:
    """Inject (using the adapter's own meta) and load weights into a base model."""
    ck = torch.load(path, map_location=device, weights_only=False)
    meta = ck["meta"]
    inject_lora(model, meta["r"], meta["alpha"], dropout, tuple(meta["targets"]))
    missing, unexpected = model.load_state_dict(ck["lora"], strict=False)
    bad = [k for k in unexpected if "lora_" in k]
    assert not bad, f"adapter keys did not match model: {bad[:5]}"
    return model
