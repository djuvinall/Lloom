"""Post-training quantization: dynamic int8 on Linear layers (CPU inference).

At the scales lloom targets, dynamic int8 is the right first tool: no
calibration set, ~3-4x smaller Linear weights, near-zero quality loss on
LM perplexity. GPU inference should simply run bf16. Note: quantizing wraps
the (tied) lm_head in its own int8 module, so the embedding stays fp32 -
expected, and harmless for inference.
"""
from __future__ import annotations

from pathlib import Path

import torch
import torch.nn as nn


def quantize_dynamic_int8(model: nn.Module) -> nn.Module:
    model = model.cpu().eval()
    return torch.ao.quantization.quantize_dynamic(model, {nn.Linear},
                                                  dtype=torch.qint8)


def state_size_mb(model: nn.Module) -> float:
    total = 0
    seen = set()
    for t in model.state_dict().values():
        if isinstance(t, torch.Tensor) and t.data_ptr() not in seen:
            seen.add(t.data_ptr())
            total += t.numel() * t.element_size()
    return total / 1e6


def save_quantized(model: nn.Module, model_cfg: dict, path: str | Path) -> None:
    torch.save({"model": model.state_dict(), "model_cfg": model_cfg,
                "quantization": "dynamic_int8"}, path)


def load_quantized(path: str | Path):
    """Rebuild: fresh fp32 model -> same dynamic transform -> load int8 state."""
    from ..model import ModelConfig, TransformerLM
    ck = torch.load(path, map_location="cpu", weights_only=False)
    model = quantize_dynamic_int8(TransformerLM(ModelConfig.from_dict(ck["model_cfg"])))
    model.load_state_dict(ck["model"])
    return model.eval()
