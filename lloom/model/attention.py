"""Attention: one implementation covering MHA / GQA / MQA, optional QK-norm,
optional sliding window, document-packed masks, and incremental KV-cache
decoding - all through PyTorch SDPA so the fused flash kernels are used
whenever the mask pattern allows.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from .config import ModelConfig
from .layers import RMSNorm
from .rope import apply_rope


def _detect_sdpa_gqa() -> bool:
    """SDPA grew enable_gqa= in torch 2.5; it's a builtin, so probe by call."""
    try:
        q = torch.zeros(1, 2, 1, 8)
        kv = torch.zeros(1, 1, 1, 8)
        F.scaled_dot_product_attention(q, kv, kv, enable_gqa=True)
        return True
    except TypeError:
        return False


_SDPA_HAS_GQA = _detect_sdpa_gqa()


class KVCache:
    """Preallocated per-layer K/V tensors for incremental decoding.
    `pos` is the number of tokens already cached; the model advances it once
    per forward (after all layers have written)."""

    def __init__(self, cfg: ModelConfig, batch_size: int, device, dtype):
        shape = (cfg.n_layers, batch_size, cfg.n_kv_heads,
                 cfg.max_position, cfg.head_dim)
        self.k = torch.zeros(shape, device=device, dtype=dtype)
        self.v = torch.zeros(shape, device=device, dtype=dtype)
        self.pos = 0

    def update(self, layer: int, k: torch.Tensor, v: torch.Tensor):
        """Write new (B, H_kv, T, hd) keys/values; return the full prefix."""
        T = k.shape[2]
        self.k[layer, :, :, self.pos:self.pos + T] = k
        self.v[layer, :, :, self.pos:self.pos + T] = v
        return (self.k[layer, :, :, :self.pos + T],
                self.v[layer, :, :, :self.pos + T])

    def advance(self, T: int):
        self.pos += T


def _window_causal_mask(q_len: int, kv_len: int, window: int | None, device):
    """Bool mask (q_len, kv_len), True = may attend. Bottom-right aligned so it
    is correct when kv_len > q_len (cached prefix)."""
    q_pos = torch.arange(kv_len - q_len, kv_len, device=device)[:, None]
    k_pos = torch.arange(kv_len, device=device)[None, :]
    mask = k_pos <= q_pos
    if window is not None:
        mask &= k_pos > q_pos - window
    return mask


class Attention(nn.Module):
    def __init__(self, cfg: ModelConfig, layer_idx: int):
        super().__init__()
        self.layer_idx = layer_idx
        self.n_heads, self.n_kv_heads = cfg.n_heads, cfg.n_kv_heads
        self.head_dim = cfg.head_dim
        self.window = cfg.sliding_window
        kv_dim = cfg.n_kv_heads * cfg.head_dim
        self.q_proj = nn.Linear(cfg.d_model, cfg.d_model, bias=False)
        self.k_proj = nn.Linear(cfg.d_model, kv_dim, bias=False)
        self.v_proj = nn.Linear(cfg.d_model, kv_dim, bias=False)
        self.o_proj = nn.Linear(cfg.d_model, cfg.d_model, bias=False)
        self.q_norm = RMSNorm(cfg.head_dim, cfg.norm_eps) if cfg.qk_norm else None
        self.k_norm = RMSNorm(cfg.head_dim, cfg.norm_eps) if cfg.qk_norm else None
        self.dropout = cfg.dropout

    def forward(self, x, cos, sin, mask=None, cache: KVCache | None = None):
        B, T, C = x.shape
        pos = cache.pos if cache is not None else 0
        q = self.q_proj(x).view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(B, T, self.n_kv_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, T, self.n_kv_heads, self.head_dim).transpose(1, 2)
        if self.q_norm is not None:
            q, k = self.q_norm(q), self.k_norm(k)
        q, k = apply_rope(q, cos, sin, pos), apply_rope(k, cos, sin, pos)

        if cache is not None:
            k, v = cache.update(self.layer_idx, k, v)

        kv_len = k.shape[2]
        if self.window is not None and T == 1 and kv_len > self.window:
            k, v = k[:, :, -self.window:], v[:, :, -self.window:]  # decode: trim
            kv_len = self.window

        # Mask selection: fast is_causal path whenever legal, explicit bool
        # mask otherwise (sliding window, cached prefill, packed documents).
        attn_mask, is_causal = None, False
        if mask is not None:                      # packed-document block mask
            attn_mask = mask
        elif T == 1:                              # decode: attend whole prefix
            pass
        elif self.window is None and kv_len == T:
            is_causal = True
        else:                                     # window and/or cached prefill
            attn_mask = _window_causal_mask(T, kv_len, self.window, x.device)

        kw = {}
        groups = self.n_heads // self.n_kv_heads
        if groups > 1:
            if _SDPA_HAS_GQA:
                kw["enable_gqa"] = True
            else:
                k = k.repeat_interleave(groups, dim=1)
                v = v.repeat_interleave(groups, dim=1)
        y = F.scaled_dot_product_attention(
            q, k, v, attn_mask=attn_mask, is_causal=is_causal,
            dropout_p=self.dropout if self.training else 0.0, **kw)
        return self.o_proj(y.transpose(1, 2).contiguous().view(B, T, C))
