"""Stage 0d: pre-flight validation. Checks the tokenizer, token streams, and
stream lengths against the resolved model config, so a bad corpus or a missing
artifact fails here in seconds instead of deep inside a GPU training run.

Exits non-zero on hard errors (the pipeline then stops at this stage).
Usage:
  python scripts/preflight.py
  python scripts/preflight.py --preset large        # validate the size you'll train
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from textlm.prep import present_sources
from lloom.config import add_config_args, load_config
from lloom.preflight import check_pretrain


def main():
    ap = argparse.ArgumentParser()
    add_config_args(ap, "config/training_config.yaml")
    ap.add_argument("--data_config", default="config/data_config.yaml")
    args = ap.parse_args()
    cfg = load_config(args.config, preset=args.preset, sets=args.sets)
    data_cfg = load_config(args.data_config)
    sources = present_sources(data_cfg)

    errors, warnings = check_pretrain(cfg, data_cfg, sources)
    for w in warnings:
        print(f"[preflight][warn]  {w}")
    for e in errors:
        print(f"[preflight][error] {e}")
    if errors:
        sys.exit(f"preflight failed with {len(errors)} error(s) - fix before training")
    print(f"preflight ok: {len(sources)} source(s) present, "
          f"{len(warnings)} warning(s)")


if __name__ == "__main__":
    main()
