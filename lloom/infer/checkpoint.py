"""Checkpoint IO: load training checkpoints, export/import safetensors.

Training checkpoints are .pt dicts carrying model_cfg, so a model is always
reconstructible from the file alone. Exported safetensors + config.json is the
distribution format (tied lm_head is dropped on export and re-tied on import).
"""
from __future__ import annotations

import json
from pathlib import Path

import torch

from ..model import ModelConfig, TransformerLM


def load_model(checkpoint_path: str | Path, device) -> TransformerLM:
    ck = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model = TransformerLM(ModelConfig.from_dict(ck["model_cfg"]))
    model.load_state_dict(ck["model"])
    return model.to(device).eval()


def export_safetensors(model: TransformerLM, out_dir: str | Path) -> Path:
    from safetensors.torch import save_file
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sd = {k: v.contiguous() for k, v in model.state_dict().items()}
    if model.cfg.tie_embeddings:
        sd.pop("lm_head.weight", None)        # shared storage; re-tied on load
    save_file(sd, str(out / "model.safetensors"))
    (out / "config.json").write_text(
        json.dumps({"architecture": "lloom.TransformerLM",
                    "model_cfg": model.cfg.__dict__}, indent=2), encoding="utf-8")
    return out / "model.safetensors"


def load_safetensors(model_dir: str | Path, device="cpu") -> TransformerLM:
    from safetensors.torch import load_file
    model_dir = Path(model_dir)
    cfg = json.loads((model_dir / "config.json").read_text())["model_cfg"]
    model = TransformerLM(ModelConfig.from_dict(cfg))
    sd = load_file(str(model_dir / "model.safetensors"), device=str(device))
    missing, unexpected = model.load_state_dict(sd, strict=False)
    assert not unexpected, unexpected
    assert all("lm_head" in k for k in missing), missing   # tied head only
    return model.to(device).eval()


def generate_text(model, tokenizer, prompt: str, max_new_tokens=150, **kw) -> str:
    from .generate import generate
    device = next(model.parameters()).device
    idx = torch.tensor([tokenizer.encode(prompt)], device=device)
    out = generate(model, idx, max_new_tokens, eot_id=tokenizer.eot_id, **kw)
    return tokenizer.decode(out[0].tolist())
