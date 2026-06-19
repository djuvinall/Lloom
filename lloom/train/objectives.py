"""Multi-objective pretraining: causal LM + span corruption.

Both losses in one forward pass would contaminate the causal objective with
corrupted inputs, so each micro-batch is assigned one objective (UL2
mixture-of-denoisers style) - same expected weighting, cleaner gradients,
losses logged separately. Deterministic in (seed, step, micro) for exact
resume.
"""
from __future__ import annotations

import math

import torch

CAUSAL = "causal_lm"
SPAN = "span_corruption"


def sample_objective(step: int, micro: int, seed: int, causal_prob: float) -> str:
    gen = torch.Generator().manual_seed(seed * 31 + step * 64 + micro + 7)
    return CAUSAL if torch.rand(1, generator=gen).item() < causal_prob else SPAN


def apply_span_corruption(x: torch.Tensor, y: torch.Tensor, mask_id: int,
                          ratio: float, mean_span: float, step: int, micro: int,
                          seed: int):
    """Replace ~ratio of input tokens with the mask sentinel in geometric-length
    spans. Targets keep only positions whose *next* token was masked, so the
    model reconstructs hidden tokens left-to-right from (corrupted) context.
    Returns new (x, y); inputs are not modified in place."""
    B, T = x.shape
    gen = torch.Generator().manual_seed(seed * 17 + step * 64 + micro + 13)
    x = x.clone()
    keep = torch.full_like(y, -100)
    n_target = max(int(T * ratio), 1)
    log_q = math.log(1.0 - 1.0 / mean_span)   # geometric span lengths, seeded
    for b in range(B):
        masked = 0
        while masked < n_target:
            u = torch.rand(1, generator=gen).item()
            span = 1 + int(math.log1p(-u) / log_q)
            span = max(1, min(span, n_target - masked, 10, T - 2))
            start = torch.randint(1, T - span, (1,), generator=gen).item()
            x[b, start:start + span] = mask_id
            # predict masked token at i from positions < i -> target index i-1
            keep[b, start - 1:start + span - 1] = y[b, start - 1:start + span - 1]
            masked += span
    return x, keep
