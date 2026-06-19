"""Norms and FFN variants. Selected by string in ModelConfig - adding a new
variant means adding a class and one registry entry."""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from .config import ModelConfig


class RMSNorm(nn.Module):
    def __init__(self, dim: int, eps: float):
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x):
        norm = x.float().pow(2).mean(-1, keepdim=True).add(self.eps).rsqrt()
        return (x.float() * norm).type_as(x) * self.weight


def build_norm(cfg: ModelConfig, dim: int | None = None) -> nn.Module:
    dim = dim or cfg.d_model
    if cfg.norm_type == "layernorm":
        return nn.LayerNorm(dim, eps=cfg.norm_eps)
    return RMSNorm(dim, cfg.norm_eps)


class GLU(nn.Module):
    """Gated linear unit FFN: SwiGLU (silu gate) or GeGLU (gelu gate)."""

    def __init__(self, cfg: ModelConfig, act):
        super().__init__()
        self.gate = nn.Linear(cfg.d_model, cfg.intermediate_size, bias=False)
        self.up = nn.Linear(cfg.d_model, cfg.intermediate_size, bias=False)
        self.down = nn.Linear(cfg.intermediate_size, cfg.d_model, bias=False)
        self.drop = nn.Dropout(cfg.dropout)
        self.act = act

    def forward(self, x):
        return self.down(self.drop(self.act(self.gate(x)) * self.up(x)))


class GeluMLP(nn.Module):
    """Classic 2-layer MLP (GPT-2 style) for parity experiments."""

    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.up = nn.Linear(cfg.d_model, cfg.intermediate_size, bias=False)
        self.down = nn.Linear(cfg.intermediate_size, cfg.d_model, bias=False)
        self.drop = nn.Dropout(cfg.dropout)

    def forward(self, x):
        return self.down(self.drop(F.gelu(self.up(x), approximate="tanh")))


def build_mlp(cfg: ModelConfig) -> nn.Module:
    if cfg.mlp_type == "swiglu":
        return GLU(cfg, F.silu)
    if cfg.mlp_type == "geglu":
        return GLU(cfg, lambda x: F.gelu(x, approximate="tanh"))
    return GeluMLP(cfg)
