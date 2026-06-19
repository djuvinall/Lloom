"""Autoregressive generation with KV cache and a modern sampling stack:
temperature, top-k, top-p, min-p, repetition penalty, greedy (temperature 0).

Sampling order: repetition penalty -> temperature -> top-k -> top-p -> min-p.
min-p (keep tokens with p >= min_p * p_max) adapts the cutoff to the model's
confidence - tighter than top-p when confident, looser when uncertain.
"""
from __future__ import annotations

from typing import Callable

import torch
import torch.nn.functional as F


def _apply_repetition_penalty(logits, seen_ids, penalty):
    if penalty == 1.0:
        return logits
    for b in range(logits.shape[0]):
        ids = seen_ids[b].unique()
        sel = logits[b, ids]
        logits[b, ids] = torch.where(sel > 0, sel / penalty, sel * penalty)
    return logits


def sample_next(logits: torch.Tensor, temperature=0.7, top_k=0, top_p=0.9,
                min_p=0.0, generator=None) -> torch.Tensor:
    """logits: (B, V) -> next ids (B, 1)."""
    if temperature <= 0:
        return logits.argmax(-1, keepdim=True)
    logits = logits / temperature
    if top_k:
        kth = torch.topk(logits, min(top_k, logits.shape[-1])).values[..., -1, None]
        logits = logits.masked_fill(logits < kth, float("-inf"))
    probs = F.softmax(logits, dim=-1)
    if top_p < 1.0:
        sp, si = torch.sort(probs, descending=True)
        keep = torch.cumsum(sp, -1) - sp < top_p          # always keep top-1
        sp = sp * keep
        probs = torch.zeros_like(probs).scatter_(-1, si, sp)
    if min_p > 0.0:
        probs = probs * (probs >= min_p * probs.max(-1, keepdim=True).values)
    probs = probs / probs.sum(-1, keepdim=True)
    return torch.multinomial(probs, 1, generator=generator)


@torch.no_grad()
def generate(model, idx: torch.Tensor, max_new_tokens: int, temperature=0.7,
             top_k=0, top_p=0.9, min_p=0.0, repetition_penalty=1.0,
             eot_id: int | None = None, use_cache=True, seed: int | None = None,
             on_token: Callable[[int], None] | None = None) -> torch.Tensor:
    """idx: (B, T) prompt ids -> (B, T+n) ids. on_token streams ids (B=1 only).
    KV-cached: prefill once, then one token per forward. Generation stops at
    eot (all rows) or when the model's max_position is reached."""
    model.eval()
    device = idx.device
    gen = None
    if seed is not None:
        gen = torch.Generator(device=device.type).manual_seed(seed)
    max_pos = model.cfg.max_position
    cache = model.new_cache(idx.shape[0]) if use_cache else None
    done = torch.zeros(idx.shape[0], dtype=torch.bool, device=device)
    logits = None

    for i in range(max_new_tokens):
        if idx.shape[1] >= max_pos:
            break
        if use_cache:
            inp = idx if i == 0 else idx[:, -1:]
            logits, _ = model(inp, cache=cache)
        else:
            logits, _ = model(idx[:, -model.cfg.max_seq_len:])
        step_logits = logits[:, -1].float()
        step_logits = _apply_repetition_penalty(step_logits, idx, repetition_penalty)
        nxt = sample_next(step_logits, temperature, top_k, top_p, min_p, gen)
        if eot_id is not None:
            nxt = torch.where(done[:, None], torch.full_like(nxt, eot_id), nxt)
            done |= nxt.squeeze(1) == eot_id
        idx = torch.cat([idx, nxt], dim=1)
        if on_token is not None:
            on_token(int(nxt[0, 0]))
        if eot_id is not None and done.all():
            break
    return idx
