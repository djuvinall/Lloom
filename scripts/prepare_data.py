"""Stage 0a: normalize raw text sources into clean, document-segmented text.

Input  (data/raw/{name}.txt):  free text; blank lines separate documents.
Output (data/processed/text/{name}.txt): normalized text, docs joined by <|endoftext|>.

Drop one .txt per source (listed in data_config.yaml) into data/raw/.
Usage: python scripts/prepare_data.py
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from textlm.prep import normalize_text, present_sources
from lloom.config import load_config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/data_config.yaml")
    args = ap.parse_args()
    cfg = load_config(args.config)
    raw, out = Path(cfg.raw_dir), Path(cfg.text_dir)
    raw.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)

    found = present_sources(cfg)
    if not found:
        sys.exit(f"no .txt files in {raw} - add sources listed in {args.config}")
    for s in found:
        n = normalize_text(s["name"], raw / f"{s['name']}.txt", out / f"{s['name']}.txt")
        print(f"{s['name']}: {n} documents")
    missing = [s["name"] for s in cfg.sources if s["name"] not in {f["name"] for f in found}]
    if missing:
        print(f"not present (fine, weights renormalize): {', '.join(missing)}")


if __name__ == "__main__":
    main()
