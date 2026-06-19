"""Retrieval metrics over embedding similarity: MRR and NDCG@k.

Input is (query, positive) text pairs; every positive doubles as a distractor
for the other queries (in-batch corpus), which is the standard zero-setup
protocol for "is this embedding space usable?".
"""
from __future__ import annotations

import math

import torch

from .embed import embed_texts


def mrr_ndcg(sim: torch.Tensor, positive_idx: torch.Tensor, k: int = 10) -> dict:
    """sim: (Q, D) similarities; positive_idx: (Q,) index of the relevant doc.
    Binary relevance: NDCG@k reduces to 1/log2(1+rank) for rank <= k."""
    ranks = (sim > sim.gather(1, positive_idx[:, None])).sum(1) + 1   # 1-based
    mrr = (1.0 / ranks.float()).mean().item()
    ndcg = torch.where(ranks <= k,
                       1.0 / torch.log2(ranks.float() + 1.0),
                       torch.zeros_like(ranks, dtype=torch.float)).mean().item()
    return {"mrr": mrr, f"ndcg@{k}": ndcg,
            "recall@1": (ranks == 1).float().mean().item(),
            f"recall@{k}": (ranks <= k).float().mean().item()}


def retrieval_eval(model, tokenizer, pairs: list[tuple[str, str]], device,
                   k: int = 10, batch_size: int = 32) -> dict:
    queries = embed_texts(model, tokenizer, [q for q, _ in pairs], device, batch_size)
    docs = embed_texts(model, tokenizer, [d for _, d in pairs], device, batch_size)
    sim = queries @ docs.T                       # rows unit-norm -> cosine
    return mrr_ndcg(sim, torch.arange(len(pairs)), k)
