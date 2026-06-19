"""Rotary position embeddings with linear / NTK-aware scaling.

- linear: positions are divided by `factor` (Chen et al. position interpolation).
- ntk:    theta is rescaled so high-frequency dims keep resolution while low
          frequencies stretch (theta' = theta * factor^(d/(d-2))).
Both extend usable context to max_seq_len * factor at inference; for from-
scratch training you normally leave scaling off and set max_seq_len directly.
"""
from __future__ import annotations

import torch


def build_rope_cache(head_dim: int, max_position: int, theta: float,
                     scaling: dict | None = None):
    scaling = scaling or {}
    factor = float(scaling.get("factor", 1.0))
    if scaling.get("type") == "ntk" and factor > 1.0:
        theta = theta * factor ** (head_dim / (head_dim - 2))
    inv = 1.0 / (theta ** (torch.arange(0, head_dim, 2).float() / head_dim))
    t = torch.arange(max_position).float()
    if scaling.get("type") == "linear" and factor > 1.0:
        t = t / factor
    freqs = torch.outer(t, inv)                      # (P, hd/2)
    return torch.cos(freqs), torch.sin(freqs)


def apply_rope(x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor,
               offset: int = 0):
    """x: (B, H, T, hd). `offset` = absolute position of x[..., 0, :], which is
    what makes incremental KV-cache decoding rotate by true positions."""
    T = x.shape[2]
    cos = cos[offset:offset + T][None, None]
    sin = sin[offset:offset + T][None, None]
    x1, x2 = x[..., 0::2], x[..., 1::2]
    out = torch.empty_like(x)
    out[..., 0::2] = x1 * cos - x2 * sin
    out[..., 1::2] = x1 * sin + x2 * cos
    return out
