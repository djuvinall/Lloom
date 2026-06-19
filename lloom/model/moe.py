"""Sparse mixture-of-experts FFN: top-k softmax routing (renormalized over the
chosen k), per-expert gathered dispatch, Switch-style load-balancing aux loss.

Routing runs in fp32 for stability. Dispatch is a loop over experts with
index_add_ scatter - on a single GPU at the scales this framework targets,
that is both the simplest and the fastest practical layout (no all-to-all)."""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from .config import ModelConfig
from .layers import build_mlp


class MoE(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.n_experts, self.top_k = cfg.n_experts, cfg.moe_top_k
        self.router = nn.Linear(cfg.d_model, cfg.n_experts, bias=False)
        self.experts = nn.ModuleList(build_mlp(cfg) for _ in range(cfg.n_experts))
        self.last_aux_loss: torch.Tensor | None = None

    def forward(self, x):
        B, T, C = x.shape
        flat = x.view(-1, C)                                   # (N, C)
        probs = F.softmax(self.router(flat.float()), dim=-1)   # (N, E) fp32
        top_p, top_i = probs.topk(self.top_k, dim=-1)          # (N, k)
        top_p = top_p / top_p.sum(-1, keepdim=True)

        out = torch.zeros_like(flat)
        for e in range(self.n_experts):
            tok, slot = (top_i == e).nonzero(as_tuple=True)
            if tok.numel() == 0:
                continue
            w = top_p[tok, slot].unsqueeze(-1).type_as(flat)
            out.index_add_(0, tok, w * self.experts[e](flat[tok]))

        if self.training:
            # Switch load-balancing: E * sum_e( assigned_fraction_e * mean_prob_e )
            N = flat.shape[0]
            f = torch.zeros(self.n_experts, device=x.device, dtype=probs.dtype)
            f.scatter_add_(0, top_i.reshape(-1),
                           torch.ones(N * self.top_k, device=x.device,
                                      dtype=probs.dtype))
            f = f / (N * self.top_k)
            self.last_aux_loss = self.n_experts * (f * probs.mean(0)).sum()
        return out.view(B, T, C)
