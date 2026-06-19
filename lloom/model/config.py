"""ModelConfig: every architecture decision is a field here, every field is a
YAML knob. One transformer implementation covers MHA/GQA/MQA, dense/MoE FFNs,
full/sliding-window attention, and RoPE scaling - so "different model" means
"different config", never "different code".
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelConfig:
    vocab_size: int = 32000
    d_model: int = 896
    n_layers: int = 14
    n_heads: int = 14
    n_kv_heads: int | None = None      # None -> n_heads (MHA); 1 -> MQA; else GQA
    intermediate_size: int = 2400
    mlp_type: str = "swiglu"           # swiglu | geglu | gelu
    norm_type: str = "rmsnorm"         # rmsnorm | layernorm
    qk_norm: bool = False              # RMSNorm on q/k per head (OLMo2/Qwen3-style)
    max_seq_len: int = 1024
    rope_theta: float = 10000.0
    rope_scaling: dict = field(default_factory=dict)  # {type: linear|ntk, factor: f}
    sliding_window: int | None = None  # tokens each position may look back; None=full
    dropout: float = 0.1
    norm_eps: float = 1e-5
    init_std: float = 0.02
    tie_embeddings: bool = True
    gradient_checkpointing: bool = False
    # --- MoE (n_experts == 0 -> dense FFN, everything below ignored) ---
    n_experts: int = 0
    moe_top_k: int = 2
    moe_aux_weight: float = 0.01       # Switch-style load-balancing loss weight

    def __post_init__(self):
        if self.n_kv_heads is None:
            self.n_kv_heads = self.n_heads
        assert self.d_model % self.n_heads == 0, "d_model must divide n_heads"
        assert self.n_heads % self.n_kv_heads == 0, "n_heads must divide n_kv_heads"
        assert self.mlp_type in ("swiglu", "geglu", "gelu"), self.mlp_type
        assert self.norm_type in ("rmsnorm", "layernorm"), self.norm_type
        if self.rope_scaling:
            assert self.rope_scaling.get("type") in ("linear", "ntk"), self.rope_scaling
            assert self.rope_scaling.get("factor", 1.0) >= 1.0
        if self.n_experts:
            assert 0 < self.moe_top_k <= self.n_experts

    @property
    def head_dim(self) -> int:
        return self.d_model // self.n_heads

    @property
    def max_position(self) -> int:
        """Longest position the RoPE cache (and KV cache) supports.
        rope_scaling extends usable context beyond the trained max_seq_len."""
        factor = self.rope_scaling.get("factor", 1.0) if self.rope_scaling else 1.0
        return int(self.max_seq_len * factor)

    @classmethod
    def from_dict(cls, d: dict) -> "ModelConfig":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
