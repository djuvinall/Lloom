"""Perplexity over token streams (sequential non-overlapping windows)."""
from __future__ import annotations

import numpy as np
import torch


@torch.no_grad()
def perplexity_on_stream(model, stream: np.ndarray, batch_size: int, seq_len: int,
                         device, max_batches: int | None = None):
    """Mean cross-entropy over sequential non-overlapping windows.
    Returns (mean_ce, n_tokens)."""
    model.eval()
    n_windows = (len(stream) - 1) // seq_len
    total, ntok, done = 0.0, 0, 0
    for start in range(0, n_windows, batch_size):
        rows = []
        for w in range(start, min(start + batch_size, n_windows)):
            a = w * seq_len
            rows.append(torch.from_numpy(stream[a:a + seq_len + 1].astype(np.int64)))
        b = torch.stack(rows).to(device)
        _, loss = model(b[:, :-1], b[:, 1:])
        total += loss.item() * b.shape[0] * seq_len
        ntok += b.shape[0] * seq_len
        done += 1
        if max_batches and done >= max_batches:
            break
    return total / max(ntok, 1), ntok
