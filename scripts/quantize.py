"""Stage 5a: quantization + export.

- dynamic int8 (CPU inference): no calibration, ~3-4x smaller Linears
- safetensors export (config.json + model.safetensors) as the share format
- optional perplexity delta check (fp32-cpu vs int8-cpu) when val streams exist

Usage:
  python scripts/quantize.py                       # uses runs/<run_name>/...
  python scripts/quantize.py --checkpoint runs/<name>/checkpoints/pretrain/best.pt
  python scripts/quantize.py ... --ppl_check       # slower, prints quality delta
"""
import argparse
import math
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from textlm.prep import present_sources
from lloom.config import add_config_args, load_config
from lloom.data import load_token_streams
from lloom.eval import perplexity_on_stream
from lloom.infer import export_safetensors, load_model
from lloom.quant import quantize_dynamic_int8, save_quantized, state_size_mb


def main():
    ap = argparse.ArgumentParser()
    add_config_args(ap, "config/eval_config.yaml")
    ap.add_argument("--checkpoint", default=None,
                    help="default: runs/<run_name>/checkpoints/pretrain/best.pt")
    ap.add_argument("--out_dir", default=None,
                    help="default: runs/<run_name>/checkpoints/export")
    ap.add_argument("--ppl_check", action="store_true")
    args = ap.parse_args()
    cfg = load_config(args.config, preset=args.preset, sets=args.sets)
    data_cfg = load_config("config/data_config.yaml")
    run = cfg.get("run_name", "default")
    ckpt = args.checkpoint or f"runs/{run}/checkpoints/pretrain/best.pt"
    out = Path(args.out_dir or f"runs/{run}/checkpoints/export")
    out.mkdir(parents=True, exist_ok=True)

    model = load_model(ckpt, torch.device("cpu"))
    fp32_mb = state_size_mb(model)
    st = export_safetensors(model, out)
    print(f"exported {st} ({fp32_mb:.0f}MB fp32)")

    q = quantize_dynamic_int8(model)
    save_quantized(q, model.cfg.__dict__, out / "model_int8.pt")
    print(f"int8: {out / 'model_int8.pt'} ({state_size_mb(q):.0f}MB, "
          f"{fp32_mb / max(state_size_mb(q), 1e-9):.1f}x smaller)")

    if args.ppl_check:
        names = [s["name"] for s in present_sources(data_cfg)]
        streams = load_token_streams(data_cfg.tokens_dir, "val", names)
        stream = next(iter(streams.values()))
        dev = torch.device("cpu")
        seq_len = min(cfg.get("seq_len") or model.cfg.max_seq_len, model.cfg.max_seq_len)
        ce_f, _ = perplexity_on_stream(load_model(ckpt, dev), stream,
                                       2, seq_len, dev, max_batches=4)
        ce_q, _ = perplexity_on_stream(q, stream, 2, seq_len, dev, max_batches=4)
        print(f"ppl fp32 {math.exp(ce_f):.3f} -> int8 {math.exp(ce_q):.3f} "
              f"(delta {100 * (math.exp(ce_q) / math.exp(ce_f) - 1):+.2f}%)")


if __name__ == "__main__":
    main()
