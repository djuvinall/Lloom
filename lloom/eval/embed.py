"""Text embeddings from a decoder LM: mean-pooled final hidden states,
L2-normalized. Decent retrieval baseline without any contrastive finetune;
the eval metrics in retrieval.py tell you whether a finetune is warranted."""
from __future__ import annotations

import torch


@torch.no_grad()
def embed_texts(model, tokenizer, texts: list[str], device,
                batch_size: int = 32, max_len: int | None = None) -> torch.Tensor:
    """-> (N, d) float32, unit-norm rows."""
    model.eval()
    max_len = max_len or model.cfg.max_seq_len
    pad = max(tokenizer.pad_id, 0)
    out = []
    for i in range(0, len(texts), batch_size):
        chunk = [tokenizer.encode(t)[:max_len] for t in texts[i:i + batch_size]]
        L = max(len(c) for c in chunk)
        ids = torch.full((len(chunk), L), pad, dtype=torch.long)
        attn = torch.zeros(len(chunk), L)
        for j, c in enumerate(chunk):
            ids[j, :len(c)] = torch.tensor(c)
            attn[j, :len(c)] = 1.0
        h = model.hidden_states(ids.to(device)).float()        # (B, L, d)
        attn = attn.to(device).unsqueeze(-1)
        emb = (h * attn).sum(1) / attn.sum(1).clamp(min=1.0)   # mean over real tokens
        out.append(torch.nn.functional.normalize(emb, dim=-1).cpu())
    return torch.cat(out)
