"""Automation entry point: run a recipe of stages with one config surface.

  python scripts/run_pipeline.py --pipeline config/pipelines/pretrain.yaml
  python scripts/run_pipeline.py --pipeline config/pipelines/pretrain.yaml \
      --preset large --set training.optimizer=muon --run-name large-muon
  python scripts/run_pipeline.py --pipeline config/pipelines/pretrain.yaml \
      --run-name large-muon --from pretrain   # resume that run where it died
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
    ap.add_argument("--run-name", dest="run_name", default=None,
                    help="namespace for this run's outputs (runs/<run_name>/...); "
                         "default 'default'. Use a fresh name to keep models "
                         "side by side instead of overwriting.")
    ap.add_argument("--only", default=None, help="run a single stage")
    ap.add_argument("--from", dest="from_", default=None, help="start at stage")
    ap.add_argument("--until", default=None, help="stop after stage")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run_pipeline(args.pipeline, preset=args.preset, sets=args.sets,
                 only=args.only, from_=args.from_, until=args.until,
                 dry_run=args.dry_run, run_name=args.run_name)


if __name__ == "__main__":
    main()
