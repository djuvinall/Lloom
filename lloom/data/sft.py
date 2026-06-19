"""SFT data: prompt-masked, sequence-packed supervised batches.

- Loss only on response tokens (prompt and padding -> -100).
- Multiple examples packed per row with first-fit-decreasing bin packing
  (near-optimal occupancy for this distribution at trivial cost).
- Packed examples DO NOT attend across boundaries: each batch carries per-
  position document ids, expanded at train time into a block-diagonal causal
  mask (see block_causal_mask). No cross-contamination, no padding waste.

The framework consumes already-tokenized (prompt_ids, response_ids) pairs;
templating (chat formats, special tokens) is the project's job.
"""
from __future__ import annotations

import json
from pathlib import Path

import torch


def load_jsonl(paths: list[str | Path]) -> list[dict]:
    rows = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def _pack_ffd(lengths: list[int], cap: int) -> list[list[int]]:
    """First-fit-decreasing bin packing; returns lists of example indices."""
    order = sorted(range(len(lengths)), key=lambda i: -lengths[i])
    bins: list[tuple[int, list[int]]] = []   # (remaining, indices)
    for i in order:
        for b, (rem, idxs) in enumerate(bins):
            if lengths[i] <= rem:
                bins[b] = (rem - lengths[i], idxs + [i])
                break
        else:
            bins.append((cap - lengths[i], [i]))
    return [idxs for _, idxs in bins]


def pack_examples(examples: list[tuple[list[int], list[int]]], seq_len: int,
                  pad_id: int) -> list[dict]:
    """examples: (prompt_ids, response_ids) pairs (response includes its EOT).
    Returns packed rows: {x (T,), y (T,), doc (T,)} with T = seq_len.
    Over-long examples keep the prompt and truncate the response tail; examples
    whose prompt alone fills >80% of the row are dropped (nothing to learn)."""
    cap = seq_len + 1                      # x/y shift consumes one extra id
    kept: list[tuple[list[int], int]] = []  # (ids, prompt_len)
    for prompt, resp in examples:
        if len(prompt) >= int(0.8 * cap):
            continue
        ids = (prompt + resp)[:cap]
        if len(ids) > len(prompt):         # at least one response token
            kept.append((ids, len(prompt)))
    rows = []
    for idxs in _pack_ffd([len(ids) for ids, _ in kept], cap):
        row_ids, doc, is_resp = [], [], []
        for d, i in enumerate(idxs):
            ids, p_len = kept[i]
            row_ids += ids
            doc += [d] * len(ids)
            is_resp += [False] * p_len + [True] * (len(ids) - p_len)
        pad = cap - len(row_ids)
        row_ids += [pad_id] * pad
        doc += [-1] * pad
        is_resp += [False] * pad
        t = torch.tensor(row_ids, dtype=torch.long)
        d = torch.tensor(doc, dtype=torch.long)
        r = torch.tensor(is_resp, dtype=torch.bool)
        x, y = t[:-1].clone(), t[1:].clone()
        # position i predicts t[i+1]: keep iff same doc and t[i+1] is response
        keep = (d[1:] == d[:-1]) & r[1:]
        y[~keep] = -100
        rows.append({"x": x, "y": y, "doc": d[:-1].clone()})
    return rows


def build_batches(rows: list[dict], batch_size: int, seed: int = 0) -> list[dict]:
    """Stack packed rows into (B, T) batches; shuffled once here, reshuffled
    per-epoch by the trainer at batch granularity."""
    gen = torch.Generator().manual_seed(seed)
    order = torch.randperm(len(rows), generator=gen).tolist()
    batches = []
    for i in range(0, len(order), batch_size):
        chunk = [rows[j] for j in order[i:i + batch_size]]
        batches.append({k: torch.stack([c[k] for c in chunk]) for k in ("x", "y", "doc")})
    return batches


def block_causal_mask(doc: torch.Tensor) -> torch.Tensor:
    """doc: (B, T) document ids (-1 = pad) -> bool (B, 1, T, T) attend-mask:
    causal AND same-document. Diagonal is always True (incl. pads), so no
    attention row is empty."""
    same = doc.unsqueeze(1) == doc.unsqueeze(2)
    causal = torch.tril(torch.ones(doc.shape[1], doc.shape[1],
                                   dtype=torch.bool, device=doc.device))
    return (same & causal).unsqueeze(1)


def train_val_split(examples: list, val_fraction: float, seed: int = 0):
    gen = torch.Generator().manual_seed(seed)
    order = torch.randperm(len(examples), generator=gen).tolist()
    n_val = max(1, int(len(examples) * val_fraction)) if examples else 0
    val_idx = set(order[:n_val])
    train = [e for i, e in enumerate(examples) if i not in val_idx]
    val = [e for i, e in enumerate(examples) if i in val_idx]
    return train, val
