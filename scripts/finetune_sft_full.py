"""Stage 3: full finetuning on prompt/response pairs (all weights, low LR).

Usage:
  python scripts/finetune_sft_full.py
  python scripts/finetune_sft_full.py --set full.training.lr=5e-6
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from textlm.sft import encode_sft_pairs, load_sft_pairs
from lloom.config import add_config_args, deep_merge, load_config, save_snapshot
from lloom.data import build_batches, pack_examples, train_val_split
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
    # the `full:` block overrides the shared training defaults (lower LR etc.)
    cfg.training = type(cfg)(deep_merge(cfg.training, cfg.get("full", {}).get("training", {})))
    set_seed(cfg.seed)
    device = get_device(cfg.device)

    tok = SPTokenizer(cfg.tokenizer_dir, cfg.get("tokenizer_prefix", "spm"))
    model = load_model(cfg.base_checkpoint, device)
    for p in model.parameters():
        p.requires_grad = True
    model.train()

    rows = load_sft_pairs(cfg.sft_dir)
    train_rows, val_rows = train_val_split(rows, cfg.val_fraction, cfg.seed)
    seq_len = model.cfg.max_seq_len
    t_batches = build_batches(pack_examples(encode_sft_pairs(tok, train_rows),
                                            seq_len, max(tok.pad_id, 0)),
                              cfg.training.batch_size, cfg.seed)
    v_batches = build_batches(pack_examples(encode_sft_pairs(tok, val_rows),
                                            seq_len, max(tok.pad_id, 0)),
                              cfg.training.batch_size, cfg.seed)

    cfg.out_dir = cfg.full_out_dir
    trainer = SFTTrainer(cfg, model, t_batches, v_batches, device)
    save_snapshot([args.config], Path(cfg.out_dir) / "config_snapshot", resolved=cfg)
    trainer.train()
    print(f"best checkpoint: {Path(cfg.out_dir) / 'best.pt'}")


if __name__ == "__main__":
    main()
