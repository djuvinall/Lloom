"""Decoder-only transformer assembled from the config: pre-norm blocks,
RoPE attention (MHA/GQA/MQA), dense or MoE FFN, tied or untied head.

forward() serves training (targets -> mean CE over non-ignored positions,
plus MoE aux loss), packed-document training (mask), and incremental
decoding (cache). Generation lives in lloom.infer.generate.
"""
from __future__ import annotations

import math

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint

from .attention import Attention, KVCache
from .config import ModelConfig
from .layers import build_mlp, build_norm
from .moe import MoE
from .rope import build_rope_cache


class Block(nn.Module):
    def __init__(self, cfg: ModelConfig, layer_idx: int):
        super().__init__()
        self.attn_norm = build_norm(cfg)
        self.attn = Attention(cfg, layer_idx)
        self.ffn_norm = build_norm(cfg)
        self.ffn = MoE(cfg) if cfg.n_experts else build_mlp(cfg)
        self.drop = nn.Dropout(cfg.dropout)

    def forward(self, x, cos, sin, mask=None, cache=None):
        x = x + self.drop(self.attn(self.attn_norm(x), cos, sin, mask, cache))
        x = x + self.ffn(self.ffn_norm(x))
        return x


class TransformerLM(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.cfg = cfg
        self.embed = nn.Embedding(cfg.vocab_size, cfg.d_model)
        self.drop = nn.Dropout(cfg.dropout)
        self.blocks = nn.ModuleList(Block(cfg, i) for i in range(cfg.n_layers))
        self.norm = build_norm(cfg)
        self.lm_head = nn.Linear(cfg.d_model, cfg.vocab_size, bias=False)
        if cfg.tie_embeddings:
            self.lm_head.weight = self.embed.weight

        cos, sin = build_rope_cache(cfg.head_dim, cfg.max_position,
                                    cfg.rope_theta, cfg.rope_scaling)
        self.register_buffer("rope_cos", cos, persistent=False)
        self.register_buffer("rope_sin", sin, persistent=False)
        self.apply(self._init)
        # scaled init on residual-out projections (GPT-2 trick)
        scale = cfg.init_std / math.sqrt(2 * cfg.n_layers)
        for blk in self.blocks:
            nn.init.normal_(blk.attn.o_proj.weight, 0.0, scale)
            for mod in ([blk.ffn] if not cfg.n_experts else blk.ffn.experts):
                nn.init.normal_(mod.down.weight, 0.0, scale)

    def _init(self, m):
        if isinstance(m, (nn.Linear, nn.Embedding)):
            nn.init.normal_(m.weight, 0.0, self.cfg.init_std)

    def new_cache(self, batch_size: int, device=None, dtype=None) -> KVCache:
        p = next(self.parameters())
        return KVCache(self.cfg, batch_size, device or p.device, dtype or p.dtype)

    def _backbone(self, idx, mask=None, cache=None):
        T = idx.shape[1]
        pos = cache.pos if cache is not None else 0
        assert pos + T <= self.cfg.max_position, \
            f"sequence {pos + T} exceeds max_position {self.cfg.max_position}"
        x = self.drop(self.embed(idx))
        for blk in self.blocks:
            if self.cfg.gradient_checkpointing and self.training:
                x = checkpoint(blk, x, self.rope_cos, self.rope_sin, mask,
                               use_reentrant=False)
            else:
                x = blk(x, self.rope_cos, self.rope_sin, mask, cache)
        if cache is not None:
            cache.advance(T)
        return self.norm(x)

    def forward(self, idx, targets=None, mask=None, cache=None):
        """targets: (B,T) next-token ids, -100 = ignore (works for causal LM,
        span corruption, and prompt-masked SFT alike).
        mask: bool (B|1, 1, T, T) attend-mask for packed documents."""
        x = self._backbone(idx, mask, cache)
        if targets is None:
            return self.lm_head(x[:, -1:]), None     # decode: last position only
        logits = self.lm_head(x)
        loss = F.cross_entropy(logits.view(-1, logits.size(-1)),
                               targets.reshape(-1), ignore_index=-100)
        self.aux_loss = None
        if self.cfg.n_experts and self.training:
            auxes = [b.ffn.last_aux_loss for b in self.blocks
                     if isinstance(b.ffn, MoE) and b.ffn.last_aux_loss is not None]
            if auxes:
                self.aux_loss = torch.stack(auxes).mean()
                loss = loss + self.cfg.moe_aux_weight * self.aux_loss
        return logits, loss

    @torch.no_grad()
    def hidden_states(self, idx, mask=None) -> torch.Tensor:
        """Final normed hidden states (B, T, d) - embedding/eval workloads."""
        return self._backbone(idx, mask)

    @torch.no_grad()
    def generate(self, idx, max_new_tokens, temperature=0.7, top_p=0.9,
                 eot_id=None, **kw):
        """Convenience wrapper; full sampling options in lloom.infer.generate."""
        from ..infer.generate import generate
        return generate(self, idx, max_new_tokens, temperature=temperature,
                        top_p=top_p, eot_id=eot_id, **kw)
