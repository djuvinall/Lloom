"""Stage 1: pretraining.
Usage:
  python scripts/pretrain.py
  python scripts/pretrain.py --preset large --set training.optimizer=muon
  python scripts/pretrain.py --resume_from runs/<name>/checkpoints/pretrain/last.pt

Resumes automatically from <out_dir>/last.pt if it exists, so a crashed run
picks up where it died; pass --no_resume to force a fresh start.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from textlm.prep import present_sources
from lloom.config import add_config_args, load_config, save_snapshot
from lloom.data import MixtureSchedule, WeightedStreamSampler, load_token_streams
from lloom.model import ModelConfig, TransformerLM
from lloom.tokenizer import SPTokenizer
from lloom.train import Trainer
from lloom.utils import (count_params, estimate_train_vram_gb, fmt_params,
                         get_device, set_seed)


def main():
    ap = argparse.ArgumentParser()
    add_config_args(ap, "config/training_config.yaml")
    ap.add_argument("--data_config", default="config/data_config.yaml")
    ap.add_argument("--resume_from", default=None,
                    help="checkpoint to resume; defaults to <out_dir>/last.pt if present")
    ap.add_argument("--no_resume", action="store_true",
                    help="ignore any existing last.pt and start a fresh run")
    args = ap.parse_args()
    cfg = load_config(args.config, preset=args.preset, sets=args.sets)
    if args.wandb:
        cfg.logging.wandb.enabled = True
    data_cfg = load_config(args.data_config)
    set_seed(cfg.seed)
    device = get_device(cfg.device)

    tok = SPTokenizer(cfg.tokenizer_dir, cfg.get("tokenizer_prefix", "spm"))
    sources = present_sources(data_cfg)
    names = [s["name"] for s in sources]
    train_streams = load_token_streams(data_cfg.tokens_dir, "train", names)
    val_streams = load_token_streams(data_cfg.tokens_dir, "val", names)
    sources = [s for s in sources if s["name"] in train_streams]

    schedule = MixtureSchedule(data_cfg.curriculum, sources, cfg.training.max_steps)
    sampler = WeightedStreamSampler(train_streams, schedule,
                                    cfg.model.max_seq_len, cfg.seed)

    mcfg = ModelConfig.from_dict(dict(cfg.model))
    # Size the embedding/head to the tokenizer (honoring a larger configured
    # floor if set) and pad up to a multiple of 64 for tensor-core throughput.
    # Record the real vocab so generation masks the padding band and never
    # samples an id the tokenizer can't decode.
    real_vocab = tok.vocab_size
    mcfg.vocab_size = (max(mcfg.vocab_size, real_vocab) + 63) // 64 * 64
    mcfg.tokenizer_vocab_size = real_vocab
    model = TransformerLM(mcfg).to(device)
    n_params = count_params(model)
    n_hidden = sum(p.numel() for n, p in model.named_parameters()
                   if p.ndim >= 2 and "embed" not in n and "lm_head" not in n)
    vram = estimate_train_vram_gb(n_params, cfg.training.get("optimizer", "adamw"), n_hidden)
    n_tok = sum(len(s) for s in train_streams.values())
    budget = cfg.training.max_steps * cfg.training.batch_size \
        * cfg.training.grad_accum_steps * mcfg.max_seq_len
    print(f"model {fmt_params(n_params)} | corpus {n_tok / 1e6:.1f}M tok "
          f"({len(train_streams)} sources) | budget {budget / 1e6:.0f}M tok "
          f"= ~{budget / max(n_tok, 1):.0f} epochs (early stopping armed)")
    print(f"est. VRAM (states, pre-activations): ~{vram:.1f}GB"
          + (" [!] tight on 16GB - consider muon/gradient_checkpointing"
             if vram > 11 else ""))

    ood = {}
    for f in data_cfg.get("ood_files", []):
        p = Path(data_cfg.ood_dir) / f
        if p.exists():
            ood[p.stem] = p.read_text(encoding="utf-8", errors="replace")

    cfg.divergence_alert = data_cfg.curriculum.get("divergence_alert", 0.05)
    trainer = Trainer(cfg, model, sampler, val_streams, tok, device, ood)
    resume_path = args.resume_from
    if resume_path is None and not args.no_resume:
        cand = Path(cfg.out_dir) / "last.pt"
        if cand.exists():
            resume_path = cand
            print(f"auto-resuming from {cand} (pass --no_resume to start fresh)")
    if resume_path:
        trainer.resume(resume_path)
    save_snapshot([args.config, args.data_config],
                  Path(cfg.out_dir) / "config_snapshot", resolved=cfg)
    trainer.train()


if __name__ == "__main__":
    main()
