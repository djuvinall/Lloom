"""Stage 2: LoRA instruction-tuning on prompt/response pairs.

Frozen base + rank-r adapters on attention and SwiGLU projections. Saves the
best adapter (small), plus a merged full checkpoint for downstream eval/serve.

Usage:
  python scripts/finetune_sft_lora.py
  python scripts/finetune_sft_lora.py --set lora.r=16 --set training.lr=2e-4
"""
import argparse
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from textlm.sft import encode_sft_pairs, load_sft_pairs
from lloom.config import add_config_args, load_config, save_snapshot
from lloom.data import build_batches, pack_examples, train_val_split
from lloom.finetune import DEFAULT_TARGETS, inject_lora, merge_lora, save_adapter
from lloom.infer import load_model
from lloom.tokenizer import SPTokenizer
from lloom.train import SFTTrainer
from lloom.utils import get_device, set_seed


def main():
    ap = argparse.ArgumentParser()
    add_config_args(ap, "config/sft_config.yaml")
    args = ap.parse_args()
    cfg = load_config(args.config, preset=args.preset, sets=args.sets)
    if args.wandb:
        cfg.logging.wandb.enabled = True
    set_seed(cfg.seed)
    device = get_device(cfg.device)

    tok = SPTokenizer(cfg.tokenizer_dir, cfg.get("tokenizer_prefix", "spm"))
    model = load_model(cfg.base_checkpoint, device)

    lora = cfg.lora
    targets = tuple(lora.get("targets") or DEFAULT_TARGETS)
    n = inject_lora(model, lora.r, lora.alpha, lora.dropout, targets)
    print(f"LoRA r={lora.r} alpha={lora.alpha} on {n} layers")
    model = model.to(device)

    rows = load_sft_pairs(cfg.sft_dir)
    train_rows, val_rows = train_val_split(rows, cfg.val_fraction, cfg.seed)
    seq_len = model.cfg.max_seq_len
    t_batches = build_batches(pack_examples(encode_sft_pairs(tok, train_rows),
                                            seq_len, max(tok.pad_id, 0)),
                              cfg.training.batch_size, cfg.seed)
    v_batches = build_batches(pack_examples(encode_sft_pairs(tok, val_rows),
                                            seq_len, max(tok.pad_id, 0)),
                              cfg.training.batch_size, cfg.seed)

    cfg.out_dir = cfg.lora_out_dir
    trainer = SFTTrainer(cfg, model, t_batches, v_batches, device)
    save_snapshot([args.config], Path(cfg.out_dir) / "config_snapshot", resolved=cfg)
    trainer.train()

    out = Path(cfg.out_dir)
    best = torch.load(out / "best.pt", map_location=device, weights_only=False)
    model.load_state_dict(best["model"])
    save_adapter(model, out / "adapter.pt", lora.r, lora.alpha)
    merged = merge_lora(model)
    torch.save({"model": merged.state_dict(), "model_cfg": merged.cfg.__dict__,
                "step": best["step"], "best_val": best["best_val"]},
               out / "merged.pt")
    print(f"saved {out / 'adapter.pt'} (adapter) and {out / 'merged.pt'} (full)")


if __name__ == "__main__":
    main()
