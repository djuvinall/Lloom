"""Automation entry point: run a recipe of stages with one config surface.

  python scripts/run_pipeline.py --pipeline config/pipelines/pretrain.yaml
  python scripts/run_pipeline.py --pipeline config/pipelines/pretrain.yaml \
      --preset large --set training.optimizer=muon --set training.max_steps=20000
  python scripts/run_pipeline.py --pipeline config/pipelines/pretrain.yaml \
      --from pretrain          # resume a failed run
  python scripts/run_pipeline.py ... --dry-run   # print commands only
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lloom.pipeline import run_pipeline


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pipeline", required=True, help="recipe YAML")
    ap.add_argument("--preset", default=None,
                    help="model preset name or path, forwarded to stages")
    ap.add_argument("--set", dest="sets", action="append", default=[],
                    metavar="KEY.PATH=VALUE", help="config override, forwarded")
    ap.add_argument("--only", default=None, help="run a single stage")
    ap.add_argument("--from", dest="from_", default=None, help="start at stage")
    ap.add_argument("--until", default=None, help="stop after stage")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run_pipeline(args.pipeline, preset=args.preset, sets=args.sets,
                 only=args.only, from_=args.from_, until=args.until,
                 dry_run=args.dry_run)


if __name__ == "__main__":
    main()
